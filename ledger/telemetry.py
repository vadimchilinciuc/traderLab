"""BehavioralTelemetry — contatori comportamentali per replica.

Misura **come si comporta** l'agente, non quanto guadagna. In Fase 0 il PnL non
esiste; il comportamento sì, ed è già informativo: turnover, flip rate,
tentativi bloccati per regola, tasso di verbali malformati, dispersione tra
repliche dello stesso giorno, componenti del Brier score dalla confidence.

La dispersione inter-repliche è il denominatore del kill-criterion: se le tre
repliche identiche divergono tra loro più di quanto l'agente diverga dalla
gamba meccanica, non c'è skill misurabile — c'è rumore di campionamento.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations

from contracts.decision import Action, DecisionRecord
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict

DEFAULT_BRIER_BINS = 10


# --------------------------------------------------------------------------
# Brier score
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BrierComponents:
    """Decomposizione di Murphy: BS = reliability - resolution + uncertainty."""

    n: int
    brier_score: float | None
    reliability: float | None
    resolution: float | None
    uncertainty: float | None
    base_rate: float | None
    mean_confidence: float | None


@dataclass(slots=True)
class BrierAccumulator:
    """Accumula coppie (confidence, esito binario).

    In Fase 0 resta **vuoto**: gli esiti arrivano solo in Stagione 0. Il
    contatore esiste dal giorno uno perché la confidence si logga dal giorno
    uno (D3), e una calibrazione non si ricostruisce a posteriori.
    """

    bins: int = DEFAULT_BRIER_BINS
    _pairs: list[tuple[float, int]] = field(default_factory=list)

    def add(self, confidence: float, outcome: int) -> None:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence fuori da [0, 1]")
        if outcome not in (0, 1):
            raise ValueError("outcome deve essere 0 o 1")
        self._pairs.append((confidence, outcome))

    def __len__(self) -> int:
        return len(self._pairs)

    def components(self) -> BrierComponents:
        n = len(self._pairs)
        if n == 0:
            return BrierComponents(0, None, None, None, None, None, None)

        brier = sum((p - o) ** 2 for p, o in self._pairs) / n
        base_rate = sum(o for _, o in self._pairs) / n
        mean_conf = sum(p for p, _ in self._pairs) / n
        uncertainty = base_rate * (1.0 - base_rate)

        buckets: dict[int, list[tuple[float, int]]] = defaultdict(list)
        for p, o in self._pairs:
            index = min(int(p * self.bins), self.bins - 1)
            buckets[index].append((p, o))

        reliability = 0.0
        resolution = 0.0
        for pairs in buckets.values():
            n_k = len(pairs)
            mean_p = sum(p for p, _ in pairs) / n_k
            mean_o = sum(o for _, o in pairs) / n_k
            reliability += n_k * (mean_p - mean_o) ** 2
            resolution += n_k * (mean_o - base_rate) ** 2
        reliability /= n
        resolution /= n

        return BrierComponents(
            n=n,
            brier_score=brier,
            reliability=reliability,
            resolution=resolution,
            uncertainty=uncertainty,
            base_rate=base_rate,
            mean_confidence=mean_conf,
        )


# --------------------------------------------------------------------------
# Contatori per replica
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReplicaMetrics:
    replica_id: str
    decisions_total: int
    decisions_directional: int
    malformed_total: int
    malformed_rate: float
    blocked_attempts: int
    blocked_by_rule: dict[str, int]
    clamped_total: int
    turnover: float
    flips: int
    flip_rate: float
    mean_confidence: float | None
    brier: BrierComponents


@dataclass(slots=True)
class ReplicaCounters:
    replica_id: str
    decisions_total: int = 0
    decisions_directional: int = 0
    malformed_total: int = 0
    clamped_total: int = 0
    blocked_by_rule: dict[str, int] = field(default_factory=dict)
    turnover: float = 0.0
    flips: int = 0
    transitions: int = 0
    confidences: list[float] = field(default_factory=list)
    _last_signed_size: dict[str, float] = field(default_factory=dict)
    brier: BrierAccumulator = field(default_factory=BrierAccumulator)


class BehavioralTelemetry:
    """Accumulatore per replica. Va alimentato in ordine cronologico."""

    def __init__(self, replica_ids: Iterable[str] = ()) -> None:
        self._counters: dict[str, ReplicaCounters] = {
            rid: ReplicaCounters(replica_id=rid) for rid in replica_ids
        }

    def _for(self, replica_id: str) -> ReplicaCounters:
        if replica_id not in self._counters:
            self._counters[replica_id] = ReplicaCounters(replica_id=replica_id)
        return self._counters[replica_id]

    # -- osservazioni ------------------------------------------------------

    def observe_decision(
        self, decision: DecisionRecord, verdict: RiskVerdict
    ) -> None:
        """Registra una decisione validata e il verdetto che l'ha attraversata."""
        counters = self._for(decision.replica_id)
        counters.decisions_total += 1
        counters.confidences.append(decision.confidence)

        if verdict.outcome is RiskOutcome.CLAMPED:
            counters.clamped_total += 1
            counters.blocked_by_rule[verdict.rule.value] = (
                counters.blocked_by_rule.get(verdict.rule.value, 0) + 1
            )
        elif verdict.outcome is RiskOutcome.REJECTED:
            self._count_block(counters, verdict.rule)

        # Turnover e flip si misurano sull'esposizione EFFETTIVA (post-risk).
        effective = _signed_size(verdict.action_out, verdict.size_fraction_out)
        previous = counters._last_signed_size.get(decision.asset, 0.0)
        counters.turnover += abs(effective - previous)
        if previous != 0.0 and effective != 0.0:
            counters.transitions += 1
            if (previous > 0.0) != (effective > 0.0):
                counters.flips += 1
        counters._last_signed_size[decision.asset] = effective
        if effective != 0.0:
            counters.decisions_directional += 1

    def observe_malformed(self, replica_id: str, verdict: RiskVerdict) -> None:
        counters = self._for(replica_id)
        counters.decisions_total += 1
        counters.malformed_total += 1
        self._count_block(counters, verdict.rule)

    def observe_outcome(self, replica_id: str, confidence: float, correct: bool) -> None:
        """Alimenta il Brier score. Usato solo quando esistono esiti."""
        self._for(replica_id).brier.add(confidence, 1 if correct else 0)

    @staticmethod
    def _count_block(counters: ReplicaCounters, rule: RiskRule) -> None:
        counters.blocked_by_rule[rule.value] = (
            counters.blocked_by_rule.get(rule.value, 0) + 1
        )

    # -- lettura -----------------------------------------------------------

    def metrics(self, replica_id: str) -> ReplicaMetrics:
        c = self._for(replica_id)
        blocked = sum(
            count
            for rule, count in c.blocked_by_rule.items()
            if rule != RiskRule.NONE.value
        )
        return ReplicaMetrics(
            replica_id=replica_id,
            decisions_total=c.decisions_total,
            decisions_directional=c.decisions_directional,
            malformed_total=c.malformed_total,
            malformed_rate=(
                c.malformed_total / c.decisions_total if c.decisions_total else 0.0
            ),
            blocked_attempts=blocked,
            blocked_by_rule=dict(sorted(c.blocked_by_rule.items())),
            clamped_total=c.clamped_total,
            turnover=c.turnover,
            flips=c.flips,
            flip_rate=(c.flips / c.transitions if c.transitions else 0.0),
            mean_confidence=(
                sum(c.confidences) / len(c.confidences) if c.confidences else None
            ),
            brier=c.brier.components(),
        )

    def all_metrics(self) -> dict[str, ReplicaMetrics]:
        return {rid: self.metrics(rid) for rid in sorted(self._counters)}


