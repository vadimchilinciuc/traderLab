"""Blocco 3 — enforcement del verbale e tabella dei casi del Risk Officer."""

from __future__ import annotations

import pytest

from contracts.decision import Action, Horizon
from contracts.risk import RiskOutcome, RiskRule
from arena.risk_officer import PortfolioState, RiskConfig, RiskOfficer
from arena.verbale import (
    SUBMIT_DECISION_SCHEMA,
    SUBMIT_TOOL_NAME,
    MalformedReason,
    parse_verbale,
    submit_schema_sha,
)
from tests.factories import ASOF, SHA_A, make_decision, make_snapshot

RAZIONALE = (
    "Il prezzo è sopra la media mobile a 20 barre e il volume dell'ultima barra "
    "supera la media del periodo. Il funding resta contenuto, quindi il costo "
    "di mantenimento non annulla la direzione osservata sull'orizzonte scelto."
)


def _payload(**overrides):
    payload = {
        "asset": "BTC",
        "action": "long",
        "size_fraction": 0.05,
        "horizon": "1-3d",
        "expected_holding": "1-3d",
        "confidence": 0.62,
        "features_used": [
            {"name": "price_vs_sma_20", "value": 0.021},
            {"name": "volume_ratio_20", "value": 1.4},
        ],
        "invalidation_conditions": [
            "Chiusura daily sotto la media mobile a 20 barre.",
        ],
        "risk_checks": [{"name": "spread_accettabile", "passed": True, "note": ""}],
    }
    payload.update(overrides)
    return payload


def _blocks(*, text=RAZIONALE, tool_name=SUBMIT_TOOL_NAME, payload=None, order="text_first"):
    text_block = {"type": "text", "text": text}
    tool_block = {
        "type": "tool_use",
        "name": tool_name,
        "input": payload if payload is not None else _payload(),
    }
    if order == "text_first":
        return [text_block, tool_block]
    if order == "tool_first":
        return [tool_block, text_block]
    if order == "tool_only":
        return [tool_block]
    if order == "text_only":
        return [text_block]
    raise AssertionError(order)


def _parse(blocks, expected_asset="BTC"):
    return parse_verbale(
        blocks,
        expected_asset=expected_asset,
        timestamp_decision=ASOF,
        replica_id="r1",
        snapshot_id=make_snapshot().snapshot_id,
        model_version="mock-llm-0",
        prompt_sha=SHA_A,
        context_git_sha="0123abc",
        tool_calls_ref="toolcalls/test.jsonl",
    )


# --------------------------------------------------------------------------
# Verbale conforme
# --------------------------------------------------------------------------


def test_verbale_conforme_produce_un_decision_record():
    parsed = _parse(_blocks())
    assert parsed.ok
    assert parsed.record is not None
    assert parsed.record.asset == "BTC"
    assert parsed.record.action is Action.LONG
    assert parsed.record.rationale_text == RAZIONALE
    assert parsed.record.horizon is Horizon.DAYS_1_3


def test_il_razionale_arriva_dal_testo_libero_non_dal_tool():
    parsed = _parse(_blocks())
    assert "rationale_text" not in SUBMIT_DECISION_SCHEMA["input_schema"]["properties"]
    assert parsed.record.rationale_text.startswith("Il prezzo è sopra")


def test_piu_blocchi_di_testo_prima_vengono_concatenati():
    blocks = [
        {"type": "text", "text": RAZIONALE},
        {"type": "text", "text": "Aggiungo che la profondità stimata è adeguata."},
        {"type": "tool_use", "name": SUBMIT_TOOL_NAME, "input": _payload()},
    ]
    parsed = _parse(blocks)
    assert parsed.ok
    assert "profondità stimata" in parsed.record.rationale_text


def test_parser_accetta_oggetti_stile_sdk():
    class Block:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    blocks = [
        Block(type="text", text=RAZIONALE),
        Block(type="tool_use", name=SUBMIT_TOOL_NAME, input=_payload()),
    ]
    assert _parse(blocks).ok


# --------------------------------------------------------------------------
# Verbale non conforme = NO TRADE
# --------------------------------------------------------------------------


def test_blocco_strutturato_prima_del_testo_e_malformato():
    parsed = _parse(_blocks(order="tool_first"))
    assert parsed.is_malformed
    assert parsed.reason is MalformedReason.NO_RATIONALE_BEFORE


def test_solo_tool_senza_testo_e_malformato():
    parsed = _parse(_blocks(order="tool_only"))
    assert parsed.reason is MalformedReason.NO_RATIONALE_BEFORE


def test_solo_testo_senza_tool_e_malformato():
    parsed = _parse(_blocks(order="text_only"))
    assert parsed.reason is MalformedReason.NO_TOOL_USE


