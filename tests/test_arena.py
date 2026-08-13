"""Blocco 5 — orchestratore: 3 repliche mock, input identici, ledger popolato."""

from __future__ import annotations

import pytest

from contracts.decision import Action
from contracts.risk import RiskOutcome, RiskRule
from arena.config import (
    DEFAULT_MODEL_STRING,
    DEFAULT_REPLICA_IDS,
    ArenaConfig,
    all_tool_schemas,
    all_tool_schemas_sha,
    build_freeze_manifest,
    load_context,
)
from arena.llm_client import (
    AnthropicTraderClient,
    BudgetExceeded,
    CallBudget,
    LLMError,
    MockLLM,
    _is_retryable,
)
from arena.risk_officer import RiskConfig
from arena.runner import DailyRunner
from arena.shadow_fill import compute_shadow_fill
from arena.verbale import MalformedReason
from contracts.freeze import SamplingPolicy
from ledger.trader_ledger import TraderLedger
from toolserver.store import SnapshotStore
from toolserver.toollog import ToolCallLog
from tests.factories import ASOF, make_snapshot


@pytest.fixture
def wired(tmp_path):
    """Pipeline completa su disco temporaneo, senza rete e senza API key."""
    store = SnapshotStore(tmp_path / "snapshots")
    snapshot = make_snapshot()
    store.save(snapshot)
    ledger = TraderLedger(tmp_path / "ledger" / "s0.jsonl")
    tool_log = ToolCallLog(tmp_path / "toolcalls", run_id="run-1")
    return store, snapshot, ledger, tool_log


def _runner(wired, *, behaviour="ok", config=None):
    store, _, ledger, tool_log = wired
    return DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=lambda replica_id: MockLLM(behaviour=behaviour),
        config=config or ArenaConfig(),
        context_git_sha="abcdef1",
    )


# --------------------------------------------------------------------------
# Smoke end-to-end con MockLLM: nessuna API
# --------------------------------------------------------------------------


def test_tre_repliche_mock_producono_verbali_validi(wired):
    _, snapshot, ledger, _ = wired
    result = _runner(wired).run_day(snapshot.snapshot_id, run_id="run-1")

    assert len(result.outcomes) == len(DEFAULT_REPLICA_IDS) * len(snapshot.universe)
    assert result.malformed_count == 0
    assert len(result.decisions) == len(result.outcomes)
    for decision in result.decisions:
        assert decision.snapshot_id == snapshot.snapshot_id
        assert decision.model_version == "mock-llm-0"
        assert len(decision.rationale_text) >= 120


def test_il_ledger_viene_popolato_e_la_catena_verifica(wired):
    _, snapshot, ledger, _ = wired
    _runner(wired).run_day(snapshot.snapshot_id, run_id="run-1")
    assert len(ledger) == len(DEFAULT_REPLICA_IDS) * len(snapshot.universe)
    assert ledger.verify().ok
    for entry in ledger.read_all():
        assert entry["snapshot_id"] == snapshot.snapshot_id
        assert entry["verdict"] is not None


def test_write_once_per_giorno_replica_asset(wired):
    _, snapshot, ledger, _ = wired
    _runner(wired).run_day(snapshot.snapshot_id, run_id="run-1")
    chiavi = [tuple(e["key"].values()) for e in ledger.read_all()]
    assert len(chiavi) == len(set(chiavi))


def test_telemetria_popolata(wired):
    _, snapshot, _, _ = wired
    result = _runner(wired).run_day(snapshot.snapshot_id, run_id="run-1")
    metrics = result.telemetry.all_metrics()
    assert set(metrics) == set(DEFAULT_REPLICA_IDS)
    for m in metrics.values():
        assert m.decisions_total == len(snapshot.universe)
        assert m.malformed_rate == 0.0
        assert m.mean_confidence is not None


def test_dispersione_calcolata_sulle_tre_repliche(wired):
    _, snapshot, _, _ = wired
    result = _runner(wired).run_day(snapshot.snapshot_id, run_id="run-1")
    assert result.dispersion is not None
    assert result.dispersion.replicas == 3
    assert result.dispersion.assets_compared == len(snapshot.universe)
    # Repliche identiche + MockLLM deterministico => dispersione nulla.
    assert result.dispersion.action_disagreement == pytest.approx(0.0)
    assert result.dispersion.confidence_dispersion == pytest.approx(0.0)


