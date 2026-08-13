"""Blocco 6 — scheletro della suite di regressione, collaudato con mock."""

from __future__ import annotations

import pytest

from contracts.decision import Action
from arena import regression as reg
from arena.regression import (
    AGREEMENT_ALARM_DROP,
    AGREEMENT_ALARM_FLOOR,
    AGREEMENT_SUNSET_DROP,
    AGREEMENT_SUNSET_FLOOR,
    CONFIDENCE_ALARM_DISTANCE,
    CONFIDENCE_SUNSET_DISTANCE,
    MAX_FROZEN_SNAPSHOTS,
    MIN_FROZEN_SNAPSHOTS,
    SAMPLES_PER_SNAPSHOT,
    BehavioralRegressionSuite,
    DecisionSnapshotRef,
    DriftThresholds,
    DriftVerdict,
    RegressionError,
    SuiteAlreadyFrozen,
    ThresholdRuleChanged,
    ThresholdsNotSet,
    threshold_rule_fingerprint,
    thresholds_from_baseline,
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


def _baseline_con(suite, *, actions):
    """Baseline sintetica con una sequenza di azioni dichiarata."""
    from arena.regression import Baseline, BaselineEntry

    sid = make_snapshot().snapshot_id
    return Baseline(
        collected_at_utc=__import__("datetime").datetime.now(
            tz=__import__("datetime").timezone.utc
        ),
        freeze_id="f" * 64,
        model_string="claude-fable-5",
        samples_per_snapshot=len(actions),
        entries=(
            BaselineEntry(
                ref=DecisionSnapshotRef(snapshot_id=sid, asset="BTC"),
                actions=tuple(actions),
                confidences=tuple(0.6 for _ in actions),
            ),
        ),
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
# TL-002: la regola precede la baseline, i valori assoluti la seguono
# --------------------------------------------------------------------------


def test_la_baseline_si_raccoglie_senza_soglie_assolute(tmp_path, refs):
    """TL-002: le soglie si DERIVANO dalla baseline, quindi non precedono."""
    suite = BehavioralRegressionSuite(tmp_path / "r" / "set.json")
    suite.freeze(refs)
    assert not suite.thresholds.is_set
    baseline = suite.collect_baseline(
        _source(), freeze_id="f" * 64, model_string="claude-fable-5"
    )
    # Cio' che deve precedere e' la REGOLA, e la baseline ne incide l'impronta.
    assert baseline.threshold_rule_sha == threshold_rule_fingerprint()


def test_soglie_non_fissate_bloccano_il_verdetto(tmp_path, refs, suite):
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(), freeze_id="f" * 64, model_string="claude-fable-5"
    )
    report = suite.measure(baseline, _source(), model_string="claude-fable-5")

    senza_soglie = BehavioralRegressionSuite(suite.path)
    with pytest.raises(ThresholdsNotSet, match="soglie assolute non derivate"):
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
        _source(), freeze_id="f" * 64, model_string="claude-fable-5"
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
        source, freeze_id="f" * 64, model_string="claude-fable-5"
    )
    report = suite.evaluate(
        suite.measure(baseline, source, model_string="claude-fable-5")
    )
    assert report.action_agreement_rate == pytest.approx(1.0)
    assert report.mean_confidence_distance == pytest.approx(0.0)
    assert report.verdict is DriftVerdict.OK
    assert not report.triggers_sunset


def test_azione_completamente_cambiata_scatena_il_sunset(suite, refs):
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(action=Action.LONG), freeze_id="f" * 64, model_string="claude-fable-5"
    )
    report = suite.evaluate(
        suite.measure(
            baseline,
            _source(action=Action.FLAT, confidence=0.6),
            model_string="claude-fable-5",
        )
    )
    assert report.action_agreement_rate == pytest.approx(0.0)
    assert report.verdict is DriftVerdict.SUNSET
    assert report.triggers_sunset
    assert "il track record si chiude qui" in report.detail


def test_deriva_solo_sulla_confidence_scatena_l_allarme(suite, refs):
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(confidence=0.60), freeze_id="f" * 64, model_string="claude-fable-5"
    )
    report = suite.evaluate(
        suite.measure(
            baseline, _source(confidence=0.75), model_string="claude-fable-5"
        )
    )
    assert report.action_agreement_rate == pytest.approx(1.0)
    assert report.mean_confidence_distance == pytest.approx(0.15)
    assert report.verdict is DriftVerdict.ALARM


def test_deriva_forte_sulla_confidence_scatena_il_sunset(suite, refs):
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(confidence=0.50), freeze_id="f" * 64, model_string="claude-fable-5"
    )
    report = suite.evaluate(
        suite.measure(
            baseline, _source(confidence=0.85), model_string="claude-fable-5"
        )
    )
    assert report.verdict is DriftVerdict.SUNSET


def test_verbali_malformati_contano_come_disaccordo(suite, refs):
    """Un modello che smette di rispettare il protocollo È derivato."""
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(), freeze_id="f" * 64, model_string="claude-fable-5"
    )
    report = suite.measure(
        baseline, _source(malformed_indexes={0, 1}), model_string="claude-fable-5"
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
            model_string="claude-fable-5",
        )