def test_razionale_troppo_corto_e_malformato():
    parsed = _parse(_blocks(text="Compro."))
    assert parsed.reason is MalformedReason.RATIONALE_TOO_SHORT


def test_tool_sbagliato_e_malformato():
    parsed = _parse(_blocks(tool_name="get_universe"))
    assert parsed.reason is MalformedReason.WRONG_TOOL


def test_due_tool_use_sono_malformati():
    blocks = [
        {"type": "text", "text": RAZIONALE},
        {"type": "tool_use", "name": SUBMIT_TOOL_NAME, "input": _payload()},
        {"type": "tool_use", "name": SUBMIT_TOOL_NAME, "input": _payload()},
    ]
    assert _parse(blocks).reason is MalformedReason.MULTIPLE_TOOL_USE


def test_asset_diverso_da_quello_atteso_e_malformato():
    parsed = _parse(_blocks(payload=_payload(asset="ETH")), expected_asset="BTC")
    assert parsed.reason is MalformedReason.ASSET_MISMATCH


@pytest.mark.parametrize(
    "override",
    [
        {"confidence": 1.4},
        {"size_fraction": -0.1},
        {"action": "hodl"},
        {"horizon": "un mese"},
        {"features_used": []},
        {"features_used": [{"name": "intuito", "value": 1.0}]},
        {"invalidation_conditions": []},
        {"invalidation_conditions": ["no"]},
        {"action": "flat", "size_fraction": 0.05},
        {"size_fraction": 0.0},
    ],
)
def test_argomenti_invalidi_sono_malformati(override):
    parsed = _parse(_blocks(payload=_payload(**override)))
    assert parsed.reason is MalformedReason.INVALID_ARGUMENTS


def test_campo_mancante_e_malformato():
    payload = _payload()
    del payload["confidence"]
    assert _parse(_blocks(payload=payload)).reason is MalformedReason.INVALID_ARGUMENTS


def test_schema_di_submit_e_strict_e_chiuso():
    schema = SUBMIT_DECISION_SCHEMA["input_schema"]
    assert SUBMIT_DECISION_SCHEMA["strict"] is True
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert len(submit_schema_sha()) == 64


# --------------------------------------------------------------------------
# Risk Officer — tabella dei casi
# --------------------------------------------------------------------------


@pytest.fixture
def snapshot():
    return make_snapshot()


@pytest.fixture
def state(snapshot):
    return PortfolioState(allowed_assets=frozenset(snapshot.universe))


def test_approved_quando_tutto_e_conforme(snapshot, state):
    officer = RiskOfficer(RiskConfig(fixed_size_fraction=0.05))
    decision = make_decision(snapshot.snapshot_id, size_fraction=0.05)
    verdict = officer.review(decision, state)
    assert verdict.outcome is RiskOutcome.APPROVED
    assert verdict.rule is RiskRule.NONE
    assert verdict.size_fraction_out == 0.05


def test_clamped_size_fissa_verso_il_basso(snapshot, state):
    officer = RiskOfficer(RiskConfig(fixed_size_fraction=0.05))
    verdict = officer.review(
        make_decision(snapshot.snapshot_id, size_fraction=0.40), state
    )
    assert verdict.outcome is RiskOutcome.CLAMPED
    assert verdict.rule is RiskRule.FIXED_SIZE_SEASON_0
    assert verdict.size_fraction_out == 0.05


def test_clamped_size_fissa_verso_l_alto_e_dichiarato(snapshot, state):
    """D3: la size non è una variabile del Trader, viene normalizzata."""
    officer = RiskOfficer(RiskConfig(fixed_size_fraction=0.05))
    verdict = officer.review(
        make_decision(snapshot.snapshot_id, size_fraction=0.01), state
    )
    assert verdict.outcome is RiskOutcome.CLAMPED
    assert verdict.rule is RiskRule.FIXED_SIZE_SEASON_0
    assert verdict.size_fraction_out == 0.05


def test_rejected_asset_fuori_universo(snapshot, state):
    officer = RiskOfficer()
    verdict = officer.review(
        make_decision(snapshot.snapshot_id, asset="DOGE"), state
    )
    assert verdict.outcome is RiskOutcome.REJECTED
    assert verdict.rule is RiskRule.UNKNOWN_ASSET
    assert verdict.action_out is Action.FLAT


def test_rejected_secondo_cambio_nello_stesso_giorno(snapshot, state):
    officer = RiskOfficer()
    state.changes_today["BTC"] = 1
    verdict = officer.review(make_decision(snapshot.snapshot_id), state)
    assert verdict.outcome is RiskOutcome.REJECTED
    assert verdict.rule is RiskRule.ONE_CHANGE_PER_ASSET_PER_DAY


