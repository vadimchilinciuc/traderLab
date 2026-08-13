"""Blocco 4 — integrità della catena, telemetria, e-process su casi noti."""

from __future__ import annotations

import json
import random
from datetime import timedelta

import pytest

from contracts.decision import Action
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict
from ledger.eprocess import (
    BettingEProcess,
    KillCriterionConfig,
    KillVerdict,
    evaluate_kill_criterion,
)
from ledger.telemetry import (
    BehavioralTelemetry,
    BrierAccumulator,
    daily_dispersion,
)
from ledger.trader_ledger import (
    GENESIS_HASH,
    DuplicateEntry,
    LedgerKey,
    TraderLedger,
)
from tests.factories import ASOF, make_decision, make_snapshot


def _verdict(
    outcome=RiskOutcome.APPROVED,
    rule=RiskRule.NONE,
    action=Action.LONG,
    size_in=0.05,
    size_out=0.05,
):
    return RiskVerdict(
        outcome=outcome,
        rule=rule,
        action_in=action,
        action_out=Action.FLAT if outcome is RiskOutcome.REJECTED else action,
        size_fraction_in=size_in,
        size_fraction_out=0.0 if outcome is RiskOutcome.REJECTED else size_out,
    )


@pytest.fixture
def ledger(tmp_path) -> TraderLedger:
    return TraderLedger(tmp_path / "ledger" / "s0.jsonl")


@pytest.fixture
def snapshot():
    return make_snapshot()


# --------------------------------------------------------------------------
# Hash-chain
# --------------------------------------------------------------------------


def test_ledger_vuoto_parte_dal_genesis(ledger):
    assert len(ledger) == 0
    assert ledger.head_hash == GENESIS_HASH
    assert ledger.verify().ok


def test_catena_verifica_dopo_piu_scritture(ledger, snapshot):
    for i, asset in enumerate(("BTC", "ETH")):
        ledger.append(
            key=LedgerKey.of(ASOF, "r1", asset),
            verdict=_verdict(),
            decision=make_decision(snapshot.snapshot_id, asset=asset),
            snapshot_id=snapshot.snapshot_id,
            run_id="run-1",
        )
    result = ledger.verify()
    assert result.ok
    assert result.entries_checked == 2


def test_ogni_riga_incatena_la_precedente(ledger, snapshot):
    first = ledger.append(
        key=LedgerKey.of(ASOF, "r1", "BTC"),
        verdict=_verdict(),
        decision=make_decision(snapshot.snapshot_id),
        snapshot_id=snapshot.snapshot_id,
        run_id="run-1",
    )
    second = ledger.append(
        key=LedgerKey.of(ASOF, "r1", "ETH"),
        verdict=_verdict(),
        decision=make_decision(snapshot.snapshot_id, asset="ETH"),
        snapshot_id=snapshot.snapshot_id,
        run_id="run-1",
    )
    assert first["prev_hash"] == GENESIS_HASH
    assert second["prev_hash"] == first["entry_hash"]


def test_manomissione_del_contenuto_rompe_la_catena(ledger, snapshot):
    for asset in ("BTC", "ETH"):
        ledger.append(
            key=LedgerKey.of(ASOF, "r1", asset),
            verdict=_verdict(),
            decision=make_decision(snapshot.snapshot_id, asset=asset),
            snapshot_id=snapshot.snapshot_id,
            run_id="run-1",
        )
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["verdict"]["size_fraction_out"] = 0.99
    lines[0] = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = TraderLedger(ledger.path).verify()
    assert not result.ok
    assert result.broken_at == 0
    assert "contenuto alterato" in result.detail


def test_rimozione_di_una_riga_rompe_la_catena(ledger, snapshot):
    for asset in ("BTC", "ETH"):
        ledger.append(
            key=LedgerKey.of(ASOF, "r1", asset),
            verdict=_verdict(),
            decision=make_decision(snapshot.snapshot_id, asset=asset),
            snapshot_id=snapshot.snapshot_id,
            run_id="run-1",
        )
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    ledger.path.write_text(lines[1] + "\n", encoding="utf-8")
    result = TraderLedger(ledger.path).verify()
    assert not result.ok
    assert result.broken_at == 0


