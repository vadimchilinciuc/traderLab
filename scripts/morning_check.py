"""scripts/morning_check.py — logica del controllo delle 08:00.

Il wrapper PowerShell (`scripts/morning_check.ps1`) è volutamente sottile,
per lo stesso motivo di `scripts/run_daily.ps1` / `arena/daily_ritual.py`: uno
script di shell non è testabile senza scheduler, e una regola non testata non
esiste per il Lab. Tutta la logica sta qui.

Il controllo fa tre cose, indipendenti tra loro:

1. **Verifica la giornata di stanotte.** Se il ledger dei verbali contiene la
   giornata corrispondente a 00:00 UTC di oggi, genera il rapporto del
   mattino (`scripts/morning_report.py`) e lo appende a
   `data/logs/morning-<data>.log`, exit 0. Se non la contiene, mostra un
   avviso **visibile** all'utente (`msg.exe`, con fallback a un popup
   PowerShell) e scrive l'allarme nello stesso log, exit 1.
2. **Esegue il preflight di stanotte** (`scripts/preflight.py`), sempre,
   indipendentemente dall'esito del punto 1: verifica di giorno le
   precondizioni della PROSSIMA passata del rito e appende la tabella al log
   del mattino. Se il preflight dice NO, mostra un secondo avviso
   **visibile**, distinto da quello del punto 1 ("stanotte NON partirà:
   causa"). Questo passo legge soltanto: non tocca né il ledger né gli exit
   code dichiarati in `EXIT_MEANING`, che restano determinati solo dalla
   giornata di stanotte (punto 1).
3. **Solo il lunedì**, tenta l'upgrade OpenTimestamps dei due file timbrati
   (`manifests/trader_v0_freeze_manifest.json`,
   `docs/PREREG_LAB_S0.md`) tramite `scripts/ots_stamp.py upgrade`, iniettando
   `TRADERLAB_ALLOW_NETWORK=1` **solo** nel processo dell'upgrade — stessa
   disciplina di rete di `run_daily` per lo snapshot (CLAUDE.md §7). Non è mai
   bloccante: se i calendar non rispondono o l'attestazione non è pronta,
   l'esito finisce nel log e il controllo prosegue.

    uv run python scripts/morning_check.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.daily_ritual import DEFAULT_LEDGER_PATH, DEFAULT_OPS_PATH, RitualLog
from ledger.ops_ledger import OpsLedger, recorded_days
from ledger.trader_ledger import TraderLedger
from scripts.morning_report import generate_report
from scripts.preflight import PreflightResult, format_table, run_preflight
from toolserver.config import ToolServerConfig

EXIT_OK = 0
EXIT_NO_VERBALI = 1

EXIT_MEANING: dict[int, str] = {
    EXIT_OK: "la giornata di stanotte e' nel ledger, rapporto scritto",
    EXIT_NO_VERBALI: "la giornata di stanotte NON e' nel ledger, avviso mostrato",
}

DEFAULT_LOG_DIR = Path("data/logs")
DEFAULT_OTS_TARGETS: tuple[Path, ...] = (
    Path("manifests/trader_v0_freeze_manifest.json"),
    Path("docs/PREREG_LAB_S0.md"),
)


def log_path_for(day: date, log_dir: Path = DEFAULT_LOG_DIR) -> Path:
    """Un file per giornata di controllo, come per il rito quotidiano."""
    return Path(log_dir) / f"morning-{day.isoformat()}.log"


def subprocess_runner(command: list[str], env: dict[str, str]):
    return subprocess.run(command, env=env, capture_output=True, text=True)


def default_alert(message: str, *, runner=subprocess.run) -> bool:
    """Avviso visibile: `msg.exe`, con fallback a un popup PowerShell.

    Ritorna True se uno dei due tentativi è partito con successo — non
    garantisce che l'utente l'abbia visto, solo che il tentativo di mostrarlo
    non è fallito. Un avviso che non riesce a comparire non deve far fallire
    il controllo: entrambi i rami sono avvolti in un `try` a parte.
    """
    try:
        result = runner(
            ["msg.exe", "*", "/TIME:60", message],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if getattr(result, "returncode", 1) == 0:
            return True
    except Exception:  # noqa: BLE001 - un avviso fallito non è un errore fatale
        pass

    try:
        escaped = message.replace("'", "''")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            f"[System.Windows.Forms.MessageBox]::Show('{escaped}', 'traderLab') "
            "| Out-Null"
        )
        result = runner(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return getattr(result, "returncode", 1) == 0
    except Exception:  # noqa: BLE001
        return False


def default_preflight_check(*, repo_root: Path, env: dict[str, str], ledger_path: Path, ops_path: Path) -> PreflightResult:
    """Wrapper reale su `scripts.preflight.run_preflight` (sottoprocessi veri)."""
    return run_preflight(repo_root=repo_root, env=env, ledger_path=ledger_path, ops_path=ops_path)


@dataclass(frozen=True, slots=True)
class MorningCheckResult:
    exit_code: int
    log_path: Path
    day_found: bool
    alert_shown: bool | None = None
    ots_attempted: bool = False
    detail: str = ""
    preflight_ready: bool | None = None
    preflight_alert_shown: bool | None = None

    @property
    def meaning(self) -> str:
        return EXIT_MEANING[self.exit_code]


def run_morning_check(
    *,
    repo_root: Path,
    today: date,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    ops_path: Path = DEFAULT_OPS_PATH,
    log_dir: Path = DEFAULT_LOG_DIR,
    toolcalls_dir: Path | None = None,
    python_executable: str = sys.executable,
    is_monday: bool | None = None,
    ots_targets: tuple[Path, ...] = DEFAULT_OTS_TARGETS,
    runner=subprocess_runner,
    env: dict[str, str] | None = None,
    alert=default_alert,
    preflight=default_preflight_check,
    echo: bool = True,
) -> MorningCheckResult:
    """Esegue il controllo del mattino e ritorna l'esito. Non solleva."""
    log = RitualLog(path=log_path_for(today, log_dir), echo=echo)
    environment = dict(os.environ if env is None else env)
    toolcalls_dir = toolcalls_dir or ToolServerConfig().toolcall_log_dir

    log.write(f"controllo del mattino — giorno UTC {today.isoformat()}")

    trader_ledger = TraderLedger(ledger_path)
    ops_ledger = OpsLedger(ops_path)
    day_found = today in recorded_days(trader_ledger)
    alert_shown: bool | None = None

    if day_found:
        log.write(f"giornata di stanotte ({today.isoformat()}) presente nel ledger")
        report = generate_report(
            trader_ledger=trader_ledger, ops_ledger=ops_ledger, toolcalls_dir=toolcalls_dir
        )
        log.block("rapporto del mattino", report)
        exit_code = EXIT_OK
        detail = "giornata di stanotte presente"
    else:
        daily_log = f"data/logs/daily-{today.isoformat()}.log"
        message = (
            f"traderLab: il rito di stanotte NON ha prodotto verbali - "
            f"controlla {daily_log}"
        )
        log.write(f"STOP: {message}")
        try:
            alert_shown = bool(alert(message))
        except Exception as exc:  # noqa: BLE001 - un avviso fallito non blocca il controllo
            log.write(f"avviso: eccezione nel mostrarlo — {type(exc).__name__}: {exc}")
            alert_shown = False
        log.write(
            "avviso mostrato" if alert_shown else "avviso NON mostrato (msg.exe e popup falliti)"
        )
        exit_code = EXIT_NO_VERBALI
        detail = message

    preflight_ready: bool | None = None
    preflight_alert_shown: bool | None = None
    try:
        preflight_result = preflight(
            repo_root=repo_root, env=environment, ledger_path=ledger_path, ops_path=ops_path
        )
    except Exception as exc:  # noqa: BLE001 - un preflight fallito non blocca il controllo
        log.write(f"preflight: eccezione nell'eseguirlo — {type(exc).__name__}: {exc}")
    else:
        log.block("preflight per stanotte", format_table(preflight_result))
        preflight_ready = preflight_result.ready
        if not preflight_result.ready:
            preflight_message = f"traderLab: stanotte NON partira' - {preflight_result.blocking_detail}"
            log.write(f"STOP: {preflight_message}")
            try:
                preflight_alert_shown = bool(alert(preflight_message))
            except Exception as exc:  # noqa: BLE001 - un avviso fallito non blocca il controllo
                log.write(f"avviso preflight: eccezione nel mostrarlo — {type(exc).__name__}: {exc}")
                preflight_alert_shown = False
            log.write(
                "avviso preflight mostrato"
                if preflight_alert_shown
                else "avviso preflight NON mostrato (msg.exe e popup falliti)"
            )
        else:
            log.write("preflight: pronto per stanotte")

    is_monday = today.weekday() == 0 if is_monday is None else is_monday
    ots_attempted = False
    if is_monday:
        ots_attempted = True
        _attempt_ots_upgrade(
            repo_root=repo_root,
            targets=ots_targets,
            python_executable=python_executable,
            base_env=environment,
            runner=runner,
            log=log,
        )
    else:
        log.write("upgrade OTS: non e' lunedi', salto")

    log.write(f"controllo del mattino concluso — exit {exit_code}")
    return MorningCheckResult(
        exit_code=exit_code,
        log_path=log.path,
        day_found=day_found,
        alert_shown=alert_shown,
        ots_attempted=ots_attempted,
        detail=detail,
        preflight_ready=preflight_ready,
        preflight_alert_shown=preflight_alert_shown,
    )


