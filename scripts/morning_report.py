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

from arena.daily_ritual import DEFAULT_LEDGER_PATH, DEFAULT_OPS_PATH
from ledger.eprocess import KillCriterionConfig
from ledger.ops_ledger import OpsEvent, OpsLedger, recorded_days
from ledger.spend import (
    FABLE_CACHE_READ_USD_PER_MTOK,
    FABLE_CACHE_WRITE_USD_PER_MTOK,
    FABLE_INPUT_USD_PER_MTOK,
    FABLE_OUTPUT_USD_PER_MTOK,
    day_token_totals,
    estimate_cost_usd,
)
from ledger.trader_ledger import TraderLedger
from toolserver.config import ToolServerConfig

# Il listino e la somma dei token vivono in `ledger/spend.py`: li leggono anche
# le guardie economiche di stagione (D5), e due copie della stessa tariffa
# divergono il giorno in cui una viene aggiornata e l'altra no. Qui si
# re-importano per non rompere chi li cita da questo modulo.
__all__ = [
    "FABLE_CACHE_READ_USD_PER_MTOK",
    "FABLE_CACHE_WRITE_USD_PER_MTOK",
    "FABLE_INPUT_USD_PER_MTOK",
    "FABLE_OUTPUT_USD_PER_MTOK",
    "classify_outcome",
    "day_entries",
    "day_token_totals",
    "estimate_cost_usd",
    "format_asset_lines",
    "generate_report",
    "last_touched_day",
    "latest_event_detail",
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
    kill_window: int = KillCriterionConfig().window,
) -> str:
    """Costruisce il testo del rapporto. Non stampa, non scrive: solo testo."""
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
    lines.append(
        "costo stimato USD     : "
        f"${estimate_cost_usd(input_t, output_t, cache_read_t, cache_creation_t):.4f}"
    )

    verify = trader_ledger.verify()
    lines.append(
        f"catena ledger (verify): {'ok' if verify.ok else f'ROTTA — {verify.detail}'}"
    )

    giorni = len(recorded_days(trader_ledger))
    lines.append(f"giornate registrate   : {giorni}/{kill_window}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH))
    parser.add_argument("--ops-ledger", default=str(DEFAULT_OPS_PATH))
    parser.add_argument("--toolcalls-dir", default=str(ToolServerConfig().toolcall_log_dir))
    args = parser.parse_args(argv)

    trader_ledger = TraderLedger(args.ledger)
    ops_ledger = OpsLedger(args.ops_ledger)
    report = generate_report(
        trader_ledger=trader_ledger,
        ops_ledger=ops_ledger,
        toolcalls_dir=Path(args.toolcalls_dir),
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
