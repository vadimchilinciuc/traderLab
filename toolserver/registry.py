"""ToolRegistry — tool read-only sopra lo snapshot congelato.

Le descrizioni sono **neutre e fattuali**: niente verbi valutativi, niente
aggettivi che suggeriscano una direzione, nessun riferimento a gara, repliche,
valutazione o performance (CLAUDE.md §6). Il wording di uno schema orienta il
comportamento dell'agente: qui è parte del disegno sperimentale, non copy.

Tutti i tool leggono un solo snapshot, identificato da `snapshot_id`. Non
esiste un tool che accetti una data, una finestra "fino a oggi" o un simbolo
fuori dall'universo dello snapshot: quelle richieste sono errori puliti.
"""

from __future__ import annotations

from typing import Any

from contracts.hashing import sha256_of
from contracts.snapshot import AssetSnapshot, MarketSnapshot
from contracts.vocabulary import PRIMITIVE_FEATURES
from toolserver import features as feat
from toolserver.errors import (
    InvalidToolArguments,
    OutOfSnapshotRequest,
    UnknownAsset,
    UnknownTool,
)
from toolserver.store import SnapshotStore
from toolserver.toollog import ToolCallLog

MAX_OHLCV_BARS = 120


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


_SYMBOL_PROP = {
    "type": "string",
    "description": "Simbolo dell'asset, come compare in get_universe.",
}

TOOL_SCHEMAS: tuple[dict[str, Any], ...] = (
    {
        "name": "get_universe",
        "description": (
            "Restituisce l'elenco dei simboli contenuti nello snapshot corrente, "
            "l'istante di riferimento dello snapshot e lo stato dichiarato "
            "dell'universo."
        ),
        "strict": True,
        "input_schema": _schema({}, []),
    },
    {
        "name": "get_ohlcv",
        "description": (
            "Restituisce le barre giornaliere open, high, low, close e volume in "
            "USD di un simbolo. Le barre sono ordinate dalla più vecchia alla più "
            f"recente. Il parametro bars limita il numero di barre restituite, al "
            f"massimo {MAX_OHLCV_BARS}."
        ),
        "strict": True,
        "input_schema": _schema(
            {
                "symbol": _SYMBOL_PROP,
                "bars": {
                    "type": "integer",
                    "description": "Numero di barre più recenti da restituire.",
                },
            },
            ["symbol", "bars"],
        ),
    },
    {
        "name": "get_funding",
        "description": (
            "Restituisce i punti di funding rate del perpetuo di un simbolo, con "
            "il timestamp e la durata in ore dell'intervallo a cui il tasso si "
            "riferisce. Il tasso è espresso in frazione per intervallo."
        ),
        "strict": True,
        "input_schema": _schema({"symbol": _SYMBOL_PROP}, ["symbol"]),
    },
    {
        "name": "get_rankings",
        "description": (
            "Restituisce la posizione di ogni simbolo dell'universo nelle "
            "classifiche cross-sezionali calcolate sullo snapshot. La posizione 1 "
            "corrisponde al valore più alto della metrica. Il valore 'all' "
            "restituisce tutte le metriche disponibili."
        ),
        "strict": True,
        "input_schema": _schema(
            {
                "metric": {
                    "type": "string",
                    "description": "Nome della metrica di classifica, oppure 'all'.",
                    "enum": [*feat.RANKED_METRICS, "all"],
                }
            },
            ["metric"],
        ),
    },
    {
        "name": "get_costs",
        "description": (
            "Restituisce, per un simbolo, le commissioni maker e taker in basis "
            "point, la stima dello spread dal book — con il nome dello stimatore "
            "usato — e la profondità dichiarata entro l'1% dal mid, che è una "
            "costante del costruttore dello snapshot, non una misura."
        ),
        "strict": True,
        "input_schema": _schema({"symbol": _SYMBOL_PROP}, ["symbol"]),
    },
    {
        "name": "get_asset_dossier",
        "description": (
            "Restituisce, per un simbolo, il prezzo mark e il valore corrente di "
            "tutte le grandezze del vocabolario primitivo calcolate sullo "
            "snapshot. Un valore null indica che la grandezza non è calcolabile "
            "con lo storico disponibile."
        ),
        "strict": True,
        "input_schema": _schema({"symbol": _SYMBOL_PROP}, ["symbol"]),
    },
)