def test_ledger_riapre_e_continua_la_catena(ledger, snapshot):
    ledger.append(
        key=LedgerKey.of(ASOF, "r1", "BTC"),
        verdict=_verdict(),
        decision=make_decision(snapshot.snapshot_id),
        snapshot_id=snapshot.snapshot_id,
        run_id="run-1",
    )
    riaperto = TraderLedger(ledger.path)
    assert len(riaperto) == 1
    riaperto.append(
        key=LedgerKey.of(ASOF, "r1", "ETH"),
        verdict=_verdict(),
        decision=make_decision(snapshot.snapshot_id, asset="ETH"),
        snapshot_id=snapshot.snapshot_id,
        run_id="run-2",
    )
    assert riaperto.verify().ok
    assert len(riaperto) == 2


# --------------------------------------------------------------------------
# Write-once per (giorno, replica, asset)
# --------------------------------------------------------------------------


def test_write_once_sulla_stessa_chiave(ledger, snapshot):
    key = LedgerKey.of(ASOF, "r1", "BTC")
    ledger.append(
        key=key,
        verdict=_verdict(),
        decision=make_decision(snapshot.snapshot_id),
        snapshot_id=snapshot.snapshot_id,
        run_id="run-1",
    )
    with pytest.raises(DuplicateEntry, match="write-once"):
        ledger.append(
            key=key,
            verdict=_verdict(),
            decision=make_decision(snapshot.snapshot_id),
            snapshot_id=snapshot.snapshot_id,
            run_id="run-1",
        )


def test_stesso_asset_replica_diversa_e_ammesso(ledger, snapshot):
    for replica in ("r1", "r2", "r3"):
        ledger.append(
            key=LedgerKey.of(ASOF, replica, "BTC"),
            verdict=_verdict(),
            decision=make_decision(snapshot.snapshot_id, replica_id=replica),
            snapshot_id=snapshot.snapshot_id,
            run_id="run-1",
        )
    assert len(ledger) == 3


def test_stesso_asset_giorno_diverso_e_ammesso(ledger, snapshot):
    for offset in (0, 1):
        ledger.append(
            key=LedgerKey.of(ASOF + timedelta(days=offset), "r1", "BTC"),
            verdict=_verdict(),
            decision=make_decision(snapshot.snapshot_id),
            snapshot_id=snapshot.snapshot_id,
            run_id="run-1",
        )
    assert len(ledger) == 2


def test_write_once_persiste_tra_riaperture(ledger, snapshot):
    key = LedgerKey.of(ASOF, "r1", "BTC")
    ledger.append(
        key=key,
        verdict=_verdict(),
        decision=make_decision(snapshot.snapshot_id),
        snapshot_id=snapshot.snapshot_id,
        run_id="run-1",
    )
    with pytest.raises(DuplicateEntry):
        TraderLedger(ledger.path).append(
            key=key,
            verdict=_verdict(),
            decision=make_decision(snapshot.snapshot_id),
            snapshot_id=snapshot.snapshot_id,
            run_id="run-2",
        )


def test_una_riga_malformata_non_porta_decisione(ledger):
    ledger.append(
        key=LedgerKey.of(ASOF, "r1", "BTC"),
        verdict=_verdict(outcome=RiskOutcome.REJECTED, rule=RiskRule.MALFORMED_VERBALE),
        decision=None,
        malformed_reason="no_rationale_before_structured_block",
        snapshot_id="a" * 64,
        run_id="run-1",
    )
    entry = ledger.read_all()[0]
    assert entry["decision"] is None
    assert entry["malformed_reason"] == "no_rationale_before_structured_block"
    assert ledger.verify().ok


# --------------------------------------------------------------------------
# Telemetria
# --------------------------------------------------------------------------


