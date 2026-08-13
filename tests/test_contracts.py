"""Blocco 1 — round-trip di serializzazione, immutabilità, rifiuto campi extra."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from contracts.decision import Action, DecisionRecord, FeatureUsed, Horizon
from contracts.fill import Liquidity, ShadowFill
from contracts.freeze import FreezeManifest, SamplingPolicy
from contracts.hashing import canonical_json, sha256_of
from contracts.outcome import OutcomeAnnotation
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict
from contracts.snapshot import MarketSnapshot, OHLCVBar
from tests.factories import (
    ASOF,
    SHA_A,
    make_asset,
    make_decision,
    make_manifest,
    make_snapshot,
)

ALL_MODELS = (MarketSnapshot, DecisionRecord, RiskVerdict, ShadowFill, FreezeManifest)


# --------------------------------------------------------------------------
# Round-trip di serializzazione
# --------------------------------------------------------------------------


def test_snapshot_round_trip_preserva_id():
    snap = make_snapshot()
    payload = snap.model_dump(mode="json")
    revived = MarketSnapshot.model_validate(json.loads(json.dumps(payload)))
    assert revived == snap
    assert revived.snapshot_id == snap.snapshot_id


def test_decision_round_trip():
    snap = make_snapshot()
    dec = make_decision(snap.snapshot_id)
    revived = DecisionRecord.model_validate(json.loads(dec.model_dump_json()))
    assert revived == dec


def test_manifest_round_trip_e_freeze_id_stabile():
    man = make_manifest()
    revived = FreezeManifest.model_validate(json.loads(man.model_dump_json()))
    assert revived == man
    assert revived.freeze_id == man.freeze_id


def test_round_trip_di_tutti_i_contratti_principali():
    snap = make_snapshot()
    dec = make_decision(snap.snapshot_id)
    verdict = RiskVerdict(
        outcome=RiskOutcome.APPROVED,
        rule=RiskRule.NONE,
        action_in=Action.LONG,
        action_out=Action.LONG,
        size_fraction_in=0.05,
        size_fraction_out=0.05,
    )
    fill = ShadowFill(
        timestamp_utc=ASOF,
        asset="BTC",
        action=Action.LONG,
        size_fraction=0.05,
        reference_price=100.0,
        liquidity=Liquidity.TAKER,
        fee_bps=4.5,
        slippage_bps=2.0,
        fill_price=100.065,
        notional_fraction=0.05,
        cost_fraction=0.0000325,
        snapshot_id=snap.snapshot_id,
        replica_id="r1",
    )
    for obj in (snap, dec, verdict, fill, make_manifest()):
        revived = type(obj).model_validate(json.loads(obj.model_dump_json()))
        assert revived == obj, type(obj).__name__


# --------------------------------------------------------------------------
# Immutabilità
# --------------------------------------------------------------------------


@pytest.mark.parametrize("model_cls", ALL_MODELS)
def test_tutti_i_contratti_sono_frozen(model_cls):
    assert model_cls.model_config["frozen"] is True


def test_assegnazione_su_snapshot_solleva():
    snap = make_snapshot()
    with pytest.raises(ValidationError):
        snap.source = "altro"


def test_assegnazione_su_decision_solleva():
    dec = make_decision(make_snapshot().snapshot_id)
    with pytest.raises(ValidationError):
        dec.confidence = 0.99


def test_le_collezioni_sono_tuple_non_liste():
    snap = make_snapshot()
    dec = make_decision(snap.snapshot_id)
    assert isinstance(snap.assets, tuple)
    assert isinstance(dec.features_used, tuple)
    assert isinstance(dec.invalidation_conditions, tuple)


# --------------------------------------------------------------------------
# Rifiuto dei campi extra
# --------------------------------------------------------------------------


@pytest.mark.parametrize("model_cls", ALL_MODELS)
def test_tutti_i_contratti_vietano_extra(model_cls):
    assert model_cls.model_config["extra"] == "forbid"


def test_campo_extra_su_snapshot_solleva():
    payload = make_snapshot().model_dump(mode="json")
    payload["campo_inatteso"] = 1
    with pytest.raises(ValidationError, match="campo_inatteso"):
        MarketSnapshot.model_validate(payload)


def test_campo_extra_su_decision_solleva():
    snap = make_snapshot()
    payload = make_decision(snap.snapshot_id).model_dump(mode="json")
    payload["size"] = 0.9  # refuso plausibile per size_fraction
    with pytest.raises(ValidationError, match="size"):
        DecisionRecord.model_validate(payload)


# --------------------------------------------------------------------------
# snapshot_id: derivato, deterministico, sensibile al contenuto
# --------------------------------------------------------------------------


def test_snapshot_id_deterministico_tra_costruzioni():
    assert make_snapshot().snapshot_id == make_snapshot().snapshot_id


def test_snapshot_id_cambia_se_cambia_il_contenuto():
    a = make_snapshot()
    b = MarketSnapshot.build(
        asof_utc=a.asof_utc,
        universe=a.universe,
        universe_status=a.universe_status,
        assets=a.assets,
        source="fonte_diversa",
        builder_version=a.builder_version,
    )
    assert a.snapshot_id != b.snapshot_id


def test_snapshot_id_manomesso_viene_rifiutato():
    payload = make_snapshot().model_dump(mode="json")
    payload["snapshot_id"] = "f" * 64
    with pytest.raises(ValidationError, match="snapshot_id non corrisponde"):
        MarketSnapshot.model_validate(payload)


def test_build_rifiuta_snapshot_id_esplicito():
    with pytest.raises(ValueError, match="derivato"):
        MarketSnapshot.build(
            asof_utc=ASOF,
            universe=("BTC",),
            universe_status="placeholder_non_ufficiale",
            assets=(make_asset("BTC", 100.0),),
            source="x",
            builder_version="v",
            snapshot_id=SHA_A,
        )


def test_universe_status_e_parte_del_contenuto_hashato():
    a = make_snapshot()
    b = MarketSnapshot.build(
        asof_utc=a.asof_utc,
        universe=a.universe,
        universe_status="pre_screen_ufficiale",
        assets=a.assets,
        source=a.source,
        builder_version=a.builder_version,
    )
    assert a.snapshot_id != b.snapshot_id


# --------------------------------------------------------------------------
# Disciplina point-in-time e coerenza dello snapshot
# --------------------------------------------------------------------------


def test_barra_successiva_ad_asof_e_look_ahead():
    asset = make_asset("BTC", 100.0)
    futura = OHLCVBar(
        ts_open_utc=ASOF + timedelta(days=1),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume_usd=1.0,
    )
    with pytest.raises(ValidationError, match="look-ahead"):
        MarketSnapshot.build(
            asof_utc=ASOF,
            universe=("BTC",),
            universe_status="placeholder_non_ufficiale",
            assets=(asset.model_copy(update={"ohlcv_daily": (*asset.ohlcv_daily, futura)}),),
            source="x",
            builder_version="v",
        )


def test_universe_e_assets_devono_coincidere():
    with pytest.raises(ValidationError, match="universe e assets"):
        MarketSnapshot.build(
            asof_utc=ASOF,
            universe=("BTC", "ETH"),
            universe_status="placeholder_non_ufficiale",
            assets=(make_asset("BTC", 100.0),),
            source="x",
            builder_version="v",
        )


def test_timestamp_naive_rifiutato():
    with pytest.raises(ValidationError, match="timezone-aware"):
        OHLCVBar(
            ts_open_utc=datetime(2026, 8, 1),
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume_usd=0.0,
        )


def test_barra_incoerente_rifiutata():
    with pytest.raises(ValidationError, match="fuori dal range"):
        OHLCVBar(
            ts_open_utc=ASOF,
            open=50.0,
            high=10.0,
            low=1.0,
            close=5.0,
            volume_usd=0.0,
        )


# --------------------------------------------------------------------------
# DecisionRecord: le regole dello schema v1
# --------------------------------------------------------------------------


def test_feature_fuori_vocabolario_rifiutata():
    with pytest.raises(ValidationError, match="vocabolario primitivo"):
        FeatureUsed(name="gut_feeling", value=1.0)


def test_features_duplicate_rifiutate():
    snap = make_snapshot()
    base = make_decision(snap.snapshot_id)
    payload = base.model_dump(mode="json")
    payload["features_used"] = [
        {"name": "return_7d", "value": 0.1},
        {"name": "return_7d", "value": 0.2},
    ]
    with pytest.raises(ValidationError, match="duplicati"):
        DecisionRecord.model_validate(payload)


def test_rationale_troppo_corto_rifiutato():
    snap = make_snapshot()
    payload = make_decision(snap.snapshot_id).model_dump(mode="json")
    payload["rationale_text"] = "sale"
    with pytest.raises(ValidationError):
        DecisionRecord.model_validate(payload)


def test_flat_con_size_positiva_rifiutato():
    snap = make_snapshot()
    payload = make_decision(snap.snapshot_id).model_dump(mode="json")
    payload["action"] = "flat"
    with pytest.raises(ValidationError, match="size_fraction=0.0"):
        DecisionRecord.model_validate(payload)


def test_long_con_size_zero_rifiutato():
    snap = make_snapshot()
    payload = make_decision(snap.snapshot_id).model_dump(mode="json")
    payload["size_fraction"] = 0.0
    with pytest.raises(ValidationError, match="size_fraction > 0.0"):
        DecisionRecord.model_validate(payload)


def test_invalidation_condition_vuota_rifiutata():
    snap = make_snapshot()
    payload = make_decision(snap.snapshot_id).model_dump(mode="json")
    payload["invalidation_conditions"] = ["boh"]
    with pytest.raises(ValidationError, match="ex-ante"):
        DecisionRecord.model_validate(payload)


def test_confidence_fuori_range_rifiutata():
    snap = make_snapshot()
    payload = make_decision(snap.snapshot_id).model_dump(mode="json")
    payload["confidence"] = 1.5
    with pytest.raises(ValidationError):
        DecisionRecord.model_validate(payload)


def test_signed_size():
    snap = make_snapshot()
    long = make_decision(snap.snapshot_id, action=Action.LONG, size_fraction=0.05)
    short = make_decision(snap.snapshot_id, action=Action.SHORT, size_fraction=0.05)
    flat = make_decision(snap.snapshot_id, action=Action.FLAT, size_fraction=0.0)
    assert (long.signed_size, short.signed_size, flat.signed_size) == (0.05, -0.05, 0.0)


# --------------------------------------------------------------------------
# RiskVerdict: coerenza dei verdetti
# --------------------------------------------------------------------------


def test_approved_non_puo_cambiare_size():
    with pytest.raises(ValidationError, match="non può cambiare la size"):
        RiskVerdict(
            outcome=RiskOutcome.APPROVED,
            rule=RiskRule.NONE,
            action_in=Action.LONG,
            action_out=Action.LONG,
            size_fraction_in=0.05,
            size_fraction_out=0.02,
        )


def test_clamped_deve_dichiarare_la_regola():
    with pytest.raises(ValidationError, match="deve dichiarare la regola"):
        RiskVerdict(
            outcome=RiskOutcome.CLAMPED,
            rule=RiskRule.NONE,
            action_in=Action.LONG,
            action_out=Action.LONG,
            size_fraction_in=0.05,
            size_fraction_out=0.02,
        )


def test_rejected_implica_flat_e_size_zero():
    with pytest.raises(ValidationError, match="size_fraction_out=0.0"):
        RiskVerdict(
            outcome=RiskOutcome.REJECTED,
            rule=RiskRule.LEVERAGE_CAP,
            action_in=Action.LONG,
            action_out=Action.FLAT,
            size_fraction_in=0.05,
            size_fraction_out=0.05,
        )


# --------------------------------------------------------------------------
# ShadowFill: il costo peggiora sempre il prezzo
# --------------------------------------------------------------------------


def test_fill_long_migliore_del_riferimento_rifiutato():
    with pytest.raises(ValidationError, match="non può essere migliore"):
        ShadowFill(
            timestamp_utc=ASOF,
            asset="BTC",
            action=Action.LONG,
            size_fraction=0.05,
            reference_price=100.0,
            liquidity=Liquidity.TAKER,
            fee_bps=4.5,
            slippage_bps=2.0,
            fill_price=99.0,
            notional_fraction=0.05,
            cost_fraction=0.0,
            snapshot_id=SHA_A,
            replica_id="r1",
        )


# --------------------------------------------------------------------------
# FreezeManifest: D2 e D4
# --------------------------------------------------------------------------


def test_d4_temperature_zero_vietata():
    with pytest.raises(ValidationError, match="D4 vieta temperature=0"):
        FreezeManifest(
            pinned_at_utc=ASOF,
            model_string="claude-sonnet-5",
            sampling_policy=SamplingPolicy.EXPLICIT,
            temperature=0.0,
            max_tokens=8000,
            system_prompt_sha=SHA_A,
            persona_sha=SHA_A,
            tool_schemas_sha=SHA_A,
            context_git_sha="0123abc",
        )


def test_api_default_omitted_non_ammette_valori_di_sampling():
    with pytest.raises(ValidationError, match="api_default_omitted"):
        FreezeManifest(
            pinned_at_utc=ASOF,
            model_string="claude-sonnet-5",
            sampling_policy=SamplingPolicy.API_DEFAULT_OMITTED,
            temperature=0.7,
            max_tokens=8000,
            system_prompt_sha=SHA_A,
            persona_sha=SHA_A,
            tool_schemas_sha=SHA_A,
            context_git_sha="0123abc",
        )


def test_explicit_richiede_una_temperatura():
    with pytest.raises(ValidationError, match="richiede una temperatura"):
        FreezeManifest(
            pinned_at_utc=ASOF,
            model_string="claude-sonnet-5",
            sampling_policy=SamplingPolicy.EXPLICIT,
            max_tokens=8000,
            system_prompt_sha=SHA_A,
            persona_sha=SHA_A,
            tool_schemas_sha=SHA_A,
            context_git_sha="0123abc",
        )


def test_ots_pending_incoerente_rifiutato():
    with pytest.raises(ValidationError, match="ots_pending"):
        FreezeManifest(
            pinned_at_utc=ASOF,
            model_string="claude-sonnet-5",
            sampling_policy=SamplingPolicy.API_DEFAULT_OMITTED,
            max_tokens=8000,
            system_prompt_sha=SHA_A,
            persona_sha=SHA_A,
            tool_schemas_sha=SHA_A,
            context_git_sha="0123abc",
            ots_pending=True,
            ots_proof_path="prova.ots",
        )


def test_freeze_id_cambia_col_modello():
    a = make_manifest()
    b = a.model_copy(update={"model_string": "claude-sonnet-4-5-20250929"})
    assert a.freeze_id != b.freeze_id


def test_freeze_id_ignora_lo_stato_ots():
    a = make_manifest()
    b = a.model_copy(update={"ots_pending": False, "ots_proof_path": "p.ots"})
    assert a.freeze_id == b.freeze_id


# --------------------------------------------------------------------------
# OutcomeAnnotation (compilato in Stagione 0, qui solo collaudato)
# --------------------------------------------------------------------------


def test_outcome_round_trip():
    out = OutcomeAnnotation(
        decision_ref="2026-08-12/r1/BTC",
        asset="BTC",
        replica_id="r1",
        annotated_at_utc=ASOF,
        pnl_fraction=0.012,
        mfe_fraction=0.03,
        mae_fraction=-0.01,
        price_at_decision=60_000.0,
        price_plus_1d=60_500.0,
        invalidation_triggered=False,
    )
    assert OutcomeAnnotation.model_validate(json.loads(out.model_dump_json())) == out


def test_mae_positivo_rifiutato():
    with pytest.raises(ValidationError):
        OutcomeAnnotation(
            decision_ref="x",
            asset="BTC",
            replica_id="r1",
            annotated_at_utc=ASOF,
            pnl_fraction=0.0,
            mfe_fraction=0.0,
            mae_fraction=0.5,
            price_at_decision=1.0,
        )


# --------------------------------------------------------------------------
# Hashing canonico
# --------------------------------------------------------------------------


def test_canonical_json_indipendente_dall_ordine_delle_chiavi():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_sha256_stabile():
    assert sha256_of({"a": 1}) == sha256_of({"a": 1})
    assert sha256_of({"a": 1}) != sha256_of({"a": 2})


def test_canonical_json_rifiuta_nan():
    with pytest.raises(ValueError):
        canonical_json({"a": float("nan")})
