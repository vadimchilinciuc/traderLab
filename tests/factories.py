"""Costruttori deterministici per i test.

Niente rete, niente API, niente casualità non seminata: ogni test parte da uno
snapshot riproducibile byte-per-byte.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from contracts.decision import (
    Action,
    DecisionRecord,
    FeatureUsed,
    Horizon,
    RiskCheck,
)
from contracts.freeze import FreezeManifest, SamplingPolicy, ThinkingPolicy
from contracts.snapshot import (
    AssetSnapshot,
    CostModel,
    CrossSectionalRank,
    FundingPoint,
    LiquidityEstimate,
    MarketSnapshot,
    OHLCVBar,
)

ASOF = datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)
SHA_A = "a" * 64
SHA_B = "b" * 64


def make_bars(n: int, start_price: float, asof: datetime = ASOF) -> tuple[OHLCVBar, ...]:
    """n barre daily deterministiche che terminano il giorno prima di `asof`."""
    bars: list[OHLCVBar] = []
    price = start_price
    for i in range(n):
        ts = asof - timedelta(days=n - i)
        # Deriva lieve verso l'alto + oscillazione: serve a esercitare sia il
        # ramo direzionale sia quello di uscita del MockLLM.
        close = price * (1.0 + 0.004 + 0.002 * ((i % 7) - 3))
        high = max(price, close) * 1.01
        low = min(price, close) * 0.99
        bars.append(
            OHLCVBar(
                ts_open_utc=ts,
                open=price,
                high=high,
                low=low,
                close=close,
                volume_usd=1_000_000.0 + 10_000.0 * i,
            )
        )
        price = close
    return tuple(bars)


def make_asset(
    symbol: str, start_price: float, asof: datetime = ASOF, n_bars: int = 60
) -> AssetSnapshot:
    bars = make_bars(n_bars, start_price, asof)
    return AssetSnapshot(
        symbol=symbol,
        mark_price=bars[-1].close,
        ohlcv_daily=bars,
        funding=(
            FundingPoint(
                ts_utc=asof - timedelta(hours=8),
                rate=0.0001,
                interval_hours=8.0,
            ),
        ),
        rankings=(
            CrossSectionalRank(
                metric="return_7d", rank=1, universe_size=2, value=0.031
            ),
        ),
        liquidity=LiquidityEstimate(
            spread_bps=2.0,
            depth_usd_1pct=500_000.0,
            depth_source="costante_dichiarata",
            estimator="static_v0",
        ),
        costs=CostModel(maker_bps=1.5, taker_bps=4.5),
    )


def make_snapshot(asof: datetime = ASOF) -> MarketSnapshot:
    assets = (make_asset("BTC", 60_000.0, asof), make_asset("ETH", 3_000.0, asof))
    return MarketSnapshot.build(
        asof_utc=asof,
        universe=tuple(a.symbol for a in assets),
        universe_status="pre_screen_ufficiale",
        assets=assets,
        source="test_factory",
        builder_version="test-0",
    )


def make_decision(
    snapshot_id: str,
    *,
    asset: str = "BTC",
    action: Action = Action.LONG,
    size_fraction: float = 0.05,
    confidence: float = 0.6,
    replica_id: str = "r1",
    timestamp: datetime = ASOF,
) -> DecisionRecord:
    return DecisionRecord(
        timestamp_decision=timestamp,
        asset=asset,
        action=action,
        size_fraction=size_fraction,
        horizon=Horizon.DAYS_1_3,
        rationale_text=(
            "Il prezzo si trova sopra la media mobile a 20 barre e il volume "
            "dell'ultima barra supera la media del periodo. Il funding resta "
            "positivo ma contenuto, quindi il costo di mantenimento non "
            "compensa la direzione osservata. Procedo con l'esposizione."
        ),
        features_used=(
            FeatureUsed(name="price_vs_sma_20", value=0.021),
            FeatureUsed(name="volume_ratio_20", value=1.4),
        ),
        confidence=confidence,
        invalidation_conditions=(
            "Chiusura daily sotto la media mobile a 20 barre.",
            "Funding annualizzato sopra il 30 percento.",
        ),
        expected_holding=Horizon.DAYS_1_3,
        risk_checks=(RiskCheck(name="spread_accettabile", passed=True),),
        tool_calls_ref="toolcalls/2026-08-12/r1.jsonl",
        model_version="mock-llm-0",
        prompt_sha=SHA_A,
        context_git_sha="0123abc",
        replica_id=replica_id,
        snapshot_id=snapshot_id,
    )


def make_manifest(pinned_at: datetime = ASOF) -> FreezeManifest:
    return FreezeManifest(
        pinned_at_utc=pinned_at,
        model_string="claude-fable-5",
        model_string_note="test",
        sampling_policy=SamplingPolicy.API_DEFAULT_OMITTED,
        max_tokens=8000,
        thinking_policy=ThinkingPolicy.API_DEFAULT,
        system_prompt_sha=SHA_A,
        persona_sha=SHA_B,
        tool_schemas_sha=SHA_A,
        context_git_sha="0123abc",
        ots_pending=True,
    )
