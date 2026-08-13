"""Log totale delle tool call, JSONL append-only.

**Cosa il Trader chiede è un dato**, alla pari di cosa decide (CLAUDE.md §9).
Il log registra chi ha chiesto, cosa, con quali argomenti, e l'hash della
risposta — non la risposta intera, che è ricostruibile dallo snapshot.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts.hashing import sha256_of
from toolserver.store import assert_path_allowed


class ToolCallLog:
    """Append-only su file JSONL. Un file per giornata di esecuzione."""

    def __init__(self, root: Path | str, run_id: str) -> None:
        self.root = assert_path_allowed(Path(root))
        self.run_id = run_id
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.root / f"{self.run_id}.jsonl"

    @property
    def ref(self) -> str:
        """Riferimento stabile da mettere in `DecisionRecord.tool_calls_ref`."""
        return f"{self.root.name}/{self.run_id}.jsonl"

    def record(
        self,
        *,
        replica_id: str,
        snapshot_id: str,
        tool: str,
        args: dict[str, Any],
        response: Any = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
            "run_id": self.run_id,
            "replica_id": replica_id,
            "snapshot_id": snapshot_id,
            "tool": tool,
            "args": args,
            "ok": error is None,
            "response_sha256": None if error is not None else sha256_of(response),
            "error": error,
        }
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return entry

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
