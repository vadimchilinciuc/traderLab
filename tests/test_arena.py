"""Blocco 5 — orchestratore: 3 repliche mock, input identici, ledger popolato."""

from __future__ import annotations

import json

import pytest

from contracts.decision import Action
from contracts.hashing import sha256_of
from contracts.risk import RiskOutcome, RiskRule

from arena.config import (
    DEFAULT_MAX_TOKENS,
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
    LLMResponse,
    LLMUsage,
    MockLLM,
    _is_retryable,
)
from arena.risk_officer import RiskConfig
from arena.runner import DailyRunner
from arena.shadow_fill import compute_shadow_fill
from arena.verbale import MalformedReason
from contracts.freeze import SamplingPolicy, ThinkingPolicy
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


class _FakeUsage:
    """Imita `anthropic.types.Usage`: solo i campi che il client legge."""

    def __init__(
        self,
        input_tokens,
        output_tokens,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    ):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = cache_creation_input_tokens
        self.cache_read_input_tokens = cache_read_input_tokens


class _FakeResponse:
    """Risposta minima compatibile con il normalizzatore del client."""

    def __init__(
        self, stop_reason="end_turn", content=None, stop_details=None, usage=None
    ):
        self.content = content or []
        self.stop_reason = stop_reason
        self.model = DEFAULT_MODEL_STRING
        self.stop_details = stop_details
        self.usage = usage


class _FakeStream:
    """Context manager che imita `client.messages.stream(...)`."""

    def __init__(self, response, recorder=None, kwargs=None):
        self._response = response
        self._recorder = recorder
        self._kwargs = kwargs or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        if self._recorder is not None:
            self._recorder.update(self._kwargs)
        return self._response


def _fake_streaming_client(response=None, recorder=None):
    """Fake che espone solo `messages.stream`: il client streamma di default."""
    resp = response or _FakeResponse()

    class FakeMessages:
        def stream(self, **kwargs):
            return _FakeStream(resp, recorder, kwargs)

    class FakeAnthropic:
        messages = FakeMessages()

    return FakeAnthropic()


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
    assert {e["tool"] for e in entries} == {"get_asset_dossier", "llm_complete"}


def test_la_chiamata_al_modello_e_loggata_con_la_sua_telemetria(wired):
    """CLAUDE.md §9: la chiamata al modello è un dato, non solo la decisione.

    Con il MockLLM ogni chiamata riesce al primo tentativo, quindi la
    telemetria è quella "vuota" di default: un tentativo, nessun errore,
    durata zero. La rete reale la popola davvero (vedi arena/llm_client.py).
    """
    _, snapshot, _, tool_log = wired
    _runner(wired).run_day(snapshot.snapshot_id, run_id="run-1")
    llm_entries = [e for e in tool_log.read_all() if e["tool"] == "llm_complete"]
    # 2 turni per decisione (dossier + submit), 3 repliche x N asset.
    assert len(llm_entries) == 2 * 3 * len(snapshot.universe)
    for entry in llm_entries:
        assert entry["ok"] is True
        assert entry["meta"]["attempts"] == 1
        assert entry["meta"]["attempt_errors"] == []
        assert entry["meta"]["duration_seconds"] >= 0.0
        # PASSO 0: il MockLLM non ha un usage reale. Null esplicito, mai zero
        # — zero direbbe "zero token consumati", non "non registrato".
        assert entry["meta"]["input_tokens"] is None
        assert entry["meta"]["output_tokens"] is None