def test_il_report_traccia_baseline_e_modello(suite, refs):
    suite.freeze(refs)
    source = _source()
    baseline = suite.collect_baseline(
        source, freeze_id="f" * 64, model_string="claude-fable-5"
    )
    report = suite.measure(baseline, source, model_string="claude-fable-5")
    assert report.baseline_id == baseline.baseline_id
    assert report.model_string == "claude-fable-5"
    assert len(report.per_snapshot) == MIN_FROZEN_SNAPSHOTS


# --------------------------------------------------------------------------
# Parametri dichiarati ORA
# --------------------------------------------------------------------------


def test_parametri_dichiarati_prima_della_baseline():
    assert (MIN_FROZEN_SNAPSHOTS, MAX_FROZEN_SNAPSHOTS) == (10, 15)
    assert SAMPLES_PER_SNAPSHOT == 5


# --------------------------------------------------------------------------
# TL-002 — la regola delle soglie
# --------------------------------------------------------------------------


def test_costanti_della_regola_tl002():
    assert (AGREEMENT_ALARM_DROP, AGREEMENT_ALARM_FLOOR) == (0.15, 0.70)
    assert (AGREEMENT_SUNSET_DROP, AGREEMENT_SUNSET_FLOOR) == (0.30, 0.50)
    assert (CONFIDENCE_ALARM_DISTANCE, CONFIDENCE_SUNSET_DISTANCE) == (0.10, 0.20)


def test_regola_applicata_senza_pavimento():
    """Baseline alta: la regola grezza domina."""
    d = thresholds_from_baseline(1.0)
    assert d.thresholds.agreement_alarm == pytest.approx(0.85)
    assert d.thresholds.agreement_sunset == pytest.approx(0.70)
    assert d.thresholds.confidence_alarm == pytest.approx(0.10)
    assert d.thresholds.confidence_sunset == pytest.approx(0.20)
    assert not d.floor_binds
    assert not d.is_degenerate


def test_il_pavimento_morde_su_baseline_intermedia():
    """Con baseline 0.80 il pavimento 0.70 e' piu' severo di 0.80-0.15."""
    d = thresholds_from_baseline(0.80)
    assert d.thresholds.agreement_alarm == pytest.approx(0.70)
    assert d.thresholds.agreement_sunset == pytest.approx(0.50)
    assert d.floor_binds
    assert not d.is_degenerate


def test_baseline_troppo_rumorosa_e_segnalata_come_degenere():
    """Se il pavimento supera la baseline, la suite allarmerebbe subito."""
    d = thresholds_from_baseline(0.65)
    assert d.is_degenerate
    assert "troppo poco consistente" in d.detail


@pytest.mark.parametrize("baseline", [0.0, 0.25, 0.5, 0.6, 0.7, 0.85, 0.95, 1.0])
def test_le_soglie_derivate_sono_sempre_coerenti(baseline):
    """Sunset mai meno severo di alarm, su tutto il dominio."""
    d = thresholds_from_baseline(baseline)
    assert d.thresholds.agreement_sunset <= d.thresholds.agreement_alarm
    assert d.thresholds.is_set


def test_baseline_fuori_dominio_rifiutata():
    with pytest.raises(ValueError):
        thresholds_from_baseline(1.5)


def test_auto_accordo_della_baseline():
    """Con un modello deterministico l'auto-accordo e' 1.0."""
    suite = BehavioralRegressionSuite("x", thresholds=SOGLIE)
    baseline = _baseline_con(suite, actions=["long"] * 5)
    assert baseline.self_agreement_rate == pytest.approx(1.0)

    misto = _baseline_con(suite, actions=["long", "long", "long", "flat", "flat"])
    assert misto.self_agreement_rate == pytest.approx(0.6)


def test_derivazione_end_to_end_dalla_baseline(suite, refs):
    suite.freeze(refs)
    baseline = suite.collect_baseline(
        _source(), freeze_id="f" * 64, model_string="claude-fable-5"
    )
    derivazione = suite.derive_thresholds(baseline)
    assert derivazione.baseline_agreement == pytest.approx(1.0)
    assert derivazione.thresholds.agreement_alarm == pytest.approx(0.85)
    assert "REGRESSION_THRESHOLDS" in derivazione.as_config_literal()
    assert "0.8500" in derivazione.as_config_literal()


def test_regola_cambiata_dopo_la_baseline_blocca_il_verdetto(suite, refs, monkeypatch):
    """Soglie riscritte dopo aver visto i dati non sono pre-registrate."""
    suite.freeze(refs)
    source = _source()
    baseline = suite.collect_baseline(
        source, freeze_id="f" * 64, model_string="claude-fable-5"
    )
    report = suite.measure(baseline, source, model_string="claude-fable-5")

    # Senza baseline il verdetto passa: e' il confronto che fa la verifica.
    assert suite.evaluate(report).verdict is DriftVerdict.OK

    monkeypatch.setattr(reg, "AGREEMENT_ALARM_DROP", 0.40)
    with pytest.raises(ThresholdRuleChanged, match="cambiata"):
        suite.evaluate(report, baseline=baseline)


def test_impronta_della_regola_stabile():
    assert threshold_rule_fingerprint() == threshold_rule_fingerprint()
    assert len(threshold_rule_fingerprint()) == 64
