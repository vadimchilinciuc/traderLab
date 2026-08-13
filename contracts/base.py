"""Base comune dei contratti del Lab.

Ogni contratto è immutabile (`frozen=True`) e rifiuta campi extra
(`extra="forbid"`). L'immutabilità impedisce che un record cambi dopo essere
stato scritto nel ledger; il rifiuto dei campi extra impedisce che un campo
scritto male entri silenziosamente e sparisca dalle analisi.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Modello immutabile, strict sui campi, serializzabile in modo canonico."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=False,
        validate_default=True,
    )

    def canonical_payload(self, exclude: set[str] | None = None) -> dict[str, Any]:
        """Dizionario JSON-safe usato per hashing e persistenza."""
        return self.model_dump(mode="json", exclude=exclude)


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def require_utc(value: datetime, field_name: str) -> datetime:
    """Rifiuta i datetime naive: un timestamp senza timezone non è un fatto."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} deve essere timezone-aware (UTC)")
    return value.astimezone(timezone.utc)