def test_usage_reale_finisce_nel_tool_log_accanto_ai_tentativi(wired):
    """PASSO 0: il client reale porta un usage — deve arrivare fino al log.

    Un `LLMClient` finto (non il MockLLM, che non ha un usage reale) gioca il
    ruolo del client Anthropic per verificare che `DailyRunner` propaghi
    `response.usage` nello stesso punto in cui propaga `attempts`.
    """
    store, snapshot, ledger, tool_log = wired

    class _UsageClient:
        model_version = DEFAULT_MODEL_STRING

        def complete(self, *, system, messages, tools):
            asset = _asset_from(messages)
            dossier = _dossier_from(messages)
            if dossier is None:
                return LLMResponse(
                    content=[
                        {
                            "type": "tool_use",
                            "name": "get_asset_dossier",
                            "input": {"symbol": asset},
                            "id": f"dossier_{asset}",
                        }
                    ],
                    stop_reason="tool_use",
                    model=DEFAULT_MODEL_STRING,
                    usage=LLMUsage(input_tokens=120, output_tokens=15),
                )
            payload = {
                "asset": asset,
                "action": "flat",
                "size_fraction": 0.0,
                "horizon": "1-3d",
                "expected_holding": "1-3d",
                "confidence": 0.5,
                "features_used": [{"name": "price_vs_sma_20", "value": 0.0}],
                "invalidation_conditions": ["n/a"],
                "risk_checks": [{"name": "costi_considerati", "passed": True, "note": ""}],
            }
            return LLMResponse(
                content=[
                    {"type": "text", "text": "Razionale minimo."},
                    {
                        "type": "tool_use",
                        "name": "submit_decision",
                        "input": payload,
                        "id": f"submit_{asset}",
                    },
                ],
                stop_reason="tool_use",
                model=DEFAULT_MODEL_STRING,
                usage=LLMUsage(
                    input_tokens=340,
                    output_tokens=58,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=300,
                ),
            )

    runner = DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=lambda replica_id: _UsageClient(),
        config=ArenaConfig(replica_ids=("r1",)),
        context_git_sha="abcdef1",
    )
    runner.run_day(snapshot.snapshot_id, run_id="run-1")

    llm_entries = [e for e in tool_log.read_all() if e["tool"] == "llm_complete"]
    assert llm_entries
    dossier_calls = [e for e in llm_entries if e["meta"]["input_tokens"] == 120]
    submit_calls = [e for e in llm_entries if e["meta"]["input_tokens"] == 340]
    assert dossier_calls and all(e["meta"]["output_tokens"] == 15 for e in dossier_calls)
    assert submit_calls and all(e["meta"]["output_tokens"] == 58 for e in submit_calls)
    # PASSO 0: nessun usage di cache dichiarato per il turno dossier -> null,
    # non zero.
    assert all(e["meta"]["cache_creation_input_tokens"] is None for e in dossier_calls)
    assert all(e["meta"]["cache_read_input_tokens"] is None for e in dossier_calls)
    # RITO CACHING: il turno submit dichiara una lettura di cache -> arriva
    # nel tool log accanto agli altri token.
    assert all(e["meta"]["cache_creation_input_tokens"] == 0 for e in submit_calls)
    assert all(e["meta"]["cache_read_input_tokens"] == 300 for e in submit_calls)


def _asset_from(messages):
    for message in messages:
        content = message.get("content")
        if isinstance(content, str) and "ASSET:" in content:
            return content.split("ASSET:", 1)[1].split()[0].strip()
    raise AssertionError("asset non trovato nei messaggi")


def _dossier_from(messages):
    import json

    for message in reversed(messages):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            payload = block.get("content")
            if isinstance(payload, list):
                payload = "".join(p.get("text", "") for p in payload if isinstance(p, dict))
            if not isinstance(payload, str):
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "features" in parsed:
                return parsed
    return None


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
    assert "PROMOSSA" in context.system_prompt
    assert "PROMOSSA" not in context.rendered_system
    assert ">" not in context.rendered_system.split("\n")[0]


# --------------------------------------------------------------------------
# PASSO 1 (rito del pin): i file in uso ora sono la persona promossa. Gli
# stessi controlli che finora giravano solo sulle bozze (tests/test_drafts.py)
# devono valere anche qui: una bozza che li avesse violati non sarebbe mai
# dovuta arrivare a essere il file in uso.
# --------------------------------------------------------------------------


def test_il_file_in_uso_non_ha_un_mandato_di_risultato():
    testo = load_context().rendered_system.lower()
    for parola in (
        "profitt",
        "guadagn",
        "massimizz",
        "obiettivo di rendimento",
        "batti",
        "supera il",
        "il migliore",
        "devi vincere",
    ):
        assert parola not in testo, f"il prompt contiene un mandato di risultato ('{parola}')"


def test_il_file_in_uso_non_esercita_pressione_emotiva():
    testo = load_context().rendered_system.lower()
    for parola in (
        "non deludere",
        "mi raccomando",
        "sei l'unico",
        "dipende da te",
        "fai del tuo meglio",
        "urgente",
        "opportunità da non perdere",
    ):
        assert parola not in testo, f"il prompt esercita pressione ('{parola}')"


