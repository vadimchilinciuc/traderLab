"""CLI del rito quotidiano. La logica sta in `arena/daily_ritual.py`.

    uv run python scripts/run_daily.py
    uv run python scripts/run_daily.py --live

Exit code: vedi `arena.daily_ritual.EXIT_MEANING` e docs/OPERATIONS.md.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.config import DEFAULT_MANIFEST_PATH
from arena.daily_ritual import (
    DEFAULT_LEDGER_PATH,
    DEFAULT_LOG_DIR,
    DEFAULT_OPS_PATH,
    run_daily,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="usa l'API reale")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER_PATH))
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help=(
            "percorso del FreezeManifest COMMITTATO della stagione, passato "
            "tal quale a scripts/run_day.py. Il rito non lo indovina: se non "
            "lo si dichiara, vale il default di arena/config.py"
        ),
    )
    parser.add_argument("--ops-ledger", default=str(DEFAULT_OPS_PATH))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument(
        "--require-configured-hour",
        action="store_true",
        help=(
            "fallisce se l'ora UTC non e' quella configurata: da usare quando "
            "il rito e' schedulato, non quando lo si lancia a mano"
        ),
    )
    args = parser.parse_args(argv)

    now = datetime.now(tz=timezone.utc)
    result = run_daily(
        repo_root=Path(__file__).resolve().parents[1],
        today=now.date(),
        now_utc=now,
        python_executable=sys.executable,
        live=args.live,
        ledger_path=Path(args.ledger),
        manifest_path=Path(args.manifest),
        ops_path=Path(args.ops_ledger),
        log_dir=Path(args.log_dir),
        require_configured_hour=args.require_configured_hour,
    )

    print(f"\nlog             : {result.log_path}")
    print(f"exit code       : {result.exit_code} — {result.meaning}")
    if result.snapshot_id:
        print(f"snapshot_id     : {result.snapshot_id}")
    if result.skipped_marked:
        print(
            "giorni saltati  : "
            + ", ".join(d.isoformat() for d in result.skipped_marked)
        )
    if result.detail:
        print(f"dettaglio       : {result.detail}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
