"""Smoke test con API reale — opzionale, dietro flag, mai nella suite normale.

Si attiva SOLO con `TRADERLAB_ALLOW_LIVE_API=1` e una `ANTHROPIC_API_KEY` in
ambiente. Consuma budget vero. Serve a verificare una cosa sola: che il
protocollo (razionale libero PRIMA, `submit_decision` DOPO) regga con il
modello reale.

**Il modello viene dal PIN, mai da un default di modulo** (decisione owner del
2026-08-20, rito PIN-BIS). Il percorso del Freeze manifest della stagione da
pinnare si passa in `TRADERLAB_SMOKE_MANIFEST`, e da lì escono model string,
`max_tokens`, `thinking_declared` e politica di caching: lo smoke prova la
configurazione che la stagione userà davvero, non una sua ricostruzione.

Perché non un default: fino al 20/08/2026 questo file chiamava
`build_freeze_manifest(ASOF)`, il cui default `DEFAULT_MODEL_STRING` era
— ed è tuttora — `claude-fable-5`. Il pin **TL-007** aveva però portato il
Trader su `claude-opus-5` il 18/08, e una costante di modulo non ha modo di
saperlo: eseguito alla lettera, lo smoke di pre-stagione avrebbe provato il
protocollo sul modello sbagliato, spendendo su un modello non pinnato e non
dimostrando nulla sul modello vero. È lo stesso difetto che TL-010 ha corretto
per il listino, in un'altra sede.

    TRADERLAB_ALLOW_LIVE_API=1 \
    TRADERLAB_SMOKE_MANIFEST=manifests/trader_v1_run2_freeze_manifest.json \
    uv run pytest tests/test_live_smoke.py -v -s
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from arena.config import ArenaConfig, current_git_sha
from contracts.freeze import FreezeManifest
from arena.llm_client import AnthropicTraderClient, CallBudget
from arena.runner import DailyRunner
from ledger.trader_ledger import TraderLedger
from toolserver.store import SnapshotStore
from toolserver.toollog import ToolCallLog
from tests.factories import make_snapshot

#: Variabile d'ambiente che porta il percorso del Freeze manifest della
#: stagione da pinnare. Non ha un default: un default è precisamente ciò che
#: questo file ha smesso di usare.
MANIFEST_ENV = "TRADERLAB_SMOKE_MANIFEST"


def _manifest_dal_pin() -> FreezeManifest:
    """Il manifest della stagione, letto da disco. Nessuna ricostruzione.

    Si legge il blocco `freeze_manifest` e lo si valida: non si passa da
    `load_pinned_manifest`, che pretende un `pin_commit` vero e un `freeze_id`
    coincidente. Lo smoke gira **prima** che il pin esista — è una delle sue
    precondizioni — quindi quelle due guardie qui rifiuterebbero a ragione.
    Quello che allo smoke serve è la **configurazione di chiamata**: model
    string, `max_tokens`, `thinking_declared`, caching. Quella c'è già.
    """
    percorso = os.environ.get(MANIFEST_ENV)
    if not percorso:
        pytest.fail(
            f"{MANIFEST_ENV} non impostata. Lo smoke prende il modello dal "
            f"pin, mai da un default di modulo: senza il percorso del Freeze "
            f"manifest della stagione non c'è un modello da provare. Vedi "
            f"docs/OPERATIONS.md, «Smoke live di pre-stagione»."
        )
        # `pytest.fail` non torna mai. La riga esiste perche' il tipo di
        # `percorso` si restringa a `str` anche per un lettore statico che non
        # abbia gli stub di pytest, invece di lasciare un `str | None` a Path.
        raise AssertionError("pytest.fail non ha interrotto il test")
    documento = json.loads(Path(percorso).read_text(encoding="utf-8"))
    return FreezeManifest.model_validate(documento["freeze_manifest"])

pytestmark = pytest.mark.skipif(
    os.environ.get("TRADERLAB_ALLOW_LIVE_API") != "1"
    or not os.environ.get("ANTHROPIC_API_KEY"),
    reason="smoke con API reale: richiede TRADERLAB_ALLOW_LIVE_API=1 e ANTHROPIC_API_KEY",
)


def test_smoke_una_replica_una_decisione_con_api_reale(tmp_path):
    store = SnapshotStore(tmp_path / "snapshots")
    snapshot = make_snapshot()
    store.save(snapshot)

    manifest = _manifest_dal_pin()
    print(f"\nmodello sotto smoke (dal pin): {manifest.model_string}")
    print(f"max_tokens (dal pin)         : {manifest.max_tokens}")
    print(f"thinking_declared (dal pin)  : {manifest.thinking_declared.value}")
    # max_calls=16: osservato nel rito del 2026-08-13 che un giro reale
    # (BTC + ETH, con retry per overloaded_error) consuma 8 chiamate
    # llm_complete da solo; 16 lascia margine a un secondo verbale malformato
    # senza esaurire il budget per un difetto del solo harness di test.
    budget = CallBudget(max_calls=16)

    runner = DailyRunner(
        store=store,
        ledger=TraderLedger(tmp_path / "ledger" / "smoke.jsonl"),
        tool_log=ToolCallLog(tmp_path / "toolcalls", run_id="smoke"),
        client_factory=lambda rid: AnthropicTraderClient(manifest, budget=budget),
        # Una sola replica e un solo giro: lo smoke non è una stagione.
        config=ArenaConfig(replica_ids=("smoke",), malformed_retries=1),
        # Sha reale del repo al momento del rito: il contesto del verbale
        # è il commit corrente, non un placeholder letterale non-esadecimale.
        context_git_sha=current_git_sha(),
    )
    result = runner.run_day(snapshot.snapshot_id, run_id="smoke")

    print(f"\nCallBudget: {budget.used}/{budget.max_calls} chiamate usate")

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
