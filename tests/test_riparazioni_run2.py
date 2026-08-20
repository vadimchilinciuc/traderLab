"""Riparazioni pre-pin del RUN2 — un test a due lati per ogni riparazione.

Ogni riparazione qui dentro esegue una decisione già ratificata (verbale RUN2
§A.2/A.4/A.5/A.6/A.7/B.3, foglio 19/08 punto 15, CODA voce 23, ratifiche D3/D5
del 20/08). Ogni test ha **due lati** — il caso che deve passare e il caso che
deve essere rifiutato — perché una guardia provata solo dal lato che passa non
è distinguibile da una guardia che non c'è.

Nessuna rete, nessuna API key, nessun modello: come tutta la suite.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from arena.config import (
    ArenaConfig,
    ManifestError,
    build_freeze_manifest,
    load_pinned_manifest,
)
from arena.llm_client import (
    CallBudget,
    LLMResponse,
    LLMUsage,
    MockLLM,
    ThinkingDeclarationViolated,
    _extract_usage,
    assert_thinking_coherent,
)
from arena.runner import DailyRunner, _to_params
from arena.verbale import (
    SUBMIT_DECISION_SCHEMA,
    MalformedReason,
    is_true_malformed,
)
from contracts.decision import Action, DecisionRecord, FeatureUsed
from contracts.freeze import (
    PIN_COMMIT_PLACEHOLDERS,
    FreezeManifest,
    ThinkingDeclaration,
)
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict
from contracts.vocabulary import FEATURE_NAMES, MAX_FEATURES_USED
from contracts.snapshot import LiquidityEstimate
from ledger.eprocess import KillCriterionConfig, KillVerdict, evaluate_kill_criterion
from ledger.ops_ledger import (
    OpsEvent,
    OpsKey,
    OpsLedger,
    last_known_day,
    mark_missing_days,
)
from ledger.spend import (
    ALARM_MULTIPLIER,
    HARD_STOP_MULTIPLIER,
    PRICE_FIELDS,
    Pricing,
    SeasonSpend,
    check_hard_stop,
    check_prorata_alarm,
    check_season_terms,
    estimate_cost_usd,
    prorata_threshold_usd,
    season_spend,
)
from ledger.telemetry import DailyDispersion, daily_dispersion
from ledger.trader_ledger import LedgerKey, TraderLedger
from tests.factories import (
    ASOF,
    LISTINO_OPUS5,
    PREZZI_OPUS5,
    make_decision,
    make_snapshot,
    manifest_con_prezzi,
    prezzi_senza,
)
from toolserver.registry import ToolRegistry
from toolserver.snapshot_builder import DECLARED_DEPTH_USD, SnapshotBuilder
from toolserver.store import SnapshotStore
from toolserver.toollog import LLM_COMPLETE_TOOL, ToolCallLog

PIN = "1a2b3c4"
ALTRO_PIN = "9f8e7d6"


# ==========================================================================
# A.2 — il runner carica il manifest committato
# ==========================================================================


def _scrivi_manifest(path: Path, manifest, *, freeze_id: str | None = None) -> Path:
    """Scrive un documento di pin come lo scrive `scripts/freeze_pin.py`."""
    documento = {
        "freeze_manifest": manifest.canonical_payload(),
        "freeze_id": freeze_id if freeze_id is not None else manifest.freeze_id,
        "rito_config": {"nota": "documento sintetico per i test"},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(documento, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def manifest_pinnato():
    return build_freeze_manifest(
        datetime.now(tz=timezone.utc), pin_commit=PIN, season_budget_usd=500.0
    )


def test_manifest_coerente_si_carica_e_divergente_viene_rifiutato(
    tmp_path, manifest_pinnato
):
    """A.2, i due lati del ricalcolo del `freeze_id`.

    Lato che passa: il file dichiara il `freeze_id` che il contenuto produce.
    Lato che rifiuta: qualcuno ha toccato il documento dopo la firma e i due
    non coincidono più — è esattamente il caso che il rito Z1 del 18/08 ha
    trovato in Stagione 0, e non si gira.
    """
    buono = _scrivi_manifest(tmp_path / "buono.json", manifest_pinnato)
    caricato = load_pinned_manifest(buono)
    assert caricato.freeze_id == manifest_pinnato.freeze_id
    assert caricato.pin_commit == PIN

    cattivo = _scrivi_manifest(
        tmp_path / "cattivo.json", manifest_pinnato, freeze_id="0" * 64
    )
    with pytest.raises(ManifestError, match="freeze_id divergente"):
        load_pinned_manifest(cattivo)


def test_pin_commit_assente_rifiuta_e_valorizzato_passa(tmp_path):
    """A.2, i due lati di `pin_commit`.

    Senza il commit del rito del pin non esiste una stagione da far girare, e
    il rifiuto deve nominare la causa invece di partire lo stesso.
    """
    senza = build_freeze_manifest(datetime.now(tz=timezone.utc))
    assert senza.pin_commit in PIN_COMMIT_PLACEHOLDERS
    assert not senza.is_pinned
    path_senza = _scrivi_manifest(tmp_path / "senza.json", senza)
    with pytest.raises(ManifestError, match="pin_commit assente"):
        load_pinned_manifest(path_senza)
    # Lo stesso file si legge senza errore quando il pin non è richiesto: il
    # rifiuto è del runner, non della lettura.
    assert load_pinned_manifest(path_senza, require_pin=False).pin_commit == ""

    con = build_freeze_manifest(datetime.now(tz=timezone.utc), pin_commit=PIN)
    assert con.is_pinned
    path_con = _scrivi_manifest(tmp_path / "con.json", con)
    assert load_pinned_manifest(path_con).pin_commit == PIN


def test_context_git_sha_esce_dal_freeze_id_e_pin_commit_ci_entra():
    """A.2, il cuore della riparazione, provato in entrambe le direzioni.

    Cambiare `context_git_sha` — cioè fare un commit qualsiasi nel repo — NON
    deve muovere il `freeze_id`: era la causa dei tre `freeze_id` diversi in
    tre giornate di Stagione 0 (TL-007). Cambiare `pin_commit` invece SÌ: è il
    campo che identifica la stagione.
    """
    momento = datetime.now(tz=timezone.utc)
    a = build_freeze_manifest(momento, context_git_sha="aaaaaaa", pin_commit=PIN)
    b = build_freeze_manifest(momento, context_git_sha="bbbbbbb", pin_commit=PIN)
    assert a.context_git_sha != b.context_git_sha
    assert a.freeze_id == b.freeze_id

    c = build_freeze_manifest(momento, context_git_sha="aaaaaaa", pin_commit=ALTRO_PIN)
    assert c.freeze_id != a.freeze_id


def test_manifest_assente_e_manifest_presente(tmp_path, manifest_pinnato):
    """A.2: un file che non c'è è un errore pulito, non un ripiego silenzioso."""
    with pytest.raises(ManifestError, match="assente"):
        load_pinned_manifest(tmp_path / "non_esiste.json")
    presente = _scrivi_manifest(tmp_path / "esiste.json", manifest_pinnato)
    assert load_pinned_manifest(presente).model_string == manifest_pinnato.model_string


