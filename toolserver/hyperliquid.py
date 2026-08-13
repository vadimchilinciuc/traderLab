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

# `fundingHistory` serve al massimo 500 record per chiamata, i più VECCHI a
# partire da `startTime`. Su una finestra di 120 giorni con funding orario
# significa fermarsi ~20 giorni dopo l'inizio: senza paginazione il funding
# corrente resterebbe fuori dallo snapshot, in silenzio.
FUNDING_PAGE_LIMIT = 500
MAX_FUNDING_PAGES = 60


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
        """Storico funding COMPLETO nella finestra, paginando in avanti.

        Una pagina piena significa "ce n'è ancora": si riparte dall'ultimo
        timestamp servito. Se la paginazione non converge entro
        `MAX_FUNDING_PAGES` è un errore pulito, non una serie troncata.
        """
        out: list[dict[str, Any]] = []
        cursor = start_ms
        for _ in range(MAX_FUNDING_PAGES):
            page = self._post(
                {
                    "type": "fundingHistory",
                    "coin": coin,
                    "startTime": cursor,
                    "endTime": end_ms,
                }
            )
            if not isinstance(page, list):
                raise HyperliquidError(f"risposta fundingHistory inattesa per {coin}")
            if not page:
                return out
            out.extend(page)
            if len(page) < FUNDING_PAGE_LIMIT:
                return out
            last_ts = _to_int(page[-1].get("time"))
            if last_ts is None:
                raise HyperliquidError(
                    f"fundingHistory per {coin}: record senza 'time', "
                    f"impossibile paginare senza perdere dati"
                )
            next_cursor = last_ts + 1
            if next_cursor <= cursor or next_cursor > end_ms:
                return out
            cursor = next_cursor
        raise HyperliquidError(
            f"fundingHistory per {coin}: paginazione non conclusa dopo "
            f"{MAX_FUNDING_PAGES} pagine. Meglio un errore che una serie troncata."
        )


def _to_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
