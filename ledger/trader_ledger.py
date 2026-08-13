"""TraderLedger — JSONL append-only con hash-chain.

Ogni riga porta `prev_hash` (l'`entry_hash` della riga precedente) e il proprio
`entry_hash`. Modificare una riga a posteriori rompe la catena da quel punto in
poi, e `verify()` lo dice esattamente dove.

Write-once per **(giorno, replica, asset)**: una seconda scrittura sulla stessa
chiave è un errore, non un aggiornamento. La storia non si riscrive
(CLAUDE.md §9).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from contracts.decision import DecisionRecord
from contracts.fill import ShadowFill
from contracts.hashing import sha256_of
from contracts.risk import RiskVerdict
from toolserver.store import assert_path_allowed

GENESIS_HASH = "0" * 64


class LedgerError(Exception):
    pass


class DuplicateEntry(LedgerError):
    """Violazione del write-once su (giorno, replica, asset)."""


class ChainBroken(LedgerError):
    """La hash-chain non verifica."""


@dataclass(frozen=True, slots=True)
class LedgerKey:
    day: str
    replica_id: str
    asset: str

    @classmethod
    def of(cls, day: date | datetime | str, replica_id: str, asset: str) -> LedgerKey:
        if isinstance(day, datetime):
            day_str = day.astimezone(timezone.utc).date().isoformat()
        elif isinstance(day, date):
            day_str = day.isoformat()
        else:
            day_str = day
        return cls(day=day_str, replica_id=replica_id, asset=asset)

    def as_dict(self) -> dict[str, str]:
        return {"day": self.day, "replica_id": self.replica_id, "asset": self.asset}


@dataclass(frozen=True, slots=True)
class VerifyResult:
    ok: bool
    entries_checked: int
    broken_at: int | None = None
    detail: str = ""


def entry_hash(entry: dict[str, Any]) -> str:
    """Hash di una riga, escluso il campo `entry_hash` stesso."""
    return sha256_of({k: v for k, v in entry.items() if k != "entry_hash"})


class TraderLedger:
    """Ledger su file JSONL. Un file per segmento di track record."""

    def __init__(self, path: Path | str) -> None:
        self.path = assert_path_allowed(Path(path).parent) / Path(path).name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._keys: set[LedgerKey] = set()
        self._last_hash = GENESIS_HASH
        self._count = 0
        self._reload()

    # -- stato -------------------------------------------------------------

    def _reload(self) -> None:
        for entry in self.read_all():
            key = LedgerKey(**entry["key"])
            self._keys.add(key)
            self._last_hash = entry["entry_hash"]
            self._count += 1

    @property
    def head_hash(self) -> str:
        return self._last_hash

    def __len__(self) -> int:
        return self._count

    def has(self, key: LedgerKey) -> bool:
        return key in self._keys

    # -- scrittura ---------------------------------------------------------

    def append(
        self,
        *,
        key: LedgerKey,
        verdict: RiskVerdict,
        decision: DecisionRecord | None = None,
        fill: ShadowFill | None = None,
        malformed_reason: str | None = None,
        snapshot_id: str,
        run_id: str,
    ) -> dict[str, Any]:
        """Aggiunge una riga. Solleva se la chiave è già stata scritta."""
        with self._lock:
            if key in self._keys:
                raise DuplicateEntry(
                    f"({key.day}, {key.replica_id}, {key.asset}) è già nel ledger: "
                    f"write-once, la storia non si riscrive"
                )
            entry: dict[str, Any] = {
                "seq": self._count,
                "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
                "run_id": run_id,
                "snapshot_id": snapshot_id,
                "key": key.as_dict(),
                "decision": decision.model_dump(mode="json") if decision else None,
                "verdict": verdict.model_dump(mode="json"),
                "fill": fill.model_dump(mode="json") if fill else None,
                "malformed_reason": malformed_reason,
                "prev_hash": self._last_hash,
            }
            entry["entry_hash"] = entry_hash(entry)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            self._keys.add(key)
            self._last_hash = entry["entry_hash"]
            self._count += 1
            return entry

    # -- lettura e verifica ------------------------------------------------

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def verify(self) -> VerifyResult:
        """Ricalcola la catena dall'inizio e riporta dove si rompe."""
        entries = self.read_all()
        expected_prev = GENESIS_HASH
        for index, entry in enumerate(entries):
            if entry.get("prev_hash") != expected_prev:
                return VerifyResult(
                    ok=False,
                    entries_checked=index,
                    broken_at=index,
                    detail=(
                        f"riga {index}: prev_hash {entry.get('prev_hash')!r} "
                        f"non corrisponde a {expected_prev!r}"
                    ),
                )
            recomputed = entry_hash(entry)
            if recomputed != entry.get("entry_hash"):
                return VerifyResult(
                    ok=False,
                    entries_checked=index,
                    broken_at=index,
                    detail=f"riga {index}: contenuto alterato (hash non corrisponde)",
                )
            if entry.get("seq") != index:
                return VerifyResult(
                    ok=False,
                    entries_checked=index,
                    broken_at=index,
                    detail=f"riga {index}: seq {entry.get('seq')} fuori sequenza",
                )
            expected_prev = entry["entry_hash"]
        return VerifyResult(ok=True, entries_checked=len(entries))

    def decisions(self) -> list[DecisionRecord]:
        return [
            DecisionRecord.model_validate(entry["decision"])
            for entry in self.read_all()
            if entry.get("decision")
        ]