# ==========================================================================
# A.4 — dispersione indefinita, mai 0,0
# ==========================================================================


def test_dispersione_intersezione_vuota_e_indefinita_e_piena_e_un_numero():
    """A.4, i due lati.

    Intersezione vuota: tre `None`, non tre zeri. Intersezione piena: numeri
    veri. Uno `0,0000` da intersezione vuota sarebbe indistinguibile, a valle,
    da un accordo perfetto fra repliche.
    """
    sid = make_snapshot().snapshot_id

    vuota = daily_dispersion(
        {
            "r1": {"BTC": make_decision(sid, replica_id="r1", asset="BTC")},
            "r2": {"ETH": make_decision(sid, replica_id="r2", asset="ETH")},
        }
    )
    assert vuota.is_degenerate
    assert vuota.action_disagreement is None
    assert vuota.confidence_dispersion is None
    assert vuota.size_dispersion is None

    piena = daily_dispersion(
        {
            "r1": {"BTC": make_decision(sid, replica_id="r1", asset="BTC")},
            "r2": {"BTC": make_decision(sid, replica_id="r2", asset="BTC")},
        }
    )
    assert piena.is_defined
    assert piena.action_disagreement is not None
    assert piena.confidence_dispersion is not None
    assert piena.size_dispersion is not None


def test_dispersione_una_replica_indefinita_e_due_repliche_definita():
    """A.4: con una replica sola non c'è niente da confrontare; con due sì."""
    sid = make_snapshot().snapshot_id
    una = daily_dispersion({"r1": {"BTC": make_decision(sid, replica_id="r1")}})
    assert una.replicas == 1
    assert una.action_disagreement is None

    due = daily_dispersion(
        {
            "r1": {"BTC": make_decision(sid, replica_id="r1")},
            "r2": {"BTC": make_decision(sid, replica_id="r2")},
        }
    )
    assert due.replicas == 2
    assert due.action_disagreement == pytest.approx(0.0)


def test_il_log_scrive_n_d_per_indefinito_e_il_numero_per_definito():
    """A.4: il formato unico dei log. `n/d` da una parte, la cifra dall'altra."""
    assert DailyDispersion.format_value(None) == "n/d"
    assert DailyDispersion.format_value(0.0) == "0.0000"
    assert DailyDispersion.format_value(0.125) == "0.1250"


def test_kill_criterion_scarta_le_coppie_indefinite_e_usa_quelle_definite():
    """A.4 a valle: `n/d` non entra nella finestra, e non diventa zero.

    Lato che scarta: venti coppie di cui cinque indefinite non fanno una
    finestra da venti, e il conteggio degli scarti è dichiarato. Lato che
    conta: venti coppie tutte definite la fanno.
    """
    cfg = KillCriterionConfig(window=20)

    gaps = [0.5] * 20
    con_buchi: list[float | None] = [None] * 5 + [0.1] * 15
    esito = evaluate_kill_criterion(gaps, con_buchi, cfg)
    assert esito.verdict is KillVerdict.INSUFFICIENT_DATA
    assert esito.window_used == 15
    assert esito.pairs_excluded_undefined == 5
    assert "dispersione indefinita" in esito.detail

    tutte_definite: list[float | None] = [0.1] * 20
    pieno = evaluate_kill_criterion(gaps, tutte_definite, cfg)
    assert pieno.verdict is KillVerdict.SIGNAL_EXCEEDS_NOISE
    assert pieno.window_used == 20
    assert pieno.pairs_excluded_undefined == 0


# ==========================================================================
# A.5 — una contabilità sola per il rifiuto del modello
# ==========================================================================


class _RispostaFissa:
    """Client finto che risponde sempre la stessa cosa. Nessuna rete."""

    model_version = "fake-per-test"

    def __init__(self, response_factory) -> None:
        self._factory = response_factory
        self.calls = 0

    def complete(self, *, system, messages, tools):
        self.calls += 1
        return self._factory()


def _runner_con(wired_paths, response_factory):
    store, _snapshot, ledger, tool_log = wired_paths
    return DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=lambda replica_id: _RispostaFissa(response_factory),
        config=ArenaConfig(),
        context_git_sha="abcdef1",
    )


@pytest.fixture
def wired_paths(tmp_path):
    store = SnapshotStore(tmp_path / "snapshots")
    snapshot = make_snapshot()
    store.save(snapshot)
    ledger = TraderLedger(tmp_path / "ledger" / "s0.jsonl")
    tool_log = ToolCallLog(tmp_path / "toolcalls", run_id="run-1")
    return store, snapshot, ledger, tool_log


def test_un_rifiuto_conta_nei_rifiuti_e_lascia_i_malformati_a_zero(wired_paths):
    """A.5, primo lato.

    La giornata del 18/08 di Stagione 0 stampò «malformati: 2» avendo un solo
    verbale malformato vero e un rifiuto del modello. Qui il rifiuto sta nel
    suo contatore e **non** in quello dei malformati.
    """
    _, snapshot, _, _ = wired_paths
    result = _runner_con(
        wired_paths,
        lambda: LLMResponse(
            content=[],
            stop_reason="refusal",
            model="claude-fable-5",
            refusal_category="cyber",
        ),
    ).run_day(snapshot.snapshot_id, run_id="run-1")

    attesi = 3 * len(snapshot.universe)
    assert result.refusal_count == attesi
    assert result.malformed_count == 0
    assert result.truncated_count == 0
    for m in result.telemetry.all_metrics().values():
        assert m.refusals_total == len(snapshot.universe)
        assert m.malformed_total == 0


def test_un_malformato_vero_conta_nei_malformati_e_lascia_i_rifiuti_a_zero(
    wired_paths,
):
    """A.5, secondo lato: il contrario esatto del test precedente."""
    _, snapshot, _, _ = wired_paths
    result = _runner_con(
        wired_paths,
        lambda: LLMResponse(
            content=[{"type": "text", "text": "nessun blocco strutturato"}],
            stop_reason="end_turn",
            model="claude-fable-5",
        ),
    ).run_day(snapshot.snapshot_id, run_id="run-1")

    attesi = 3 * len(snapshot.universe)
    assert result.malformed_count == attesi
    assert result.refusal_count == 0
    assert result.truncated_count == 0
    for m in result.telemetry.all_metrics().values():
        assert m.malformed_total == len(snapshot.universe)
        assert m.refusals_total == 0


