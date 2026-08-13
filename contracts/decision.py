"""DecisionRecord — Schema v1 (decima revisione della rassegna di fedeltà).

Ordine obbligatorio di generazione: `rationale_text` (scratchpad libero) esce
PRIMA del blocco strutturato. Questo è l'unico intervento sull'elicitazione con
supporto empirico solido (Tam et al., EMNLP 2024: il degrado da vincolo di
formato nasce dall'answer-field che precede il reasoning-field).

Il contratto non può *verificare* quell'ordine — lo impone il parser in
`arena/verbale.py`, che rifiuta un verbale in cui il testo libero manca o
arriva dopo. Qui si impone tutto il resto.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator

from contracts.base import FrozenModel, require_utc
from contracts.vocabulary import is_known_feature

# Testo minimo del razionale: sotto questa soglia non è uno scratchpad, è un
# segnaposto. Soglia dichiarata qui, non nel prompt (CLAUDE.md §2).
MIN_RATIONALE_CHARS = 120


class Action(StrEnum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"
    CLOSE = "close"


class Horizon(StrEnum):
    INTRADAY = "intraday"
    DAYS_1_3 = "1-3d"
    DAYS_4_10 = "4-10d"
    DAYS_10_PLUS = "10d+"


class FeatureUsed(FrozenModel):
    """Attribuzione dichiarata: nome nel vocabolario primitivo + valore numerico.

    Ancoraggio numerico richiesto per verificabilità, NON perché ci sia
    evidenza che il numero aumenti la fedeltà (non c'è).
    """

    name: str = Field(min_length=1)
    value: float

    @field_validator("name")
    @classmethod
    def _in_vocabulary(cls, v: str) -> str:
        if not is_known_feature(v):
            raise ValueError(f"feature '{v}' non è nel vocabolario primitivo")
        return v


class RiskCheck(FrozenModel):
    """Check di rischio dichiarato dal Trader come superato."""

    name: str = Field(min_length=1)
    passed: bool
    note: str = Field(default="", max_length=500)


class DecisionRecord(FrozenModel):
    """Verbale di una singola decisione, per un singolo asset, di una replica."""

    schema_version: Annotated[int, Field(ge=1)] = 1

    # --- Nucleo dell'ordine ---
    timestamp_decision: datetime
    asset: str = Field(min_length=1)
    action: Action
    size_fraction: float = Field(ge=0.0, le=1.0)
    horizon: Horizon

    # --- Ipotesi dichiarata (ordine: rationale PRIMA) ---
    rationale_text: str = Field(min_length=MIN_RATIONALE_CHARS)
    features_used: tuple[FeatureUsed, ...] = Field(min_length=1, max_length=12)
    confidence: float = Field(ge=0.0, le=1.0)
    invalidation_conditions: tuple[str, ...] = Field(min_length=1, max_length=6)
    expected_holding: Horizon
    risk_checks: tuple[RiskCheck, ...] = ()

    # --- Provenienza e riproducibilità ---
    tool_calls_ref: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    prompt_sha: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_git_sha: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    replica_id: str = Field(min_length=1)
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("timestamp_decision")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return require_utc(v, "timestamp_decision")

    @field_validator("invalidation_conditions")
    @classmethod
    def _non_empty_conditions(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for cond in v:
            if len(cond.strip()) < 10:
                raise ValueError(
                    "ogni invalidation_condition deve essere una condizione "
                    "ex-ante leggibile (>= 10 caratteri)"
                )
        return v

    @model_validator(mode="after")
    def _features_unique(self) -> Self:
        names = [f.name for f in self.features_used]
        if len(set(names)) != len(names):
            raise ValueError("features_used contiene nomi duplicati")
        return self

    @model_validator(mode="after")
    def _size_matches_action(self) -> Self:
        """FLAT e CLOSE non portano size: una size > 0 su FLAT è un verbale incoerente."""
        if self.action in (Action.FLAT, Action.CLOSE) and self.size_fraction != 0.0:
            raise ValueError(f"action={self.action} richiede size_fraction=0.0")
        if self.action in (Action.LONG, Action.SHORT) and self.size_fraction <= 0.0:
            raise ValueError(f"action={self.action} richiede size_fraction > 0.0")
        return self

    @property
    def is_directional(self) -> bool:
        return self.action in (Action.LONG, Action.SHORT)

    @property
    def signed_size(self) -> float:
        if self.action is Action.LONG:
            return self.size_fraction
        if self.action is Action.SHORT:
            return -self.size_fraction
        return 0.0