def test_i_tool_call_sono_loggati_per_replica(wired):
    _, snapshot, _, tool_log = wired
    _runner(wired).run_day(snapshot.snapshot_id, run_id="run-1")
    entries = tool_log.read_all()
    assert entries
    assert {e["replica_id"] for e in entries} == set(DEFAULT_REPLICA_IDS)
    assert all(e["tool"] == "get_asset_dossier" for e in entries)


# --------------------------------------------------------------------------
# D1: input byte-identici tra repliche
# --------------------------------------------------------------------------


def test_input_byte_identici_tra_repliche(wired):
    _, snapshot, _, _ = wired
    result = _runner(wired).run_day(snapshot.snapshot_id, run_id="run-1")
    for asset in snapshot.universe:
        impronte = {
            result.request_fingerprints[rid][asset] for rid in DEFAULT_REPLICA_IDS
        }
        assert len(impronte) == 1, f"input divergenti su {asset}"


def test_il_replica_id_non_entra_mai_nel_prompt(wired):
    _, snapshot, _, _ = wired
    context = load_context()
    testo = context.rendered_system.lower()
    for rid in DEFAULT_REPLICA_IDS:
        assert rid not in testo


def test_il_prompt_non_menziona_gara_repliche_o_valutazione():
    """CLAUDE.md §6: l'agente è inconsapevole della gara e delle repliche.

    Nota: dire al Trader che *non ha* accesso a notizie è consentito e voluto —
    dichiarare l'assenza di un feed non è un feed (§4). Il divieto riguarda
    l'iniezione di testo di terzi, non la descrizione dei propri dati.
    """
    testo = load_context().rendered_system.lower()
    for parola in (
        "replica",
        "repliche",
        "gara",
        "competiz",
        "arena",
        "confronto",
        "punteggio",
        "valutat",
        "meccanic",
        "benchmark",
        "backtest",
        "track record",
    ):
        assert parola not in testo, f"il prompt contiene '{parola}'"


def test_le_note_editoriali_non_finiscono_nel_prompt():
    """I blockquote dei context file sono per chi mantiene il Lab, non per il Trader."""
    context = load_context()
    assert "Bozza v0" in context.system_prompt
    assert "Bozza v0" not in context.rendered_system
    assert ">" not in context.rendered_system.split("\n")[0]


def test_le_repliche_sono_isolate_tra_loro(wired):
    """Ogni replica riceve un client nuovo: nessun contesto condiviso."""
    _, snapshot, ledger, tool_log = wired
    store = wired[0]
    creati = []

    def factory(replica_id):
        client = MockLLM()
        creati.append((replica_id, client))
        return client

    runner = DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=factory,
        context_git_sha="abcdef1",
    )
    runner.run_day(snapshot.snapshot_id, run_id="run-1")
    assert [rid for rid, _ in creati] == list(DEFAULT_REPLICA_IDS)
    assert len({id(c) for _, c in creati}) == 3


# --------------------------------------------------------------------------
# Verbale malformato: retry singolo dichiarato, poi NO TRADE
# --------------------------------------------------------------------------


def test_verbale_malformato_produce_rejected_e_nessuna_decisione(wired):
    _, snapshot, ledger, _ = wired
    result = _runner(wired, behaviour="malformed").run_day(
        snapshot.snapshot_id, run_id="run-1"
    )
    assert result.malformed_count == len(result.outcomes)
    assert result.decisions == []
    for outcome in result.outcomes:
        assert outcome.verdict.outcome is RiskOutcome.REJECTED
        assert outcome.verdict.rule is RiskRule.MALFORMED_VERBALE
        assert outcome.malformed_reason is MalformedReason.NO_RATIONALE_BEFORE
        # Un solo retry dichiarato: due tentativi in tutto.
        assert outcome.attempts == 2
    assert ledger.verify().ok
    assert all(e["decision"] is None for e in ledger.read_all())


def test_retry_disattivabile(wired):
    _, snapshot, _, _ = wired
    config = ArenaConfig(malformed_retries=0)
    result = _runner(wired, behaviour="malformed", config=config).run_day(
        snapshot.snapshot_id, run_id="run-1"
    )
    assert all(o.attempts == 1 for o in result.outcomes)


