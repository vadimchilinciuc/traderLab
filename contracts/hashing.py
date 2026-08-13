"""Hashing canonico condiviso da tutti i contratti.

Un solo posto definisce cosa significa "il contenuto di questo oggetto", così
che snapshot_id, prompt_sha e prev_hash siano confrontabili tra processi e tra
macchine. JSON canonico = chiavi ordinate, separatori compatti, UTF-8 esplicito.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Serializzazione deterministica: stesso contenuto -> stessi byte."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_of(payload: Any) -> str:
    """SHA-256 esadecimale del JSON canonico di `payload`."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def sha256_of_text(text: str) -> str:
    """SHA-256 esadecimale di un testo (prompt, persona, file di context)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()