def test_turnover_e_flip_rate(snapshot):
    tel = BehavioralTelemetry(["r1"])
    sid = snapshot.snapshot_id
    tel.observe_decision(
        make_decision(sid, action=Action.LONG, size_fraction=0.05), _verdict()
    )
    tel.observe_decision(
        make_decision(sid, action=Action.SHORT, size_fraction=0.05),
        _verdict(action=Action.SHORT),
    )
    m = tel.metrics("r1")
    assert m.decisions_total == 2
    assert m.flips == 1
    assert m.flip_rate == pytest.approx(1.0)
    # 0 -> +0.05 -> -0.05 : 0.05 + 0.10
    assert m.turnover == pytest.approx(0.15)


def test_nessun_flip_se_la_direzione_resta(snapshot):
    tel = BehavioralTelemetry(["r1"])
    for _ in range(3):
        tel.observe_decision(
            make_decision(snapshot.snapshot_id, action=Action.LONG), _verdict()
        )
    assert tel.metrics("r1").flips == 0


def test_conteggio_dei_tentativi_bloccati(snapshot):
    tel = BehavioralTelemetry(["r1"])
    tel.observe_decision(
        make_decision(snapshot.snapshot_id, size_fraction=0.4),
        _verdict(
            outcome=RiskOutcome.CLAMPED,
            rule=RiskRule.FIXED_SIZE_SEASON_0,
            size_in=0.4,
            size_out=0.05,
        ),
    )
    tel.observe_decision(
        make_decision(snapshot.snapshot_id, asset="ETH"),
        _verdict(outcome=RiskOutcome.REJECTED, rule=RiskRule.LEVERAGE_CAP),
    )
    m = tel.metrics("r1")
    assert m.clamped_total == 1
    assert m.blocked_by_rule["fixed_size_season_0"] == 1
    assert m.blocked_by_rule["leverage_cap"] == 1
    assert m.blocked_attempts == 2


def test_tasso_di_verbali_malformati():
    tel = BehavioralTelemetry(["r1"])
    tel.observe_malformed(
        "r1", _verdict(outcome=RiskOutcome.REJECTED, rule=RiskRule.MALFORMED_VERBALE)
    )
    tel.observe_decision(make_decision(make_snapshot().snapshot_id), _verdict())
    m = tel.metrics("r1")
    assert m.malformed_total == 1
    assert m.malformed_rate == pytest.approx(0.5)


def test_confidence_media_registrata_dal_giorno_uno(snapshot):
    tel = BehavioralTelemetry(["r1"])
    for c in (0.4, 0.6):
        tel.observe_decision(
            make_decision(snapshot.snapshot_id, confidence=c), _verdict()
        )
    assert tel.metrics("r1").mean_confidence == pytest.approx(0.5)


def test_brier_vuoto_in_fase_0(snapshot):
    tel = BehavioralTelemetry(["r1"])
    tel.observe_decision(make_decision(snapshot.snapshot_id), _verdict())
    brier = tel.metrics("r1").brier
    assert brier.n == 0
    assert brier.brier_score is None


def test_brier_previsione_perfetta():
    acc = BrierAccumulator()
    for _ in range(10):
        acc.add(1.0, 1)
        acc.add(0.0, 0)
    comp = acc.components()
    assert comp.brier_score == pytest.approx(0.0)
    assert comp.reliability == pytest.approx(0.0)


def test_brier_previsione_non_informativa():
    acc = BrierAccumulator()
    for i in range(100):
        acc.add(0.5, i % 2)
    comp = acc.components()
    assert comp.brier_score == pytest.approx(0.25)
    assert comp.resolution == pytest.approx(0.0)
    assert comp.uncertainty == pytest.approx(0.25)


def test_brier_decomposizione_di_murphy():
    rng = random.Random(7)
    acc = BrierAccumulator()
    for _ in range(2000):
        p = rng.choice([0.1, 0.3, 0.5, 0.7, 0.9])
        acc.add(p, 1 if rng.random() < p else 0)
    c = acc.components()
    assert c.brier_score == pytest.approx(
        c.reliability - c.resolution + c.uncertainty, abs=1e-9
    )


