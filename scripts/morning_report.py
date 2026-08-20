"""scripts/morning_report.py — rapporto del mattino, zero rete, zero API.

Legge `data/ledger/season0.jsonl`, `data/ledger/ops.jsonl` e il log delle tool
call sotto `data/toolcalls/`, e stampa un rapporto sintetico dell'ultima
giornata toccata dal rito: esito, decisioni delle repliche con l'accordo tra
loro, token consumati e costo stimato, integrità della catena del ledger,
conteggio delle giornate registrate sulla finestra del kill-criterion
pre-registrato (`ledger/eprocess.py`, `window=20`).

Nessuna chiamata al modello, nessuna scrittura: solo lettura.

    uv run python scripts/morning_report.py
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.config import DEFAULT_MANIFEST_PATH, ManifestError, load_pinned_manifest
from arena.daily_ritual import DEFAULT_LEDGER_PATH, DEFAULT_OPS_PATH
from ledger.eprocess import KillCriterionConfig
from ledger.ops_ledger import OpsEvent, OpsLedger, recorded_days
from ledger.spend import (
    Pricing,
    day_token_totals,
    estimate_cost_usd,
    read_pricing,
)
from ledger.trader_ledger import TraderLedger
from toolserver.config import ToolServerConfig

# Il listino non è più un dato di questo modulo né di `ledger/spend.py`: è un
# campo del Freeze manifest, firmato al rito del pin insieme al preventivo che
# da esso è stato calcolato. Il rapporto lo riceve da chi lo chiama; quando non
# c'è, stampa i token e dichiara il costo non calcolabile — inventarsi una
# tariffa per riempire la riga è il modo in cui il listino di Fable è
# sopravvissuto al cambio di modello.
__all__ = [
    "classify_outcome",
    "day_entries",
    "day_token_totals",
    "estimate_cost_usd",
    "format_asset_lines",
    "generate_report",
    "last_touched_day",
    "latest_event_detail",
    "pricing_from_manifest",
    "read_pricing",
    "run_ids_for_day",
]


# --------------------------------------------------------------------------
# Ultima giornata ed esito
# --------------------------------------------------------------------------


def last_touched_day(trader_ledger: TraderLedger, ops_ledger: OpsLedger) -> date | None:
    """L'ultimo giorno toccato dal rito, nel ledger dei verbali o in quello operativo."""
    days = set(recorded_days(trader_ledger))
    days.update(date.fromisoformat(e["key"]["day"]) for e in ops_ledger.read_all())
    return max(days) if days else None


def classify_outcome(day: date, trader_ledger: TraderLedger, ops_ledger: OpsLedger) -> str:
    """completata / skipped_day / failed_decisions, secondo la telemetria del rito."""
    events = {
        e["key"]["event"] for e in ops_ledger.read_all() if e["key"]["day"] == day.isoformat()
    }
    if OpsEvent.DAY_COMPLETED.value in events:
        return "completata"
    if OpsEvent.SKIPPED_DAY.value in events:
        return "skipped_day"
    if OpsEvent.FAILED_DECISIONS.value in events or OpsEvent.RUN_FAILED.value in events:
        return "failed_decisions"
    if day in recorded_days(trader_ledger):
        # Verbali presenti ma nessun evento operativo corrispondente: capita
        # per ledger scritti prima della telemetria operativa o a mano (es.
        # nei test). Il verbale è il dato che conta.
        return "completata"
    return "nessuna"


def latest_event_detail(day: date, ops_ledger: OpsLedger) -> str | None:
    """Il `detail` dell'evento operativo più recente per il giorno dato."""
    events = [e for e in ops_ledger.read_all() if e["key"]["day"] == day.isoformat()]
    if not events:
        return None
    return events[-1]["detail"]


# --------------------------------------------------------------------------
# Decisioni delle repliche
# --------------------------------------------------------------------------


def day_entries(trader_ledger: TraderLedger, day: date) -> list[dict[str, Any]]:
    day_str = day.isoformat()
    return [e for e in trader_ledger.read_all() if e["key"]["day"] == day_str]


def format_asset_lines(entries: list[dict[str, Any]]) -> list[str]:
    """Una riga per asset: azione e confidence delle tre repliche, e l'accordo."""
    by_asset: dict[str, dict[str, dict[str, Any]]] = {}
    for e in entries:
        by_asset.setdefault(e["key"]["asset"], {})[e["key"]["replica_id"]] = e

    lines: list[str] = []
    for asset in sorted(by_asset):
        replicas = by_asset[asset]
        parts: list[str] = []
        actions: list[str] = []
        for replica_id in sorted(replicas):
            entry = replicas[replica_id]
            action = entry["verdict"]["action_out"]
            actions.append(action)
            decision = entry.get("decision")
            if decision is not None:
                label = f"conf={decision['confidence']:.2f}"
            elif entry.get("malformed_reason"):
                label = entry["malformed_reason"]
            else:
                label = "n/d"
            parts.append(f"{replica_id}={action:<5} {label}")
        agreement = Counter(actions).most_common(1)[0][1] if actions else 0
        lines.append(
            f"{asset:<5} " + " | ".join(parts) + f"   accordo {agreement}/{len(actions)}"
        )
    return lines


