"""Suite di regressione comportamentale — design e scheletro.

Serve a rispondere a una domanda sola: **il Trader pinnato si comporta ancora
come si comportava quando abbiamo cominciato a contare?** Un modello che deriva
sotto i piedi del track record invalida il track record, e lo fa in silenzio.

## Metrica di deriva, DICHIARATA ORA

Dichiarata **prima** di qualunque baseline, perché una metrica scelta dopo aver
visto i dati è una metrica scelta per il risultato che dà:

1. **Action agreement rate** (primaria): per ogni Decision Snapshot, la quota
   di campioni la cui `action` coincide con l'azione modale della baseline;
   poi si media sugli snapshot.
2. **Distanza assoluta media sulla confidence** (secondaria): media di
   `|confidence - confidence_media_baseline|` sui campioni, mediata sugli
   snapshot.

## Cosa NON è dichiarato qui

Le **soglie** di allarme e di sunset. Sono `TODO-owner` nel
`MILESTONE_TRACKER.md` e vanno fissate **prima** della raccolta della baseline.
`evaluate()` **solleva** se le soglie non sono state fissate: un default
silenzioso qui significherebbe scoprire la deriva quando conviene.

## Aggancio al model sunset

Deriva oltre la soglia di sunset ⇒ il track record **si chiude pulito** in quel
punto e ne inizia uno nuovo. Non si "aggiusta" un track record che ha
attraversato una deriva.

## Stato in Fase 0

Scheletro. I 10-15 Decision Snapshot REALI verranno scelti in Stagione 0, una
volta e mai più toccati; `freeze()` rifiuta di sovrascrivere un set già
congelato.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from contracts.decision import Action, DecisionRecord
from contracts.hashing import sha256_of
from toolserver.store import assert_path_allowed

# Parametri dichiarati ora (vedi MILESTONE_TRACKER.md).
MIN_FROZEN_SNAPSHOTS = 10
MAX_FROZEN_SNAPSHOTS = 15
SAMPLES_PER_SNAPSHOT = 5
CADENCE = "settimanale"


class RegressionError(Exception):
    pass


class ThresholdsNotSet(RegressionError):
    """Le soglie sono TODO-owner: vanno fissate prima della baseline."""


class SuiteAlreadyFrozen(RegressionError):
    """Il set di Decision Snapshot si congela una volta e mai più."""


class DriftVerdict(StrEnum):
    OK = "ok"
    ALARM = "alarm"
    SUNSET = "sunset"


# --------------------------------------------------------------------------
# Il set congelato
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DecisionSnapshotRef:
    """Puntatore a una situazione decisionale congelata."""

    snapshot_id: str
    asset: str

    @property
    def key(self) -> str:
        return f"{self.snapshot_id[:12]}/{self.asset}"


@dataclass(frozen=True, slots=True)
class BaselineEntry:
    """Comportamento di riferimento su un Decision Snapshot."""

    ref: DecisionSnapshotRef
    actions: tuple[str, ...]
    confidences: tuple[float, ...]

    @property
    def modal_action(self) -> str:
        return Counter(self.actions).most_common(1)[0][0]

    @property
    def mean_confidence(self) -> float:
        return sum(self.confidences) / len(self.confidences)


@dataclass(frozen=True, slots=True)
class Baseline:
    """Baseline completa, con il pin del modello a cui si riferisce."""

    collected_at_utc: datetime
    freeze_id: str
    model_string: str
    samples_per_snapshot: int
    entries: tuple[BaselineEntry, ...]

    @property
    def baseline_id(self) -> str:
        return sha256_of(
            {
                "freeze_id": self.freeze_id,
                "model_string": self.model_string,
                "entries": [
                    {
                        "snapshot_id": e.ref.snapshot_id,
                        "asset": e.ref.asset,
                        "actions": list(e.actions),
                        "confidences": list(e.confidences),
                    }
                    for e in self.entries
                ],
            }
        )


# --------------------------------------------------------------------------
# Soglie: TODO-owner
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DriftThresholds:
    """Soglie di allarme e di sunset.

    `None` significa **non ancora fissata dall'owner**, non "nessun limite".
    Vanno fissate PRIMA della raccolta della baseline.
    """

    agreement_alarm: float | None = None
    agreement_sunset: float | None = None
    confidence_alarm: float | None = None
    confidence_sunset: float | None = None

    def __post_init__(self) -> None:
        if (
            self.agreement_alarm is not None
            and self.agreement_sunset is not None
            and self.agreement_sunset > self.agreement_alarm
        ):
            raise ValueError(
                "la soglia di sunset sull'agreement deve essere più severa "
                "(più bassa) di quella di allarme"
            )
        if (
            self.confidence_alarm is not None
            and self.confidence_sunset is not None
            and self.confidence_sunset < self.confidence_alarm
        ):
            raise ValueError(
                "la soglia di sunset sulla confidence deve essere più severa "
                "(più alta) di quella di allarme"
            )

    @property
    def is_set(self) -> bool:
        return None not in (
            self.agreement_alarm,
            self.agreement_sunset,
            self.confidence_alarm,
            self.confidence_sunset,
        )

    def missing(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, value in (
                ("agreement_alarm", self.agreement_alarm),
                ("agreement_sunset", self.agreement_sunset),
                ("confidence_alarm", self.confidence_alarm),
                ("confidence_sunset", self.confidence_sunset),
            )
            if value is None
        )


# --------------------------------------------------------------------------
# Misura della deriva
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SnapshotDrift:
    ref: DecisionSnapshotRef
    agreement_rate: float
    confidence_distance: float
    samples: int
    malformed: int


@dataclass(frozen=True, slots=True)
class DriftReport:
    measured_at_utc: datetime
    baseline_id: str
    model_string: str
    per_snapshot: tuple[SnapshotDrift, ...]
    action_agreement_rate: float
    mean_confidence_distance: float
    verdict: DriftVerdict | None = None
    detail: str = ""

    @property
    def triggers_sunset(self) -> bool:
        return self.verdict is DriftVerdict.SUNSET


# Sorgente di campioni: (ref, indice_campione) -> DecisionRecord oppure None
# se il verbale è risultato malformato. In Stagione 0 sarà il runner sul
# Trader pinnato; nei test è deterministica.
SampleSource = Callable[[DecisionSnapshotRef, int], DecisionRecord | None]


class BehavioralRegressionSuite:
    """Congela i Decision Snapshot, raccoglie la baseline, misura la deriva."""

    def __init__(
        self,
        path: Path | str,
        *,
        thresholds: DriftThresholds | None = None,
        samples_per_snapshot: int = SAMPLES_PER_SNAPSHOT,
    ) -> None:
        p = Path(path)
        self.path = assert_path_allowed(p.parent) / p.name
        self.thresholds = thresholds or DriftThresholds()
        self.samples_per_snapshot = samples_per_snapshot

    # -- congelamento del set ---------------------------------------------

    def is_frozen(self) -> bool:
        return self.path.exists()

    def freeze(self, refs: Sequence[DecisionSnapshotRef]) -> None:
        """Congela il set. Una volta e mai più.

        In Stagione 0 i 10-15 snapshot si scelgono una volta; da quel momento
        il set è immutabile, altrimenti la "regressione" misura il set, non il
        modello.
        """
        if self.is_frozen():
            raise SuiteAlreadyFrozen(
                f"{self.path} esiste già: il set di Decision Snapshot si "
                f"congela una volta e mai più"
            )
        if not MIN_FROZEN_SNAPSHOTS <= len(refs) <= MAX_FROZEN_SNAPSHOTS:
            raise RegressionError(
                f"servono da {MIN_FROZEN_SNAPSHOTS} a {MAX_FROZEN_SNAPSHOTS} "
                f"Decision Snapshot, ricevuti {len(refs)}"
            )
        keys = [(r.snapshot_id, r.asset) for r in refs]
        if len(set(keys)) != len(keys):
            raise RegressionError("il set contiene riferimenti duplicati")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "frozen_at_utc": datetime.now(tz=timezone.utc).isoformat(),
                    "samples_per_snapshot": self.samples_per_snapshot,
                    "cadence": CADENCE,
                    "refs": [
                        {"snapshot_id": r.snapshot_id, "asset": r.asset} for r in refs
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def refs(self) -> tuple[DecisionSnapshotRef, ...]:
        if not self.is_frozen():
            raise RegressionError(f"nessun set congelato in {self.path}")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return tuple(
            DecisionSnapshotRef(snapshot_id=r["snapshot_id"], asset=r["asset"])
            for r in payload["refs"]
        )

    # -- baseline ----------------------------------------------------------

    def collect_baseline(
        self, source: SampleSource, *, freeze_id: str, model_string: str
    ) -> Baseline:
        """Raccoglie k campioni per snapshot sul Trader pinnato."""
        if not self.thresholds.is_set:
            raise ThresholdsNotSet(
                "le soglie vanno fissate PRIMA della baseline. Mancano: "
                + ", ".join(self.thresholds.missing())
            )
        entries: list[BaselineEntry] = []
        for ref in self.refs():
            actions: list[str] = []
            confidences: list[float] = []
            for i in range(self.samples_per_snapshot):
                record = source(ref, i)
                if record is None:
                    continue
                actions.append(record.action.value)
                confidences.append(record.confidence)
            if not actions:
                raise RegressionError(
                    f"nessun campione valido per {ref.key}: baseline non raccoglibile"
                )
            entries.append(
                BaselineEntry(
                    ref=ref,
                    actions=tuple(actions),
                    confidences=tuple(confidences),
                )
            )
        return Baseline(
            collected_at_utc=datetime.now(tz=timezone.utc),
            freeze_id=freeze_id,
            model_string=model_string,
            samples_per_snapshot=self.samples_per_snapshot,
            entries=tuple(entries),
        )

    # -- misura ------------------------------------------------------------

    def measure(
        self, baseline: Baseline, source: SampleSource, *, model_string: str
    ) -> DriftReport:
        """Rigioca i Decision Snapshot e misura la deriva rispetto alla baseline."""
        per_snapshot: list[SnapshotDrift] = []
        for entry in baseline.entries:
            agree = 0
            distances: list[float] = []
            malformed = 0
            for i in range(self.samples_per_snapshot):
                record = source(entry.ref, i)
                if record is None:
                    malformed += 1
                    continue
                if record.action.value == entry.modal_action:
                    agree += 1
                distances.append(abs(record.confidence - entry.mean_confidence))
            valid = self.samples_per_snapshot - malformed
            per_snapshot.append(
                SnapshotDrift(
                    ref=entry.ref,
                    # Un verbale malformato conta come disaccordo: è una deriva
                    # comportamentale, non un campione da scartare.
                    agreement_rate=(
                        agree / self.samples_per_snapshot
                        if self.samples_per_snapshot
                        else 0.0
                    ),
                    confidence_distance=(
                        sum(distances) / len(distances) if distances else 0.0
                    ),
                    samples=valid,
                    malformed=malformed,
                )
            )

        n = len(per_snapshot)
        agreement = sum(d.agreement_rate for d in per_snapshot) / n if n else 0.0
        distance = sum(d.confidence_distance for d in per_snapshot) / n if n else 0.0

        return DriftReport(
            measured_at_utc=datetime.now(tz=timezone.utc),
            baseline_id=baseline.baseline_id,
            model_string=model_string,
            per_snapshot=tuple(per_snapshot),
            action_agreement_rate=agreement,
            mean_confidence_distance=distance,
        )

    # -- verdetto ----------------------------------------------------------

    def evaluate(self, report: DriftReport) -> DriftReport:
        """Applica le soglie. **Solleva** se non sono state fissate.

        Un default silenzioso qui significherebbe scoprire la deriva quando
        conviene, cioè mai.
        """
        t = self.thresholds
        if not t.is_set:
            raise ThresholdsNotSet(
                "impossibile emettere un verdetto: soglie TODO-owner non "
                "fissate. Mancano: " + ", ".join(t.missing())
            )

        if (
            report.action_agreement_rate <= t.agreement_sunset
            or report.mean_confidence_distance >= t.confidence_sunset
        ):
            verdict, detail = (
                DriftVerdict.SUNSET,
                (
                    f"agreement {report.action_agreement_rate:.4f} "
                    f"(sunset <= {t.agreement_sunset}), distanza confidence "
                    f"{report.mean_confidence_distance:.4f} "
                    f"(sunset >= {t.confidence_sunset}): il track record si "
                    f"chiude qui e ne inizia uno nuovo"
                ),
            )
        elif (
            report.action_agreement_rate <= t.agreement_alarm
            or report.mean_confidence_distance >= t.confidence_alarm
        ):
            verdict, detail = (
                DriftVerdict.ALARM,
                (
                    f"agreement {report.action_agreement_rate:.4f}, distanza "
                    f"confidence {report.mean_confidence_distance:.4f}: "
                    f"soglia di allarme superata"
                ),
            )
        else:
            verdict, detail = DriftVerdict.OK, "deriva entro le soglie dichiarate"

        return DriftReport(
            measured_at_utc=report.measured_at_utc,
            baseline_id=report.baseline_id,
            model_string=report.model_string,
            per_snapshot=report.per_snapshot,
            action_agreement_rate=report.action_agreement_rate,
            mean_confidence_distance=report.mean_confidence_distance,
            verdict=verdict,
            detail=detail,
        )


def modal_action_of(records: Sequence[DecisionRecord]) -> Action:
    return Action(Counter(r.action.value for r in records).most_common(1)[0][0])
