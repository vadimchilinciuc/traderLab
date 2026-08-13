"""Smoke test con API reale — opzionale, dietro flag, mai nella suite normale.

Si attiva SOLO con `TRADERLAB_ALLOW_LIVE_API=1` e una `ANTHROPIC_API_KEY` in
ambiente. Consuma budget vero. Serve a verificare una cosa sola: che il
protocollo (razionale libero PRIMA, `submit_decision` DOPO) regga con il
modello reale.

    TRADERLAB_ALLOW_LIVE_API=1 uv run pytest tests/test_live_smoke.py -v
"""

from __future__ import annotations

import os

import pytest

from arena.config import ArenaConfig, build_freeze_manifest
from arena.llm_client import AnthropicTraderClient, CallBudget
from arena.runner import DailyRunner
from ledger.trader_ledger import TraderLedger
from toolserver.store import SnapshotStore
from toolserver.toollog import ToolCallLog
from tests.factories import ASOF, make_snapshot

pytestmark = pytest.mark.skipif(
    os.environ.get("TRADERLAB_ALLOW_LIVE_API") != "1"
    or not os.environ.get("ANTHROPIC_API_KEY"),
    reason="smoke con API reale: richiede TRADERLAB_ALLOW_LIVE_API=1 e ANTHROPIC_API_KEY",
)


def test_smoke_una_replica_una_decisione_con_api_reale(tmp_path):
    store = SnapshotStore(tmp_path / "snapshots")
    snapshot = make_snapshot()
    store.save(snapshot)

    manifest = build_freeze_manifest(ASOF)
    budget = CallBudget(max_calls=8)

    runner = DailyRunner(
        store=store,
        ledger=TraderLedger(tmp_path / "ledger" / "smoke.jsonl"),
        tool_log=ToolCallLog(tmp_path / "toolcalls", run_id="smoke"),
        client_factory=lambda rid: AnthropicTraderClient(manifest, budget=budget),
        # Una sola replica e un solo giro: lo smoke non è una stagione.
        config=ArenaConfig(replica_ids=("smoke",), malformed_retries=1),
        context_git_sha="smoke00",
    )
    result = runner.run_day(snapshot.snapshot_id, run_id="smoke")

    assert result.outcomes
    for outcome in result.outcomes:
        print(f"\n{outcome.asset}: {outcome.verdict.outcome.value}")
        if outcome.decision:
            print(f"  action     : {outcome.decision.action.value}")
            print(f"  confidence : {outcome.decision.confidence}")
            print(f"  features   : {[f.name for f in outcome.decision.features_used]}")
        else:
            print(f"  malformed  : {outcome.malformed_reason}")

    # Il protocollo deve reggere: almeno un verbale conforme.
    assert any(o.decision is not None for o in result.outcomes), (
        "nessun verbale conforme: il protocollo razionale-prima non ha retto"
    )
