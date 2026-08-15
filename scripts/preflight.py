"""scripts/preflight.py — precondizioni del rito di STANOTTE, verificate di GIORNO.

Nato da due notti di Stagione 0 perse per precondizioni scoperte solo a
mezzanotte: la prima volta per il flag `-Live` assente dal task, la seconda
per la cache dell'ambiente del Task Scheduler che non vedeva una variabile
utente appena impostata. La correzione operativa di quest'ultimo caso è
stata iniettare `TRADERLAB_ALLOW_LIVE_API='1'` **dentro** l'`Arguments` del
task stesso (`$env:TRADERLAB_ALLOW_LIVE_API='1'; & run_daily.ps1 -Live`),
così il valore non dipende più da una variabile utente persistente e dalla
sua propagazione al processo del task.

Punto importante, verificato leggendo `arena/daily_ritual.py` e
`scripts/run_daily.ps1`: **il rito non legge mai `.env`** (vedi
`docs/OPERATIONS.md` §4 e §7). Se `.env` dichiara un valore diverso da quello
dell'ambiente di processo, quel valore non ha alcun effetto sulla
risoluzione reale — è esattamente il tipo di trappola che ha causato una
delle due notti perse. Questo script quindi non "simula" una lettura di
`.env` che il rito non fa: legge `.env` solo in via diagnostica, per
segnalare un disallineamento, e lo dichiara esplicitamente nel dettaglio.

Otto precondizioni, in quest'ordine:

  (a) ANTHROPIC_API_KEY presente e con il formato atteso, nell'ambiente di
      processo — mai il valore, solo presenza e lunghezza.
  (b) Il flag -Live risulterebbe attivo stanotte: risoluzione ESATTA di
      `run_daily.ps1` — Arguments del task registrato (se imposta la
      variabile inline), poi ambiente di processo. `.env` è solo un
      confronto diagnostico, mai una fonte reale.
  (c) Rete verso Hyperliquid raggiungibile: una chiamata leggera in un
      sotto-processo separato, con TRADERLAB_ALLOW_NETWORK=1 iniettato SOLO
      lì — stessa disciplina del passo 2 del rito (CLAUDE.md §7).
  (d) Il task è registrato nel Task Scheduler e il suo Arguments contiene
      sia `-Live` sia l'assegnazione inline di TRADERLAB_ALLOW_LIVE_API='1';
      prossima esecuzione riportata.
  (e) Spazio disco > 1 GB e `data/` scrivibile.
  (f) verify() delle catene hash — ledger dei verbali E registro operativo.
  (g) FreezeManifest presente coi due .ots accanto (manifest e PREREG).
  (h) Sessione utente attiva: non verificabile in anticipo — PROMEMORIA, mai
      FAIL (il task gira con LogonType=Interactive: Win+L va bene, il
      logoff no).

    uv run python scripts/preflight.py

Exit code: 0 se "PRONTO PER STANOTTE: SI", 1 altrimenti. Nessuna scrittura:
solo lettura e, per (c), una singola chiamata di rete in un sotto-processo
usa-e-getta.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.daily_ritual import DEFAULT_LEDGER_PATH, DEFAULT_OPS_PATH
from ledger.ops_ledger import OpsLedger
from ledger.trader_ledger import TraderLedger

DEFAULT_TASK_NAME_PATTERN = "*rito*quotidiano*"
DEFAULT_MANIFEST_PATH = Path("manifests/trader_v0_freeze_manifest.json")
DEFAULT_PREREG_PATH = Path("docs/PREREG_LAB_S0.md")
DEFAULT_DOTENV_PATH = Path(".env")
DEFAULT_DATA_DIR = Path("data")
MIN_FREE_BYTES = 1 * 1024 * 1024 * 1024  # 1 GB
DEFAULT_NETWORK_TIMEOUT = 20.0

_LIVE_INLINE_RE = re.compile(r"TRADERLAB_ALLOW_LIVE_API\s*=\s*['\"]?1['\"]?")
_LIVE_SWITCH_RE = re.compile(r"(?<![\w-])-Live\b", re.IGNORECASE)


# --------------------------------------------------------------------------
# Risultato di una singola precondizione
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CheckResult:
    """`ok=None` significa PROMEMORIA: non blocca, non è un FAIL."""

    label: str
    ok: bool | None
    detail: str = ""

    @property
    def status(self) -> str:
        if self.ok is None:
            return "PROMEMORIA"
        return "PASS" if self.ok else "FAIL"


@dataclass(frozen=True, slots=True)
class PreflightResult:
    checks: tuple[CheckResult, ...]
    ready: bool
    blocking_detail: str = ""


# --------------------------------------------------------------------------
# Sottoprocessi iniettabili (stesso pattern di arena/daily_ritual.py)
# --------------------------------------------------------------------------


def subprocess_runner(command: list[str], env: Mapping[str, str] | None = None, **kwargs):
    return subprocess.run(
        command,
        env=dict(env) if env is not None else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )


# --------------------------------------------------------------------------
# (a) ANTHROPIC_API_KEY
# --------------------------------------------------------------------------


def check_api_key(env: Mapping[str, str]) -> CheckResult:
    label = "(a) ANTHROPIC_API_KEY presente in ambiente"
    value = env.get("ANTHROPIC_API_KEY", "")
    if not value.strip():
        return CheckResult(label, False, "assente dall'ambiente effettivo del rito")
    if not value.startswith("sk-ant-"):
        return CheckResult(
            label,
            False,
            f"presente (lunghezza {len(value)}) ma non inizia con 'sk-ant-': formato inatteso",
        )
    return CheckResult(label, True, f"presente, formato valido (lunghezza {len(value)})")


# --------------------------------------------------------------------------
# (b) risoluzione ESATTA del flag -Live
# --------------------------------------------------------------------------


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Parsing minimale KEY=VALUE. Solo diagnostico: il rito non legge questo file."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        values[key.strip()] = raw_value.strip()
    return values


def check_live_flag(
    env: Mapping[str, str],
    dotenv_path: Path,
    task_arguments: str | None,
) -> CheckResult:
    """Stessa risoluzione di `run_daily.ps1`: -Live richiede
    `$env:TRADERLAB_ALLOW_LIVE_API -eq "1"` E la chiave presente.

    Il valore dell'ambiente di processo può arrivare da un'assegnazione
    inline nell'Arguments del task stesso (fonte "comando", il fix adottato
    dopo l'incidente della cache) o da una variabile utente/macchina
    persistente (fonte "ambiente"). `.env` non è mai una fonte reale: è
    riportato solo per segnalare un disallineamento.
    """
    label = "(b) flag -Live risulterebbe attivo stanotte"

    inline_in_command = bool(task_arguments and _LIVE_INLINE_RE.search(task_arguments))
    switch_in_command = bool(task_arguments and _LIVE_SWITCH_RE.search(task_arguments))
    process_value = env.get("TRADERLAB_ALLOW_LIVE_API")
    dotenv_value = _parse_dotenv(dotenv_path).get("TRADERLAB_ALLOW_LIVE_API")

    if inline_in_command:
        source = "comando (assegnazione inline nell'Arguments del task registrato)"
        live_api_value = "1"
    elif process_value is not None:
        source = "ambiente di processo"
        live_api_value = process_value
    else:
        source = "assente ovunque nella risoluzione reale"
        live_api_value = None

    key_present = bool(env.get("ANTHROPIC_API_KEY", "").strip())
    active = switch_in_command and live_api_value == "1" and key_present

    detail = (
        f"valore finale: {'ATTIVO' if active else 'NON attivo'} - fonte: {source}"
        f" - switch -Live nel comando: {'si' if switch_in_command else 'no'}"
        f" - ANTHROPIC_API_KEY presente: {'si' if key_present else 'no'}"
    )
    if dotenv_value is not None and dotenv_value != (live_api_value or ""):
        detail += (
            f". ATTENZIONE: {dotenv_path} dichiara TRADERLAB_ALLOW_LIVE_API="
            f"{dotenv_value!r} ma il rito NON legge .env (OPERATIONS.md sez. 4/7) - "
            f"questo valore e' IGNORATO dalla risoluzione reale, non fidarsi di .env"
            f" per questo flag."
        )
    return CheckResult(label, active, detail)


# --------------------------------------------------------------------------
# (c) rete verso Hyperliquid, in un sotto-processo usa-e-getta
# --------------------------------------------------------------------------


_NETWORK_PROBE_SCRIPT = (
    "from toolserver.hyperliquid import HyperliquidPublicClient\n"
    "client = HyperliquidPublicClient(timeout={timeout})\n"
    "universe, ctxs = client.meta_and_asset_ctxs()\n"
    "print(f'OK universe={{len(universe)}}')\n"
)


def check_network_reachable(
    *,
    python_executable: str,
    repo_root: Path,
    base_env: Mapping[str, str],
    timeout: float = DEFAULT_NETWORK_TIMEOUT,
    runner=subprocess_runner,
) -> CheckResult:
    """Stessa disciplina di rete del passo 1 dello snapshot (CLAUDE.md §7):
    il flag entra SOLO nell'ambiente di questo sotto-processo, mai nel
    processo di preflight stesso.
    """
    label = "(c) rete verso Hyperliquid raggiungibile"
    probe_env = dict(base_env)
    probe_env["TRADERLAB_ALLOW_NETWORK"] = "1"
    command = [python_executable, "-c", _NETWORK_PROBE_SCRIPT.format(timeout=timeout)]
    try:
        result = runner(command, probe_env, cwd=str(repo_root), timeout=timeout + 10.0)
    except Exception as exc:  # noqa: BLE001 - una rete assente non deve far crashare il preflight
        return CheckResult(label, False, f"{type(exc).__name__}: {exc}")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "nessun dettaglio").strip().splitlines()
        return CheckResult(label, False, detail[-1] if detail else "chiamata fallita")
    return CheckResult(label, True, (result.stdout or "").strip() or "chiamata riuscita")


# --------------------------------------------------------------------------
# (d) task registrato nel Task Scheduler
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TaskInfo:
    found: bool
    task_name: str = ""
    arguments: str = ""
    next_run_time: str = ""
    last_run_time: str = ""
    last_task_result: str = ""
    logon_type: str = ""
    error: str = ""


def _ps_escape_single_quoted(value: str) -> str:
    return value.replace("'", "''")


_TASK_QUERY_SCRIPT = """
$t = Get-ScheduledTask | Where-Object {{ $_.TaskName -like '{pattern}' }} | Select-Object -First 1
if (-not $t) {{ [PSCustomObject]@{{ found = $false }} | ConvertTo-Json -Compress; exit 0 }}
$info = $t | Get-ScheduledTaskInfo
[PSCustomObject]@{{
    found = $true
    TaskName = $t.TaskName
    Arguments = $t.Actions[0].Arguments
    LogonType = [string]$t.Principal.LogonType
    NextRunTime = [string]$info.NextRunTime
    LastRunTime = [string]$info.LastRunTime
    LastTaskResult = [string]$info.LastTaskResult
}} | ConvertTo-Json -Compress
"""


def query_scheduled_task(task_name_pattern: str, *, runner=subprocess_runner) -> TaskInfo:
    import json

    script = _TASK_QUERY_SCRIPT.format(pattern=_ps_escape_single_quoted(task_name_pattern))
    command = ["powershell.exe", "-NoProfile", "-Command", script]
    try:
        result = runner(command, None)
    except Exception as exc:  # noqa: BLE001 - un errore di query e' un FAIL, non un crash
        return TaskInfo(found=False, error=f"{type(exc).__name__}: {exc}")

    if result.returncode != 0:
        return TaskInfo(found=False, error=(result.stderr or "").strip()[:300])

    try:
        payload = json.loads((result.stdout or "").strip())
    except Exception as exc:  # noqa: BLE001
        return TaskInfo(found=False, error=f"output illeggibile: {exc}")

    if not payload.get("found"):
        return TaskInfo(found=False)

    return TaskInfo(
        found=True,
        task_name=payload.get("TaskName") or "",
        arguments=payload.get("Arguments") or "",
        next_run_time=payload.get("NextRunTime") or "",
        last_run_time=payload.get("LastRunTime") or "",
        last_task_result=payload.get("LastTaskResult") or "",
        logon_type=payload.get("LogonType") or "",
    )


def check_task_registration(task_info: TaskInfo) -> CheckResult:
    label = "(d) task schedulato registrato, con -Live nel comando"
    if not task_info.found:
        detail = "nessun task trovato nel Task Scheduler"
        if task_info.error:
            detail += f" - {task_info.error}"
        return CheckResult(label, False, detail)

    switch_ok = bool(_LIVE_SWITCH_RE.search(task_info.arguments))
    inline_ok = bool(_LIVE_INLINE_RE.search(task_info.arguments))
    ok = switch_ok and inline_ok
    detail = (
        f"task: {task_info.task_name!r} - switch -Live: {'si' if switch_ok else 'no'}"
        f" - TRADERLAB_ALLOW_LIVE_API='1' inline: {'si' if inline_ok else 'no'}"
        f" - prossima esecuzione: {task_info.next_run_time or 'N/D'}"
        f" - ultimo esito: {task_info.last_task_result or 'N/D'}"
    )
    return CheckResult(label, ok, detail)


# --------------------------------------------------------------------------
# (e) spazio disco e data/ scrivibile
# --------------------------------------------------------------------------


def check_disk_and_writable(
    repo_root: Path, data_dir: Path, *, min_free_bytes: int = MIN_FREE_BYTES
) -> CheckResult:
    label = "(e) spazio disco > 1 GB e data/ scrivibile"
    try:
        free_bytes = shutil.disk_usage(str(repo_root)).free
    except OSError as exc:
        return CheckResult(label, False, f"spazio disco illeggibile: {exc}")

    free_gb = free_bytes / (1024**3)
    if free_bytes <= min_free_bytes:
        return CheckResult(label, False, f"solo {free_gb:.2f} GB liberi su {repo_root}")

    marker = data_dir / ".preflight_write_test"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        marker.write_text("preflight", encoding="utf-8")
        marker.unlink()
    except OSError as exc:
        return CheckResult(label, False, f"{free_gb:.2f} GB liberi ma {data_dir} non scrivibile: {exc}")

    return CheckResult(label, True, f"{free_gb:.2f} GB liberi, {data_dir} scrivibile")


# --------------------------------------------------------------------------
# (f) verify() delle catene ledger
# --------------------------------------------------------------------------


def check_ledger_chains(ledger_path: Path, ops_path: Path) -> CheckResult:
    label = "(f) verify() delle catene ledger (verbali + operativo)"
    try:
        trader_verify = TraderLedger(ledger_path).verify()
        ops_verify = OpsLedger(ops_path).verify()
    except Exception as exc:  # noqa: BLE001 - un ledger illeggibile e' un FAIL, non un crash
        return CheckResult(label, False, f"{type(exc).__name__}: {exc}")

    ok = trader_verify.ok and ops_verify.ok
    detail = (
        f"verbali: {'ok' if trader_verify.ok else f'ROTTA - {trader_verify.detail}'}"
        f" ({trader_verify.entries_checked} righe) - "
        f"operativo: {'ok' if ops_verify.ok else f'ROTTA - {ops_verify.detail}'}"
        f" ({ops_verify.entries_checked} righe)"
    )
    return CheckResult(label, ok, detail)


# --------------------------------------------------------------------------
# (g) FreezeManifest + i due .ots
# --------------------------------------------------------------------------


def check_freeze_manifest(manifest_path: Path, prereg_path: Path) -> CheckResult:
    label = "(g) FreezeManifest presente coi due .ots accanto"
    manifest_ots = manifest_path.with_name(manifest_path.name + ".ots")
    prereg_ots = prereg_path.with_name(prereg_path.name + ".ots")

    missing = [
        str(p)
        for p in (manifest_path, manifest_ots, prereg_path, prereg_ots)
        if not p.exists()
    ]
    if missing:
        return CheckResult(label, False, "mancanti: " + ", ".join(missing))
    return CheckResult(
        label,
        True,
        f"presenti: {manifest_path.name}, {manifest_ots.name}, {prereg_path.name}, {prereg_ots.name}",
    )


# --------------------------------------------------------------------------
# (h) sessione utente — promemoria, mai FAIL
# --------------------------------------------------------------------------


def check_user_session(task_info: TaskInfo) -> CheckResult:
    label = "(h) sessione utente attiva"
    base = (
        "non verificabile in anticipo: il task gira con LogonType=Interactive, "
        "serve una sessione utente attiva (Win+L va bene, il logoff no)"
    )
    if task_info.found and task_info.logon_type:
        base += f" - LogonType registrato: {task_info.logon_type}"
        if "interactive" not in task_info.logon_type.lower():
            base += " (ATTENZIONE: non e' Interactive)"
    return CheckResult(label, None, base)


# --------------------------------------------------------------------------
# Orchestratore
# --------------------------------------------------------------------------


def run_preflight(
    *,
    repo_root: Path,
    env: Mapping[str, str],
    python_executable: str = sys.executable,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    ops_path: Path = DEFAULT_OPS_PATH,
    data_dir: Path = DEFAULT_DATA_DIR,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    prereg_path: Path = DEFAULT_PREREG_PATH,
    dotenv_path: Path = DEFAULT_DOTENV_PATH,
    task_name_pattern: str = DEFAULT_TASK_NAME_PATTERN,
    min_free_bytes: int = MIN_FREE_BYTES,
    network_timeout: float = DEFAULT_NETWORK_TIMEOUT,
    process_runner=subprocess_runner,
    task_query_runner=subprocess_runner,
) -> PreflightResult:
    """Esegue le otto precondizioni e ritorna l'esito. Non solleva, non scrive."""

    def _abs(path: Path) -> Path:
        return path if path.is_absolute() else repo_root / path

    task_info = query_scheduled_task(task_name_pattern, runner=task_query_runner)

    checks = [
        check_api_key(env),
        check_live_flag(env, _abs(dotenv_path), task_info.arguments or None),
        check_network_reachable(
            python_executable=python_executable,
            repo_root=repo_root,
            base_env=env,
            timeout=network_timeout,
            runner=process_runner,
        ),
        check_task_registration(task_info),
        check_disk_and_writable(repo_root, _abs(data_dir), min_free_bytes=min_free_bytes),
        check_ledger_chains(_abs(ledger_path), _abs(ops_path)),
        check_freeze_manifest(_abs(manifest_path), _abs(prereg_path)),
        check_user_session(task_info),
    ]

    failure = next((c for c in checks if c.ok is False), None)
    ready = failure is None
    blocking_detail = "" if ready else f"{failure.label}: {failure.detail}"

    return PreflightResult(checks=tuple(checks), ready=ready, blocking_detail=blocking_detail)