def test_il_file_in_uso_non_nomina_i_guardrail_a_valle():
    """Un trader che sa di essere corretto a valle chiede più di quanto serve."""
    testo = load_context().rendered_system.lower()
    for parola in ("risk officer", "clamp", "guardrail", "tool server"):
        assert parola not in testo, f"il prompt contiene '{parola}'"


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


def test_un_rifiuto_non_e_un_verbale_malformato(wired):
    """Il rifiuto del modello ha una categoria propria e non si ritenta."""
    store, snapshot, ledger, tool_log = wired

    class RifiutaSempre:
        model_version = "fable-fake"

        def __init__(self):
            self.calls = 0

        def complete(self, *, system, messages, tools):
            self.calls += 1
            return LLMResponse(
                content=[],
                stop_reason="refusal",
                model="claude-fable-5",
                refusal_category="cyber",
            )

    clients = {}

    def factory(replica_id):
        clients[replica_id] = RifiutaSempre()
        return clients[replica_id]

    result = DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=factory,
        context_git_sha="abcdef1",
    ).run_day(snapshot.snapshot_id, run_id="run-1")

    for outcome in result.outcomes:
        assert outcome.verdict.rule is RiskRule.MODEL_REFUSAL
        assert outcome.malformed_reason is MalformedReason.MODEL_REFUSAL
        assert outcome.decision is None
        # Un rifiuto non si ritenta: input identico, risposta identica.
        assert outcome.attempts == 1

    for m in result.telemetry.all_metrics().values():
        assert m.refusal_rate == pytest.approx(1.0)
        assert m.malformed_rate == pytest.approx(0.0)
        assert m.blocked_by_rule["model_refusal"] == len(snapshot.universe)

    # Una chiamata per asset, non due: il retry non è scattato.
    for client in clients.values():
        assert client.calls == len(snapshot.universe)
    assert ledger.verify().ok


def test_una_risposta_troncata_e_no_trade_categoria_propria(wired):
    """stop_reason='max_tokens' e' INVALIDO: NO TRADE, mai un verbale parziale.

    Guardia sul troncamento (rito tuning max_tokens): un tetto piu' basso
    riduce lo shedding nei picchi, ma puo' tagliare un turno insolitamente
    lungo. La categoria e' distinta sia da `malformed` sia da `refusal`.
    """
    store, snapshot, ledger, tool_log = wired

    class TronchaSempre:
        model_version = "fable-fake"

        def __init__(self):
            self.calls = 0

        def complete(self, *, system, messages, tools):
            self.calls += 1
            return LLMResponse(
                content=[{"type": "text", "text": "Il razionale si interrompe qui"}],
                stop_reason="max_tokens",
                model="claude-fable-5",
            )

    clients = {}

    def factory(replica_id):
        clients[replica_id] = TronchaSempre()
        return clients[replica_id]

    result = DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=factory,
        context_git_sha="abcdef1",
    ).run_day(snapshot.snapshot_id, run_id="run-1")

    for outcome in result.outcomes:
        assert outcome.verdict.rule is RiskRule.TRUNCATED_RESPONSE
        assert outcome.verdict.outcome is RiskOutcome.REJECTED
        assert outcome.malformed_reason is MalformedReason.TRUNCATED
        assert outcome.decision is None
        # Un solo retry dichiarato, come per un verbale malformato.
        assert outcome.attempts == 2

    for m in result.telemetry.all_metrics().values():
        assert m.truncated_rate == pytest.approx(1.0)
        assert m.refusal_rate == pytest.approx(0.0)
        assert m.malformed_rate == pytest.approx(0.0)
        assert m.blocked_by_rule["truncated_response"] == len(snapshot.universe)

    # Un retry dichiarato: due chiamate per asset, non una.
    for client in clients.values():
        assert client.calls == 2 * len(snapshot.universe)
    assert ledger.verify().ok


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


