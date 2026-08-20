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
from arena.verbale import MalformedReason, is_true_malformed
from contracts.decision import Action
from contracts.freeze import PIN_COMMIT_PLACEHOLDERS, ThinkingDeclaration
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict
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
    SeasonSpend,
    check_hard_stop,
    check_prorata_alarm,
    estimate_cost_usd,
    season_spend,
)
from ledger.telemetry import DailyDispersion, daily_dispersion
from ledger.trader_ledger import LedgerKey, TraderLedger
from tests.factories import ASOF, make_decision, make_snapshot
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
    omesso = ThinkingDeclaration.ALWAYS_ON_PARAM_OMITTED
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


def test_allarme_prorata_scatta_sopra_e_tace_sotto():
    """D5, i due lati dell'allarme di ritmo (`1,25 x` il pro-rata)."""
    preventivo = 420.0
    attese = 42
    eseguite = 10
    prorata = preventivo * eseguite / attese  # 100.0
    soglia = prorata * ALARM_MULTIPLIER  # 125.0

    sotto = check_prorata_alarm(
        _spesa(soglia - 0.01, eseguite), preventivo, expected_days=attese
    )
    assert sotto.ok
    assert sotto.threshold_usd == pytest.approx(soglia)

    sopra = check_prorata_alarm(
        _spesa(soglia + 0.01, eseguite), preventivo, expected_days=attese
    )
    assert not sopra.ok
    assert "piu' in fretta" in sopra.detail


def test_a_zero_giornate_non_c_e_ritmo_e_a_una_giornata_c_e():
    """D5: il pro-rata a zero giornate non è una soglia, ed è dichiarato tale."""
    zero = check_prorata_alarm(_spesa(999.0, 0), 100.0, expected_days=42)
    assert zero.ok
    assert "non c'è ancora un ritmo" in zero.detail

    una = check_prorata_alarm(_spesa(999.0, 1), 100.0, expected_days=42)
    assert not una.ok


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

    con_log = season_spend(trader_ledger=ledger, toolcalls_dir=toolcalls)
    assert con_log.days_executed == 2
    assert set(con_log.run_ids) == {"run-a", "run-b"}
    assert con_log.usd == pytest.approx(estimate_cost_usd(2_000_000, 0, 0, 0))

    # Lato opposto: il log delle tool call è gitignorato e un clone pulito non
    # ce l'ha. Le giornate restano contate, la spesa scende a zero — ed è per
    # questo che `run_ids` viaggia nel risultato: la cifra è un minimo.
    senza_log = season_spend(trader_ledger=ledger, toolcalls_dir=tmp_path / "assente")
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
