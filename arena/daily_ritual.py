"""Rito quotidiano: giorni mancati, snapshot del giorno, decisioni.

È quello che il Task Scheduler esegue una volta al giorno, all'ora UTC fissa di
`toolserver.config.DEFAULT_SNAPSHOT_HOUR_UTC`. Fa tre cose, in quest'ordine, e
ognuna ha un esito proprio:

1. **Marca i giorni mancati.** Se l'ultima giornata con verbali è più vecchia
   di ieri, i giorni in mezzo finiscono nel registro operativo come
   `skipped_day`. Non vengono recuperati: una decisione presa oggi su dati di
   tre giorni fa vedrebbe un futuro che il Trader di allora non aveva, e
   sarebbe un backtest travestito da verbale (CLAUDE.md §5).
2. **Costruisce lo snapshot**, in un **processo separato** e con
   `TRADERLAB_ALLOW_NETWORK=1`. È l'unico punto in cui si tocca la rete
   (CLAUDE.md §7): questo modulo non importa nemmeno il client di rete, si
   limita a lanciare il processo che ce l'ha.
3. **Esegue le decisioni** sullo snapshot appena congelato, in un altro
   processo, con la variabile di rete rimossa dall'ambiente.

Il rito **non solleva**: ogni esito è un exit code dichiarato e una riga di
log. Uno scheduler non legge le eccezioni, legge i codici di uscita.

La logica sta qui e non nello script PowerShell perché uno script di shell non
è testabile senza scheduler — e una regola che non ha un test, per il Lab, non
esiste.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from arena.llm_client import RETRYABLE_PROCESS_EXIT_CODE
from ledger.ops_ledger import (
    OpsEvent,
    OpsKey,
    OpsLedger,
    mark_missing_days,
    recorded_days,
)
from ledger.trader_ledger import TraderLedger
from toolserver.config import DEFAULT_SNAPSHOT_HOUR_UTC

# -- exit code dichiarati --------------------------------------------------
EXIT_OK = 0
EXIT_PRECONDITION = 2
EXIT_SNAPSHOT_FAILED = 3
EXIT_DECISIONS_FAILED = 4
EXIT_ALREADY_DONE = 5
EXIT_GAP_MARKING_FAILED = 6
EXIT_DECISIONS_RETRY_EXHAUSTED = 7

EXIT_MEANING: dict[int, str] = {
    EXIT_OK: "giornata completata",
    EXIT_PRECONDITION: "precondizione non soddisfatta (rito non partito)",
    EXIT_SNAPSHOT_FAILED: "costruzione dello snapshot fallita",
    EXIT_DECISIONS_FAILED: "esecuzione delle decisioni fallita",
    EXIT_ALREADY_DONE: "la giornata di oggi e' gia' nel ledger",
    EXIT_GAP_MARKING_FAILED: "marcatura dei giorni mancati fallita",
    EXIT_DECISIONS_RETRY_EXHAUSTED: (
        "decisioni fallite con errore ritentabile per tutta la finestra di retry"
    ),
}

# Pazienza lunga del rito, distinta dalla pazienza corta del client (che
# resta max_retries=3, backoff 1/2/4 — vedi arena/llm_client.py). Se il passo
# delle decisioni fallisce con un errore che il client ha già classificato
# come transitorio ed esaurito, il rito riprova l'INTERO passo fino a
# `RITUAL_RETRY_MAX_ATTEMPTS` volte, distanziate di `RITUAL_RETRY_WAIT_SECONDS`:
# finestra totale = 3 * 15 min = 45 min.
RITUAL_RETRY_MAX_ATTEMPTS = 3
RITUAL_RETRY_WAIT_SECONDS = 15 * 60.0

DEFAULT_LOG_DIR = Path("data/logs")
DEFAULT_LEDGER_PATH = Path("data/ledger/season0.jsonl")
DEFAULT_OPS_PATH = Path("data/ledger/ops.jsonl")

_SNAPSHOT_ID_RE = re.compile(r"snapshot_id\s*:\s*([0-9a-f]{64})")


@dataclass(slots=True)
class RitualLog:
    """Log della passata: stesso testo su file e su stdout, stesso ordine."""

    path: Path
    echo: bool = True
    _lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> None:
        stamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{stamp} {message}"
        self._lines.append(line)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        if self.echo:
            print(line, flush=True)

    def block(self, title: str, body: str) -> None:
        if not (body or "").strip():
            return
        self.write(f"--- {title} ---")
        for line in body.rstrip().splitlines():
            self.write(f"    {line}")

    @property
    def lines(self) -> list[str]:
        return list(self._lines)


@dataclass(frozen=True, slots=True)
class RitualResult:
    exit_code: int
    log_path: Path
    snapshot_id: str | None = None
    skipped_marked: tuple[date, ...] = ()
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == EXIT_OK

    @property
    def meaning(self) -> str:
        return EXIT_MEANING[self.exit_code]


def log_path_for(day: date, log_dir: Path = DEFAULT_LOG_DIR) -> Path:
    """Un file per giornata. Il nome è la data UTC, mai l'ora locale."""
    return Path(log_dir) / f"daily-{day.isoformat()}.log"


