"""OutcomeAnnotation — l'esito, compilato ex-post.

In Fase 0 questo contratto esiste e ha i suoi test, ma **non viene popolato**:
serve la Stagione 0 per avere esiti. MFE/MAE sono qui perché discriminano un
errore di entrata da un errore di uscita, che è la diagnosi che serve al
mining di ipotesi; `invalidation_triggered` chiude il cerchio con le condizioni
dichiarate ex-ante nel DecisionRecord.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from contracts.base import FrozenModel, require_utc


class OutcomeAnnotation(FrozenModel):
    """Esito osservato di una decisione, in frazione di capitale."""

    decision_ref: str = Field(min_length=1)
    asset: str = Field(min_length=1)
    replica_id: str = Field(min_length=1)
    annotated_at_utc: datetime

    pnl_fraction: float
    mfe_fraction: float = Field(ge=0.0)
    mae_fraction: float = Field(le=0.0)

    price_at_decision: float = Field(gt=0.0)
    price_plus_1d: float | None = Field(default=None, gt=0.0)
    price_plus_7d: float | None = Field(default=None, gt=0.0)

    invalidation_triggered: bool | None = None
    invalidation_note: str = Field(default="", max_length=500)

    @field_validator("annotated_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return require_utc(v, "annotated_at_utc")