TOOL_NAMES: tuple[str, ...] = tuple(t["name"] for t in TOOL_SCHEMAS)


def tool_schemas_sha() -> str:
    """Sha degli schemi dei tool di lettura, per il Freeze manifest."""
    return sha256_of(list(TOOL_SCHEMAS))


class ToolRegistry:
    """Dispatcher dei tool di lettura, con logging totale.

    Non conosce la rete. Non conosce l'orologio di sistema come sorgente di
    dati. Conosce solo lo `SnapshotStore` che gli è stato passato.
    """

    def __init__(self, store: SnapshotStore, log: ToolCallLog) -> None:
        self._store = store
        self._log = log

    @staticmethod
    def schemas() -> list[dict[str, Any]]:
        return [dict(s) for s in TOOL_SCHEMAS]

    def call(
        self,
        *,
        snapshot_id: str,
        replica_id: str,
        name: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Esegue un tool e logga sempre — anche quando fallisce."""
        args = dict(args or {})
        try:
            result = self._dispatch(snapshot_id, name, args)
        except Exception as exc:
            self._log.record(
                replica_id=replica_id,
                snapshot_id=snapshot_id,
                tool=name,
                args=args,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        self._log.record(
            replica_id=replica_id,
            snapshot_id=snapshot_id,
            tool=name,
            args=args,
            response=result,
        )
        return result

    # -- dispatch ----------------------------------------------------------

    def _dispatch(
        self, snapshot_id: str, name: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        if name not in TOOL_NAMES:
            raise UnknownTool(
                f"tool '{name}' non esiste. Tool disponibili: {', '.join(TOOL_NAMES)}"
            )
        snapshot = self._store.load(snapshot_id)
        handler = getattr(self, f"_tool_{name}")
        return handler(snapshot, args)

    def _asset(self, snapshot: MarketSnapshot, args: dict[str, Any]) -> AssetSnapshot:
        symbol = args.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            raise InvalidToolArguments("il parametro 'symbol' è obbligatorio")
        asset = next((a for a in snapshot.assets if a.symbol == symbol), None)
        if asset is None:
            raise UnknownAsset(
                f"'{symbol}' non è nell'universo dello snapshot "
                f"({', '.join(snapshot.universe)})"
            )
        return asset

    # -- implementazioni ---------------------------------------------------

    def _tool_get_universe(
        self, snapshot: MarketSnapshot, args: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "asof_utc": snapshot.asof_utc.isoformat(),
            "universe": list(snapshot.universe),
            "universe_status": snapshot.universe_status,
            "snapshot_id": snapshot.snapshot_id,
        }

    def _tool_get_ohlcv(
        self, snapshot: MarketSnapshot, args: dict[str, Any]
    ) -> dict[str, Any]:
        asset = self._asset(snapshot, args)
        bars_arg = args.get("bars")
        if not isinstance(bars_arg, int) or isinstance(bars_arg, bool):
            raise InvalidToolArguments("il parametro 'bars' deve essere un intero")
        if bars_arg < 1:
            raise InvalidToolArguments("il parametro 'bars' deve essere >= 1")
        if bars_arg > MAX_OHLCV_BARS:
            raise OutOfSnapshotRequest(
                f"richieste {bars_arg} barre, il massimo servibile è {MAX_OHLCV_BARS}"
            )
        selected = asset.ohlcv_daily[-bars_arg:]
        return {
            "symbol": asset.symbol,
            "asof_utc": snapshot.asof_utc.isoformat(),
            "bars_returned": len(selected),
            "bars_available": len(asset.ohlcv_daily),
            "bars": [
                {
                    "ts_open_utc": b.ts_open_utc.isoformat(),
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume_usd": b.volume_usd,
                }
                for b in selected
            ],
        }

    def _tool_get_funding(
        self, snapshot: MarketSnapshot, args: dict[str, Any]
    ) -> dict[str, Any]:
        asset = self._asset(snapshot, args)
        return {
            "symbol": asset.symbol,
            "asof_utc": snapshot.asof_utc.isoformat(),
            "points": [
                {
                    "ts_utc": p.ts_utc.isoformat(),
                    "rate": p.rate,
                    "interval_hours": p.interval_hours,
                }
                for p in asset.funding
            ],
        }

    def _tool_get_rankings(
        self, snapshot: MarketSnapshot, args: dict[str, Any]
    ) -> dict[str, Any]:
        metric = args.get("metric", "all")
        ranks = feat.cross_sectional_ranks(snapshot)
        if metric != "all":
            if metric not in ranks:
                raise InvalidToolArguments(
                    f"metrica '{metric}' non disponibile. "
                    f"Disponibili: {', '.join(sorted(ranks))}"
                )
            ranks = {metric: ranks[metric]}
        return {
            "asof_utc": snapshot.asof_utc.isoformat(),
            "rankings": {
                m: [
                    {
                        "symbol": sym,
                        "rank": entry["rank"],
                        "universe_size": entry["universe_size"],
                        "value": entry["value"],
                    }
                    for sym, entry in sorted(by_symbol.items(), key=lambda kv: kv[1]["rank"])
                ]
                for m, by_symbol in sorted(ranks.items())
            },
        }

    def _tool_get_costs(
        self, snapshot: MarketSnapshot, args: dict[str, Any]
    ) -> dict[str, Any]:
        asset = self._asset(snapshot, args)
        # Foglio 19/08 punto 15, secondo tempo. Lo spread e' davvero stimato
        # dal book e la chiave lo dice; la profondita' no — il builder ci
        # mette la costante dichiarata di `snapshot_builder.DECLARED_DEPTH_USD`
        # in entrambi i rami, e `LiquidityEstimate.depth_source` lo registra.
        # La chiave esposta all'agente si chiamava `depth_usd_1pct_estimated`:
        # un nome che dopo l'etichettatura del T1 **mente**, perche' dice
        # "stimata" di un numero che e' una costante. Il nome onesto e'
        # `depth_usd_1pct_declared`, coerente con `costante_dichiarata`.
        #
        # E' una variabile di CONTENUTO: cambia cosa il Trader legge, non solo
        # come lo si misura. Va nella lista onesta del PREREG_LAB_S0_RUN2,
        # stessa classe di `depth_source`. Non tocca `tool_schemas_sha`: lo
        # schema di input di `get_costs` e' invariato, cambia solo la risposta.
        return {
            "symbol": asset.symbol,
            "maker_bps": asset.costs.maker_bps,
            "taker_bps": asset.costs.taker_bps,
            "spread_bps_estimated": asset.liquidity.spread_bps,
            "depth_usd_1pct_declared": asset.liquidity.depth_usd_1pct,
            "estimator": asset.liquidity.estimator,
        }

    def _tool_get_asset_dossier(
        self, snapshot: MarketSnapshot, args: dict[str, Any]
    ) -> dict[str, Any]:
        asset = self._asset(snapshot, args)
        values = feat.full_features(snapshot, asset.symbol)
        return {
            "symbol": asset.symbol,
            "asof_utc": snapshot.asof_utc.isoformat(),
            "mark_price": asset.mark_price,
            "features": {
                name: values.get(name) for name in sorted(PRIMITIVE_FEATURES)
            },
        }