def test_clamped_dal_cap_di_leva(snapshot, state):
    officer = RiskOfficer(RiskConfig(fixed_size_fraction=0.5, max_gross_leverage=3.0))
    state.gross_exposure = 2.8
    verdict = officer.review(
        make_decision(snapshot.snapshot_id, size_fraction=0.5), state
    )
    assert verdict.outcome is RiskOutcome.CLAMPED
    assert verdict.rule is RiskRule.LEVERAGE_CAP
    assert verdict.size_fraction_out == pytest.approx(0.2)


def test_rejected_quando_il_cap_di_leva_e_saturo(snapshot, state):
    officer = RiskOfficer(RiskConfig(max_gross_leverage=3.0))
    state.gross_exposure = 3.0
    verdict = officer.review(make_decision(snapshot.snapshot_id), state)
    assert verdict.outcome is RiskOutcome.REJECTED
    assert verdict.rule is RiskRule.LEVERAGE_CAP


def test_flat_passa_senza_consumare_rischio(snapshot, state):
    officer = RiskOfficer()
    verdict = officer.review(
        make_decision(snapshot.snapshot_id, action=Action.FLAT, size_fraction=0.0),
        state,
    )
    assert verdict.outcome is RiskOutcome.APPROVED
    assert verdict.size_fraction_out == 0.0


def test_verbale_malformato_produce_rejected():
    verdict = RiskOfficer.reject_malformed("BTC", "no_rationale_before")
    assert verdict.outcome is RiskOutcome.REJECTED
    assert verdict.rule is RiskRule.MALFORMED_VERBALE
    assert verdict.size_fraction_out == 0.0


# -- anti-martingala: dormiente con size fissa, attiva senza ---------------


def test_anti_martingala_e_dormiente_con_size_fissa(snapshot, state):
    officer = RiskOfficer(RiskConfig(fixed_size_fraction=0.05, enforce_fixed_size=True))
    state.loss_streak_by_asset["BTC"] = 3
    state.last_size_by_asset["BTC"] = 0.02
    verdict = officer.review(
        make_decision(snapshot.snapshot_id, size_fraction=0.30), state
    )
    assert verdict.rule is RiskRule.FIXED_SIZE_SEASON_0
    assert verdict.size_fraction_out == 0.05


def test_anti_martingala_blocca_l_aumento_dopo_una_perdita(snapshot, state):
    officer = RiskOfficer(RiskConfig(enforce_fixed_size=False))
    state.loss_streak_by_asset["BTC"] = 1
    state.last_size_by_asset["BTC"] = 0.02
    verdict = officer.review(
        make_decision(snapshot.snapshot_id, size_fraction=0.08), state
    )
    assert verdict.outcome is RiskOutcome.CLAMPED
    assert verdict.rule is RiskRule.ANTI_MARTINGALE
    assert verdict.size_fraction_out == 0.02


def test_anti_martingala_non_scatta_senza_perdite(snapshot, state):
    officer = RiskOfficer(RiskConfig(enforce_fixed_size=False))
    state.last_size_by_asset["BTC"] = 0.02
    verdict = officer.review(
        make_decision(snapshot.snapshot_id, size_fraction=0.08), state
    )
    assert verdict.outcome is RiskOutcome.APPROVED
    assert verdict.size_fraction_out == 0.08


def test_anti_martingala_non_blocca_una_riduzione(snapshot, state):
    officer = RiskOfficer(RiskConfig(enforce_fixed_size=False))
    state.loss_streak_by_asset["BTC"] = 5
    state.last_size_by_asset["BTC"] = 0.10
    verdict = officer.review(
        make_decision(snapshot.snapshot_id, size_fraction=0.03), state
    )
    assert verdict.outcome is RiskOutcome.APPROVED
    assert verdict.size_fraction_out == 0.03


def test_il_risk_officer_non_puo_aprire_o_invertire(snapshot, state):
    """Invariante: l'action non viene mai cambiata se non verso FLAT."""
    officer = RiskOfficer(RiskConfig(fixed_size_fraction=0.05))
    for action in (Action.LONG, Action.SHORT):
        size = 0.0 if action in (Action.FLAT, Action.CLOSE) else 0.4
        verdict = officer.review(
            make_decision(snapshot.snapshot_id, action=action, size_fraction=size),
            PortfolioState(allowed_assets=frozenset(snapshot.universe)),
        )
        assert verdict.action_out in (action, Action.FLAT)


def test_config_invalida_solleva():
    with pytest.raises(ValueError):
        RiskConfig(fixed_size_fraction=0.0)
    with pytest.raises(ValueError):
        RiskConfig(max_gross_leverage=-1.0)


def test_portfolio_state_registra_le_decisioni(state):
    state.register("BTC", 0.05)
    state.register("BTC", 0.05)
    assert state.changes_today["BTC"] == 2
    assert state.gross_exposure == pytest.approx(0.10)
    assert state.last_size_by_asset["BTC"] == 0.05