def test_un_troncamento_ha_la_sua_contabilita_e_non_tocca_le_altre_due(wired_paths):
    """A.5, terzo caso: `max_tokens` non è né un rifiuto né un malformato."""
    _, snapshot, _, _ = wired_paths
    result = _runner_con(
        wired_paths,
        lambda: LLMResponse(
            content=[{"type": "text", "text": "il razionale si interrompe"}],
            stop_reason="max_tokens",
            model="claude-fable-5",
        ),
    ).run_day(snapshot.snapshot_id, run_id="run-1")

    attesi = 3 * len(snapshot.universe)
    assert result.truncated_count == attesi
    assert result.malformed_count == 0
    assert result.refusal_count == 0


def test_is_true_malformed_separa_le_categorie():
    """A.5 alla radice: la funzione che decide cosa è un malformato vero."""
    assert is_true_malformed(MalformedReason.NO_TOOL_USE)
    assert is_true_malformed(MalformedReason.INVALID_ARGUMENTS)
    assert not is_true_malformed(MalformedReason.MODEL_REFUSAL)
    assert not is_true_malformed(MalformedReason.TRUNCATED)
    assert not is_true_malformed(None)


# ==========================================================================
# A.7 — thinking dichiarato e assenza loggata
# ==========================================================================


class _UsageFinto:
    def __init__(self, thinking_tokens=None):
        self.input_tokens = 100
        self.output_tokens = 200
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = 0
        if thinking_tokens is not None:
            self.thinking_tokens = thinking_tokens


class _RispostaFinta:
    def __init__(self, content, usage):
        self.content = content
        self.usage = usage
        self.stop_reason = "end_turn"
        self.model = "claude-fable-5"


def test_usage_dichiara_il_thinking_presente_e_dichiara_l_assenza(wired_paths):
    """A.7, i due lati.

    Con blocchi di thinking nella risposta: `thinking_absent=False` e, se
    l'API espone un contatore, il numero. Senza: `thinking_absent=True` e
    `thinking_tokens=None` — l'assenza è **registrata**, non taciuta, e `None`
    significa "non registrato", mai "zero token".
    """
    con_thinking = _extract_usage(
        _RispostaFinta(
            content=[
                {"type": "thinking", "thinking": "ragiono"},
                {"type": "text", "text": "rispondo"},
            ],
            usage=_UsageFinto(thinking_tokens=42),
        )
    )
    assert con_thinking is not None
    assert con_thinking.thinking_absent is False
    assert con_thinking.thinking_tokens == 42
    # Separato dall'output, non dentro di esso.
    assert con_thinking.output_tokens == 200

    senza_thinking = _extract_usage(
        _RispostaFinta(
            content=[{"type": "text", "text": "rispondo e basta"}],
            usage=_UsageFinto(),
        )
    )
    assert senza_thinking is not None
    assert senza_thinking.thinking_absent is True
    assert senza_thinking.thinking_tokens is None


def test_il_thinking_oscurato_conta_come_presente_e_il_testo_no():
    """A.7: `redacted_thinking` è ragionamento pagato, un blocco di testo no."""
    oscurato = _extract_usage(
        _RispostaFinta(
            content=[{"type": "redacted_thinking", "data": "..."}],
            usage=_UsageFinto(),
        )
    )
    assert oscurato is not None and oscurato.thinking_absent is False

    solo_testo = _extract_usage(
        _RispostaFinta(content=[{"type": "text", "text": "x"}], usage=_UsageFinto())
    )
    assert solo_testo is not None and solo_testo.thinking_absent is True


def test_payload_coerente_passa_e_payload_incoerente_viene_rifiutato():
    """A.7, la verifica a ogni chiamata, in entrambe le direzioni."""
    omesso = ThinkingDeclaration.API_DEFAULT_PARAM_OMITTED
    esplicito = ThinkingDeclaration.EXPLICIT_PARAM_SENT

    # Dichiarazione "parametro omesso": senza `thinking` passa, con no.
    assert_thinking_coherent({"model": "m", "messages": []}, omesso)
    with pytest.raises(ThinkingDeclarationViolated, match="parametro omesso"):
        assert_thinking_coherent(
            {"model": "m", "thinking": {"type": "enabled"}}, omesso
        )

    # Dichiarazione "parametro inviato": con `thinking` passa, senza no.
    assert_thinking_coherent({"model": "m", "thinking": {"type": "enabled"}}, esplicito)
    with pytest.raises(ThinkingDeclarationViolated, match="non contiene"):
        assert_thinking_coherent({"model": "m", "messages": []}, esplicito)


def test_il_thinking_finisce_nel_log_delle_tool_call_anche_da_assente(wired_paths):
    """A.7: i due campi ci sono in ogni riga del log, anche quando è "no"."""
    _, snapshot, _, tool_log = wired_paths
    mock = MockLLM()
    result = DailyRunner(
        store=wired_paths[0],
        ledger=wired_paths[2],
        tool_log=tool_log,
        client_factory=lambda replica_id: MockLLM(),
        context_git_sha="abcdef1",
    ).run_day(snapshot.snapshot_id, run_id="run-1")
    assert result.decisions

    righe = [e for e in tool_log.read_all() if e["tool"] == LLM_COMPLETE_TOOL]
    assert righe
    for riga in righe:
        # Il MockLLM non porta `usage`: i campi restano comunque presenti.
        assert "thinking_tokens" in riga["meta"]
        assert "thinking_absent" in riga["meta"]
        assert riga["meta"]["thinking_absent"] is True
    assert mock.calls == 0  # il mock locale non è quello usato: nessun refuso


# ==========================================================================
# B.3 — il turno echo porta i soli blocchi tool_use
# ==========================================================================


def test_il_turno_echo_non_contiene_blocchi_text_ma_la_conversione_generica_si():
    """B.3, i due lati della stessa funzione.

    `only_tool_use=True` è la forma che il runner rimanda indietro: testo
    libero rimosso, id deterministici. È il rimedio misurato 8,8x sul costo
    per chiamata e la rimozione della fonte di divergenza dei prefissi.
    `only_tool_use=False` resta la conversione generica.
    """
    content = [
        {"type": "text", "text": "penso ad alta voce, e cambio ogni volta"},
        {
            "type": "tool_use",
            "id": "toolu_api_123",
            "name": "get_universe",
            "input": {},
        },
    ]

    echo = _to_params(content, tool_ids=["toolu_det_fisso"], only_tool_use=True)
    assert [b["type"] for b in echo] == ["tool_use"]
    assert echo[0]["id"] == "toolu_det_fisso"

    generica = _to_params(content, tool_ids=["toolu_det_fisso"])
    assert [b["type"] for b in generica] == ["text", "tool_use"]