def test_telemetria_conta_i_malformati(wired):
    _, snapshot, _, _ = wired
    result = _runner(wired, behaviour="malformed").run_day(
        snapshot.snapshot_id, run_id="run-1"
    )
    for m in result.telemetry.all_metrics().values():
        assert m.malformed_rate == pytest.approx(1.0)
        assert m.blocked_by_rule["malformed_verbale"] == len(snapshot.universe)


# --------------------------------------------------------------------------
# Risk Officer nella pipeline
# --------------------------------------------------------------------------


def test_la_size_viene_normalizzata_al_valore_fisso(wired):
    _, snapshot, _, _ = wired
    config = ArenaConfig(risk=RiskConfig(fixed_size_fraction=0.02))
    result = _runner(wired, config=config).run_day(snapshot.snapshot_id, run_id="run-1")
    direzionali = [o for o in result.outcomes if o.decision.is_directional]
    assert direzionali
    for outcome in direzionali:
        assert outcome.verdict.size_fraction_out == 0.02
        assert outcome.verdict.rule is RiskRule.FIXED_SIZE_SEASON_0


def test_flat_non_genera_fill(wired):
    _, snapshot, _, _ = wired
    result = _runner(wired, behaviour="flat").run_day(
        snapshot.snapshot_id, run_id="run-1"
    )
    assert all(o.decision.action is Action.FLAT for o in result.outcomes)
    assert all(o.fill is None for o in result.outcomes)


def test_i_fill_usano_i_costi_reali(wired):
    _, snapshot, _, _ = wired
    result = _runner(wired).run_day(snapshot.snapshot_id, run_id="run-1")
    fills = [o.fill for o in result.outcomes if o.fill is not None]
    assert fills
    for fill in fills:
        assert fill.fee_bps == 4.5
        assert fill.slippage_bps == pytest.approx(1.0)
        assert fill.fill_price > fill.reference_price


# --------------------------------------------------------------------------
# ShadowFill
# --------------------------------------------------------------------------


def test_shadow_fill_long_e_short_peggiorano_il_prezzo():
    snapshot = make_snapshot()
    asset = snapshot.assets[0]
    long = compute_shadow_fill(
        asset=asset,
        action=Action.LONG,
        size_fraction=0.05,
        timestamp_utc=ASOF,
        snapshot_id=snapshot.snapshot_id,
        replica_id="r1",
    )
    short = compute_shadow_fill(
        asset=asset,
        action=Action.SHORT,
        size_fraction=0.05,
        timestamp_utc=ASOF,
        snapshot_id=snapshot.snapshot_id,
        replica_id="r1",
    )
    assert long.fill_price > asset.mark_price
    assert short.fill_price < asset.mark_price
    assert long.cost_fraction == pytest.approx(0.05 * 5.5 / 10_000)


def test_shadow_fill_none_su_flat():
    snapshot = make_snapshot()
    assert (
        compute_shadow_fill(
            asset=snapshot.assets[0],
            action=Action.FLAT,
            size_fraction=0.0,
            timestamp_utc=ASOF,
            snapshot_id=snapshot.snapshot_id,
            replica_id="r1",
        )
        is None
    )


# --------------------------------------------------------------------------
# Client: budget, D4, retry
# --------------------------------------------------------------------------


def test_budget_guard_blocca_oltre_il_tetto():
    budget = CallBudget(max_calls=2)
    budget.consume()
    budget.consume()
    with pytest.raises(BudgetExceeded, match="tetto"):
        budget.consume()


def test_il_mock_consuma_budget(wired):
    _, snapshot, ledger, tool_log = wired
    store = wired[0]
    client = MockLLM(budget=CallBudget(max_calls=1000))
    runner = DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=lambda rid: client,
        context_git_sha="abcdef1",
    )
    runner.run_day(snapshot.snapshot_id, run_id="run-1")
    # 2 turni per decisione, 3 repliche x N asset.
    assert client.budget.used == 2 * 3 * len(snapshot.universe)


