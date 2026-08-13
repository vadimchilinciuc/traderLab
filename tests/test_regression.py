"""Blocco 6 — scheletro della suite di regressione, collaudato con mock."""

from __future__ import annotations

import pytest

from contracts.decision import Action
from arena.regression import (
    MAX_FROZEN_SNAPSHOTS,
    MIN_FROZEN_SNAPSHOTS,
    SAMPLES_PER_SNAPSHOT,
    BehavioralRegressionSuite,
    DecisionSnapshotRef,
    DriftThresholds,
    DriftVerdict,
    RegressionError,
    SuiteAlreadyFrozen,
    ThresholdsNotSet,
)
from tests.factories import make_decision, make_snapshot

SOGLIE = DriftThresholds(
    agreement_alarm=0.85,
    agreement_sunset=0.60,
    confidence_alarm=0.10,
    confidence_sunset=0.25,
)


@pytest.fixture
def refs():
    sid = make_snapshot().snapshot_id
    return [
        DecisionSnapshotRef(snapshot_id=sid, asset=f"SYM{i}")
        for i in range(MIN_FROZEN_SNAPSHOTS)
    ]


@pytest.fixture
def suite(tmp_path):
    return BehavioralRegressionSuite(
        tmp_path / "regression" / "set.json", thresholds=SOGLIE
    )


def _source(action=Action.LONG, confidence=0.6, malformed_indexes=()):
    sid = make_snapshot().snapshot_id

    def source(ref, index):
        if index in malformed_indexes:
            return None
        return make_decision(
            sid,
            asset=ref.asset,
            action=action,
            size_fraction=0.05 if action in (Action.LONG, Action.SHORT) else 0.0,
            confidence=confidence,
        )

    return source


# --------------------------------------------------------------------------
# Il set si congela una volta e mai più
# --------------------------------------------------------------------------


def test_congelamento_del_set(suite, refs):
    assert not suite.is_frozen()
    suite.freeze(refs)
    assert suite.is_frozen()
    assert len(suite.refs()) == MIN_FROZEN_SNAPSHOTS


def test_ricongelare_e_vietato(suite, refs):
    suite.freeze(refs)
    with pytest.raises(SuiteAlreadyFrozen, match="una volta e mai più"):
        suite.freeze(refs)


def test_cardinalita_del_set_vincolata(suite, refs):
    with pytest.raises(RegressionError, match=f"da {MIN_FROZEN_SNAPSHOTS}"):
        suite.freeze(refs[:3])
    with pytest.raises(RegressionError):
        suite.freeze(refs * 3)


def test_riferimenti_duplicati_rifiutati(suite, refs):
    with pytest.raises(RegressionError, match="duplicati"):
        suite.freeze([refs[0]] * MIN_FROZEN_SNAPSHOTS)


def test_refs_senza_set_congelato_solleva(suite):
    with pytest.raises(RegressionError, match="nessun set congelato"):
        suite.refs()


# --------------------------------------------------------------------------
# Le soglie sono TODO-owner: senza, non si misura e non si giudica
# --------------------------------------------------------------------------


def test_soglie_non_fissate_bloccano_la_baseline(tmp_path, refs):
    suite = BehavioralRegressionSuite(tmp_path / "r" / "set.json")
    suite.freeze(refs)
    assert not suite.thresholds.is_set
    with pytest.raises(ThresholdsNotSet, match="PRIMA della baseline"):
        suite.collect_baseline(_source(), freeze_id="f" * 64, model_string="m")


def test_soglie_non_fissate_bloccano_il_verdetto(tmp_path, refs, suite):
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(), freeze_id="f" * 64, model_string="claude-sonnet-5"
    )
    report = suite.measure(baseline, _source(), model_string="claude-sonnet-5")

    senza_soglie = BehavioralRegressionSuite(suite.path)
    with pytest.raises(ThresholdsNotSet, match="TODO-owner"):
        senza_soglie.evaluate(report)


def test_soglie_incoerenti_rifiutate():
    with pytest.raises(ValueError, match="sunset sull'agreement"):
        DriftThresholds(agreement_alarm=0.60, agreement_sunset=0.85)
    with pytest.raises(ValueError, match="sunset sulla confidence"):
        DriftThresholds(confidence_alarm=0.30, confidence_sunset=0.10)


def test_elenco_delle_soglie_mancanti():
    parziali = DriftThresholds(agreement_alarm=0.85)
    assert not parziali.is_set
    assert "agreement_sunset" in parziali.missing()
    assert "agreement_alarm" not in parziali.missing()