def test_d4_su_fable_il_client_non_invia_sampling_ne_thinking():
    """Il payload non contiene temperature, top_p, top_k, thinking, fallbacks.

    Su claude-fable-5 ognuna di queste omissioni è obbligatoria, non stilistica:
    i parametri di sampling e `thinking: disabled` producono 400, e `fallbacks`
    servirebbe la risposta con un altro modello, violando D2.
    """
    catturato = {}
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=_fake_streaming_client(recorder=catturato)
    )
    client.complete(system="s", messages=[{"role": "user", "content": "x"}], tools=[])

    for vietato in ("temperature", "top_p", "top_k", "thinking", "fallbacks"):
        assert vietato not in catturato, f"il payload contiene {vietato}"
    assert catturato["model"] == DEFAULT_MODEL_STRING == "claude-fable-5"
    assert catturato["max_tokens"] == manifest.max_tokens


def test_d4_il_client_rifiuta_un_manifest_con_sampling_esplicito():
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    esplicito = manifest.model_copy(
        update={"sampling_policy": SamplingPolicy.EXPLICIT, "temperature": 0.7}
    )
    with pytest.raises(LLMError, match="api_default_omitted"):
        AnthropicTraderClient(esplicito, client=object())


@pytest.mark.parametrize("policy", [ThinkingPolicy.DISABLED, ThinkingPolicy.ADAPTIVE])
def test_il_client_rifiuta_una_thinking_policy_non_inviabile(policy):
    """Su Fable il thinking non si configura: l'unica policy è l'omissione."""
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    with pytest.raises(LLMError, match="thinking"):
        AnthropicTraderClient(
            manifest.model_copy(update={"thinking_policy": policy}), client=object()
        )


def test_il_client_streamma_di_default():
    """Turni lunghi + max_tokens alto: senza streaming si rischia il timeout."""
    usato = {"stream": False}
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")

    class FakeMessages:
        def stream(self, **kwargs):
            usato["stream"] = True
            return _FakeStream(_FakeResponse())

        def create(self, **kwargs):
            raise AssertionError("il client non deve usare create() di default")

    class FakeAnthropic:
        messages = FakeMessages()

    AnthropicTraderClient(manifest, client=FakeAnthropic()).complete(
        system="s", messages=[], tools=[]
    )
    assert usato["stream"] is True


def test_max_tokens_e_il_tetto_deciso_dal_tuning_anti_shedding():
    """Tuning (diagnosi C): 8_000 evita lo shedding nei picchi di carico.

    Su Fable il thinking consuma lo stesso budget della risposta, quindi il
    tetto resta un compromesso: abbastanza basso da non farsi scartare
    dall'overloaded in-stream, abbastanza alto per un verbale completo nel
    caso comune. La guardia sul troncamento (`stop_reason="max_tokens"`)
    copre il caso raro in cui non basta.
    """
    assert DEFAULT_MAX_TOKENS == 8_000


def test_il_client_reale_rispetta_il_budget():
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=_fake_streaming_client(), budget=CallBudget(max_calls=1)
    )
    client.complete(system="s", messages=[], tools=[])
    with pytest.raises(BudgetExceeded):
        client.complete(system="s", messages=[], tools=[])


def test_rifiuto_del_modello_riconosciuto_e_categorizzato():
    """stop_reason='refusal' arriva con HTTP 200: non è un errore di rete."""

    class Details:
        category = "cyber"

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest,
        client=_fake_streaming_client(
            _FakeResponse(stop_reason="refusal", stop_details=Details())
        ),
    )
    response = client.complete(system="s", messages=[], tools=[])
    assert response.is_refusal
    assert response.refusal_category == "cyber"


def test_il_client_lascia_passare_stop_reason_max_tokens():
    """stop_reason='max_tokens' e' HTTP 200: il client non lo tratta da errore.

    La classificazione (NO TRADE, categoria 'truncated') vive nel runner
    (`arena/runner.py`), non nel client: qui basta che il client non la
    inghiotta ne' la scambi per un rifiuto.
    """
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest,
        client=_fake_streaming_client(_FakeResponse(stop_reason="max_tokens")),
    )
    response = client.complete(system="s", messages=[], tools=[])
    assert response.stop_reason == "max_tokens"
    assert response.is_refusal is False