def test_d4_il_client_reale_non_invia_parametri_di_sampling():
    """Il payload non contiene temperature, top_p, top_k."""
    catturato = {}

    class FakeMessages:
        def create(self, **kwargs):
            catturato.update(kwargs)

            class R:
                content = []
                stop_reason = "end_turn"
                model = DEFAULT_MODEL_STRING

            return R()

    class FakeAnthropic:
        messages = FakeMessages()

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(manifest, client=FakeAnthropic())
    client.complete(system="s", messages=[{"role": "user", "content": "x"}], tools=[])

    assert "temperature" not in catturato
    assert "top_p" not in catturato
    assert "top_k" not in catturato
    assert catturato["model"] == DEFAULT_MODEL_STRING
    assert catturato["max_tokens"] == manifest.max_tokens


def test_d4_il_client_rifiuta_un_manifest_con_sampling_esplicito():
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    esplicito = manifest.model_copy(
        update={"sampling_policy": SamplingPolicy.EXPLICIT, "temperature": 0.7}
    )
    with pytest.raises(LLMError, match="api_default_omitted"):
        AnthropicTraderClient(esplicito, client=object())


def test_il_client_reale_rispetta_il_budget():
    class FakeMessages:
        def create(self, **kwargs):
            class R:
                content = []
                stop_reason = "end_turn"
                model = DEFAULT_MODEL_STRING

            return R()

    class FakeAnthropic:
        messages = FakeMessages()

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=FakeAnthropic(), budget=CallBudget(max_calls=1)
    )
    client.complete(system="s", messages=[], tools=[])
    with pytest.raises(BudgetExceeded):
        client.complete(system="s", messages=[], tools=[])


def test_retry_con_backoff_su_errore_ritentabile():
    tentativi = {"n": 0}
    dormite = []

    class Boom(Exception):
        status_code = 529

    class FakeMessages:
        def create(self, **kwargs):
            tentativi["n"] += 1
            if tentativi["n"] < 3:
                raise Boom("overloaded")

            class R:
                content = []
                stop_reason = "end_turn"
                model = DEFAULT_MODEL_STRING

            return R()

    class FakeAnthropic:
        messages = FakeMessages()

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=FakeAnthropic(), sleep=dormite.append
    )
    client.complete(system="s", messages=[], tools=[])
    assert tentativi["n"] == 3
    assert dormite == [1.0, 2.0]


def test_un_400_non_viene_ritentato():
    tentativi = {"n": 0}

    class Bad(Exception):
        status_code = 400

    class FakeMessages:
        def create(self, **kwargs):
            tentativi["n"] += 1
            raise Bad("invalid_request_error")

    class FakeAnthropic:
        messages = FakeMessages()

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(manifest, client=FakeAnthropic(), sleep=lambda _: None)
    with pytest.raises(LLMError):
        client.complete(system="s", messages=[], tools=[])
    assert tentativi["n"] == 1


def test_classificazione_degli_errori_ritentabili():
    class WithStatus(Exception):
        status_code = 503

    class RateLimitError(Exception):
        pass

    assert _is_retryable(WithStatus())
    assert _is_retryable(RateLimitError())
    assert not _is_retryable(ValueError("boom"))


# --------------------------------------------------------------------------
# Freeze manifest costruito dal contenuto reale
# --------------------------------------------------------------------------


def test_manifest_riflette_i_file_congelati():
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    context = load_context()
    assert manifest.model_string == DEFAULT_MODEL_STRING
    assert manifest.sampling_policy is SamplingPolicy.API_DEFAULT_OMITTED
    assert manifest.temperature is None
    assert manifest.system_prompt_sha == context.system_prompt_sha
    assert manifest.persona_sha == context.persona_sha
    assert manifest.tool_schemas_sha == all_tool_schemas_sha()
    assert manifest.ots_pending is True


def test_gli_schemi_inviati_includono_lettura_e_registrazione():
    nomi = [s["name"] for s in all_tool_schemas()]
    assert "submit_decision" in nomi
    assert "get_asset_dossier" in nomi
    assert len(nomi) == len(set(nomi))


def test_cambiare_il_prompt_cambia_il_freeze_id(tmp_path):
    base = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    modificato = base.model_copy(update={"system_prompt_sha": "f" * 64})
    assert base.freeze_id != modificato.freeze_id


def test_config_arena_rifiuta_repliche_duplicate():
    with pytest.raises(ValueError, match="duplicati"):
        ArenaConfig(replica_ids=("r1", "r1"))