def subprocess_runner(command: list[str], env: dict[str, str]):
    return subprocess.run(command, env=env, capture_output=True, text=True)


def run_daily(
    *,
    repo_root: Path,
    today: date,
    now_utc: datetime,
    python_executable: str,
    live: bool = False,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    ops_path: Path = DEFAULT_OPS_PATH,
    log_dir: Path = DEFAULT_LOG_DIR,
    require_configured_hour: bool = False,
    snapshot_hour_utc: int = DEFAULT_SNAPSHOT_HOUR_UTC,
    runner=subprocess_runner,
    env: dict[str, str] | None = None,
    echo: bool = True,
    sleep=time.sleep,
) -> RitualResult:
    """Esegue il rito e ritorna l'esito. Non solleva."""
    log = RitualLog(path=log_path_for(today, log_dir), echo=echo)
    environment = dict(os.environ if env is None else env)

    log.write(f"rito quotidiano — giorno UTC {today.isoformat()}")
    log.write(f"ora UTC configurata per il rito : {snapshot_hour_utc:02d}:00")
    log.write(f"ora UTC di questa passata       : {now_utc.strftime('%H:%M')}")
    log.write(f"modalita'                       : {'LIVE' if live else 'mock'}")

    if require_configured_hour and now_utc.hour != snapshot_hour_utc:
        detail = (
            f"il rito e' registrato per le {snapshot_hour_utc:02d}:00 UTC ma "
            f"questa passata parte alle {now_utc.hour:02d}:00 UTC"
        )
        log.write(f"STOP: {detail}")
        return RitualResult(EXIT_PRECONDITION, log.path, detail=detail)

    if live and environment.get("TRADERLAB_ALLOW_LIVE_API") != "1":
        detail = "la modalita' live richiede TRADERLAB_ALLOW_LIVE_API=1"
        log.write(f"STOP: {detail}")
        return RitualResult(EXIT_PRECONDITION, log.path, detail=detail)

    trader_ledger = TraderLedger(ledger_path)
    ops_ledger = OpsLedger(ops_path)

    # -- 1. giorni mancati -------------------------------------------------
    try:
        marcati = mark_missing_days(
            trader_ledger=trader_ledger,
            ops_ledger=ops_ledger,
            today=today,
            detected_at_utc=now_utc,
        )
    except Exception as exc:  # noqa: BLE001 - diventa un exit code, non un crash
        detail = f"{type(exc).__name__}: {exc}"
        log.write(f"STOP: marcatura dei giorni mancati fallita — {detail}")
        return RitualResult(EXIT_GAP_MARKING_FAILED, log.path, detail=detail)

    if marcati:
        log.write(
            "giorni mancati marcati come skipped_day: "
            + ", ".join(d.isoformat() for d in marcati)
        )
        log.write(
            "le decisioni di quei giorni NON vengono recuperate: un verbale "
            "scritto oggi su dati di allora vedrebbe il futuro"
        )
    else:
        log.write("nessun giorno mancato da marcare")

    if today in recorded_days(trader_ledger):
        detail = f"il ledger contiene gia' verbali per {today.isoformat()}"
        log.write(f"STOP: {detail} — write-once, il rito non riparte")
        return RitualResult(
            EXIT_ALREADY_DONE, log.path, skipped_marked=tuple(marcati), detail=detail
        )

    # La rete si abilita per un solo processo, esplicitamente. Ovunque altrove
    # la variabile viene tolta dall'ambiente, non lasciata al caso.
    base_env = dict(environment)
    base_env.pop("TRADERLAB_ALLOW_NETWORK", None)

    # -- 2. snapshot: processo separato, rete ON ---------------------------
    log.write("passo 1/2 — costruzione dello snapshot (processo separato, rete ON)")
    build_env = dict(base_env)
    build_env["TRADERLAB_ALLOW_NETWORK"] = "1"
    build = runner(
        [python_executable, str(repo_root / "scripts" / "build_snapshot.py")],
        build_env,
    )
    log.block("build_snapshot stdout", build.stdout or "")
    log.block("build_snapshot stderr", build.stderr or "")

    if build.returncode != 0:
        return _stop(
            log,
            ops_ledger,
            today,
            now_utc,
            EXIT_SNAPSHOT_FAILED,
            f"build_snapshot.py ha restituito {build.returncode}",
            marcati,
        )

    match = _SNAPSHOT_ID_RE.search(build.stdout or "")
    if match is None:
        return _stop(
            log,
            ops_ledger,
            today,
            now_utc,
            EXIT_SNAPSHOT_FAILED,
            "snapshot_id assente dall'output di build_snapshot.py",
            marcati,
        )
    snapshot_id = match.group(1)
    log.write(f"snapshot congelato: {snapshot_id}")

    # -- 3. decisioni: processo separato, rete OFF -------------------------
    log.write("passo 2/2 — decisioni sulle repliche (rete OFF)")
    command = [
        python_executable,
        str(repo_root / "scripts" / "run_day.py"),
        "--snapshot-id",
        snapshot_id,
        "--ledger",
        str(ledger_path),
    ]
    if live:
        command.append("--live")
    decisions = runner(command, dict(base_env))
    log.block("run_day stdout", decisions.stdout or "")
    log.block("run_day stderr", decisions.stderr or "")

    retry_attempt = 0
    while (
        decisions.returncode == RETRYABLE_PROCESS_EXIT_CODE
        and retry_attempt < RITUAL_RETRY_MAX_ATTEMPTS
    ):
        retry_attempt += 1
        log.write(
            f"decisioni fallite con errore ritentabile (rete/capacita') — "
            f"attesa {RITUAL_RETRY_WAIT_SECONDS:.0f}s prima del tentativo "
            f"{retry_attempt}/{RITUAL_RETRY_MAX_ATTEMPTS} di ripetere l'intero "
            f"passo"
        )
        _record(
            ops_ledger,
            OpsKey.of(today, f"{OpsEvent.DECISIONS_RETRY_WAIT}:{retry_attempt}"),
            (
                f"attesa di {RITUAL_RETRY_WAIT_SECONDS:.0f}s dopo un fallimento "
                f"ritentabile del passo delle decisioni, prima del tentativo "
                f"{retry_attempt}/{RITUAL_RETRY_MAX_ATTEMPTS}"
            ),
            now_utc,
            log,
        )
        sleep(RITUAL_RETRY_WAIT_SECONDS)
        log.write(
            f"passo 2/2 — nuovo tentativo ({retry_attempt}/"
            f"{RITUAL_RETRY_MAX_ATTEMPTS}) del passo delle decisioni (rete OFF)"
        )
        decisions = runner(command, dict(base_env))
        log.block("run_day stdout", decisions.stdout or "")
        log.block("run_day stderr", decisions.stderr or "")

    if decisions.returncode == RETRYABLE_PROCESS_EXIT_CODE:
        detail = (
            f"il passo delle decisioni ha fallito con errore ritentabile per "
            f"tutti i {RITUAL_RETRY_MAX_ATTEMPTS} tentativi (finestra "
            f"~{RITUAL_RETRY_MAX_ATTEMPTS * RITUAL_RETRY_WAIT_SECONDS / 60:.0f} "
            f"min): il rito e' partito e l'API non ha risposto, non e' un "
            f"giorno saltato"
        )
        log.write(f"STOP: {detail}")
        _record(ops_ledger, OpsKey.of(today, OpsEvent.FAILED_DECISIONS), detail, now_utc, log)
        return RitualResult(
            EXIT_DECISIONS_RETRY_EXHAUSTED,
            log.path,
            snapshot_id=snapshot_id,
            skipped_marked=tuple(marcati),
            detail=detail,
        )

    if decisions.returncode != 0:
        return _stop(
            log,
            ops_ledger,
            today,
            now_utc,
            EXIT_DECISIONS_FAILED,
            f"run_day.py ha restituito {decisions.returncode}",
            marcati,
            snapshot_id=snapshot_id,
        )

    _record(
        ops_ledger,
        OpsKey.of(today, OpsEvent.DAY_COMPLETED),
        f"snapshot {snapshot_id}",
        now_utc,
        log,
    )
    log.write("giornata completata")
    return RitualResult(
        EXIT_OK, log.path, snapshot_id=snapshot_id, skipped_marked=tuple(marcati)
    )


def _stop(
    log: RitualLog,
    ops_ledger: OpsLedger,
    today: date,
    moment: datetime,
    exit_code: int,
    detail: str,
    marcati: list[date],
    snapshot_id: str | None = None,
) -> RitualResult:
    log.write(f"STOP: {detail}")
    _record(ops_ledger, OpsKey.of(today, OpsEvent.RUN_FAILED), detail, moment, log)
    return RitualResult(
        exit_code,
        log.path,
        snapshot_id=snapshot_id,
        skipped_marked=tuple(marcati),
        detail=detail,
    )


def _record(
    ops_ledger: OpsLedger,
    key: OpsKey,
    detail: str,
    moment: datetime,
    log: RitualLog,
) -> None:
    """Registra un evento operativo senza far fallire il rito per questo.

    Il registro è write-once: se l'evento di oggi c'è già — secondo tentativo
    nella stessa giornata — non è un fatto nuovo da scrivere, ed è comunque il
    log della passata a raccontare cosa è successo adesso.
    """
    if ops_ledger.has(key):
        log.write(f"evento '{key.event}' gia' registrato per {key.day}")
        return
    ops_ledger.append(key=key, detail=detail, detected_at_utc=moment)
