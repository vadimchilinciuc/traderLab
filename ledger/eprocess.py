"""E-process anytime-valid per il confronto appaiato agente vs gamba meccanica.

Perché un e-process e non un t-test: la valutazione è forward e continua, si
guarda il risultato mentre arriva, e con un p-value questo è "optional
stopping" — inflaziona i falsi positivi. Un e-process resta valido a qualunque
istante di arresto, incluso "mi fermo appena vedo qualcosa".

Implementazione: test-martingale di betting su differenze appaiate giornaliere,
con scommessa scelta da Online Newton Step (Cutkosky & Orabona; Waudby-Smith &
Ramdas). Le differenze si normalizzano in [0,1] rispetto a un bound dichiarato
ex-ante; l'ipotesi nulla è media 0.5, cioè differenza appaiata nulla.

    H0: E[agente - macchina] <= 0     rifiutata quando e-value >= 1/alpha

**In Fase 0 non esiste la gamba meccanica**: qui l'e-process è collaudato su
dati sintetici. Si attiva quando la gamba meccanica esisterà.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

# Costante ONS di Cutkosky & Orabona: 2 / (2 - ln 3).
ONS_SCALE = 2.0 / (2.0 - math.log(3.0))
# |lambda| <= 0.5 garantisce 1 + lambda*(x - 0.5) in [0.75, 1.25]: il capitale
# resta positivo e il logaritmo non esplode mai.
LAMBDA_BOUND = 0.5


@dataclass(slots=True)
class BettingEProcess:
    """Processo di capitale anytime-valid su differenze appaiate.

    `bound` è il massimo |differenza| dichiarato **ex-ante**. Le differenze
    oltre il bound vengono troncate: un bound scelto dopo aver visto i dati
    invaliderebbe la garanzia, quindi si dichiara prima e si tronca.

    `one_sided=True` (default) vincola la scommessa a lambda >= 0: si può
    accumulare capitale solo scommettendo che la differenza sia **positiva**.
    È la forma corretta per H0: E[agente - macchina] <= 0 — un agente peggiore
    della macchina non deve poter produrre evidenza "a favore" solo perché
    devia dallo zero. Con `one_sided=False` il test diventa bilaterale
    (H0: differenza nulla) e rifiuta anche gli effetti negativi.
    """

    bound: float
    alpha: float = 0.05
    one_sided: bool = True
    _log_capital: float = 0.0
    _max_log_capital: float = 0.0
    _lam: float = 0.0
    _grad_sq_sum: float = 1.0
    _n: int = 0
    _truncated: int = 0

    def __post_init__(self) -> None:
        if self.bound <= 0.0:
            raise ValueError("bound deve essere positivo")
        if not 0.0 < self.alpha < 1.0:
            raise ValueError("alpha deve stare in (0, 1)")

    # -- aggiornamento -----------------------------------------------------

    def update(self, difference: float) -> float:
        """Osserva una differenza appaiata e ritorna l'e-value corrente."""
        clipped = max(-self.bound, min(self.bound, difference))
        if clipped != difference:
            self._truncated += 1
        # Normalizzazione in [0, 1]; y = x - 0.5 sta in [-0.5, 0.5].
        y = clipped / (2.0 * self.bound)

        factor = 1.0 + self._lam * y
        # Con |lam| <= 0.5 e |y| <= 0.5 il fattore non può annullarsi.
        self._log_capital += math.log(factor)
        self._max_log_capital = max(self._max_log_capital, self._log_capital)
        self._n += 1

        # ONS: gradiente del log-capitale rispetto a lambda.
        gradient = y / factor
        self._grad_sq_sum += gradient * gradient
        self._lam = _clip(
            self._lam + ONS_SCALE * gradient / self._grad_sq_sum,
            0.0 if self.one_sided else -LAMBDA_BOUND,
            LAMBDA_BOUND,
        )
        return self.e_value

    def update_many(self, differences: Sequence[float]) -> float:
        for d in differences:
            self.update(d)
        return self.e_value

    # -- lettura -----------------------------------------------------------

    @property
    def e_value(self) -> float:
        return math.exp(self._log_capital)

    @property
    def log_e_value(self) -> float:
        return self._log_capital

    @property
    def max_e_value(self) -> float:
        """Massimo raggiunto: è questo che va confrontato con 1/alpha."""
        return math.exp(self._max_log_capital)

    @property
    def n_observations(self) -> int:
        return self._n

    @property
    def n_truncated(self) -> int:
        return self._truncated

    @property
    def threshold(self) -> float:
        return 1.0 / self.alpha

    @property
    def rejected(self) -> bool:
        """Rifiuto anytime-valid: il massimo storico supera 1/alpha."""
        return self.max_e_value >= self.threshold


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# --------------------------------------------------------------------------
# Kill-criterion pre-registrato
# --------------------------------------------------------------------------


