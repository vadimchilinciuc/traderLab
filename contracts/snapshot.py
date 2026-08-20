"""MarketSnapshot — la fotografia congelata del mondo che il Trader può vedere.

Disciplina point-in-time: tutto ciò che sta qui dentro ha timestamp <= asof_utc.
Lo `snapshot_id` è lo sha256 del contenuto canonico *escluso lo snapshot_id
stesso*: due costruzioni con lo stesso contenuto producono lo stesso id, e un
contenuto alterato di un byte produce un id diverso.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import Field, ValidationInfo, field_validator, model_validator

from contracts.base import FrozenModel, require_utc
from contracts.hashing import sha256_of

Bps = Annotated[float, Field(ge=0.0, le=10_000.0)]


class OHLCVBar(FrozenModel):
    """Barra daily. `ts_open_utc` è l'apertura della barra, non la chiusura."""

    ts_open_utc: datetime
    open: float = Field(gt=0.0)
    high: float = Field(gt=0.0)
    low: float = Field(gt=0.0)
    close: float = Field(gt=0.0)
    volume_usd: float = Field(ge=0.0)

    @field_validator("ts_open_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return require_utc(v, "ts_open_utc")

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.high < self.low:
            raise ValueError("high < low")
        if not (self.low <= self.open <= self.high):
            raise ValueError("open fuori dal range [low, high]")
        if not (self.low <= self.close <= self.high):
            raise ValueError("close fuori dal range [low, high]")
        return self


class FundingPoint(FrozenModel):
    """Funding rate perpetuo, in frazione per intervallo (non annualizzato)."""

    ts_utc: datetime
    rate: float
    interval_hours: float = Field(gt=0.0)

    @field_validator("ts_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return require_utc(v, "ts_utc")


#: Provenienza di `depth_usd_1pct`, dichiarata dentro lo snapshot stesso.
#: Foglio 19/08 punto 15: la profondità non è stimata, è una **costante
#: dichiarata** — il builder ci mette 250.000 USD sempre, qualunque cosa dica
#: il book. Finché l'etichetta stava solo nel nome del campo (`..._estimated`)
#: e nel commento del builder, chi leggeva un record vecchio non aveva modo di
#: sapere quale delle due cose stesse guardando.
DepthSource = Literal["costante_dichiarata", "stimata", "misurata"]


class LiquidityEstimate(FrozenModel):
    """Spread e profondità dell'asset, ciascuno con la propria provenienza.

    `spread_bps` è davvero stimato, dal book: `estimator` dice come.
    `depth_usd_1pct` no — oggi è una costante, e `depth_source` lo dice a
    chiunque legga il record senza dover risalire al codice del builder che
    l'ha scritto. Una costante spacciata per stima è il tipo di errore che si
    scopre mesi dopo, quando qualcuno ci calcola sopra un impatto di mercato.
    """

    spread_bps: Bps
    depth_usd_1pct: float = Field(ge=0.0)
    depth_source: DepthSource
    estimator: str = Field(min_length=1)


class CostModel(FrozenModel):
    """Costi reali Hyperliquid, in basis point sul nozionale."""

    maker_bps: Bps
    taker_bps: Bps


class CrossSectionalRank(FrozenModel):
    """Posizione dell'asset in una classifica cross-sezionale del giorno.

    `rank` è 1-based; `universe_size` permette di normalizzare senza dover
    ricostruire l'universo.
    """

    metric: str = Field(min_length=1)
    rank: int = Field(ge=1)
    universe_size: int = Field(ge=1)
    value: float

    @model_validator(mode="after")
    def _rank_in_range(self) -> Self:
        if self.rank > self.universe_size:
            raise ValueError("rank > universe_size")
        return self


class AssetSnapshot(FrozenModel):
    """Tutto ciò che si sa di un asset al momento `asof_utc` dello snapshot."""

    symbol: str = Field(min_length=1)
    mark_price: float = Field(gt=0.0)
    ohlcv_daily: tuple[OHLCVBar, ...] = Field(min_length=1)
    funding: tuple[FundingPoint, ...] = ()
    rankings: tuple[CrossSectionalRank, ...] = ()
    liquidity: LiquidityEstimate
    costs: CostModel

    @model_validator(mode="after")
    def _bars_ordered(self) -> Self:
        ts = [bar.ts_open_utc for bar in self.ohlcv_daily]
        if ts != sorted(ts):
            raise ValueError("ohlcv_daily non ordinato per ts_open_utc crescente")
        if len(set(ts)) != len(ts):
            raise ValueError("ohlcv_daily contiene timestamp duplicati")
        return self


class MarketSnapshot(FrozenModel):
    """Stato del mondo congelato per una giornata di decisioni.

    `universe_status` dichiara se l'universo è quello ufficiale del Pre-Screen
    o un placeholder di lavoro. Il campo è parte del contenuto hashato: un
    cambio di stato produce uno snapshot_id diverso.
    """

    asof_utc: datetime
    universe: tuple[str, ...] = Field(min_length=1)
    universe_status: Literal["placeholder_non_ufficiale", "pre_screen_ufficiale"]
    assets: tuple[AssetSnapshot, ...] = Field(min_length=1)
    source: str = Field(min_length=1)
    builder_version: str = Field(min_length=1)
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("asof_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return require_utc(v, "asof_utc")

    @model_validator(mode="after")
    def _integrity(self, info: ValidationInfo) -> Self:
        symbols = [a.symbol for a in self.assets]
        if len(set(symbols)) != len(symbols):
            raise ValueError("assets contiene simboli duplicati")
        if set(symbols) != set(self.universe):
            raise ValueError("universe e assets non coincidono")
        for asset in self.assets:
            for bar in asset.ohlcv_daily:
                if bar.ts_open_utc > self.asof_utc:
                    raise ValueError(
                        f"look-ahead: barra {bar.ts_open_utc.isoformat()} di "
                        f"{asset.symbol} è successiva ad asof_utc"
                    )
            for point in asset.funding:
                if point.ts_utc > self.asof_utc:
                    raise ValueError(
                        f"look-ahead: funding {point.ts_utc.isoformat()} di "
                        f"{asset.symbol} è successivo ad asof_utc"
                    )
        context = info.context or {}
        if not context.get("sealing"):
            expected = compute_snapshot_id(
                self.canonical_payload(exclude={"snapshot_id"})
            )
            if self.snapshot_id != expected:
                raise ValueError(
                    f"snapshot_id non corrisponde al contenuto "
                    f"(atteso {expected}, ricevuto {self.snapshot_id})"
                )
        return self

    @classmethod
    def build(cls, **fields: Any) -> MarketSnapshot:
        """Costruisce lo snapshot calcolando `snapshot_id` dal contenuto.

        Due passate: la prima valida tutto tranne l'id (contesto `sealing`) per
        ottenere il payload canonico, la seconda sigilla con l'id calcolato e
        ri-valida senza scorciatoie.
        """
        if "snapshot_id" in fields:
            raise ValueError("snapshot_id è derivato, non va passato a build()")
        probe = cls.model_validate(
            {**fields, "snapshot_id": "0" * 64}, context={"sealing": True}
        )
        payload = probe.canonical_payload(exclude={"snapshot_id"})
        return cls.model_validate(
            {**fields, "snapshot_id": compute_snapshot_id(payload)}
        )


def compute_snapshot_id(payload_without_id: dict[str, Any]) -> str:
    return sha256_of(payload_without_id)
