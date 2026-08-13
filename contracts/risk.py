"""RiskVerdict — esito del Risk Officer su un DecisionRecord.

Il Risk Officer è codice puro e **può solo ridurre il rischio**. Il verdetto
registra sempre quale regola è scattata: senza quel campo la telemetria dei
tentativi bloccati non è ricostruibile a posteriori.

Unica eccezione dichiarata all'invariante "solo ridurre": in Stagione 0 la size
è FISSA per decisione dell'owner (D3) e non è una variabile del Trader — che
decide solo direzione e dentro/fuori. La normalizzazione alla size fissa può
quindi alzare una size richiesta più bassa. Non è un aumento di rischio
discrezionale: è la rimozione di un grado di libertà che il protocollo non
concede. Tutte le altre regole (leva, anti-martingala, un cambio al giorno)
possono solo ridurre.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from contracts.base import FrozenModel
from contracts.decision import Action


class RiskOutcome(StrEnum):
    APPROVED = "approved"
    CLAMPED = "clamped"
    REJECTED = "rejected"


class RiskRule(StrEnum):
    """Regole pre-registrate. L'elenco è chiuso: una regola nuova è un commit."""

    NONE = "none"
    FIXED_SIZE_SEASON_0 = "fixed_size_season_0"
    LEVERAGE_CAP = "leverage_cap"
    ONE_CHANGE_PER_ASSET_PER_DAY = "one_change_per_asset_per_day"
    ANTI_MARTINGALE = "anti_martingale"
    MALFORMED_VERBALE = "malformed_verbale"
    UNKNOWN_ASSET = "unknown_asset"


class RiskVerdict(FrozenModel):
    """Decisione del Risk Officer, con la size effettivamente ammessa."""

    outcome: RiskOutcome
    rule: RiskRule
    action_in: Action
    action_out: Action
    size_fraction_in: float = Field(ge=0.0, le=1.0)
    size_fraction_out: float = Field(ge=0.0, le=1.0)
    detail: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.outcome is RiskOutcome.APPROVED:
            if self.rule is not RiskRule.NONE:
                raise ValueError("approved implica rule=none")
            if self.size_fraction_out != self.size_fraction_in:
                raise ValueError("approved non può cambiare la size")
            if self.action_out != self.action_in:
                raise ValueError("approved non può cambiare l'action")
        if self.outcome is RiskOutcome.CLAMPED and self.rule is RiskRule.NONE:
            raise ValueError("clamped deve dichiarare la regola scattata")
        if self.outcome is RiskOutcome.REJECTED:
            if self.rule is RiskRule.NONE:
                raise ValueError("rejected deve dichiarare la regola scattata")
            if self.size_fraction_out != 0.0:
                raise ValueError("rejected implica size_fraction_out=0.0")
            if self.action_out is not Action.FLAT:
                raise ValueError("rejected implica action_out=flat")
        return self

    @property
    def is_executable(self) -> bool:
        return self.outcome in (RiskOutcome.APPROVED, RiskOutcome.CLAMPED)
