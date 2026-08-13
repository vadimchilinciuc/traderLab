"""Costruisce lo snapshot del giorno e lo salva nello store.

Questo è l'UNICO punto del repo che tocca la rete pubblica, e solo con
`TRADERLAB_ALLOW_NETWORK=1`. Va eseguito in un processo separato dalle
decisioni, all'ora UTC fissa di configurazione.

    TRADERLAB_ALLOW_NETWORK=1 uv run python scripts/build_snapshot.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toolserver.config import (
    DEFAULT_SNAPSHOT_HOUR_UTC,
    DEFAULT_TOP_N_BY_VOLUME,
    SnapshotConfig,
    ToolServerConfig,
    network_allowed,
)
from toolserver.hyperliquid import HyperliquidPublicClient
from toolserver.snapshot_builder import SnapshotBuilder, normalized_asof
from toolserver.store import SnapshotStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--asof",
        default=None,
        help="Istante di riferimento ISO-8601 UTC (default: adesso, normalizzato).",
    )
    # I default vengono dalla config: un default duplicato qui sovrascriverebbe
    # in silenzio l'universo ufficiale del Pre-Screen.
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N_BY_VOLUME)
    parser.add_argument(
        "--hour-utc", type=int, default=DEFAULT_SNAPSHOT_HOUR_UTC
    )
    args = parser.parse_args()

    if not network_allowed():
        print(
            "ERRORE: rete disabilitata. Esegui con TRADERLAB_ALLOW_NETWORK=1 "
            "solo per costruire uno snapshot, mai durante una decisione.",
            file=sys.stderr,
        )
        return 2

    config = SnapshotConfig(top_n_by_volume=args.top_n, snapshot_hour_utc=args.hour_utc)
    moment = (
        datetime.fromisoformat(args.asof)
        if args.asof
        else datetime.now(tz=timezone.utc)
    )
    asof = normalized_asof(moment, config)

    builder = SnapshotBuilder(HyperliquidPublicClient(), config)
    snapshot = builder.build(asof)

    store = SnapshotStore(ToolServerConfig().snapshot_dir)
    path = store.save(snapshot)

    print(f"asof_utc        : {snapshot.asof_utc.isoformat()}")
    print(f"snapshot_id     : {snapshot.snapshot_id}")
    print(f"universo        : {', '.join(snapshot.universe)}")
    print(f"stato universo  : {snapshot.universe_status}")
    print(f"salvato in      : {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
