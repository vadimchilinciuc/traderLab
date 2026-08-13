"""Configurazione del Tool Server e dello SnapshotBuilder."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Universo UFFICIALE, consegnato dal Pre-Screen (che gira in zeroPipes) con la
# promozione del Candidato 2: campagna carry sul perimetro P3 = BTC + ETH.
# L'universo è esattamente questo: nessuna coda per volume, perché ogni asset
# in più è un asset su cui il Pre-Screen non si è pronunciato.
DEFAULT_CORE_UNIVERSE: tuple[str, ...] = ("BTC", "ETH")
DEFAULT_TOP_N_BY_VOLUME: int = 0

# Oltre questo ritardo il funding non descrive più il presente: errore pulito.
DEFAULT_MAX_FUNDING_STALENESS_HOURS: float = 48.0

# Ora UTC fissa a cui lo snapshot del giorno viene costruito, UNA volta sola.
DEFAULT_SNAPSHOT_HOUR_UTC: int = 0

BUILDER_VERSION = "snapshot_builder-0.1.0"


@dataclass(frozen=True, slots=True)
class SnapshotConfig:
    """Parametri di costruzione dello snapshot giornaliero."""

    core_universe: tuple[str, ...] = DEFAULT_CORE_UNIVERSE
    top_n_by_volume: int = DEFAULT_TOP_N_BY_VOLUME
    snapshot_hour_utc: int = DEFAULT_SNAPSHOT_HOUR_UTC
    lookback_days: int = 120
    maker_bps: float = 1.5
    taker_bps: float = 4.5
    universe_status: str = "pre_screen_ufficiale"
    max_funding_staleness_hours: float = DEFAULT_MAX_FUNDING_STALENESS_HOURS

    def __post_init__(self) -> None:
        if not 0 <= self.snapshot_hour_utc <= 23:
            raise ValueError("snapshot_hour_utc fuori range")
        if self.top_n_by_volume < 0:
            raise ValueError("top_n_by_volume negativo")
        if self.max_funding_staleness_hours <= 0:
            raise ValueError("max_funding_staleness_hours non positivo")


@dataclass(frozen=True, slots=True)
class ToolServerConfig:
    """Percorsi dello store. Il Tool Server non conosce altre sorgenti."""

    snapshot_dir: Path = field(default_factory=lambda: Path("data/snapshots"))
    toolcall_log_dir: Path = field(default_factory=lambda: Path("data/toolcalls"))


def network_allowed() -> bool:
    """La rete pubblica si tocca solo in build, dietro flag esplicito."""
    return os.environ.get("TRADERLAB_ALLOW_NETWORK") == "1"


def live_api_allowed() -> bool:
    """Lo smoke test con API reale è opt-in e mai attivo nella suite."""
    return os.environ.get("TRADERLAB_ALLOW_LIVE_API") == "1"
