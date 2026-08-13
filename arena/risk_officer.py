"""RiskOfficer — codice puro, nessun LLM, può solo ridurre il rischio.

Regole pre-registrate (Fase 0 / Stagione 0):

1. **Size fissa (D3)**: in Stagione 0 la size non è una variabile del Trader.
   Viene normalizzata al valore di config con un *clamp*, non con un errore.
2. **Cap di leva 3x**: l'esposizione lorda del portafoglio non supera 3.0.
   Se non c'è spazio, la size viene ridotta; se non c'è spazio affatto, la
   decisione è rifiutata.
3. **Un solo cambio di posizione per asset al giorno.**
4. **Anti-martingala**: blocca l'aumento di size dopo una perdita. **Dormiente**
   finché la size è fissa — ma implementata e testata, perché il giorno in cui
   la size si sblocca la regola deve esistere già, non essere scritta allora.

Ogni tentativo bloccato produce un `RiskVerdict` con la regola scattata, che
finisce in telemetria. Un blocco silenzioso non è un blocco: è un buco.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contracts.decision import Action, DecisionRecord
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict

DEFAULT_FIXED_SIZE_FRACTION = 0.05
DEFAULT_MAX_GROSS_LEVERAGE = 3.0


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Parametri pre-registrati. Cambiarli è un commit, non una variabile."""

    fixed_size_fraction: float = DEFAULT_FIXED_SIZE_FRACTION
    enforce_fixed_size: bool = True
    max_gross_leverage: float = DEFAULT_MAX_GROSS_LEVERAGE
    max_changes_per_asset_per_day: int = 1
    # Perdite consecutive oltre le quali l'anti-martingala si attiva.
    anti_martingale_loss_streak: int = 1

    def __post_init__(self) -> None:
        if not 0.0 < self.fixed_size_fraction <= 1.0:
            raise ValueError("fixed_size_fraction fuori da (0, 1]")
        if self.max_gross_leverage <= 0.0:
            raise ValueError("max_gross_leverage deve essere positivo")


@dataclass(slots=True)
class PortfolioState:
    """Stato osservabile su cui il Risk Officer decide.

    Esplicito e passato dall'esterno: il Risk Officer non tiene stato nascosto
    e resta testabile riga per riga.
    """

    allowed_assets: frozenset[str] = frozenset()
    changes_today: dict[str, int] = field(default_factory=dict)
    gross_exposure: float = 0.0
    last_size_by_asset: dict[str, float] = field(default_factory=dict)
    loss_streak_by_asset: dict[str, int] = field(default_factory=dict)

    def register(self, asset: str, size_fraction: float) -> None:
        """Aggiorna lo stato dopo una decisione ammessa."""
        self.changes_today[asset] = self.changes_today.get(asset, 0) + 1
        self.gross_exposure += size_fraction
        self.last_size_by_asset[asset] = size_fraction