# --------------------------------------------------------------------------
# Baseline e misura della deriva
# --------------------------------------------------------------------------


def test_baseline_raccoglie_k_campioni_per_snapshot(suite, refs):
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(), freeze_id="f" * 64, model_string="claude-sonnet-5"
    )
    assert len(baseline.entries) == MIN_FROZEN_SNAPSHOTS
    assert baseline.samples_per_snapshot == SAMPLES_PER_SNAPSHOT
    for entry in baseline.entries:
        assert len(entry.actions) == SAMPLES_PER_SNAPSHOT
        assert entry.modal_action == "long"
    assert len(baseline.baseline_id) == 64


def test_nessuna_deriva_se_il_comportamento_e_identico(suite, refs):
    suite.freeze(refs)
    source = _source()
    baseline = suite.collect_baseline(
        source, freeze_id="f" * 64, model_string="claude-sonnet-5"
    )
    report = suite.evaluate(
        suite.measure(baseline, source, model_string="claude-sonnet-5")
    )
    assert report.action_agreement_rate == pytest.approx(1.0)
    assert report.mean_confidence_distance == pytest.approx(0.0)
    assert report.verdict is DriftVerdict.OK
    assert not report.triggers_sunset


def test_azione_completamente_cambiata_scatena_il_sunset(suite, refs):
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(action=Action.LONG), freeze_id="f" * 64, model_string="claude-sonnet-5"
    )
    report = suite.evaluate(
        suite.measure(
            baseline,
            _source(action=Action.FLAT, confidence=0.6),
            model_string="claude-sonnet-5",
        )
    )
    assert report.action_agreement_rate == pytest.approx(0.0)
    assert report.verdict is DriftVerdict.SUNSET
    assert report.triggers_sunset
    assert "il track record si chiude qui" in report.detail


def test_deriva_solo_sulla_confidence_scatena_l_allarme(suite, refs):
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(confidence=0.60), freeze_id="f" * 64, model_string="claude-sonnet-5"
    )
    report = suite.evaluate(
        suite.measure(
            baseline, _source(confidence=0.75), model_string="claude-sonnet-5"
        )
    )
    assert report.action_agreement_rate == pytest.approx(1.0)
    assert report.mean_confidence_distance == pytest.approx(0.15)
    assert report.verdict is DriftVerdict.ALARM


def test_deriva_forte_sulla_confidence_scatena_il_sunset(suite, refs):
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(confidence=0.50), freeze_id="f" * 64, model_string="claude-sonnet-5"
    )
    report = suite.evaluate(
        suite.measure(
            baseline, _source(confidence=0.85), model_string="claude-sonnet-5"
        )
    )
    assert report.verdict is DriftVerdict.SUNSET


def test_verbali_malformati_contano_come_disaccordo(suite, refs):
    """Un modello che smette di rispettare il protocollo È derivato."""
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(), freeze_id="f" * 64, model_string="claude-sonnet-5"
    )
    report = suite.measure(
        baseline, _source(malformed_indexes={0, 1}), model_string="claude-sonnet-5"
    )
    assert report.action_agreement_rate == pytest.approx(3 / SAMPLES_PER_SNAPSHOT)
    for drift in report.per_snapshot:
        assert drift.malformed == 2
        assert drift.samples == 3


def test_baseline_impossibile_se_nessun_campione_e_valido(suite, refs):
    suite.freeze(refs)
    with pytest.raises(RegressionError, match="baseline non raccoglibile"):
        suite.collect_baseline(
            _source(malformed_indexes=set(range(SAMPLES_PER_SNAPSHOT))),
            freeze_id="f" * 64,
            model_string="claude-sonnet-5",
        )


def test_il_report_traccia_baseline_e_modello(suite, refs):
    suite.freeze(refs)
    source = _source()
    baseline = suite.collect_baseline(
        source, freeze_id="f" * 64, model_string="claude-sonnet-5"
    )
    report = suite.measure(baseline, source, model_string="claude-sonnet-5")
    assert report.baseline_id == baseline.baseline_id
    assert report.model_string == "claude-sonnet-5"
    assert len(report.per_snapshot) == MIN_FROZEN_SNAPSHOTS


# --------------------------------------------------------------------------
# Parametri dichiarati ORA
# --------------------------------------------------------------------------


def test_parametri_dichiarati_prima_della_baseline():
    assert (MIN_FROZEN_SNAPSHOTS, MAX_FROZEN_SNAPSHOTS) == (10, 15)
    assert SAMPLES_PER_SNAPSHOT == 5
