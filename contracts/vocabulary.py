"""Vocabolario chiuso delle feature primitive.

`features_used` è **un'ipotesi da verificare**, non un dato affidabile: la
letteratura sulla fedeltà (AlMarri et al. 2025/26; STaDS 2025) trova accordo
tra feature dichiarate e feature causalmente determinanti che va da rho=+0.25 a
rho=-0.54. Il vocabolario chiuso non rende le attribuzioni fedeli: le rende
*verificabili* e *ablabili*, che è la precondizione del Faithfulness Audit.

Ogni nome qui elencato deve essere calcolabile dal solo MarketSnapshot. Se un
nome non è calcolabile dallo snapshot, non appartiene a questo elenco.
"""

from __future__ import annotations

from types import MappingProxyType

# nome -> descrizione neutra e fattuale (nessun verbo valutativo)
PRIMITIVE_FEATURES: MappingProxyType[str, str] = MappingProxyType(
    {
        # Prezzo / rendimento
        "return_1d": "Rendimento semplice sull'ultima barra daily.",
        "return_7d": "Rendimento semplice sulle ultime 7 barre daily.",
        "return_30d": "Rendimento semplice sulle ultime 30 barre daily.",
        "price_vs_sma_20": "Rapporto prezzo/media mobile semplice a 20 barre, meno 1.",
        "price_vs_sma_50": "Rapporto prezzo/media mobile semplice a 50 barre, meno 1.",
        "drawdown_from_high_30d": "Scostamento dal massimo delle ultime 30 barre.",
        # Volatilità
        "realized_vol_20d": "Deviazione standard dei rendimenti daily su 20 barre.",
        "atr_pct_14d": "Average true range a 14 barre, in frazione del prezzo.",
        # Volume
        "volume_usd_1d": "Volume in USD dell'ultima barra daily.",
        "volume_ratio_20": "Volume dell'ultima barra diviso la media a 20 barre.",
        # Funding
        "funding_rate_current": "Ultimo funding rate per intervallo.",
        "funding_rate_mean_7d": "Media dei funding rate degli ultimi 7 giorni.",
        "funding_rate_annualized": "Ultimo funding rate riportato su base annua.",
        # Cross-sezionale
        "rank_return_7d": "Posizione nell'universo per rendimento a 7 giorni.",
        "rank_return_30d": "Posizione nell'universo per rendimento a 30 giorni.",
        "rank_volume_1d": "Posizione nell'universo per volume dell'ultima barra.",
        "rank_realized_vol_20d": "Posizione nell'universo per volatilità a 20 barre.",
        # Microstruttura / costi
        "spread_bps": "Spread stimato in basis point.",
        "depth_usd_1pct": "Profondità stimata in USD entro l'1% dal mid.",
        "cost_taker_bps": "Commissione taker in basis point.",
        "cost_maker_bps": "Commissione maker in basis point.",
    }
)

FEATURE_NAMES: tuple[str, ...] = tuple(sorted(PRIMITIVE_FEATURES))


def is_known_feature(name: str) -> bool:
    return name in PRIMITIVE_FEATURES