class RiskOfficer:
    """Applica le regole in ordine fisso e dichiarato."""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()

    def review(self, decision: DecisionRecord, state: PortfolioState) -> RiskVerdict:
        cfg = self.config
        action_in = decision.action
        size_in = decision.size_fraction

        # -- 1. Asset ammesso? --------------------------------------------
        if state.allowed_assets and decision.asset not in state.allowed_assets:
            return _reject(
                RiskRule.UNKNOWN_ASSET,
                action_in,
                size_in,
                f"{decision.asset} non è nell'universo dello snapshot",
            )

        # -- 2. Un solo cambio per asset al giorno ------------------------
        already = state.changes_today.get(decision.asset, 0)
        if already >= cfg.max_changes_per_asset_per_day:
            return _reject(
                RiskRule.ONE_CHANGE_PER_ASSET_PER_DAY,
                action_in,
                size_in,
                f"{decision.asset} ha già {already} cambio/i registrato/i oggi",
            )

        # Le decisioni non direzionali non consumano rischio: passano.
        if not decision.is_directional:
            return _approve(action_in, size_in)

        size_out = size_in
        rule = RiskRule.NONE

        # -- 3. Size fissa (D3) oppure anti-martingala --------------------
        if cfg.enforce_fixed_size:
            # Con size fissa l'anti-martingala è dormiente per costruzione:
            # non esiste una size crescente da bloccare.
            if size_out != cfg.fixed_size_fraction:
                size_out = cfg.fixed_size_fraction
                rule = RiskRule.FIXED_SIZE_SEASON_0
        else:
            streak = state.loss_streak_by_asset.get(decision.asset, 0)
            previous = state.last_size_by_asset.get(decision.asset)
            if (
                streak >= cfg.anti_martingale_loss_streak
                and previous is not None
                and size_out > previous
            ):
                size_out = previous
                rule = RiskRule.ANTI_MARTINGALE

        # -- 4. Cap di leva: può solo ridurre -----------------------------
        headroom = cfg.max_gross_leverage - state.gross_exposure
        if headroom <= 0.0:
            return _reject(
                RiskRule.LEVERAGE_CAP,
                action_in,
                size_in,
                f"esposizione lorda già a {state.gross_exposure:.4f}, "
                f"cap {cfg.max_gross_leverage:.2f}",
            )
        if size_out > headroom:
            size_out = headroom
            rule = RiskRule.LEVERAGE_CAP

        if size_out <= 0.0:
            return _reject(
                RiskRule.LEVERAGE_CAP,
                action_in,
                size_in,
                "nessuno spazio residuo sotto il cap di leva",
            )

        if rule is RiskRule.NONE:
            return _approve(action_in, size_out)

        return RiskVerdict(
            outcome=RiskOutcome.CLAMPED,
            rule=rule,
            action_in=action_in,
            action_out=action_in,
            size_fraction_in=size_in,
            size_fraction_out=size_out,
            detail=_clamp_detail(rule, size_in, size_out),
        )

    @staticmethod
    def reject_malformed(asset: str, detail: str) -> RiskVerdict:
        """Verdetto per un verbale non conforme: NO TRADE."""
        return RiskVerdict(
            outcome=RiskOutcome.REJECTED,
            rule=RiskRule.MALFORMED_VERBALE,
            action_in=Action.FLAT,
            action_out=Action.FLAT,
            size_fraction_in=0.0,
            size_fraction_out=0.0,
            detail=f"{asset}: {detail}"[:500],
        )

    @staticmethod
    def reject_refusal(asset: str, detail: str) -> RiskVerdict:
        """Verdetto per un rifiuto del modello: NO TRADE, ma categoria distinta.

        Tenerlo separato da `malformed_verbale` non è pedanteria contabile: il
        tasso di verbali malformati misura se il **protocollo** regge, e un
        rifiuto dei classificatori non dice nulla sul protocollo. Mescolarli
        renderebbe illeggibili entrambe le metriche.
        """
        return RiskVerdict(
            outcome=RiskOutcome.REJECTED,
            rule=RiskRule.MODEL_REFUSAL,
            action_in=Action.FLAT,
            action_out=Action.FLAT,
            size_fraction_in=0.0,
            size_fraction_out=0.0,
            detail=f"{asset}: {detail}"[:500],
        )


def _approve(action: Action, size: float) -> RiskVerdict:
    return RiskVerdict(
        outcome=RiskOutcome.APPROVED,
        rule=RiskRule.NONE,
        action_in=action,
        action_out=action,
        size_fraction_in=size,
        size_fraction_out=size,
    )


def _reject(rule: RiskRule, action: Action, size: float, detail: str) -> RiskVerdict:
    return RiskVerdict(
        outcome=RiskOutcome.REJECTED,
        rule=rule,
        action_in=action,
        action_out=Action.FLAT,
        size_fraction_in=size,
        size_fraction_out=0.0,
        detail=detail[:500],
    )


def _clamp_detail(rule: RiskRule, size_in: float, size_out: float) -> str:
    return f"{rule.value}: size {size_in:.6f} -> {size_out:.6f}"