def test_nessun_turno_assistente_rimandato_indietro_porta_testo(wired_paths):
    """B.3 end-to-end: il MockLLM scrive testo prima della tool call, e nel
    turno rimandato indietro quel testo non c'è.

    Il lato opposto è nella stessa passata: il verbale finale — quello che va
    al parser — il razionale in testo libero ce l'ha eccome, ed è obbligatorio
    (CLAUDE.md §8). Rimuovere il testo dall'echo non lo indebolisce.
    """
    _, snapshot, _, _ = wired_paths
    turni: list[list[dict]] = []

    class Spia:
        model_version = "mock-llm-0"

        def __init__(self) -> None:
            self._mock = MockLLM()

        def complete(self, *, system, messages, tools):
            turni.extend(m["content"] for m in messages if m.get("role") == "assistant")
            return self._mock.complete(system=system, messages=messages, tools=tools)

    result = DailyRunner(
        store=wired_paths[0],
        ledger=wired_paths[2],
        tool_log=wired_paths[3],
        client_factory=lambda replica_id: Spia(),
        context_git_sha="abcdef1",
    ).run_day(snapshot.snapshot_id, run_id="run-1")

    assert turni, "nessun turno dell'assistente rimandato indietro: test cieco"
    for blocchi in turni:
        assert blocchi, "turno echo vuoto"
        assert all(b["type"] == "tool_use" for b in blocchi)

    # L'altro lato: il razionale c'è, nel verbale.
    assert result.decisions
    for decision in result.decisions:
        assert len(decision.rationale_text) >= 120


# ==========================================================================
# CODA 23 — il registro operativo regge anche a ledger dei verbali vuoto
# ==========================================================================


def _verdetto_ok() -> RiskVerdict:
    return RiskVerdict(
        outcome=RiskOutcome.APPROVED,
        rule=RiskRule.NONE,
        action_in=Action.LONG,
        action_out=Action.LONG,
        size_fraction_in=0.05,
        size_fraction_out=0.05,
    )


def test_run_failed_si_scrive_a_ledger_vuoto_e_la_riga_e_leggibile(tmp_path):
    """CODA 23, primo lato: ledger dei verbali vuoto + giornata fallita.

    La riga `run_failed` deve esistere e la catena del registro operativo deve
    verificare. Il lato opposto: senza fallimento, quella riga non c'è.
    """
    ops = OpsLedger(tmp_path / "ops.jsonl")
    trader = TraderLedger(tmp_path / "season.jsonl")
    assert len(trader) == 0

    giorno = date(2026, 8, 20)
    ops.append(
        key=OpsKey.of(giorno, OpsEvent.RUN_FAILED),
        detail="build_snapshot.py ha restituito 1",
        detected_at_utc=datetime(2026, 8, 20, 0, 5, tzinfo=timezone.utc),
    )
    righe = ops.events(OpsEvent.RUN_FAILED)
    assert len(righe) == 1
    assert righe[0]["key"]["day"] == "2026-08-20"
    assert "build_snapshot" in righe[0]["detail"]
    assert ops.verify().ok

    # Lato opposto: un registro in cui la giornata è andata bene non ha
    # nessuna riga `run_failed`.
    ops_ok = OpsLedger(tmp_path / "ops_ok.jsonl")
    ops_ok.append(key=OpsKey.of(giorno, OpsEvent.DAY_COMPLETED), detail="snapshot x")
    assert ops_ok.events(OpsEvent.RUN_FAILED) == []


def test_il_registro_operativo_ancora_i_buchi_quando_i_verbali_mancano(tmp_path):
    """CODA 23, secondo lato: la riga `run_failed` fa da ancoraggio.

    Senza questo, una stagione che fallisce le prime giornate non registra mai
    i buchi che seguono, perché `last_recorded_day` guarda solo i verbali e
    quel ledger è vuoto.
    """
    trader = TraderLedger(tmp_path / "season.jsonl")
    ops = OpsLedger(tmp_path / "ops.jsonl")
    ops.append(
        key=OpsKey.of(date(2026, 8, 20), OpsEvent.RUN_FAILED),
        detail="il rito e' partito e non ha prodotto verbali",
    )

    assert last_known_day(trader, ops) == date(2026, 8, 20)
    marcati = mark_missing_days(
        trader_ledger=trader, ops_ledger=ops, today=date(2026, 8, 23)
    )
    assert marcati == [date(2026, 8, 21), date(2026, 8, 22)]

    # Lato opposto: senza nessuna traccia da nessuna parte non c'è un "prima"
    # da cui misurare, e non si inventa nulla.
    trader_vuoto = TraderLedger(tmp_path / "vuoto.jsonl")
    ops_vuoto = OpsLedger(tmp_path / "ops_vuoto.jsonl")
    assert last_known_day(trader_vuoto, ops_vuoto) is None
    assert (
        mark_missing_days(
            trader_ledger=trader_vuoto,
            ops_ledger=ops_vuoto,
            today=date(2026, 8, 23),
        )
        == []
    )


def test_un_verbale_batte_un_evento_piu_vecchio_e_viceversa(tmp_path):
    """CODA 23: l'ancoraggio è il più recente dei due, in entrambi gli ordini."""
    trader = TraderLedger(tmp_path / "season.jsonl")
    ops = OpsLedger(tmp_path / "ops.jsonl")
    ops.append(key=OpsKey.of(date(2026, 8, 18), OpsEvent.RUN_FAILED), detail="x")
    trader.append(
        key=LedgerKey.of(date(2026, 8, 19), "r1", "BTC"),
        verdict=_verdetto_ok(),
        decision=make_decision("a" * 64, replica_id="r1"),
        snapshot_id="a" * 64,
        run_id="run-1",
    )
    assert last_known_day(trader, ops) == date(2026, 8, 19)

    ops.append(key=OpsKey.of(date(2026, 8, 21), OpsEvent.RUN_FAILED), detail="y")
    assert last_known_day(trader, ops) == date(2026, 8, 21)


# ==========================================================================
# D5 — guardie economiche di stagione
# ==========================================================================


def _spesa(usd: float, giorni: int = 10) -> SeasonSpend:
    return SeasonSpend(
        days_executed=giorni,
        run_ids=("run-finto",),
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=0,
        cache_creation_tokens=0,
        usd=usd,
    )


def test_soglia_dura_ferma_sopra_e_lascia_passare_sotto():
    """D5, i due lati della soglia dura (`1,5 x` il preventivo)."""
    preventivo = 100.0
    limite = preventivo * HARD_STOP_MULTIPLIER  # 150.0

    sotto = check_hard_stop(_spesa(limite - 0.01), preventivo)
    assert sotto.ok
    assert sotto.threshold_usd == pytest.approx(limite)

    sopra = check_hard_stop(_spesa(limite + 0.01), preventivo)
    assert not sopra.ok
    assert "non parte" in sopra.detail


