"""Client minimale dell'API pubblica Hyperliquid.

**Usato solo dallo SnapshotBuilder**, mai durante una decisione. Il Tool Server
non importa questo modulo. La rete richiede il flag `TRADERLAB_ALLOW_NETWORK=1`:
senza flag, ogni chiamata solleva prima di aprire un socket.

Nessuna chiave, nessuna firma, nessun endpoint di trading: solo `/info`.
"""

from __future__ import annotations

from typing import Any

import httpx

from toolserver.config import network_allowed
from toolserver.errors import ToolServerError

INFO_URL = "https://api.hyperliquid.xyz/info"
DEFAULT_TIMEOUT = 30.0


class NetworkDisabled(ToolServerError):
    code = "network_disabled"


class HyperliquidError(ToolServerError):
    code = "hyperliquid_error"


class HyperliquidPublicClient:
    """Wrapper sull'endpoint pubblico `/info`."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, url: str = INFO_URL) -> None:
        self._timeout = timeout
        self._url = url

    def _post(self, payload: dict[str, Any]) -> Any:
        if not network_allowed():
            raise NetworkDisabled(
                "rete disabilitata. Imposta TRADERLAB_ALLOW_NETWORK=1 solo per "
                "costruire uno snapshot, mai durante una decisione."
            )
        try:
            response = httpx.post(self._url, json=payload, timeout=self._timeout)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise HyperliquidError(f"chiamata a {self._url} fallita: {exc}") from exc

    def meta_and_asset_ctxs(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Metadati dell'universo perp e contesto corrente per asset."""
        data = self._post({"type": "metaAndAssetCtxs"})
        if not isinstance(data, list) or len(data) != 2:
            raise HyperliquidError("risposta metaAndAssetCtxs inattesa")
        meta, ctxs = data
        universe = meta.get("universe") if isinstance(meta, dict) else None
        if not isinstance(universe, list) or not isinstance(ctxs, list):
            raise HyperliquidError("struttura metaAndAssetCtxs inattesa")
        return universe, ctxs

    def candles(
        self, coin: str, interval: str, start_ms: int, end_ms: int
    ) -> list[dict[str, Any]]:
        """Candele storiche. `interval` tipicamente '1d'."""
        data = self._post(
            {
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": interval,
                    "startTime": start_ms,
                    "endTime": end_ms,
                },
            }
        )
        if not isinstance(data, list):
            raise HyperliquidError(f"risposta candleSnapshot inattesa per {coin}")
        return data

    def funding_history(
        self, coin: str, start_ms: int, end_ms: int
    ) -> list[dict[str, Any]]:
        data = self._post(
            {
                "type": "fundingHistory",
                "coin": coin,
                "startTime": start_ms,
                "endTime": end_ms,
            }
        )
        if not isinstance(data, list):
            raise HyperliquidError(f"risposta fundingHistory inattesa per {coin}")
        return data