class KillVerdict(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    NO_MEASURABLE_SKILL = "no_measurable_skill"
    SIGNAL_EXCEEDS_NOISE = "signal_exceeds_noise"


@dataclass(frozen=True, slots=True)
class KillCriterionConfig:
    """Parametri pre-registrati. Cambiarli dopo aver visto i dati è barare.

    `window` è la finestra dichiarata; `dominance_ratio` è quanto il gap deve
    superare la dispersione per non essere considerato rumore.
    """

    window: int = 20
    dominance_ratio: float = 1.0

    def __post_init__(self) -> None:
        if self.window < 2:
            raise ValueError("window deve essere >= 2")
        if self.dominance_ratio <= 0.0:
            raise ValueError("dominance_ratio deve essere positivo")


@dataclass(frozen=True, slots=True)
class KillCriterionResult:
    verdict: KillVerdict
    window_used: int
    mean_abs_gap: float
    mean_dispersion: float
    ratio: float | None
    detail: str = ""

    @property
    def is_kill(self) -> bool:
        return self.verdict is KillVerdict.NO_MEASURABLE_SKILL


def evaluate_kill_criterion(
    agent_machine_gaps: Sequence[float],
    inter_replica_dispersions: Sequence[float],
    config: KillCriterionConfig | None = None,
) -> KillCriterionResult:
    """KILL-CRITERION PRE-REGISTRATO.

    Se sulla finestra dichiarata la **dispersione inter-repliche domina il gap
    agente-macchina**, il verdetto è "no skill misurabile": tre repliche
    identiche che divergono tra loro più di quanto l'agente diverga dalla
    macchina stanno misurando rumore di campionamento, non abilità.

    Il criterio è codice, non una nota. Non è negoziabile a posteriori.
    """
    cfg = config or KillCriterionConfig()
    n = min(len(agent_machine_gaps), len(inter_replica_dispersions))
    if n < cfg.window:
        return KillCriterionResult(
            verdict=KillVerdict.INSUFFICIENT_DATA,
            window_used=n,
            mean_abs_gap=0.0,
            mean_dispersion=0.0,
            ratio=None,
            detail=f"servono {cfg.window} osservazioni appaiate, ce ne sono {n}",
        )

    gaps = agent_machine_gaps[-cfg.window :]
    dispersions = inter_replica_dispersions[-cfg.window :]
    mean_gap = sum(abs(g) for g in gaps) / cfg.window
    mean_disp = sum(abs(d) for d in dispersions) / cfg.window

    if mean_disp == 0.0:
        ratio = math.inf if mean_gap > 0.0 else 0.0
    else:
        ratio = mean_gap / mean_disp

    if ratio <= cfg.dominance_ratio:
        return KillCriterionResult(
            verdict=KillVerdict.NO_MEASURABLE_SKILL,
            window_used=cfg.window,
            mean_abs_gap=mean_gap,
            mean_dispersion=mean_disp,
            ratio=ratio,
            detail=(
                f"gap medio {mean_gap:.6f} <= {cfg.dominance_ratio:.2f} x "
                f"dispersione media {mean_disp:.6f}: no skill misurabile"
            ),
        )

    return KillCriterionResult(
        verdict=KillVerdict.SIGNAL_EXCEEDS_NOISE,
        window_used=cfg.window,
        mean_abs_gap=mean_gap,
        mean_dispersion=mean_disp,
        ratio=ratio,
        detail=(
            f"gap medio {mean_gap:.6f} > {cfg.dominance_ratio:.2f} x "
            f"dispersione media {mean_disp:.6f}"
        ),
    )
