"""Calcolo delle feature primitive dal solo MarketSnapshot.

Ogni nome prodotto qui appartiene a `contracts.vocabulary.PRIMITIVE_FEATURES`.
Il calcolo è deterministico e chiuso sullo snapshot: nessuna sorgente esterna,
nessuno stato, nessuna data corrente. Due processi che ricevono lo stesso
snapshot producono gli stessi numeri.

Questo modulo è anche ciò che rende `features_used` **ablabile**: un audit di
fedeltà può mascherare una feature qui e rigiocare la decisione.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from contracts.snapshot import AssetSnapshot, MarketSnapshot

# Decimali di arrotondamento delle feature derivate. Fisso, per rendere il
# dossier byte-identico tra repliche e tra macchine.
ROUND_TO = 10

# Metriche su cui si calcolano i ranking cross-sezionali.
# rank 1 = valore più alto, tranne dove indicato.
RANKED_METRICS: tuple[str, ...] = (
    "return_7d",
    "return_30d",
    "volume_usd_1d",
    "realized_vol_20d",
)
RANK_FEATURE_NAMES: dict[str, str] = {
    "return_7d": "rank_return_7d",
    "return_30d": "rank_return_30d",
    "volume_usd_1d": "rank_volume_1d",
    "realized_vol_20d": "rank_realized_vol_20d",
}


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    return round(value, ROUND_TO)


def _simple_return(closes: list[float], lookback: int) -> float | None:
    if len(closes) < lookback + 1:
        return None
    past = closes[-(lookback + 1)]
    if past <= 0.0:
        return None
    return closes[-1] / past - 1.0


def _sma(closes: list[float], window: int) -> float | None:
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def _realized_vol(closes: list[float], window: int) -> float | None:
    if len(closes) < window + 1:
        return None
    rets = [
        closes[i] / closes[i - 1] - 1.0
        for i in range(len(closes) - window, len(closes))
        if closes[i - 1] > 0.0
    ]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var)


def _atr_pct(asset: AssetSnapshot, window: int) -> float | None:
    bars = asset.ohlcv_daily
    if len(bars) < window + 1:
        return None
    trs: list[float] = []
    for i in range(len(bars) - window, len(bars)):
        prev_close = bars[i - 1].close
        bar = bars[i]
        trs.append(
            max(
                bar.high - bar.low,
                abs(bar.high - prev_close),
                abs(bar.low - prev_close),
            )
        )
    last_close = bars[-1].close
    if last_close <= 0.0:
        return None
    return (sum(trs) / len(trs)) / last_close


def asset_features(asset: AssetSnapshot) -> dict[str, float | None]:
    """Feature per-asset, senza la parte cross-sezionale."""
    bars = asset.ohlcv_daily
    closes = [b.close for b in bars]
    volumes = [b.volume_usd for b in bars]
    last_close = closes[-1]

    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    high30 = max((b.high for b in bars[-30:]), default=None) if bars else None
    vol_mean_20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else None

    funding_rates = [p.rate for p in asset.funding]
    funding_current = funding_rates[-1] if funding_rates else None
    funding_7d = None
    funding_annualized = None
    if asset.funding:
        last = asset.funding[-1]
        # La finestra "7d" si deriva dalla cadenza dichiarata nel punto: un
        # numero fisso di punti vorrebbe dire sette giorni solo a 8h di
        # intervallo, e ventun ore a cadenza oraria.
        window = max(1, round(7.0 * 24.0 / last.interval_hours))
        recent = funding_rates[-window:]
        funding_7d = sum(recent) / len(recent)
        funding_annualized = last.rate * (365.0 * 24.0) / last.interval_hours

    features: dict[str, float | None] = {
        "return_1d": _simple_return(closes, 1),
        "return_7d": _simple_return(closes, 7),
        "return_30d": _simple_return(closes, 30),
        "price_vs_sma_20": (last_close / sma20 - 1.0) if sma20 else None,
        "price_vs_sma_50": (last_close / sma50 - 1.0) if sma50 else None,
        "drawdown_from_high_30d": (
            (last_close / high30 - 1.0) if high30 and high30 > 0.0 else None
        ),
        "realized_vol_20d": _realized_vol(closes, 20),
        "atr_pct_14d": _atr_pct(asset, 14),
        "volume_usd_1d": volumes[-1],
        "volume_ratio_20": (
            (volumes[-1] / vol_mean_20) if vol_mean_20 and vol_mean_20 > 0.0 else None
        ),
        "funding_rate_current": funding_current,
        "funding_rate_mean_7d": funding_7d,
        "funding_rate_annualized": funding_annualized,
        "spread_bps": asset.liquidity.spread_bps,
        "depth_usd_1pct": asset.liquidity.depth_usd_1pct,
        "cost_taker_bps": asset.costs.taker_bps,
        "cost_maker_bps": asset.costs.maker_bps,
    }
    return {k: _round(v) for k, v in features.items()}


def cross_sectional_ranks(
    snapshot: MarketSnapshot,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Ranking cross-sezionali del giorno, a partire da uno snapshot sigillato."""
    return ranks_from_assets(snapshot.assets)


def ranks_from_assets(
    assets: Sequence[AssetSnapshot],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Ranking cross-sezionali da una collezione di asset.

    Ritorna: {metrica: {simbolo: {"rank", "universe_size", "value"}}}.
    Rank 1 = valore più alto. Gli asset con valore assente sono esclusi dalla
    classifica di quella metrica (e non vengono messi in coda arbitrariamente).

    Accetta gli asset e non lo snapshot perché lo SnapshotBuilder deve calcolare
    i ranking *prima* di poter sigillare lo snapshot.
    """
    per_asset = {a.symbol: asset_features(a) for a in assets}
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for metric in RANKED_METRICS:
        scored = [
            (sym, feats[metric])
            for sym, feats in per_asset.items()
            if feats.get(metric) is not None
        ]
        # Ordinamento deterministico: valore decrescente, poi simbolo crescente
        # per spezzare i pari in modo riproducibile.
        scored.sort(key=lambda item: (-item[1], item[0]))
        size = len(scored)
        out[metric] = {
            sym: {"rank": i + 1, "universe_size": size, "value": value}
            for i, (sym, value) in enumerate(scored)
        }
    return out


def full_features(snapshot: MarketSnapshot, symbol: str) -> dict[str, float | None]:
    """Feature per-asset + rank cross-sezionali, con i nomi del vocabolario."""
    asset = next((a for a in snapshot.assets if a.symbol == symbol), None)
    if asset is None:
        raise KeyError(symbol)
    features = asset_features(asset)
    ranks = cross_sectional_ranks(snapshot)
    for metric, feature_name in RANK_FEATURE_NAMES.items():
        entry = ranks.get(metric, {}).get(symbol)
        features[feature_name] = float(entry["rank"]) if entry else None
    return features