def test_preventivo_assente_e_un_rifiuto_e_preventivo_presente_no():
    """D5: `season_budget_usd` assente = rifiuto, non budget infinito.

    Trattare l'assenza come "nessun limite" trasformerebbe la dimenticanza di
    un campo in una stagione senza tetto.
    """
    assente = check_hard_stop(_spesa(0.0), None)
    assert not assente.ok
    assert not assente.has_budget
    assert "season_budget_usd assente" in assente.detail

    presente = check_hard_stop(_spesa(0.0), 100.0)
    assert presente.ok
    assert presente.has_budget


#: Costo giornaliero di riferimento di questi test. Il preventivo si scrive
#: come `GIORNATE_ATTESE x D_USD` e le spese come multipli di `D_USD`: cosi'
#: le soglie si leggono in giornate invece che in numeri magici.
D_USD = 12.50
GIORNATE_ATTESE = 28


def test_allarme_prorata_scatta_sopra_e_tace_sotto():
    """D5, i due lati dell'allarme di ritmo, tarati sul preventivo firmato.

    Preventivo `28 x D` su **28** giornate attese: al giorno `g` il pro-rata
    vale esattamente `g x D` — la spesa attesa — e la soglia `1,25 x g x D`.
    Provato su tre giorni diversi, perche' la relazione deve reggere per ogni
    `g` e non solo per uno:

    - spesa `1,0 x g x D` → nessun allarme;
    - spesa `1,3 x g x D` → allarme.

    **Perche' le giornate attese vengono dal manifest e non da una costante di
    questo modulo.** Erano `SEASON_EXPECTED_DAYS = 42`, il cap di calendario
    del verbale RUN2 §A.8. Con un preventivo tarato su 28 giornate e un
    pro-rata calcolato su 42, la soglia varrebbe
    `1,25 x 28D x g/42 = 0,833 x g x D`: **sotto** la spesa attesa. Una
    stagione perfettamente in linea col proprio preventivo suonerebbe
    l'allarme il primo giorno e tutti i successivi — e un allarme che suona
    sempre e' un allarme spento. Numeratore e denominatore della stessa
    frazione si firmano insieme, al rito del pin.
    """
    preventivo = GIORNATE_ATTESE * D_USD  # 350.00

    for g in (1, 7, 28):
        atteso = g * D_USD
        soglia = prorata_threshold_usd(preventivo, g, GIORNATE_ATTESE)
        assert soglia == pytest.approx(ALARM_MULTIPLIER * atteso)

        in_linea = check_prorata_alarm(
            _spesa(atteso, g), preventivo, expected_days=GIORNATE_ATTESE
        )
        assert in_linea.ok, g
        assert in_linea.threshold_usd == pytest.approx(soglia)

        in_fretta = check_prorata_alarm(
            _spesa(1.3 * atteso, g), preventivo, expected_days=GIORNATE_ATTESE
        )
        assert not in_fretta.ok, g
        assert "piu' in fretta" in in_fretta.detail

    # Contro-prova del motivo inciso sopra: con lo STESSO preventivo e il
    # denominatore sbagliato (42), la spesa attesa sfonda la soglia al giorno 1.
    sbagliato = check_prorata_alarm(_spesa(D_USD, 1), preventivo, expected_days=42)
    assert not sbagliato.ok


def test_a_zero_giornate_non_c_e_ritmo_e_a_una_giornata_c_e():
    """D5: il pro-rata a zero giornate non è una soglia, ed è dichiarato tale."""
    zero = check_prorata_alarm(_spesa(999.0, 0), 100.0, expected_days=42)
    assert zero.ok
    assert "non c'è ancora un ritmo" in zero.detail

    una = check_prorata_alarm(_spesa(999.0, 1), 100.0, expected_days=42)
    assert not una.ok


def _manifest_economico(
    *,
    season_budget_usd: float | None = 350.0,
    season_expected_days: int | None = 28,
    prezzi: Mapping[str, float] | None = None,
) -> FreezeManifest:
    """Un manifest con i termini economici che gli si passano."""
    return manifest_con_prezzi(
        datetime.now(tz=timezone.utc),
        pin_commit=PIN,
        season_budget_usd=season_budget_usd,
        season_expected_days=season_expected_days,
        prezzi=PREZZI_OPUS5 if prezzi is None else prezzi,
    )


def test_i_termini_economici_ci_sono_tutti_o_e_un_rifiuto():
    """D5: i sei termini economici si firmano insieme, nello stesso manifest.

    Sono `season_budget_usd`, `season_expected_days` e le quattro voci di
    listino. I due lati: tutti presenti → si gira; uno qualsiasi assente →
    rifiuto, con il nome del campo mancante dentro il motivo. Il rifiuto elenca
    **tutti** i campi mancanti, non solo il primo, perche' chi lo legge deve
    poterli valorizzare in una passata sola.

    Il listino entra in questo controllo per un difetto misurato: stava fra le
    costanti di `ledger/spend.py` coi prezzi di Fable ($10/$50) mentre il
    modello pinnato era `claude-opus-5` ($5/$25), e le guardie contavano la
    spesa al doppio. Una costante non puo' accorgersi che il modello e'
    cambiato; un campo del pin, assente finche' non lo si firma, si'.
    """
    completo = check_season_terms(_manifest_economico())
    assert completo.ok
    assert "350.00" in completo.detail and "28" in completo.detail
    assert completo.pricing == LISTINO_OPUS5

    senza_preventivo = check_season_terms(
        _manifest_economico(season_budget_usd=None)
    )
    assert not senza_preventivo.ok
    assert "season_budget_usd" in senza_preventivo.detail
    assert "season_expected_days" not in senza_preventivo.detail
    assert senza_preventivo.pricing is None

    senza_giornate = check_season_terms(
        _manifest_economico(season_expected_days=None)
    )
    assert not senza_giornate.ok
    assert "season_expected_days" in senza_giornate.detail

    senza_niente = check_season_terms(
        _manifest_economico(season_budget_usd=None, season_expected_days=None)
    )
    assert not senza_niente.ok
    assert "season_budget_usd" in senza_niente.detail
    assert "season_expected_days" in senza_niente.detail

    # Il listino: assente del tutto, e assente per una voce sola.
    senza_listino = check_season_terms(_manifest_economico(prezzi={}))
    assert not senza_listino.ok
    assert senza_listino.pricing is None
    for campo in PRICE_FIELDS:
        assert campo in senza_listino.detail

    monco = check_season_terms(
        _manifest_economico(prezzi=prezzi_senza("price_per_mtok_cache_write_5m"))
    )
    assert not monco.ok
    assert "price_per_mtok_cache_write_5m" in monco.detail
    assert "price_per_mtok_input" not in monco.detail


