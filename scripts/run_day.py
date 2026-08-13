"""Esegue una giornata di decisioni sulle 3 repliche.

Di default usa il **MockLLM**: gira senza rete e senza API key. Con `--live`
usa il modello pinnato nel Freeze manifest e consuma budget vero.

    uv run python scripts/run_day.py --snapshot-id <sha256>
    uv run python scripts/run_day.py --snapshot-id <sha256> --live
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.config import ArenaConfig, build_freeze_manifest, current_git_sha
from arena.llm_client import (
    AnthropicTraderClient,
    CallBudget,
    LLMError,
    MockLLM,
    RETRYABLE_PROCESS_EXIT_CODE,
)
from arena.runner import DailyRunner
from ledger.trader_ledger import TraderLedger
from toolserver.config import ToolServerConfig, live_api_allowed
from toolserver.store import SnapshotStore
from toolserver.toollog import ToolCallLog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--ledger", default="data/ledger/season0.jsonl")
    parser.add_argument("--live", action="store_true", help="usa l'API reale")
    args = parser.parse_args()

    run_id = args.run_id or datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths = ToolServerConfig()
    store = SnapshotStore(paths.snapshot_dir)
    tool_log = ToolCallLog(paths.toolcall_log_dir, run_id=run_id)
    ledger = TraderLedger(args.ledger)

    if args.live:
        if not live_api_allowed():
            print(
                "ERRORE: --live richiede TRADERLAB_ALLOW_LIVE_API=1.",
                file=sys.stderr,
            )
            return 2
        manifest = build_freeze_manifest(datetime.now(tz=timezone.utc))
        budget = CallBudget(max_calls=ArenaConfig().max_llm_calls_per_day)
        print(f"modello pinnato : {manifest.model_string}")
        print(f"sampling        : {manifest.sampling_policy.value} (D4)")
        print(f"freeze_id       : {manifest.freeze_id}")

        def factory(replica_id: str):
            return AnthropicTraderClient(manifest, budget=budget)
    else:
        print("modello         : MockLLM deterministico (nessuna API)")

        def factory(replica_id: str):
            return MockLLM()

    runner = DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=factory,
        context_git_sha=current_git_sha(),
    )
    try:
        result = runner.run_day(args.snapshot_id, run_id=run_id)
    except LLMError as exc:
        # Un rifiuto resta un rifiuto e un 400 resta un 400: qui distinguiamo
        # solo se vale la pena che il rito ritenti l'intero passo (pazienza
        # lunga) da un fallimento definitivo. Nessun fallback di modello, mai
        # (CLAUDE.md §10): questo blocco classifica, non nasconde, l'errore.
        print(f"ERRORE: chiamata al modello fallita — {exc}", file=sys.stderr)
        print(
            f"tentativi       : {exc.attempts}  errori: {list(exc.attempt_errors)}  "
            f"durata: {exc.duration_seconds:.1f}s",
            file=sys.stderr,
        )
        if exc.retryable:
            print(
                "classificazione: errore transitorio (rete/capacita'), "
                "ritentabile a livello di rito",
                file=sys.stderr,
            )
            return RETRYABLE_PROCESS_EXIT_CODE
        print("classificazione: errore non ritentabile", file=sys.stderr)
        return 1

    print(f"\nrun_id          : {result.run_id}")
    print(f"asof_utc        : {result.asof_utc.isoformat()}")
    print(f"decisioni       : {len(result.decisions)}")
    print(f"malformati      : {result.malformed_count}")
    if result.dispersion:
        d = result.dispersion
        print(
            f"dispersione     : azioni {d.action_disagreement:.4f}, "
            f"confidence {d.confidence_dispersion:.4f}"
        )
    print(f"catena ledger   : {'ok' if ledger.verify().ok else 'ROTTA'}")
    print(f"tool call log   : {tool_log.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
