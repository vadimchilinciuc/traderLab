"""SnapshotBuilder — costruisce lo snapshot del giorno UNA volta sola.

Disciplina point-in-time strutturale: entrano solo barre **chiuse** prima di
`asof_utc`. Una barra ancora in formazione non è un fatto osservabile e non
entra. Il filtro è qui, non nel prompt.

L'universo è quello UFFICIALE consegnato dal Pre-Screen
(`pre_screen_ufficiale`), e lo stato viaggia dentro lo snapshot: chi legge un
record non deve andare a cercare altrove se l'universo era definitivo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from contracts.snapshot import (
    AssetSnapshot,
    CostModel,
    CrossSectionalRank,
    FundingPoint,
    LiquidityEstimate,
    MarketSnapshot,
    OHLCVBar,
)
from toolserver import features as feat
from toolserver.config import BUILDER_VERSION, SnapshotConfig
from toolserver.errors import ToolServerError

FALLBACK_SPREAD_BPS = 3.0
FALLBACK_DEPTH_USD = 250_000.0
DAY = timedelta(days=1)

# Cadenza di funding usata solo quando la serie è troppo corta per osservarla.
DEFAULT_FUNDING_INTERVAL_HOURS = 1.0


class MarketDataSource(Protocol):
    """Ciò che serve al builder. I test iniettano una sorgente deterministica."""

    def meta_and_asset_ctxs(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...

    def candles(
        self, coin: str, interval: str, start_ms: int, end_ms: int
    ) -> list[dict[str, Any]]: ...

    def funding_history(
        self, coin: str, start_ms: int, end_ms: int
    ) -> list[dict[str, Any]]: ...


class SnapshotBuildError(ToolServerError):
    code = "snapshot_build_error"


def normalized_asof(moment: datetime, config: SnapshotConfig) -> datetime:
    """Ora UTC fissa e configurabile: lo snapshot del giorno ha un solo asof."""
    moment_utc = moment.astimezone(timezone.utc)
    return moment_utc.replace(
        hour=config.snapshot_hour_utc, minute=0, second=0, microsecond=0
    )


class SnapshotBuilder:
    """Costruisce un MarketSnapshot sigillato da una sorgente di dati."""

    def __init__(self, source: MarketDataSource, config: SnapshotConfig | None = None):
        self._source = source
        self._config = config or SnapshotConfig()

    def build(self, asof: datetime) -> MarketSnapshot:
        asof_utc = normalized_asof(asof, self._config)
        universe, ctx_by_symbol = self._select_universe()
        if not universe:
            raise SnapshotBuildError("universo vuoto: nessun asset selezionabile")

        start_ms = int((asof_utc - timedelta(days=self._config.lookback_days)).timestamp() * 1000)
        end_ms = int(asof_utc.timestamp() * 1000)

        provisional: list[AssetSnapshot] = []
        for symbol in universe:
            bars = self._fetch_bars(symbol, start_ms, end_ms, asof_utc)
            if not bars:
                raise SnapshotBuildError(
                    f"nessuna barra chiusa disponibile per {symbol} entro {asof_utc.isoformat()}"
                )
            funding = self._fetch_funding(symbol, start_ms, end_ms, asof_utc)
            ctx = ctx_by_symbol.get(symbol, {})
            provisional.append(
                AssetSnapshot(
                    symbol=symbol,
                    mark_price=self._mark_price(ctx, bars),
                    ohlcv_daily=bars,
                    funding=funding,
                    rankings=(),
                    liquidity=self._liquidity(ctx),
                    costs=CostModel(
                        maker_bps=self._config.maker_bps,
                        taker_bps=self._config.taker_bps,
                    ),
                )
            )

        # I ranking si calcolano sugli asset, non sullo snapshot: lo snapshot
        # non esiste ancora, e sigillarlo due volte cambierebbe lo snapshot_id.
        ranks = feat.ranks_from_assets(provisional)
        assets = tuple(
            asset.model_copy(
                update={"rankings": self._ranks_for(asset.symbol, ranks)}
            )
            for asset in provisional
        )

        return MarketSnapshot.build(
            asof_utc=asof_utc,
            universe=tuple(a.symbol for a in assets),
            universe_status=self._config.universe_status,
            assets=assets,
            source="hyperliquid_public_info",
            builder_version=BUILDER_VERSION,
        )

    # -- universo ----------------------------------------------------------

    def _select_universe(self) -> tuple[list[str], dict[str, dict[str, Any]]]:
        """Core (BTC, ETH) + top-N per volume giornaliero. Ordine deterministico."""
        meta, ctxs = self._source.meta_and_asset_ctxs()
        names = [entry.get("name") for entry in meta]
        ctx_by_symbol: dict[str, dict[str, Any]] = {}
        volume_by_symbol: dict[str, float] = {}
        for name, ctx in zip(names, ctxs, strict=False):
            if not isinstance(name, str) or not isinstance(ctx, dict):
                continue
            ctx_by_symbol[name] = ctx
            volume_by_symbol[name] = _to_float(ctx.get("dayNtlVlm")) or 0.0

        core = [s for s in self._config.core_universe if s in ctx_by_symbol]
        ranked = sorted(
            (s for s in ctx_by_symbol if s not in core),
            key=lambda s: (-volume_by_symbol[s], s),
        )
        selected = core + ranked[: self._config.top_n_by_volume]
        return selected, ctx_by_symbol

    # -- serie -------------------------------------------------------------

    def _fetch_bars(
        self, symbol: str, start_ms: int, end_ms: int, asof_utc: datetime
    ) -> tuple[OHLCVBar, ...]:
        raw = self._source.candles(symbol, "1d", start_ms, end_ms)
        bars: list[OHLCVBar] = []
        for candle in raw:
            ts_open = datetime.fromtimestamp(int(candle["t"]) / 1000, tz=timezone.utc)
            # Solo barre CHIUSE: una barra daily che apre a ts è completa solo
            # quando ts + 1 giorno <= asof. Questo è il filtro anti look-ahead.
            if ts_open + DAY > asof_utc:
                continue
            bars.append(
                OHLCVBar(
                    ts_open_utc=ts_open,
                    open=float(candle["o"]),
                    high=float(candle["h"]),
                    low=float(candle["l"]),
                    close=float(candle["c"]),
                    volume_usd=float(candle.get("v", 0.0)) * float(candle["c"]),
                )
            )
        bars.sort(key=lambda b: b.ts_open_utc)
        return tuple(bars)

    def _fetch_funding(
        self, symbol: str, start_ms: int, end_ms: int, asof_utc: datetime
    ) -> tuple[FundingPoint, ...]:
        raw = self._source.funding_history(symbol, start_ms, end_ms)
        by_ts: dict[datetime, float] = {}
        for item in raw:
            ts = datetime.fromtimestamp(int(item["time"]) / 1000, tz=timezone.utc)
            if ts > asof_utc:
                continue
            rate = _to_float(item.get("fundingRate"))
            if rate is None:
                continue
            # La paginazione può ripresentare un bordo: l'ultimo vince, ma il
            # valore è lo stesso — serve solo a non duplicare il punto.
            by_ts[ts] = rate

        timestamps = sorted(by_ts)
        if not timestamps:
            return ()
        self._assert_funding_fresh(symbol, timestamps[-1], asof_utc)
        interval = self._funding_interval_hours(timestamps)
        return tuple(
            FundingPoint(ts_utc=ts, rate=by_ts[ts], interval_hours=interval)
            for ts in timestamps
        )

    def _assert_funding_fresh(
        self, symbol: str, latest: datetime, asof_utc: datetime
    ) -> None:
        """Il funding stantio è il fallimento silenzioso più costoso qui.

        Una serie che si ferma settimane prima di `asof` continua a validare e
        a produrre uno snapshot sigillato, ma `funding_rate_current` descrive
        un altro mondo. Meglio un errore pulito (§7).
        """
        lag_hours = (asof_utc - latest).total_seconds() / 3600.0
        if lag_hours > self._config.max_funding_staleness_hours:
            raise SnapshotBuildError(
                f"funding stantio per {symbol}: ultimo punto "
                f"{latest.isoformat()}, {lag_hours:.1f}h prima di "
                f"{asof_utc.isoformat()} (limite "
                f"{self._config.max_funding_staleness_hours}h)"
            )

    @staticmethod
    def _funding_interval_hours(timestamps: list[datetime]) -> float:
        """Cadenza OSSERVATA, non assunta.

        Hyperliquid accredita il funding ogni ora; altre venue ogni otto.
        Fissare il valore a 8.0 gonfierebbe di 8x `funding_rate_annualized`,
        che su una campagna carry è la feature che decide. Il valore si aggancia
        al quarto d'ora più vicino per non far dipendere lo `snapshot_id` dal
        jitter di qualche millisecondo nei timestamp.
        """
        if len(timestamps) < 2:
            return DEFAULT_FUNDING_INTERVAL_HOURS
        deltas = sorted(
            (b - a).total_seconds() / 3600.0
            for a, b in zip(timestamps, timestamps[1:])
        )
        median = deltas[len(deltas) // 2]
        snapped = round(median * 4.0) / 4.0
        return snapped if snapped > 0.0 else DEFAULT_FUNDING_INTERVAL_HOURS

    # -- derivati ----------------------------------------------------------

    @staticmethod
    def _mark_price(ctx: dict[str, Any], bars: tuple[OHLCVBar, ...]) -> float:
        mark = _to_float(ctx.get("markPx"))
        if mark and mark > 0.0:
            return mark
        return bars[-1].close

    @staticmethod
    def _liquidity(ctx: dict[str, Any]) -> LiquidityEstimate:
        """Spread e depth **stimati**, con lo stimatore dichiarato nel record."""
        impact = ctx.get("impactPxs")
        mid = _to_float(ctx.get("midPx")) or _to_float(ctx.get("markPx"))
        if isinstance(impact, list) and len(impact) == 2 and mid and mid > 0.0:
            bid, ask = _to_float(impact[0]), _to_float(impact[1])
            if bid and ask and ask >= bid:
                return LiquidityEstimate(
                    spread_bps=min((ask - bid) / mid * 10_000.0, 10_000.0),
                    depth_usd_1pct=FALLBACK_DEPTH_USD,
                    estimator="hyperliquid_impact_px_v0",
                )
        return LiquidityEstimate(
            spread_bps=FALLBACK_SPREAD_BPS,
            depth_usd_1pct=FALLBACK_DEPTH_USD,
            estimator="static_fallback_v0",
        )

    @staticmethod
    def _ranks_for(
        symbol: str, ranks: dict[str, dict[str, dict[str, Any]]]
    ) -> tuple[CrossSectionalRank, ...]:
        out: list[CrossSectionalRank] = []
        for metric in sorted(ranks):
            entry = ranks[metric].get(symbol)
            if entry is None:
                continue
            out.append(
                CrossSectionalRank(
                    metric=metric,
                    rank=entry["rank"],
                    universe_size=entry["universe_size"],
                    value=entry["value"],
                )
            )
        return tuple(out)


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
