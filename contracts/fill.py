"""ShadowFill — esecuzione simulata con i costi reali di Hyperliquid.

Nessun ordine reale parte da questo repo. Il fill è una contabilizzazione:
prezzo di riferimento dello snapshot, più commissione, più slippage stimato,
tutto nella direzione sfavorevole al Trader.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from contracts.base import FrozenModel, require_utc
from contracts.decision import Action

# Costi reali Hyperliquid (perp), in basis point sul nozionale.
HYPERLIQUID_MAKER_BPS = 1.5
HYPERLIQUID_TAKER_BPS = 4.5


class Liquidity(StrEnum):
    MAKER = "maker"
    TAKER = "taker"


class ShadowFill(FrozenModel):
    """Fill simulato per una decisione approvata o clampata."""

    timestamp_utc: datetime
    asset: str = Field(min_length=1)
    action: Action
    size_fraction: float = Field(ge=0.0, le=1.0)
    reference_price: float = Field(gt=0.0)
    liquidity: Liquidity
    fee_bps: float = Field(ge=0.0)
    slippage_bps: float = Field(ge=0.0)
    fill_price: float = Field(gt=0.0)
    notional_fraction: float = Field(ge=0.0, le=1.0)
    cost_fraction: float = Field(ge=0.0)
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    replica_id: str = Field(min_length=1)

    @field_validator("timestamp_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return require_utc(v, "timestamp_utc")

    @model_validator(mode="after")
    def _direction_of_cost(self) -> Self:
        """Il costo peggiora sempre il prezzo: sopra il mid in long, sotto in short."""
        if self.action is Action.LONG and self.fill_price < self.reference_price:
            raise ValueError("fill long non può essere migliore del prezzo di riferimento")
        if self.action is Action.SHORT and self.fill_price > self.reference_price:
            raise ValueError("fill short non può essere migliore del prezzo di riferimento")
        return self