def test_brier_rifiuta_input_invalidi():
    acc = BrierAccumulator()
    with pytest.raises(ValueError):
        acc.add(1.5, 1)
    with pytest.raises(ValueError):
        acc.add(0.5, 2)


# --------------------------------------------------------------------------
# Dispersione inter-repliche
# --------------------------------------------------------------------------


def test_dispersione_nulla_se_le_repliche_concordano(snapshot):
    sid = snapshot.snapshot_id
    by_replica = {
        rid: {"BTC": make_decision(sid, replica_id=rid, confidence=0.6)}
        for rid in ("r1", "r2", "r3")
    }
    d = daily_dispersion(by_replica)
    assert d.replicas == 3
    assert d.assets_compared == 1
    assert d.action_disagreement == pytest.approx(0.0)
    assert d.confidence_dispersion == pytest.approx(0.0)


def test_dispersione_massima_su_azioni_tutte_diverse(snapshot):
    sid = snapshot.snapshot_id
    by_replica = {
        "r1": {"BTC": make_decision(sid, replica_id="r1", action=Action.LONG)},
        "r2": {
            "BTC": make_decision(
                sid, replica_id="r2", action=Action.SHORT, size_fraction=0.05
            )
        },
        "r3": {
            "BTC": make_decision(
                sid, replica_id="r3", action=Action.FLAT, size_fraction=0.0
            )
        },
    }
    d = daily_dispersion(by_replica)
    assert d.action_disagreement == pytest.approx(1.0)
    assert d.size_dispersion > 0.0


def test_dispersione_su_confidence(snapshot):
    sid = snapshot.snapshot_id
    by_replica = {
        "r1": {"BTC": make_decision(sid, replica_id="r1", confidence=0.2)},
        "r2": {"BTC": make_decision(sid, replica_id="r2", confidence=0.8)},
    }
    assert daily_dispersion(by_replica).confidence_dispersion == pytest.approx(0.6)


def test_dispersione_confronta_solo_asset_comuni(snapshot):
    sid = snapshot.snapshot_id
    by_replica = {
        "r1": {
            "BTC": make_decision(sid, replica_id="r1"),
            "ETH": make_decision(sid, replica_id="r1", asset="ETH"),
        },
        "r2": {"BTC": make_decision(sid, replica_id="r2")},
    }
    assert daily_dispersion(by_replica).assets_compared == 1


def test_dispersione_degenere_con_una_sola_replica(snapshot):
    by_replica = {"r1": {"BTC": make_decision(snapshot.snapshot_id)}}
    assert daily_dispersion(by_replica).is_degenerate


# --------------------------------------------------------------------------
# E-process su casi sintetici noti
# --------------------------------------------------------------------------


def test_eprocess_sotto_il_nullo_non_produce_evidenza():
    """Differenze simmetriche attorno a zero: nessuna evidenza accumulata."""
    rng = random.Random(11)
    proc = BettingEProcess(bound=1.0, alpha=0.05)
    for _ in range(500):
        proc.update(rng.gauss(0.0, 0.2))
    assert not proc.rejected
    assert proc.max_e_value < proc.threshold


def test_eprocess_nullo_e_conservativo_su_molte_ripetizioni():
    """Falsi positivi ben sotto alpha: la garanzia anytime-valid tiene."""
    falsi_positivi = 0
    ripetizioni = 200
    for seed in range(ripetizioni):
        rng = random.Random(seed)
        proc = BettingEProcess(bound=1.0, alpha=0.05)
        for _ in range(200):
            proc.update(rng.gauss(0.0, 0.3))
        if proc.rejected:
            falsi_positivi += 1
    assert falsi_positivi / ripetizioni <= 0.05


