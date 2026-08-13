"""SnapshotStore — persistenza su disco degli snapshot congelati.

Unica sorgente di verità del Tool Server durante una decisione. Lo store è
read-only per il Tool Server: scrive solo lo SnapshotBuilder, in un processo
separato e in un momento separato.

Firewall (CLAUDE.md §7): la radice dello store non può puntare a `zeroPipes`.
Il controllo è in codice, non in una convenzione.
"""

from __future__ import annotations

import json
from pathlib import Path

from contracts.snapshot import MarketSnapshot
from toolserver.errors import (
    FirewallViolation,
    SnapshotCorrupted,
    SnapshotNotFound,
)

FORBIDDEN_PATH_TOKENS = ("zeropipes",)


def assert_path_allowed(path: Path) -> Path:
    """Rifiuta radici che romperebbero l'isolamento dal repo di produzione."""
    resolved = path.expanduser().resolve()
    lowered = str(resolved).lower().replace("\\", "/")
    for token in FORBIDDEN_PATH_TOKENS:
        if token in lowered:
            raise FirewallViolation(
                f"percorso vietato: '{token}' compare in {resolved}. Il Tool "
                f"Server non ha alcun path verso zeroPipes."
            )
    return resolved


class SnapshotStore:
    """Store su filesystem, indicizzato per snapshot_id."""

    def __init__(self, root: Path | str) -> None:
        self.root = assert_path_allowed(Path(root))
        self._cache: dict[str, MarketSnapshot] = {}

    # -- scrittura (solo builder) -----------------------------------------

    def save(self, snapshot: MarketSnapshot) -> Path:
        """Scrive lo snapshot. Se esiste già con lo stesso id, è un no-op.

        Lo `snapshot_id` è funzione del contenuto: una riscrittura con id
        identico non può cambiare i byte, quindi non si sovrascrive nulla.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(snapshot.snapshot_id)
        if path.exists():
            return path
        path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        self._cache[snapshot.snapshot_id] = snapshot
        return path

    # -- lettura (Tool Server) --------------------------------------------

    def path_for(self, snapshot_id: str) -> Path:
        if not (len(snapshot_id) == 64 and all(c in "0123456789abcdef" for c in snapshot_id)):
            raise SnapshotNotFound(f"snapshot_id malformato: {snapshot_id!r}")
        return self.root / f"{snapshot_id}.json"

    def exists(self, snapshot_id: str) -> bool:
        try:
            return self.path_for(snapshot_id).exists()
        except SnapshotNotFound:
            return False

    def load(self, snapshot_id: str) -> MarketSnapshot:
        """Carica e **ri-valida** lo snapshot, id incluso.

        La ri-validazione è il controllo di integrità: un file manomesso non
        supera il check di `snapshot_id` e solleva invece di essere servito.
        """
        if snapshot_id in self._cache:
            return self._cache[snapshot_id]
        path = self.path_for(snapshot_id)
        if not path.exists():
            raise SnapshotNotFound(
                f"snapshot {snapshot_id} non presente in {self.root}. "
                f"Il Tool Server non ricade su dati live."
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            snapshot = MarketSnapshot.model_validate(payload)
        except SnapshotNotFound:
            raise
        except Exception as exc:  # noqa: BLE001 - viene ri-alzato tipizzato
            raise SnapshotCorrupted(f"snapshot {snapshot_id} illeggibile: {exc}") from exc
        self._cache[snapshot_id] = snapshot
        return snapshot

    def list_ids(self) -> tuple[str, ...]:
        if not self.root.exists():
            return ()
        return tuple(sorted(p.stem for p in self.root.glob("*.json")))

    def raw_bytes(self, snapshot_id: str) -> bytes:
        """Byte grezzi del file: usato dai test di identità byte-per-byte."""
        path = self.path_for(snapshot_id)
        if not path.exists():
            raise SnapshotNotFound(f"snapshot {snapshot_id} non presente")
        return path.read_bytes()
