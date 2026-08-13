"""Esecuzione shadow con i costi reali di Hyperliquid.

Nessun ordine parte da qui. Il fill è una contabilizzazione, e le assunzioni
sono dichiarate e conservative:

- si assume **liquidity taker** (4.5 bps), il caso peggiore tra i due;
- lo slippage stimato è **mezzo spread** stimato dallo snapshot;
- il costo peggiora sempre il prezzo, in entrambe le direzioni.
"""

from __future__ import annotations

from datetime import datetime

from contracts.decision import Action
from contracts.fill import Liquidity, ShadowFill
from contracts.snapshot import AssetSnapshot

BPS = 10_000.0


def compute_shadow_fill(
    *,
    asset: AssetSnapshot,
    action: Action,
    size_fraction: float,
    timestamp_utc: datetime,
    snapshot_id: str,
    replica_id: str,
    assume_taker: bool = True,
    slippage_as_half_spread: bool = True,
) -> ShadowFill | None:
    """Ritorna il fill simulato, oppure `None` se non c'è nulla da eseguire."""
    if action not in (Action.LONG, Action.SHORT) or size_fraction <= 0.0:
        return None

    liquidity = Liquidity.TAKER if assume_taker else Liquidity.MAKER
    fee_bps = asset.costs.taker_bps if assume_taker else asset.costs.maker_bps
    slippage_bps = (
        asset.liquidity.spread_bps / 2.0 if slippage_as_half_spread else 0.0
    )
    total_bps = fee_bps + slippage_bps

    reference = asset.mark_price
    direction = 1.0 if action is Action.LONG else -1.0
    fill_price = reference * (1.0 + direction * total_bps / BPS)

    return ShadowFill(
        timestamp_utc=timestamp_utc,
        asset=asset.symbol,
        action=action,
        size_fraction=size_fraction,
        reference_price=reference,
        liquidity=liquidity,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        fill_price=fill_price,
        notional_fraction=size_fraction,
        cost_fraction=size_fraction * total_bps / BPS,
        snapshot_id=snapshot_id,
        replica_id=replica_id,
    )