def test_retry_con_backoff_su_errore_ritentabile():
    tentativi = {"n": 0}
    dormite = []

    class Boom(Exception):
        status_code = 529

    class FakeMessages:
        def stream(self, **kwargs):
            tentativi["n"] += 1
            if tentativi["n"] < 3:
                raise Boom("overloaded")
            return _FakeStream(_FakeResponse())

    class FakeAnthropic:
        messages = FakeMessages()

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=FakeAnthropic(), sleep=dormite.append
    )
    client.complete(system="s", messages=[], tools=[])
    assert tentativi["n"] == 3
    assert dormite == [1.0, 2.0]


def test_la_risposta_riuscita_porta_la_telemetria_dei_tentativi_falliti():
    """PASSO 1: la risposta finale sa quanti tentativi ha richiesto e con
    quale errore sono falliti quelli precedenti — senza dover fare grep sui
    log di testo (CLAUDE.md §9)."""
    tentativi = {"n": 0}

    class Boom(Exception):
        status_code = 529

    class FakeMessages:
        def stream(self, **kwargs):
            tentativi["n"] += 1
            if tentativi["n"] < 3:
                raise Boom("overloaded")
            return _FakeStream(_FakeResponse())

    class FakeAnthropic:
        messages = FakeMessages()

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=FakeAnthropic(), sleep=lambda _: None
    )
    response = client.complete(system="s", messages=[], tools=[])
    assert response.attempts == 3
    assert response.attempt_errors == ("Boom", "Boom")
    assert response.duration_seconds >= 0.0


def test_usage_estratto_dalla_risposta_finale_in_streaming():
    """PASSO 0: `get_final_message()` consolida l'usage — il client lo legge.

    In streaming l'usage completo (input + output) viaggia nel
    `message_delta` finale; l'SDK lo accumula da solo e lo espone su
    `.usage` dell'oggetto restituito da `get_final_message()`.
    """
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest,
        client=_fake_streaming_client(
            _FakeResponse(usage=_FakeUsage(input_tokens=512, output_tokens=64))
        ),
    )
    response = client.complete(system="s", messages=[], tools=[])
    assert response.usage == LLMUsage(input_tokens=512, output_tokens=64)


def test_usage_assente_diventa_none_non_zero():
    """Se il payload non porta un usage, il campo resta `None`: mai `0`."""
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=_fake_streaming_client(_FakeResponse(usage=None))
    )
    response = client.complete(system="s", messages=[], tools=[])
    assert response.usage is None


def test_i_token_di_cache_finiscono_nella_risposta():
    """RITO CACHING: cache_creation/cache_read arrivano accanto a input/output."""
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest,
        client=_fake_streaming_client(
            _FakeResponse(
                usage=_FakeUsage(
                    input_tokens=900,
                    output_tokens=40,
                    cache_creation_input_tokens=800,
                    cache_read_input_tokens=0,
                )
            )
        ),
    )
    response = client.complete(system="s", messages=[], tools=[])
    assert response.usage == LLMUsage(
        input_tokens=900,
        output_tokens=40,
        cache_creation_input_tokens=800,
        cache_read_input_tokens=0,
    )


def test_i_token_di_cache_assenti_restano_none():
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest,
        client=_fake_streaming_client(
            _FakeResponse(usage=_FakeUsage(input_tokens=10, output_tokens=5))
        ),
    )
    response = client.complete(system="s", messages=[], tools=[])
    assert response.usage.cache_creation_input_tokens is None
    assert response.usage.cache_read_input_tokens is None


# --------------------------------------------------------------------------
# RITO CACHING: marcatori cache_control sui blocchi giusti della richiesta
# --------------------------------------------------------------------------


