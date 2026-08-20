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

# Nome sintetico sotto cui la chiamata al modello — che non è un tool del Tool
# Server — finisce in questo stesso log: è un dato sulla richiesta al pari
# degli altri (CLAUDE.md §9). Vive qui, e non in `arena/runner.py` che lo
# scrive, perché lo leggono anche i moduli che contano i token
# (`ledger/spend.py`): tenerlo nell'arena obbligherebbe il ledger a importare
# l'arena, che importa il ledger.
LLM_COMPLETE_TOOL = "llm_complete"


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
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """`meta` porta telemetria propria della chiamata (es. tentativi del
        client LLM: numero, `type` di ciascun errore, durata totale) che non
        è né un argomento né la risposta stessa, ma un dato su *come* è
        avvenuta la chiamata."""
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
            "meta": meta or {},
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
