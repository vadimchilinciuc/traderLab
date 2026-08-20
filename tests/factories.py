"""Costruttori deterministici per i test.

Niente rete, niente API, niente casualità non seminata: ogni test parte da uno
snapshot riproducibile byte-per-byte.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from arena.config import build_freeze_manifest
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
from ledger.spend import Pricing

ASOF = datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)
SHA_A = "a" * 64
SHA_B = "b" * 64

#: Listino di `claude-opus-5` — il modello pinnato in TL-007 — in USD per
#: milione di token. Trascritto dalla pagina ufficiale il 20/08/2026 ed
#: elencato nel §4 di
#: `docs/research/results/2026-08-20_PREREG-EVIDENCE_PREVENTIVO_RUN2.md`:
#: input $5, output $25, scrittura in cache a 5 minuti $6.25 (1,25x l'input),
#: lettura da cache $0.50 (0,1x l'input). La scrittura è quella a **5 minuti**
#: perché è il TTL di default del client; quella a 1 ora ($10) non si applica.
#:
#: I test lo scrivono qui e non se lo ricalcolano ciascuno: due copie della
#: stessa tariffa divergono il giorno in cui una viene aggiornata e l'altra no,
#: che è lo stesso difetto per cui il listino è uscito da `ledger/spend.py`.
PREZZI_OPUS5: dict[str, float] = {
    "price_per_mtok_input": 5.00,
    "price_per_mtok_output": 25.00,
    "price_per_mtok_cache_write_5m": 6.25,
    "price_per_mtok_cache_read": 0.50,
}

def prezzi_senza(*campi: str) -> dict[str, float]:
    """Il listino di opus-5 privato dei campi elencati.

    Serve ai test che provano il **lato mancante**: un listino a tre voci su
    quattro non è un conto approssimativo, è un conto che non si può fare, e
    la guardia deve dirlo invece di sommare quello che ha.
    """
    sconosciuti = set(campi) - set(PREZZI_OPUS5)
    if sconosciuti:
        raise ValueError(f"campi di listino inesistenti: {sorted(sconosciuti)}")
    return {k: v for k, v in PREZZI_OPUS5.items() if k not in campi}


def manifest_con_prezzi(
    pinned_at: datetime,
    *,
    pin_commit: str = "",
    season_budget_usd: float | None = None,
    season_expected_days: int | None = None,
    prezzi: Mapping[str, float] = PREZZI_OPUS5,
) -> FreezeManifest:
    """Un manifest coi termini economici che gli si passano.

    Le quattro voci di listino si nominano una per una invece di srotolare un
    dizionario con `**`: un `**dict[str, float]` su una firma eterogenea non è
    verificabile staticamente, e questi quattro campi sono precisamente quelli
    che il rito ha tolto dal regno delle costanti implicite. Un campo assente
    da `prezzi` arriva come `None`, cioè "non firmato".
    """
    return build_freeze_manifest(
        pinned_at,
        pin_commit=pin_commit,
        season_budget_usd=season_budget_usd,
        season_expected_days=season_expected_days,
        price_per_mtok_input=prezzi.get("price_per_mtok_input"),
        price_per_mtok_output=prezzi.get("price_per_mtok_output"),
        price_per_mtok_cache_write_5m=prezzi.get("price_per_mtok_cache_write_5m"),
        price_per_mtok_cache_read=prezzi.get("price_per_mtok_cache_read"),
    )


#: Lo stesso listino nella forma che le guardie economiche consumano.
LISTINO_OPUS5 = Pricing(
    input_usd_per_mtok=PREZZI_OPUS5["price_per_mtok_input"],
    output_usd_per_mtok=PREZZI_OPUS5["price_per_mtok_output"],
    cache_write_usd_per_mtok=PREZZI_OPUS5["price_per_mtok_cache_write_5m"],
    cache_read_usd_per_mtok=PREZZI_OPUS5["price_per_mtok_cache_read"],
)


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