def test_cache_control_sul_system_e_sull_ultimo_tool():
    """System e tool sono identici a ogni chiamata (D1): marcati sempre."""
    catturato = {}
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=_fake_streaming_client(recorder=catturato)
    )
    tools = [{"name": "get_universe"}, {"name": "get_asset_dossier"}]
    client.complete(
        system="persona e istruzioni",
        messages=[{"role": "user", "content": "x"}],
        tools=tools,
    )

    assert catturato["system"] == [
        {
            "type": "text",
            "text": "persona e istruzioni",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    assert "cache_control" not in catturato["tools"][0]
    assert catturato["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    # Gli originali passati dal chiamante non vengono mutati.
    assert "cache_control" not in tools[-1]


def test_cache_control_assente_sui_messaggi_al_primo_turno():
    """Al primo turno non c'e' ancora un tool_result da marcare."""
    catturato = {}
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=_fake_streaming_client(recorder=catturato)
    )
    messages = [{"role": "user", "content": "ASSET: BTC"}]
    client.complete(system="s", messages=messages, tools=[])

    assert catturato["messages"] == messages
    assert messages[0]["content"] == "ASSET: BTC"  # invariato


def test_cache_control_sull_ultimo_tool_result_quando_presente():
    """Il dossier letto al turno precedente: prefisso stabile da riusare."""
    catturato = {}
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=_fake_streaming_client(recorder=catturato)
    )
    messages = [
        {"role": "user", "content": "ASSET: BTC"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "name": "get_asset_dossier", "id": "t1"}],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": '{"features": {}}'}
            ],
        },
    ]
    client.complete(system="s", messages=messages, tools=[])

    ultimo = catturato["messages"][-1]
    assert ultimo["content"][0]["cache_control"] == {"type": "ephemeral"}
    # Il messaggio originale del chiamante (il runner) non viene mutato: la
    # sua lista serve intatta per costruire il turno successivo.
    assert "cache_control" not in messages[-1]["content"][0]


def test_cache_control_ignora_un_ultimo_messaggio_senza_tool_result():
    """Un ultimo messaggio 'assistant' non e' un punto di cache valido."""
    catturato = {}
    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=_fake_streaming_client(recorder=catturato)
    )
    messages = [
        {"role": "user", "content": "ASSET: BTC"},
        {"role": "assistant", "content": [{"type": "text", "text": "..."}]},
    ]
    client.complete(system="s", messages=messages, tools=[])
    assert catturato["messages"] == messages