def test_il_listino_del_pin_e_quello_di_opus_5_e_conta_la_meta_di_fable():
    """Il conto cambia col listino, ed e' il punto dell'intera riparazione.

    1M di token per ciascuna delle quattro voci. Al listino di `claude-opus-5`
    (§4 dell'evidenza del preventivo del 20/08) valgono $36.75; al listino di
    Fable che `ledger/spend.py` portava ancora, $73.50 — **il doppio**. Con il
    preventivo proposto di $89,90 su 28 giornate, la soglia dura di 1,5x
    ($134,85) si tocca al giorno 42 col listino giusto e al giorno **21** con
    quello sbagliato: la stagione si sarebbe fermata a meta' credendo di aver
    speso il doppio di quanto aveva speso.
    """
    opus = estimate_cost_usd(
        1_000_000, 1_000_000, 1_000_000, 1_000_000, pricing=LISTINO_OPUS5
    )
    assert opus == pytest.approx(5.00 + 25.00 + 0.50 + 6.25)

    fable = Pricing(
        input_usd_per_mtok=10.00,
        output_usd_per_mtok=50.00,
        cache_write_usd_per_mtok=12.50,
        cache_read_usd_per_mtok=1.00,
    )
    assert estimate_cost_usd(
        1_000_000, 1_000_000, 1_000_000, 1_000_000, pricing=fable
    ) == pytest.approx(2 * opus)

    # I due giorni in cui la soglia dura scatta, con lo stesso preventivo e la
    # stessa spesa giornaliera VERA. Preventivo dell'evidenza del 20/08:
    # $89,90 su 28 giornate, cioe' $3,2107 al giorno nello scenario caldo.
    preventivo, giornaliero_vero = 89.90, 3.2107
    soglia = preventivo * HARD_STOP_MULTIPLIER
    giorno_giusto = soglia / giornaliero_vero
    giorno_sbagliato = soglia / (2 * giornaliero_vero)
    assert round(giorno_giusto) == 42
    assert round(giorno_sbagliato) == 21


def test_il_manifest_porta_le_giornate_attese_e_le_lascia_assenti_di_default():
    """Le giornate attese sono un campo del pin, non una costante di modulo.

    I due lati: composto senza il campo resta `None` — e senza rito del pin è
    la situazione normale; composto con il campo lo conserva, ed **entra nel
    `freeze_id`**, perché cambiare il denominatore della soglia economica di
    una stagione cambia la stagione.
    """
    senza = build_freeze_manifest(datetime.now(tz=timezone.utc), pin_commit=PIN)
    assert senza.season_expected_days is None

    con = build_freeze_manifest(
        datetime.now(tz=timezone.utc), pin_commit=PIN, season_expected_days=28
    )
    assert con.season_expected_days == 28
    assert con.freeze_id != senza.freeze_id

    with pytest.raises(ValidationError):
        build_freeze_manifest(
            datetime.now(tz=timezone.utc), pin_commit=PIN, season_expected_days=0
        )


def test_il_prorata_senza_giornate_attese_non_e_una_soglia():
    """D5: manca il denominatore → non esiste un pro-rata, e si dice.

    Il lato opposto è già negli altri test: col denominatore la soglia c'è.
    """
    indefinito = check_prorata_alarm(_spesa(1.0, 1), 100.0, expected_days=None)
    assert not indefinito.ok
    assert not indefinito.has_budget
    assert "season_expected_days assente" in indefinito.detail


def test_la_spesa_di_stagione_somma_i_run_id_del_ledger(tmp_path):
    """D5: la spesa si legge dal ledger (le giornate e i run_id) incrociato col
    log delle tool call (i token). I due lati: con log e senza log."""
    ledger = TraderLedger(tmp_path / "season.jsonl")
    toolcalls = tmp_path / "toolcalls"
    toolcalls.mkdir()

    for giorno, run_id in ((date(2026, 8, 18), "run-a"), (date(2026, 8, 19), "run-b")):
        ledger.append(
            key=LedgerKey.of(giorno, "r1", "BTC"),
            verdict=_verdetto_ok(),
            decision=make_decision("a" * 64, replica_id="r1"),
            snapshot_id="a" * 64,
            run_id=run_id,
        )
        (toolcalls / f"{run_id}.jsonl").write_text(
            json.dumps(
                {
                    "tool": LLM_COMPLETE_TOOL,
                    "meta": {"input_tokens": 1_000_000, "output_tokens": 0},
                }
            )
            + "\n",
            encoding="utf-8",
        )

    con_log = season_spend(
        trader_ledger=ledger, toolcalls_dir=toolcalls, pricing=LISTINO_OPUS5
    )
    assert con_log.days_executed == 2
    assert set(con_log.run_ids) == {"run-a", "run-b"}
    assert con_log.usd == pytest.approx(
        estimate_cost_usd(2_000_000, 0, 0, 0, pricing=LISTINO_OPUS5)
    )
    # 2M token di input a $5/Mtok: la cifra si legge, non si ricava.
    assert con_log.usd == pytest.approx(10.00)

    # Lato opposto: il log delle tool call è gitignorato e un clone pulito non
    # ce l'ha. Le giornate restano contate, la spesa scende a zero — ed è per
    # questo che `run_ids` viaggia nel risultato: la cifra è un minimo.
    senza_log = season_spend(
        trader_ledger=ledger,
        toolcalls_dir=tmp_path / "assente",
        pricing=LISTINO_OPUS5,
    )
    assert senza_log.days_executed == 2
    assert senza_log.usd == pytest.approx(0.0)


# ==========================================================================
# Foglio 19/08 punto 15 — `depth_usd_1pct` etichettata costante dichiarata
# ==========================================================================


class _SorgenteFinta:
    """Sorgente deterministica per lo SnapshotBuilder. Nessuna rete."""

    def __init__(self, *, con_impact: bool) -> None:
        self._con_impact = con_impact

    def meta_and_asset_ctxs(self):
        ctx = {"markPx": "60000", "midPx": "60000", "dayNtlVlm": "1000000"}
        if self._con_impact:
            ctx["impactPxs"] = ["59990", "60010"]
        return ([{"name": "BTC"}, {"name": "ETH"}], [dict(ctx), dict(ctx)])

    def candles(self, coin, interval, start_ms, end_ms):
        giorno = 86_400_000
        base = end_ms - 30 * giorno
        return [
            {
                "t": base + i * giorno,
                "o": "60000",
                "h": "60100",
                "l": "59900",
                "c": "60000",
                "v": "10",
            }
            for i in range(20)
        ]

    def funding_history(self, coin, start_ms, end_ms):
        ora = 3_600_000
        return [
            {"time": end_ms - i * ora, "fundingRate": "0.00001"}
            for i in range(24, 0, -1)
        ]


