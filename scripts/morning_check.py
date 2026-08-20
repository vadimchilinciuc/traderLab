"""scripts/morning_check.py — logica del controllo delle 08:00.

Il wrapper PowerShell (`scripts/morning_check.ps1`) è volutamente sottile,
per lo stesso motivo di `scripts/run_daily.ps1` / `arena/daily_ritual.py`: uno
script di shell non è testabile senza scheduler, e una regola non testata non
esiste per il Lab. Tutta la logica sta qui.

Il controllo fa tre cose, indipendenti tra loro:

1. **Verifica la giornata di stanotte, ma solo se una stagione e' attiva.**
   Se il ledger dei verbali contiene la giornata corrispondente a 00:00 UTC
   di oggi, genera il rapporto del mattino (`scripts/morning_report.py`) e lo
   appende a `data/logs/morning-<data>.log`, exit 0. Se non la contiene **e
   una stagione e' attiva**, mostra un avviso **visibile** all'utente
   (`msg.exe`, con fallback a un popup PowerShell) e scrive l'allarme nello
   stesso log, exit 1.

   Una stagione e' attiva quando il Freeze manifest di default esiste, si
   carica e porta un `pin_commit` vero (`is_pinned`). Fuori da una stagione i
   verbali notturni **non sono attesi**: il rito e' spento per costruzione, e
   trasformare quella normalita' in un allarme quotidiano insegnerebbe
   all'owner a ignorare il file — che e' il modo piu' efficace di
   disattivare un allarme senza spegnerlo. Ogni **altra** anomalia continua
   ad allarmare anche fuori stagione.
2. **Esegue il preflight di stanotte** (`scripts/preflight.py`), sempre,
   indipendentemente dall'esito del punto 1: verifica di giorno le
   precondizioni della PROSSIMA passata del rito e appende la tabella al log
   del mattino. Se il preflight dice NO, mostra un secondo avviso
   **visibile**, distinto da quello del punto 1 ("stanotte NON partirà:
   causa"). Questo passo legge soltanto: non tocca né il ledger né gli exit
   code dichiarati in `EXIT_MEANING`, che restano determinati solo dalla
   giornata di stanotte (punto 1).
3. **Solo il lunedì**, tenta l'upgrade OpenTimestamps dei tre file timbrati
   (`manifests/trader_v0_freeze_manifest.json`, `docs/PREREG_LAB_S0.md`,
   `MANIFEST_S0.json`) tramite `scripts/ots_stamp.py upgrade`, iniettando
   `TRADERLAB_ALLOW_NETWORK=1` **solo** nel processo dell'upgrade — stessa
   disciplina di rete di `run_daily` per lo snapshot (CLAUDE.md §7). Non è mai
   bloccante: se i calendar non rispondono o l'attestazione non è pronta,
   l'esito finisce nel log e il controllo prosegue.
4. **Verifica il ritmo di spesa della stagione** (D5): se la spesa cumulata
   supera `ALARM_MULTIPLIER` volte il pro-rata del preventivo, è un'anomalia.
   Numeratore, denominatore e listino vengono **tutti** dal Freeze manifest
   (`season_budget_usd`, `season_expected_days`, le quattro voci di prezzo):
   se ne manca uno il passo si salta con il motivo scritto nel log. Non tocca l'exit code — la
   soglia che ferma le cose è quella dura, e vive nel runner.

**Il canale d'allarme** (verbale RUN2 §A.6, decisione D3). Su exit ≠ 0 o su
anomalia rilevata il controllo scrive `ALLARME_<data>.txt` alla radice del
repo, **con dentro il motivo**. Il file è gitignorato: è un segnale per
l'owner che apre il laptop, non un artefatto del track record. Esiste perché
un avviso `msg.exe` su una macchina senza sessione interattiva non compare, e
un log che nessuno apre non è un allarme — il file invece resta lì finché
qualcuno non lo guarda.

    uv run python scripts/morning_check.py
    uv run python scripts/morning_check.py --force-alarm   # prova del canale
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

from arena.config import DEFAULT_MANIFEST_PATH, ManifestError, load_pinned_manifest
from arena.daily_ritual import DEFAULT_LEDGER_PATH, DEFAULT_OPS_PATH, RitualLog
from contracts.freeze import FreezeManifest
from ledger.ops_ledger import OpsLedger, recorded_days
from ledger.spend import (
    check_prorata_alarm,
    check_season_terms,
    read_pricing,
    season_spend,
)
from ledger.trader_ledger import TraderLedger
from scripts.morning_report import generate_report
from scripts.preflight import PreflightResult, format_table, run_preflight
from toolserver.config import ToolServerConfig

EXIT_OK = 0
EXIT_NO_VERBALI = 1

#: Significato dei due exit code. Sono **grossolani** per costruzione: il
#: wrapper PowerShell e il Task Scheduler leggono un numero, non una frase. Il
#: dettaglio di cosa e' successo sta in `MorningCheckResult.detail`, che
#: finisce nel log e nel file d'allarme. Exit 0 copre due casi diversi ma
#: entrambi senza niente da segnalare: la giornata c'e', oppure non c'e' e non
#: era attesa perche' nessuna stagione e' attiva.
EXIT_MEANING: dict[int, str] = {
    EXIT_OK: "niente da segnalare sulla giornata di stanotte",
    EXIT_NO_VERBALI: (
        "stagione attiva e giornata di stanotte assente dal ledger, avviso mostrato"
    ),
}

DEFAULT_LOG_DIR = Path("data/logs")
#: I file che l'upgrade settimanale ritenta di ancorare. Sono **cinque**: i
#: tre timbri della Stagione 0, elencati in
#: `docs/research/results/2026-08-20_PREREG-EVIDENCE_ANCORAGGI_OTS_S0.md`, piu'
#: i due del RUN2, apposti al rito PIN-QUATER del 2026-08-20.
#:
#: `MANIFEST_S0.json` mancava, e la conseguenza si e' misurata: il 20/08 il suo
#: `.ots` era ancora **pending su tutti e quattro i calendar** mentre gli altri
#: due erano gia' confermati su Bitcoin: nessuno stava ritentando l'upgrade per
#: lui. Un ancoraggio fuori da questa lista non e' meno timbrato, ma resta
#: fermo alla ricevuta provvisoria finche' qualcuno non se ne ricorda a mano —
#: ed e' la ricevuta definitiva a valere come prova. I due del RUN2 nascono
#: pending come quello: entrano qui **nello stesso rito che li appone**,
#: perche' aggiungerli dopo significherebbe ripetere quell'errore sapendolo.
#:
#: Regola che ne discende, per chi timbrera' il prossimo artefatto: un
#: ancoraggio nuovo si aggiunge a questa lista nel rito che lo crea, non in
#: uno successivo.
DEFAULT_OTS_TARGETS: tuple[Path, ...] = (
    Path("manifests/trader_v0_freeze_manifest.json"),
    Path("docs/PREREG_LAB_S0.md"),
    Path("MANIFEST_S0.json"),
    Path("docs/PREREG_LAB_S0_RUN2.md"),
    Path("manifests/trader_v1_run2_freeze_manifest.json"),
)

#: Nome del file d'allarme, alla radice del repo. Gitignorato (`ALLARME_*.txt`).
ALARM_FILENAME = "ALLARME_{day}.txt"


def log_path_for(day: date, log_dir: Path = DEFAULT_LOG_DIR) -> Path:
    """Un file per giornata di controllo, come per il rito quotidiano."""
    return Path(log_dir) / f"morning-{day.isoformat()}.log"


def alarm_path_for(day: date, repo_root: Path) -> Path:
    """`ALLARME_<data>.txt` alla radice del repo. Un file per giornata."""
    return Path(repo_root) / ALARM_FILENAME.format(day=day.isoformat())


def write_alarm(path: Path, day: date, reasons: list[str]) -> Path:
    """Scrive il file d'allarme con dentro i motivi. Sovrascrive quello del giorno.

    Sovrascrive e non appende: il file è la fotografia dello stato di **questa**
    passata, e due passate nella stessa mattina non devono produrre un elenco
    che cresce. Il registro di ciò che è successo è il log, non questo file.
    """
    corpo = [
        f"ALLARME traderLab — {day.isoformat()}",
        "",
        "Il controllo del mattino ha rilevato quanto segue:",
        "",
    ]
    corpo.extend(f"  {n}. {motivo}" for n, motivo in enumerate(reasons, start=1))
    corpo.extend(
        [
            "",
            f"Log della passata : data/logs/morning-{day.isoformat()}.log",
            f"Log del rito      : data/logs/daily-{day.isoformat()}.log",
            "",
            "Questo file e' gitignorato: cancellarlo dopo averlo letto e' la",
            "chiusura prevista. Nessun automatismo lo rimuove.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(corpo) + "\n", encoding="utf-8")
    return path


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
    # Canale d'allarme (§A.6 / D3). `alarm_file` è valorizzato solo se il file
    # è stato davvero scritto; `alarm_reasons` porta i motivi che ci sono
    # finiti dentro, nello stesso ordine.
    alarm_file: Path | None = None
    alarm_reasons: tuple[str, ...] = ()
    budget_ok: bool | None = None
    #: Una stagione e' attiva? Vero solo se il Freeze manifest esiste, si
    #: carica e porta un `pin_commit` vero. Fuori stagione i verbali notturni
    #: non sono attesi e la loro assenza non e' un'anomalia.
    season_active: bool = False

    @property
    def meaning(self) -> str:
        return EXIT_MEANING[self.exit_code]

    @property
    def alarm_raised(self) -> bool:
        return self.alarm_file is not None


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
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    force_alarm: bool = False,
) -> MorningCheckResult:
    """Esegue il controllo del mattino e ritorna l'esito. Non solleva.

    `force_alarm=True` scrive il file d'allarme comunque, con il motivo
    "prova forzata". Serve a verificare che il canale funzioni **senza dover
    rompere qualcosa** per provarlo: un allarme che nessuno ha mai visto
    scattare è indistinguibile da un allarme che non scatta.
    """
    log = RitualLog(path=log_path_for(today, log_dir), echo=echo)
    environment = dict(os.environ if env is None else env)
    toolcalls_dir = toolcalls_dir or ToolServerConfig().toolcall_log_dir

    log.write(f"controllo del mattino — giorno UTC {today.isoformat()}")

    trader_ledger = TraderLedger(ledger_path)
    ops_ledger = OpsLedger(ops_path)
    day_found = today in recorded_days(trader_ledger)
    alert_shown: bool | None = None

    # Il manifest si legge UNA volta: serve a due domande diverse — "c'e' una
    # stagione attiva?" e "con quali termini economici?" — e leggerlo due
    # volte permetterebbe alle due risposte di divergere.
    manifest, manifest_detail = _load_manifest_quiet(manifest_path)
    season_active = manifest is not None and manifest.is_pinned
    log.write(
        f"stagione: {'ATTIVA' if season_active else 'nessuna'} — {manifest_detail}"
    )

    if day_found:
        log.write(f"giornata di stanotte ({today.isoformat()}) presente nel ledger")
        # Il listino del rapporto viene dallo stesso manifest gia' caricato:
        # senza pin (o senza listino nel pin) il rapporto stampa i token e
        # dichiara il costo non calcolabile, invece di inventarsi una tariffa.
        pricing_report, _ = read_pricing(manifest) if manifest else (None, [])
        report = generate_report(
            trader_ledger=trader_ledger,
            ops_ledger=ops_ledger,
            toolcalls_dir=toolcalls_dir,
            pricing=pricing_report,
        )
        log.block("rapporto del mattino", report)
        exit_code = EXIT_OK
        detail = "giornata di stanotte presente"
    elif not season_active:
        # Fuori stagione i verbali notturni non sono attesi: il rito e' spento
        # per costruzione. Nessun avviso, nessun allarme, nessun exit code
        # diverso da zero — un allarme che suona ogni mattina di un cantiere
        # fermo e' un allarme che l'owner impara a non guardare, ed e' la
        # stessa ragione per cui il passo del budget si salta invece di
        # allarmare quando il preventivo non c'e' ancora.
        detail = (
            f"nessuna stagione attiva ({manifest_detail}): i verbali di "
            f"stanotte non sono attesi e la loro assenza non e' un'anomalia"
        )
        log.write(detail)
        exit_code = EXIT_OK
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
    preflight_detail = ""
    try:
        preflight_result = preflight(
            repo_root=repo_root, env=environment, ledger_path=ledger_path, ops_path=ops_path
        )
    except Exception as exc:  # noqa: BLE001 - un preflight fallito non blocca il controllo
        log.write(f"preflight: eccezione nell'eseguirlo — {type(exc).__name__}: {exc}")
    else:
        log.block("preflight per stanotte", format_table(preflight_result))
        preflight_ready = preflight_result.ready
        preflight_detail = preflight_result.blocking_detail or ""
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

    # -- ritmo di spesa della stagione (D5) --------------------------------
    budget_ok, budget_detail = _check_budget_rhythm(
        trader_ledger=trader_ledger,
        toolcalls_dir=toolcalls_dir,
        manifest=manifest,
        manifest_detail=manifest_detail,
        log=log,
    )

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

    # -- canale d'allarme (§A.6 / D3) --------------------------------------
    reasons: list[str] = []
    if force_alarm:
        reasons.append(
            "prova forzata del canale d'allarme (--force-alarm): nessuna "
            "anomalia reale implicita in questo motivo"
        )
    if exit_code != EXIT_OK:
        reasons.append(f"exit {exit_code} — {EXIT_MEANING[exit_code]}: {detail}")
    if preflight_ready is False:
        reasons.append(f"preflight NO per stanotte: {preflight_detail}")
    if budget_ok is False:
        reasons.append(f"ritmo di spesa oltre soglia (D5): {budget_detail}")

    alarm_file: Path | None = None
    if reasons:
        alarm_file = write_alarm(alarm_path_for(today, repo_root), today, reasons)
        log.write(f"ALLARME scritto in {alarm_file} — {len(reasons)} motivo/i")
        for motivo in reasons:
            log.write(f"    motivo: {motivo}")
    else:
        log.write("nessun allarme: nessun motivo rilevato, il file non viene creato")

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
        alarm_file=alarm_file,
        alarm_reasons=tuple(reasons),
        budget_ok=budget_ok,
        season_active=season_active,
    )


def _load_manifest_quiet(
    manifest_path: Path | str,
) -> tuple[FreezeManifest | None, str]:
    """Carica il Freeze manifest senza pretendere il pin, senza sollevare.

    Ritorna `(manifest, motivo)`. Un manifest assente, illeggibile o con
    `freeze_id` divergente da' `(None, motivo)`: per il controllo del mattino
    tutti e tre significano la stessa cosa — **non c'e' una stagione** — e la
    distinzione fra loro sta nel motivo, che finisce nel log.

    Un manifest che si carica ma non e' ancora pinnato torna comunque
    (`is_pinned` sara' falso): e' un documento valido, semplicemente non e'
    ancora un pin di stagione.
    """
    try:
        manifest = load_pinned_manifest(manifest_path, require_pin=False)
    except ManifestError as exc:
        return None, f"manifest non utilizzabile: {exc}"
    if not manifest.is_pinned:
        return manifest, (
            f"manifest {manifest_path} leggibile ma non pinnato "
            f"(pin_commit={manifest.pin_commit!r})"
        )
    return manifest, f"pin_commit={manifest.pin_commit}"


def _check_budget_rhythm(
    *,
    trader_ledger: TraderLedger,
    toolcalls_dir: Path,
    manifest: FreezeManifest | None,
    manifest_detail: str,
    log: RitualLog,
) -> tuple[bool | None, str]:
    """La stagione sta bruciando piu' in fretta del pro-rata? (D5)

    Ritorna `(None, motivo)` quando la domanda **non si pone**: manifest
    assente o illeggibile, oppure senza uno dei termini economici
    (`season_budget_usd`, `season_expected_days`, le quattro voci di listino).
    Prima del rito del pin è la
    situazione normale, e trasformarla in un allarme quotidiano insegnerebbe
    all'owner a ignorare il file — che è il modo più efficace di disattivare
    un allarme senza spegnerlo.

    Il manifest arriva **già caricato**: e' lo stesso oggetto che ha deciso se
    una stagione e' attiva, e rileggerlo qui permetterebbe alle due risposte
    di divergere.

    La soglia che **ferma** le cose non è questa: è quella dura, in
    `scripts/run_day.py`. Questa sveglia soltanto.
    """
    if manifest is None:
        log.write(f"ritmo di spesa: controllo saltato — {manifest_detail}")
        return None, manifest_detail

    termini = check_season_terms(manifest)
    if not termini.ok:
        log.write(f"ritmo di spesa: controllo saltato — {termini.detail}")
        return None, termini.detail

    pricing = termini.pricing
    assert pricing is not None  # garantito da `termini.ok`
    spesa = season_spend(
        trader_ledger=trader_ledger, toolcalls_dir=toolcalls_dir, pricing=pricing
    )
    verdetto = check_prorata_alarm(
        spesa,
        manifest.season_budget_usd,
        expected_days=manifest.season_expected_days,
    )
    log.write(f"ritmo di spesa: {verdetto.detail}")
    return verdetto.ok, verdetto.detail


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
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument(
        "--force-alarm",
        action="store_true",
        help=(
            "scrive comunque ALLARME_<data>.txt, con motivo 'prova forzata': "
            "verifica il canale senza dover rompere niente per provarlo"
        ),
    )
    args = parser.parse_args(argv)

    today = datetime.now(tz=timezone.utc).date()
    result = run_morning_check(
        repo_root=Path(__file__).resolve().parents[1],
        today=today,
        ledger_path=Path(args.ledger),
        ops_path=Path(args.ops_ledger),
        log_dir=Path(args.log_dir),
        manifest_path=Path(args.manifest),
        force_alarm=args.force_alarm,
    )

    print(f"\nlog             : {result.log_path}")
    print(f"stagione        : {'attiva' if result.season_active else 'nessuna'}")
    print(f"exit code       : {result.exit_code} — {result.meaning}")
    if result.detail:
        print(f"dettaglio       : {result.detail}")
    if result.alarm_file is not None:
        print(f"ALLARME         : {result.alarm_file}")
        for motivo in result.alarm_reasons:
            print(f"                  - {motivo}")
    else:
        print("ALLARME         : nessuno")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