def test_rito_diagnosi_caching_id_deterministico_permette_il_riuso(wired):
    """RITO DIAGNOSI CACHING (2026-08-16).

    Diagnosi: l'id che l'API assegna a un blocco tool_use cambia a ogni
    generazione, anche a parita' di asset e argomenti. Il runner lo
    rimandava indietro cosi' com'e' nel turno di submit (vecchio
    `_to_params`/`_execute_tool`, senza `tool_ids`): il `messages` inviato
    al turno di submit non era mai byte-identico tra due chiamate, nemmeno
    per lo stesso asset, e il blocco degli ultimi tool_result (deterministico
    per costruzione, D1) veniva riscritto in cache invece che riletto —
    esattamente il pattern osservato in
    `data/toolcalls/20260816T000019Z.jsonl` (cache_creation 1.001.811,
    cache_read 236.381).

    Con `_deterministic_tool_id` l'id sostituito e' derivato dal contenuto
    (nome, argomenti, posizione), non dalla generazione: il `messages` del
    turno di submit torna byte-identico tra le repliche dello stesso asset,
    e un client fittizio che ricalca l'economia byte-esatta della cache
    reale (scrive alla prima chiamata su un prefisso mai visto, rilegge alle
    successive) lo dimostra rileggendo dalla seconda chiamata in poi.
    """
    store, snapshot, ledger, tool_log = wired

    class _CacheAwareFakeClient:
        """Id del tool_use diverso a ogni generazione, come l'API reale
        (non normalizzato: quello e' compito del runner, non del client)."""

        model_version = DEFAULT_MODEL_STRING

        def __init__(self):
            self._n = 0
            self._seen_message_tokens: dict[str, int] = {}

        def complete(self, *, system, messages, tools):
            self._n += 1
            asset = _asset_from(messages)
            dossier = _dossier_from(messages)
            if dossier is None:
                return LLMResponse(
                    content=[
                        {
                            "type": "tool_use",
                            "name": "get_asset_dossier",
                            "input": {"symbol": asset},
                            "id": f"toolu_rand_{self._n}",
                        }
                    ],
                    stop_reason="tool_use",
                    model=DEFAULT_MODEL_STRING,
                )
            key = sha256_of(messages)
            tokens = max(1, len(json.dumps(messages, sort_keys=True, default=str)) // 4)
            if key in self._seen_message_tokens:
                creation, read = None, self._seen_message_tokens[key]
            else:
                creation, read = tokens, None
                self._seen_message_tokens[key] = tokens
            payload = {
                "asset": asset,
                "action": "flat",
                "size_fraction": 0.0,
                "horizon": "1-3d",
                "expected_holding": "1-3d",
                "confidence": 0.5,
                "features_used": [{"name": "price_vs_sma_20", "value": 0.0}],
                "invalidation_conditions": [
                    "Chiusura giornaliera sotto la media mobile a 20 barre."
                ],
                "risk_checks": [{"name": "costi_considerati", "passed": True, "note": ""}],
            }
            return LLMResponse(
                content=[
                    {
                        "type": "text",
                        "text": (
                            f"I dati disponibili per {asset} non sostengono una tesi "
                            "netta in nessuna direzione su questo orizzonte: resto "
                            "fuori ed evito di forzare una lettura che i numeri non "
                            "giustificano."
                        ),
                    },
                    {
                        "type": "tool_use",
                        "name": "submit_decision",
                        "input": payload,
                        "id": f"toolu_rand_{self._n}_submit",
                    },
                ],
                stop_reason="tool_use",
                model=DEFAULT_MODEL_STRING,
                usage=LLMUsage(
                    input_tokens=2,
                    output_tokens=50,
                    cache_creation_input_tokens=creation,
                    cache_read_input_tokens=read,
                ),
            )

    # Un solo client "backend" condiviso tra le repliche: nella realta' le
    # repliche parlano a client Anthropic separati (isolamento, §3/§6), ma
    # la cache che stiamo simulando vive lato server Anthropic, condivisa
    # per costruzione — qui il client fittizio la rappresenta.
    backend = _CacheAwareFakeClient()
    runner = DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=lambda replica_id: backend,
        config=ArenaConfig(replica_ids=("r1", "r2", "r3")),
        context_git_sha="abcdef1",
    )
    runner.run_day(snapshot.snapshot_id, run_id="run-1")

    for asset in snapshot.universe:
        submit_entries = [
            e
            for e in tool_log.read_all()
            if e["tool"] == "llm_complete"
            and e["args"]["asset"] == asset
            and e["meta"]["output_tokens"] == 50
        ]
        assert len(submit_entries) == 3  # una per replica
        # La prima chiamata (prima replica) scrive la cache su un prefisso
        # mai visto per questo asset.
        assert submit_entries[0]["meta"]["cache_creation_input_tokens"] > 0
        assert submit_entries[0]["meta"]["cache_read_input_tokens"] is None
        # Dalla seconda chiamata in poi (repliche successive, stesso asset)
        # il prefisso e' byte-identico: cache riletta, non riscritta.
        for entry in submit_entries[1:]:
            assert entry["meta"]["cache_read_input_tokens"] > 0
            assert entry["meta"]["cache_creation_input_tokens"] is None


def test_un_400_non_viene_ritentato():
    tentativi = {"n": 0}

    class Bad(Exception):
        status_code = 400

    class FakeMessages:
        def stream(self, **kwargs):
            tentativi["n"] += 1
            raise Bad("invalid_request_error")

    class FakeAnthropic:
        messages = FakeMessages()

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(manifest, client=FakeAnthropic(), sleep=lambda _: None)
    with pytest.raises(LLMError) as excinfo:
        client.complete(system="s", messages=[], tools=[])
    assert tentativi["n"] == 1
    assert excinfo.value.retryable is False
    assert excinfo.value.attempts == 1
    assert excinfo.value.attempt_errors == ("Bad",)


def test_errore_esaurito_dopo_i_retry_resta_marcato_ritentabile():
    """Un overloaded che sopravvive a tutti i retry del client è comunque un
    errore di classe transitoria: il rito (pazienza lunga) deve poterlo
    distinguere da un 400 definitivo per decidere se vale la pena ritentare
    l'intero passo."""

    class Boom(Exception):
        status_code = 529

    class FakeMessages:
        def stream(self, **kwargs):
            raise Boom("overloaded")

    class FakeAnthropic:
        messages = FakeMessages()

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=FakeAnthropic(), max_retries=2, sleep=lambda _: None
    )
    with pytest.raises(LLMError) as excinfo:
        client.complete(system="s", messages=[], tools=[])
    assert excinfo.value.retryable is True
    assert excinfo.value.attempts == 3
    assert excinfo.value.attempt_errors == ("Boom", "Boom", "Boom")