def test_depth_e_etichettata_costante_dichiarata_in_entrambi_i_rami():
    """Foglio 15, i due lati.

    Con i prezzi di impatto lo spread è una stima vera; senza, è il fallback
    statico. La **profondità** è la stessa costante in tutti e due i casi, e in
    tutti e due i casi lo dichiara nel record.
    """
    asof = datetime(2026, 8, 20, 0, 0, tzinfo=timezone.utc)

    con = SnapshotBuilder(_SorgenteFinta(con_impact=True)).build(asof)
    for asset in con.assets:
        assert asset.liquidity.estimator == "hyperliquid_impact_px_v0"
        assert asset.liquidity.depth_source == "costante_dichiarata"
        assert asset.liquidity.depth_usd_1pct == DECLARED_DEPTH_USD

    senza = SnapshotBuilder(_SorgenteFinta(con_impact=False)).build(asof)
    for asset in senza.assets:
        assert asset.liquidity.estimator == "static_fallback_v0"
        assert asset.liquidity.depth_source == "costante_dichiarata"
        assert asset.liquidity.depth_usd_1pct == DECLARED_DEPTH_USD


def test_lo_snapshot_resta_hashabile_e_stabile_a_parita_di_input():
    """Foglio 15: l'etichetta cambia lo `snapshot_id` — atteso — ma lo lascia
    **stabile**: due costruzioni con lo stesso input danno lo stesso id.

    Il lato opposto: un input diverso dà un id diverso, cioè l'id continua a
    dipendere dal contenuto e non è diventato una costante.
    """
    asof = datetime(2026, 8, 20, 0, 0, tzinfo=timezone.utc)

    uno = SnapshotBuilder(_SorgenteFinta(con_impact=True)).build(asof)
    due = SnapshotBuilder(_SorgenteFinta(con_impact=True)).build(asof)
    assert uno.snapshot_id == due.snapshot_id

    altro = SnapshotBuilder(_SorgenteFinta(con_impact=False)).build(asof)
    assert altro.snapshot_id != uno.snapshot_id


def test_il_campo_depth_source_e_obbligatorio_e_vincolato():
    """Foglio 15: non si può costruire una liquidità senza dichiarare la
    provenienza della profondità, e non si può dichiararne una inventata."""
    valido = LiquidityEstimate(
        spread_bps=2.0,
        depth_usd_1pct=250_000.0,
        depth_source="costante_dichiarata",
        estimator="test_v0",
    )
    assert valido.depth_source == "costante_dichiarata"

    with pytest.raises(ValidationError, match="depth_source"):
        LiquidityEstimate(spread_bps=2.0, depth_usd_1pct=250_000.0, estimator="test_v0")
    with pytest.raises(ValidationError, match="depth_source"):
        LiquidityEstimate(
            spread_bps=2.0,
            depth_usd_1pct=250_000.0,
            depth_source="inventata",
            estimator="test_v0",
        )


# ==========================================================================
# Coerenza fra i pezzi
# ==========================================================================


def test_usage_ha_i_campi_thinking_anche_costruito_a_mano():
    """A.7: i due campi hanno un default che non mente.

    Costruito senza dire niente sul thinking, `LLMUsage` dichiara l'assenza —
    che è la lettura corretta di "non ho visto blocchi di thinking" — e lascia
    il conteggio a `None`, che è "non registrato".
    """
    nudo = LLMUsage(input_tokens=1, output_tokens=2)
    assert nudo.thinking_absent is True
    assert nudo.thinking_tokens is None

    pieno = LLMUsage(
        input_tokens=1, output_tokens=2, thinking_tokens=7, thinking_absent=False
    )
    assert pieno.thinking_absent is False
    assert pieno.thinking_tokens == 7


def test_il_budget_di_chiamate_resta_indipendente_dalla_guardia_economica():
    """D5: il tetto di chiamate/giorno e la spesa di stagione sono due cose.

    Il primo protegge la giornata, la seconda la stagione. Confonderle
    significherebbe che una giornata sotto il tetto di chiamate può comunque
    sfondare il preventivo, e nessuno se ne accorge.
    """
    budget = CallBudget(max_calls=2)
    budget.consume()
    assert budget.remaining == 1
    # La guardia di stagione non guarda le chiamate, guarda i dollari.
    assert check_hard_stop(_spesa(1_000.0), 100.0).ok is False
    assert check_hard_stop(_spesa(1.0), 100.0).ok is True


def test_asof_delle_factory_resta_quello_atteso():
    """Guardia banale ma utile: i test sopra usano `ASOF` delle factory, e se
    cambiasse silenziosamente i confronti sui giorni smetterebbero di dire
    quello che dicono."""
    assert ASOF.tzinfo is not None
    assert ASOF.utcoffset() == timezone.utc.utcoffset(None)


# ==========================================================================
# A.6 / D3 — il canale d'allarme del controllo mattutino
# ==========================================================================


# ==========================================================================
# Foglio 19/08 punto 15, secondo tempo — la chiave esposta all'agente
# ==========================================================================
#
# Il T1 ha etichettato la profondita' dentro il contratto (`depth_source =
# "costante_dichiarata"`) ma ha lasciato al Tool Server la chiave
# `depth_usd_1pct_estimated`, che da quel momento **mente** all'agente: dice
# "stimata" di un numero che e' una costante. Qui la chiave si chiama
# `depth_usd_1pct_declared`.
#
# E' una variabile di CONTENUTO — cambia cosa il Trader legge — e va nella
# lista onesta del PREREG_LAB_S0_RUN2, nella stessa classe di `depth_source`.


def test_get_costs_espone_la_profondita_come_dichiarata_e_non_come_stimata(tmp_path):
    """I due lati sulla stessa risposta: il nome onesto c'è, quello che mente no.

    Lo spread resta `spread_bps_estimated` perché quello è davvero stimato dal
    book: la riparazione riguarda la profondità, non tutto il blocco.
    """
    store = SnapshotStore(tmp_path / "snapshots")
    log = ToolCallLog(tmp_path / "toolcalls", run_id="run-depth")
    snapshot = make_snapshot()
    store.save(snapshot)
    registry = ToolRegistry(store, log)

    risposta = registry.call(
        snapshot_id=snapshot.snapshot_id,
        replica_id="r1",
        name="get_costs",
        args={"symbol": "BTC"},
    )

    assert "depth_usd_1pct_declared" in risposta
    assert "depth_usd_1pct_estimated" not in risposta
    assert "spread_bps_estimated" in risposta

    asset = next(a for a in snapshot.assets if a.symbol == "BTC")
    assert risposta["depth_usd_1pct_declared"] == asset.liquidity.depth_usd_1pct
    # La chiave e' coerente con la provenienza registrata nello snapshot: e'
    # esattamente cio' che il nome vecchio contraddiceva.
    assert asset.liquidity.depth_source == "costante_dichiarata"