# --------------------------------------------------------------------------
# Formattazione tabellare
# --------------------------------------------------------------------------


def format_table(result: PreflightResult) -> str:
    label_width = max((len(c.label) for c in result.checks), default=0)
    status_width = len("PROMEMORIA")
    lines = [f"{'STATO':<{status_width}}  {'PRECONDIZIONE':<{label_width}}  DETTAGLIO"]
    for c in result.checks:
        lines.append(f"{c.status:<{status_width}}  {c.label:<{label_width}}  {c.detail}")
    lines.append("")
    if result.ready:
        lines.append("PRONTO PER STANOTTE: SI")
    else:
        lines.append(f"PRONTO PER STANOTTE: NO - {result.blocking_detail}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    import os

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH))
    parser.add_argument("--ops-ledger", default=str(DEFAULT_OPS_PATH))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--prereg", default=str(DEFAULT_PREREG_PATH))
    parser.add_argument("--dotenv", default=str(DEFAULT_DOTENV_PATH))
    parser.add_argument("--task-name-pattern", default=DEFAULT_TASK_NAME_PATTERN)
    parser.add_argument("--min-free-gb", type=float, default=1.0)
    parser.add_argument("--network-timeout", type=float, default=DEFAULT_NETWORK_TIMEOUT)
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    result = run_preflight(
        repo_root=repo_root,
        env=os.environ,
        ledger_path=Path(args.ledger),
        ops_path=Path(args.ops_ledger),
        data_dir=Path(args.data_dir),
        manifest_path=Path(args.manifest),
        prereg_path=Path(args.prereg),
        dotenv_path=Path(args.dotenv),
        task_name_pattern=args.task_name_pattern,
        min_free_bytes=int(args.min_free_gb * 1024**3),
        network_timeout=args.network_timeout,
    )
    print(format_table(result))
    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