def test_classificazione_degli_errori_ritentabili():
    class WithStatus(Exception):
        status_code = 503

    class RateLimitError(Exception):
        pass

    assert _is_retryable(WithStatus())
    assert _is_retryable(RateLimitError())
    assert not _is_retryable(ValueError("boom"))


# --------------------------------------------------------------------------
# Errori arrivati DENTRO lo stream: HTTP 200, il verdetto sta nel `type`
# --------------------------------------------------------------------------


class _FakeHttpResponse:
    """Risposta HTTP dello stream: 200, perché gli header sono già partiti."""

    status_code = 200


class _InStreamAPIError(Exception):
    """Come l'`APIError` nudo che l'SDK solleva su un evento `error`.

    Nessuno `status_code` proprio, `response.status_code` a 200, e il tipo
    reale dell'errore solo dentro il corpo.
    """

    def __init__(self, error_type, *, wrapped=False, declare_type=False):
        super().__init__(error_type)
        payload = {"type": error_type, "message": "in-stream"}
        self.body = {"error": payload} if wrapped else payload
        self.response = _FakeHttpResponse()
        if declare_type:
            self.type = error_type

    __name__ = "APIError"


@pytest.mark.parametrize(
    "error_type",
    ["overloaded_error", "rate_limit_error", "api_error"],
)
def test_errore_in_stream_transitorio_e_ritentabile(error_type):
    """Il difetto trovato dallo smoke: 200 nello stream, ma non è definitivo."""
    assert _is_retryable(_InStreamAPIError(error_type))
    assert _is_retryable(_InStreamAPIError(error_type, wrapped=True))
    assert _is_retryable(_InStreamAPIError(error_type, declare_type=True))


@pytest.mark.parametrize(
    "error_type",
    [
        "invalid_request_error",
        "authentication_error",
        "permission_error",
        "not_found_error",
    ],
)
def test_errore_in_stream_semantico_non_e_ritentabile(error_type):
    """I 4xx restano definitivi anche se arrivano a stream aperto."""
    assert not _is_retryable(_InStreamAPIError(error_type))
    assert not _is_retryable(_InStreamAPIError(error_type, wrapped=True))


def test_errore_in_stream_di_tipo_ignoto_non_e_ritentabile():
    """Senza `type` riconosciuto e con HTTP 200 non si inventa un retry."""
    assert not _is_retryable(_InStreamAPIError("qualcosa_di_nuovo"))


def test_retry_effettivo_su_overloaded_arrivato_dentro_lo_stream():
    """Regressione end-to-end: prima il retry non scattava mai (200 = fatale)."""
    tentativi = {"n": 0}
    dormite = []

    class FakeMessages:
        def stream(self, **kwargs):
            tentativi["n"] += 1
            if tentativi["n"] < 3:
                raise _InStreamAPIError("overloaded_error")
            return _FakeStream(_FakeResponse())

    class FakeAnthropic:
        messages = FakeMessages()

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=FakeAnthropic(), sleep=dormite.append
    )
    client.complete(system="s", messages=[], tools=[])
    assert tentativi["n"] == 3
    assert dormite == [1.0, 2.0]


def test_400_in_stream_non_consuma_i_tentativi():
    tentativi = {"n": 0}

    class FakeMessages:
        def stream(self, **kwargs):
            tentativi["n"] += 1
            raise _InStreamAPIError("invalid_request_error")

    class FakeAnthropic:
        messages = FakeMessages()

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest, client=FakeAnthropic(), sleep=lambda _: None
    )
    with pytest.raises(LLMError):
        client.complete(system="s", messages=[], tools=[])
    assert tentativi["n"] == 1


def test_il_rifiuto_resta_categoria_propria_e_non_un_errore():
    """`stop_reason='refusal'` non passa mai dalla classificazione degli errori."""

    class Details:
        category = "cyber"

    manifest = build_freeze_manifest(ASOF, context_git_sha="abcdef1")
    client = AnthropicTraderClient(
        manifest,
        client=_fake_streaming_client(
            _FakeResponse(stop_reason="refusal", stop_details=Details())
        ),
        sleep=lambda _: None,
    )
    response = client.complete(system="s", messages=[], tools=[])
    assert response.is_refusal and response.refusal_category == "cyber"


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