def test_eprocess_con_effetto_accumula_evidenza():
    """Differenze sistematicamente positive: l'e-value cresce e rifiuta."""
    rng = random.Random(3)
    proc = BettingEProcess(bound=1.0, alpha=0.05)
    for _ in range(300):
        proc.update(0.25 + rng.gauss(0.0, 0.1))
    assert proc.rejected
    assert proc.max_e_value >= proc.threshold


def test_eprocess_evidenza_monotona_con_effetto_costante():
    proc = BettingEProcess(bound=1.0)
    valori = [proc.update(0.3) for _ in range(50)]
    assert valori[-1] > valori[10] > valori[0]


def test_eprocess_effetto_negativo_non_rifiuta():
    """Un agente peggiore della macchina non deve produrre evidenza a favore.

    È la proprietà che distingue il test unilaterale da quello bilaterale:
    H0 è "differenza <= 0", non "differenza = 0".
    """
    rng = random.Random(5)
    proc = BettingEProcess(bound=1.0)
    for _ in range(300):
        proc.update(-0.25 + rng.gauss(0.0, 0.1))
    assert not proc.rejected
    assert proc.e_value <= 1.0


def test_eprocess_bilaterale_rileva_anche_gli_effetti_negativi():
    """Con one_sided=False il test torna bilaterale, per confronto."""
    rng = random.Random(5)
    proc = BettingEProcess(bound=1.0, one_sided=False)
    for _ in range(300):
        proc.update(-0.25 + rng.gauss(0.0, 0.1))
    assert proc.rejected


def test_eprocess_tronca_oltre_il_bound_dichiarato():
    proc = BettingEProcess(bound=0.1)
    proc.update(5.0)
    assert proc.n_truncated == 1
    assert proc.n_observations == 1


def test_eprocess_capitale_resta_positivo_su_input_estremi():
    proc = BettingEProcess(bound=1.0)
    for value in (1.0, -1.0) * 200:
        proc.update(value)
    assert proc.e_value > 0.0
    assert not proc.rejected


def test_eprocess_config_invalida():
    with pytest.raises(ValueError):
        BettingEProcess(bound=0.0)
    with pytest.raises(ValueError):
        BettingEProcess(bound=1.0, alpha=0.0)


# --------------------------------------------------------------------------
# Kill-criterion pre-registrato
# --------------------------------------------------------------------------


def test_kill_criterion_dati_insufficienti():
    res = evaluate_kill_criterion([0.1] * 5, [0.05] * 5)
    assert res.verdict is KillVerdict.INSUFFICIENT_DATA
    assert not res.is_kill


def test_kill_criterion_dispersione_domina():
    res = evaluate_kill_criterion([0.01] * 20, [0.10] * 20)
    assert res.verdict is KillVerdict.NO_MEASURABLE_SKILL
    assert res.is_kill
    assert "no skill misurabile" in res.detail


def test_kill_criterion_segnale_supera_il_rumore():
    res = evaluate_kill_criterion([0.30] * 20, [0.02] * 20)
    assert res.verdict is KillVerdict.SIGNAL_EXCEEDS_NOISE
    assert not res.is_kill


def test_kill_criterion_usa_solo_la_finestra_dichiarata():
    gaps = [10.0] * 20 + [0.001] * 20
    disp = [0.001] * 20 + [0.5] * 20
    res = evaluate_kill_criterion(gaps, disp, KillCriterionConfig(window=20))
    assert res.verdict is KillVerdict.NO_MEASURABLE_SKILL
    assert res.window_used == 20


def test_kill_criterion_al_confine_e_kill():
    """Parità esatta conta come dominanza: il beneficio del dubbio va al kill."""
    res = evaluate_kill_criterion([0.1] * 20, [0.1] * 20)
    assert res.verdict is KillVerdict.NO_MEASURABLE_SKILL


def test_kill_criterion_config_invalida():
    with pytest.raises(ValueError):
        KillCriterionConfig(window=1)
    with pytest.raises(ValueError):
        KillCriterionConfig(dominance_ratio=0.0)