def _attempt_ots_upgrade(
    *,
    repo_root: Path,
    targets: tuple[Path, ...],
    python_executable: str,
    base_env: dict[str, str],
    runner,
    log: RitualLog,
) -> None:
    """Tenta l'upgrade OTS di ogni file. Mai bloccante: logga e prosegue.

    La rete si accende solo per questo sottoprocesso, esplicitamente — stessa
    disciplina del passo dello snapshot in `arena/daily_ritual.py`
    (CLAUDE.md §7).
    """
    log.write("upgrade OTS settimanale (lunedi'): avvio")
    upgrade_env = dict(base_env)
    upgrade_env["TRADERLAB_ALLOW_NETWORK"] = "1"
    for target in targets:
        target_path = repo_root / target
        command = [
            python_executable,
            str(repo_root / "scripts" / "ots_stamp.py"),
            "upgrade",
            str(target_path),
        ]
        try:
            result = runner(command, upgrade_env)
        except Exception as exc:  # noqa: BLE001 - mai bloccante
            log.write(f"upgrade OTS {target}: eccezione — {type(exc).__name__}: {exc}")
            continue
        log.write(f"upgrade OTS {target}: exit {result.returncode}")
        log.block(f"ots_stamp stdout ({target})", result.stdout or "")
        log.block(f"ots_stamp stderr ({target})", result.stderr or "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH))
    parser.add_argument("--ops-ledger", default=str(DEFAULT_OPS_PATH))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    args = parser.parse_args(argv)

    today = datetime.now(tz=timezone.utc).date()
    result = run_morning_check(
        repo_root=Path(__file__).resolve().parents[1],
        today=today,
        ledger_path=Path(args.ledger),
        ops_path=Path(args.ops_ledger),
        log_dir=Path(args.log_dir),
    )

    print(f"\nlog             : {result.log_path}")
    print(f"exit code       : {result.exit_code} — {result.meaning}")
    if result.detail:
        print(f"dettaglio       : {result.detail}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