def test_la_chiave_nuova_non_tocca_lo_sha_degli_schemi_dei_tool():
    """La rinomina sta nella RISPOSTA, non nello schema di input di `get_costs`.

    Conta perché `tool_schemas_sha` entra nel `freeze_id`: se la riparazione
    lo avesse mosso sarebbe stata una variabile di protocollo in più, non solo
    di contenuto. Il lato opposto — che lo sha reagisca davvero a un cambio di
    schema — è provato mutandone una copia.
    """
    from arena.config import all_tool_schemas, all_tool_schemas_sha
    from contracts.hashing import sha256_of

    schemi = all_tool_schemas()
    costi = next(s for s in schemi if s["name"] == "get_costs")
    assert "depth" not in json.dumps(costi["input_schema"], ensure_ascii=False)

    mutati = [dict(s) for s in schemi]
    mutati[0] = {**mutati[0], "description": mutati[0]["description"] + " "}
    assert sha256_of(mutati) != all_tool_schemas_sha()


# ==========================================================================
# F12 — il tetto di `features_used` deriva dal vocabolario, e lo schema lo dice
# ==========================================================================


def _verbale_con(nomi) -> DecisionRecord:
    """Un verbale valido in tutto, tranne per quante grandezze dichiara.

    Si passa dalla **validazione**, non da `model_copy`: quest'ultimo non
    rivalida, e un test costruito così proverebbe soltanto che pydantic sa
    copiare un oggetto.
    """
    payload = make_decision("c" * 64).model_dump()
    payload["features_used"] = [
        FeatureUsed(name=n, value=float(i)).model_dump() for i, n in enumerate(nomi)
    ]
    return DecisionRecord.model_validate(payload)


def test_il_tetto_di_features_used_e_il_vocabolario_e_oltre_si_rifiuta():
    """F12, i due lati.

    Il vocabolario espone 21 primitive e i nomi non si ripetono: un verbale
    che le cita **tutte** è il massimo dichiarabile e deve passare. Una voce
    in più non può che essere un nome ripetuto, e viene respinta.

    Il lato che passa è quello che conta: prima del 2026-08-20 il tetto era un
    **12** costante di origine non documentata, e questo stesso verbale — che
    non viola nessuna regola del vocabolario — sarebbe stato rifiutato.
    """
    assert MAX_FEATURES_USED == len(FEATURE_NAMES) == 21

    tutte = _verbale_con(FEATURE_NAMES)
    assert len(tutte.features_used) == MAX_FEATURES_USED

    with pytest.raises(ValidationError) as errore:
        _verbale_con((*FEATURE_NAMES, FEATURE_NAMES[0]))
    assert errore.value.errors()[0]["type"] == "too_long"


def test_il_verbale_da_tredici_voci_dello_smoke_ora_passa():
    """La regressione della trappola del rito PIN-BIS.

    Lo smoke del 2026-08-20 su `claude-opus-5` produsse, su **entrambi** gli
    asset, un verbale con **13** voci di `features_used`: valido in tutto il
    resto, e rifiutato con «Tuple should have at most 12 items after
    validation, not 13». Il difetto non era del modello — 13 nomi su 21
    disponibili è un comportamento ragionevole — ma di un tetto che il Trader
    non poteva leggere in nessun punto dello schema.

    Sono i nomi a non contare qui: conta il **numero**, che è la grandezza su
    cui la validazione cadeva.
    """
    tredici = _verbale_con(FEATURE_NAMES[:13])
    assert len(tredici.features_used) == 13


def test_lo_schema_dichiara_lo_stesso_tetto_che_il_contratto_applica():
    """F12(b): il vincolo è conoscibile dove si decide, non solo dove respinge.

    Due lati: lo schema porta il tetto ed è lo **stesso numero** del contratto
    (se qualcuno ne cambiasse uno solo, questo test cade); e la descrizione lo
    nomina, perché un `maxItems` in mezzo allo schema è più facile da mancare
    di una frase nella riga che il modello legge.
    """
    features = SUBMIT_DECISION_SCHEMA["input_schema"]["properties"]["features_used"]
    assert features["maxItems"] == MAX_FEATURES_USED

    campo = DecisionRecord.model_fields["features_used"]
    tetti = [m.max_length for m in campo.metadata if hasattr(m, "max_length")]
    assert tetti == [MAX_FEATURES_USED]

    assert str(MAX_FEATURES_USED) in features["description"]


# ==========================================================================
# F13 — il contatore del ragionamento è annidato, e si legge da lì
# ==========================================================================


class _DettagliOutput:
    def __init__(self, thinking_tokens: int) -> None:
        self.thinking_tokens = thinking_tokens


class _UsageAnnidato(_UsageFinto):
    """Un `usage` come quello che l'SDK espone: il contatore sta in un
    sotto-oggetto `output_tokens_details`, non fra gli attributi di primo
    livello."""

    def __init__(self, thinking_tokens: int | None = None) -> None:
        super().__init__()
        if thinking_tokens is not None:
            self.output_tokens_details = _DettagliOutput(thinking_tokens)


def test_il_contatore_annidato_si_legge_e_la_sua_assenza_resta_assenza():
    """F13, i due lati.

    Presente: `usage.output_tokens_details.thinking_tokens` viene letto, ed è
    il percorso che la documentazione ufficiale indica. Assente: il campo
    resta `None` — «non registrato» — e `thinking_absent` continua a dire la
    verità sui blocchi. **Mai uno zero al posto di una misura**: uno zero
    direbbe «ha ragionato per zero token», che è un'affermazione diversa.

    Prima del 2026-08-20 il client guardava solo il primo livello di `usage`:
    nello smoke del rito PIN-BIS il contatore risultò `None` su tutte e 12 le
    chiamate, e il repo ne dedusse che l'API non lo esponesse.
    """
    letto = _extract_usage(
        _RispostaFinta(
            content=[
                {"type": "thinking", "thinking": "ragiono"},
                {"type": "text", "text": "rispondo"},
            ],
            usage=_UsageAnnidato(thinking_tokens=1234),
        )
    )
    assert letto is not None
    assert letto.thinking_tokens == 1234
    assert letto.thinking_absent is False

    senza = _extract_usage(
        _RispostaFinta(
            content=[{"type": "text", "text": "rispondo e basta"}],
            usage=_UsageAnnidato(),
        )
    )
    assert senza is not None
    assert senza.thinking_tokens is None
    assert senza.thinking_absent is True


def test_uno_zero_annidato_e_una_misura_e_si_legge_come_tale():
    """Lo zero **vero** non va confuso con l'assenza, e viceversa.

    Se l'API dichiara `thinking_tokens = 0` su una risposta senza blocchi di
    thinking, quello è un dato: il modello non ha ragionato, e il contatore lo
    dice. Deve arrivare come `0`, non come `None` — altrimenti la riparazione
    di F13 avrebbe solo spostato il silenzio.
    """
    zero = _extract_usage(
        _RispostaFinta(
            content=[{"type": "text", "text": "x"}],
            usage=_UsageAnnidato(thinking_tokens=0),
        )
    )
    assert zero is not None
    assert zero.thinking_tokens == 0
    assert zero.thinking_absent is True