# --------------------------------------------------------------------------
# Dispersione inter-repliche
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DailyDispersion:
    """Quanto le repliche identiche divergono tra loro nello stesso giorno."""

    assets_compared: int
    replicas: int
    action_disagreement: float
    confidence_dispersion: float
    size_dispersion: float

    @property
    def is_degenerate(self) -> bool:
        """Con meno di due repliche la dispersione non è definita."""
        return self.replicas < 2 or self.assets_compared == 0


def daily_dispersion(
    decisions_by_replica: Mapping[str, Mapping[str, DecisionRecord]],
) -> DailyDispersion:
    """Dispersione media a coppie sugli asset visti da tutte le repliche.

    `decisions_by_replica`: {replica_id: {asset: DecisionRecord}}.
    Si confrontano solo gli asset presenti in **tutte** le repliche: confrontare
    un asset che una replica non ha deciso significa misurare la copertura, non
    la dispersione.
    """
    replica_ids = sorted(decisions_by_replica)
    if len(replica_ids) < 2:
        return DailyDispersion(0, len(replica_ids), 0.0, 0.0, 0.0)

    common: set[str] | None = None
    for rid in replica_ids:
        assets = set(decisions_by_replica[rid])
        common = assets if common is None else (common & assets)
    shared = sorted(common or set())
    if not shared:
        return DailyDispersion(0, len(replica_ids), 0.0, 0.0, 0.0)

    action_scores: list[float] = []
    conf_scores: list[float] = []
    size_scores: list[float] = []
    for asset in shared:
        pairs = list(combinations(replica_ids, 2))
        action_scores.append(
            sum(
                1.0
                if decisions_by_replica[a][asset].action
                != decisions_by_replica[b][asset].action
                else 0.0
                for a, b in pairs
            )
            / len(pairs)
        )
        conf_scores.append(
            sum(
                abs(
                    decisions_by_replica[a][asset].confidence
                    - decisions_by_replica[b][asset].confidence
                )
                for a, b in pairs
            )
            / len(pairs)
        )
        size_scores.append(
            sum(
                abs(
                    decisions_by_replica[a][asset].signed_size
                    - decisions_by_replica[b][asset].signed_size
                )
                for a, b in pairs
            )
            / len(pairs)
        )

    return DailyDispersion(
        assets_compared=len(shared),
        replicas=len(replica_ids),
        action_disagreement=sum(action_scores) / len(action_scores),
        confidence_dispersion=sum(conf_scores) / len(conf_scores),
        size_dispersion=sum(size_scores) / len(size_scores),
    )


def _signed_size(action: Action, size: float) -> float:
    if action is Action.LONG:
        return size
    if action is Action.SHORT:
        return -size
    return 0.0


def mean_absolute(values: Sequence[float]) -> float:
    return sum(abs(v) for v in values) / len(values) if values else 0.0