# --------------------------------------------------------------------------
# Token e costo
# --------------------------------------------------------------------------


def run_ids_for_day(entries: list[dict[str, Any]]) -> list[str]:
    """`run_id` distinti che hanno scritto verbali per il giorno (in ordine)."""
    seen: list[str] = []
    for e in entries:
        run_id = e.get("run_id")
        if run_id and run_id not in seen:
            seen.append(run_id)
    return seen


# --------------------------------------------------------------------------
# Rapporto
# --------------------------------------------------------------------------


def generate_report(
    *,
    trader_ledger: TraderLedger,
    ops_ledger: OpsLedger,
    toolcalls_dir: Path,
    pricing: Pricing | None = None,
    kill_window: int = KillCriterionConfig().window,
) -> str:
    """Costruisce il testo del rapporto. Non stampa, non scrive: solo testo.

    `pricing` viene dal Freeze manifest. Assente — perché il pin non c'è
    ancora, o perché non porta il listino — la riga del costo lo **dichiara**
    invece di stimare a una tariffa qualsiasi: i token restano stampati, ed è
    da quelli che si ricava il costo il giorno in cui il listino c'è.
    """
    lines = ["RAPPORTO DEL MATTINO — traderLab"]

    day = last_touched_day(trader_ledger, ops_ledger)
    outcome = classify_outcome(day, trader_ledger, ops_ledger) if day else "nessuna"
    entries = day_entries(trader_ledger, day) if day else []

    lines.append(
        "data ultima giornata  : "
        + (day.isoformat() if day else "nessuna giornata ancora")
    )
    lines.append(f"esito                 : {outcome}")

    if outcome == "completata" and entries:
        lines.extend(format_asset_lines(entries))
    elif day and outcome in ("skipped_day", "failed_decisions"):
        detail = latest_event_detail(day, ops_ledger)
        if detail:
            lines.append(f"dettaglio             : {detail}")

    run_ids = run_ids_for_day(entries)
    input_t, output_t, cache_read_t, cache_creation_t = day_token_totals(run_ids, toolcalls_dir)
    lines.append(
        "token (input/output/cache_read/cache_creation): "
        f"{input_t}/{output_t}/{cache_read_t}/{cache_creation_t}"
    )
    if pricing is None:
        lines.append(
            "costo stimato USD     : non calcolabile — listino assente dal "
            "Freeze manifest (si firma al rito del pin, D5)"
        )
    else:
        costo = estimate_cost_usd(
            input_t, output_t, cache_read_t, cache_creation_t, pricing=pricing
        )
        lines.append(
            f"costo stimato USD     : ${costo:.4f} "
            f"(listino ${pricing.input_usd_per_mtok:g}/"
            f"${pricing.output_usd_per_mtok:g} per Mtok, input/output)"
        )

    verify = trader_ledger.verify()
    lines.append(
        f"catena ledger (verify): {'ok' if verify.ok else f'ROTTA — {verify.detail}'}"
    )

    giorni = len(recorded_days(trader_ledger))
    lines.append(f"giornate registrate   : {giorni}/{kill_window}")

    return "\n".join(lines)


def pricing_from_manifest(manifest_path: Path | str) -> Pricing | None:
    """Il listino del pin, o `None` con il motivo taciuto: il rapporto non alza.

    Il rapporto del mattino è di sola lettura e non deve fallire perché il pin
    non c'è ancora — è la condizione normale del cantiere. Il manifest si
    legge senza pretendere il pin (`require_pin=False`): serve il listino, non
    l'autorizzazione a girare, e quella la pretende il runner.
    """
    try:
        manifest = load_pinned_manifest(manifest_path, require_pin=False)
    except ManifestError:
        return None
    pricing, _ = read_pricing(manifest)
    return pricing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH))
    parser.add_argument("--ops-ledger", default=str(DEFAULT_OPS_PATH))
    parser.add_argument("--toolcalls-dir", default=str(ToolServerConfig().toolcall_log_dir))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    args = parser.parse_args(argv)

    trader_ledger = TraderLedger(args.ledger)
    ops_ledger = OpsLedger(args.ops_ledger)
    report = generate_report(
        trader_ledger=trader_ledger,
        ops_ledger=ops_ledger,
        toolcalls_dir=Path(args.toolcalls_dir),
        pricing=pricing_from_manifest(args.manifest),
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
