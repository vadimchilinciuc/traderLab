"""Parser e validatore del verbale del Trader.

Ordine imposto: **razionale libero PRIMA, blocco strutturato DOPO**. Non è una
preferenza stilistica — è l'unica mitigazione del "format tax" con supporto
empirico (Tam et al., EMNLP 2024: il degrado nasce dall'answer-field che
precede il reasoning-field).

Conseguenza operativa: `tool_choice` **non** può essere forzato su
`submit_decision`. Forzare il tool sopprime il testo che lo precede, cioè
esattamente il campo che vogliamo generato per primo. Si usa `tool_choice`
automatico e si impone l'ordine **qui**, rifiutando i verbali che non lo
rispettano.

Verbale non conforme = NO TRADE, registrato come `rejected_malformed`.
È ammesso **un solo retry**, dichiarato in `arena/config.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from contracts.decision import (
    MIN_RATIONALE_CHARS,
    Action,
    DecisionRecord,
    Horizon,
)
from contracts.hashing import sha256_of
from contracts.vocabulary import FEATURE_NAMES

SUBMIT_TOOL_NAME = "submit_decision"

SUBMIT_DECISION_SCHEMA: dict[str, Any] = {
    "name": SUBMIT_TOOL_NAME,
    "description": (
        "Registra la decisione per un asset. Va chiamato una sola volta per "
        "asset, dopo aver scritto il ragionamento in testo libero."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "asset": {
                "type": "string",
                "description": "Simbolo dell'asset a cui la decisione si riferisce.",
            },
            "action": {
                "type": "string",
                "enum": [a.value for a in Action],
                "description": (
                    "long apre esposizione al rialzo, short al ribasso, "
                    "close chiude una posizione esistente, flat resta fuori."
                ),
            },
            "size_fraction": {
                "type": "number",
                "description": (
                    "Frazione di capitale da impiegare, tra 0 e 1. Deve essere 0 "
                    "per flat e per close."
                ),
            },
            "horizon": {
                "type": "string",
                "enum": [h.value for h in Horizon],
                "description": "Orizzonte temporale della decisione.",
            },
            "expected_holding": {
                "type": "string",
                "enum": [h.value for h in Horizon],
                "description": "Durata di mantenimento attesa.",
            },
            "confidence": {
                "type": "number",
                "description": (
                    "Probabilità soggettiva, tra 0 e 1, che la direzione scelta "
                    "risulti corretta sull'orizzonte dichiarato."
                ),
            },
            "features_used": {
                "type": "array",
                "description": (
                    "Grandezze del vocabolario primitivo che hanno determinato "
                    "questa decisione, con il valore letto."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": list(FEATURE_NAMES)},
                        "value": {"type": "number"},
                    },
                    "required": ["name", "value"],
                    "additionalProperties": False,
                },
            },
            "invalidation_conditions": {
                "type": "array",
                "description": (
                    "Condizioni dichiarate ora che, se si verificassero, "
                    "renderebbero questa decisione non più valida."
                ),
                "items": {"type": "string"},
            },
            "risk_checks": {
                "type": "array",
                "description": "Controlli effettuati e loro esito.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "passed": {"type": "boolean"},
                        "note": {"type": "string"},
                    },
                    "required": ["name", "passed", "note"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "asset",
            "action",
            "size_fraction",
            "horizon",
            "expected_holding",
            "confidence",
            "features_used",
            "invalidation_conditions",
            "risk_checks",
        ],
        "additionalProperties": False,
    },
}


def submit_schema_sha() -> str:
    return sha256_of(SUBMIT_DECISION_SCHEMA)


class MalformedReason(StrEnum):
    """Motivi di rifiuto. Elenco chiuso: entra in telemetria come categoria."""

    NO_TOOL_USE = "no_tool_use"
    WRONG_TOOL = "wrong_tool"
    MULTIPLE_TOOL_USE = "multiple_tool_use"
    NO_RATIONALE_BEFORE = "no_rationale_before_structured_block"
    RATIONALE_TOO_SHORT = "rationale_too_short"
    INVALID_ARGUMENTS = "invalid_arguments"
    ASSET_MISMATCH = "asset_mismatch"


@dataclass(frozen=True, slots=True)
class ParsedVerbale:
    """Esito del parsing. `record` è valorizzato solo se `ok` è True."""

    ok: bool
    record: DecisionRecord | None = None
    reason: MalformedReason | None = None
    detail: str = ""
    rationale_text: str = ""

    @property
    def is_malformed(self) -> bool:
        return not self.ok


def _malformed(reason: MalformedReason, detail: str = "") -> ParsedVerbale:
    return ParsedVerbale(ok=False, reason=reason, detail=detail)


def parse_verbale(
    content_blocks: list[Any],
    *,
    expected_asset: str,
    timestamp_decision: datetime,
    replica_id: str,
    snapshot_id: str,
    model_version: str,
    prompt_sha: str,
    context_git_sha: str,
    tool_calls_ref: str,
) -> ParsedVerbale:
    """Valida la risposta del Trader e la promuove a DecisionRecord.

    `content_blocks` sono i blocchi della risposta nell'ordine ricevuto: si
    accettano sia oggetti dell'SDK Anthropic (con attributi `type`, `text`,
    `name`, `input`) sia dizionari equivalenti.
    """
    normalized = [_normalize_block(b) for b in content_blocks]

    tool_blocks = [b for b in normalized if b["type"] == "tool_use"]
    if not tool_blocks:
        return _malformed(
            MalformedReason.NO_TOOL_USE,
            "la risposta non contiene alcun blocco strutturato",
        )
    if len(tool_blocks) > 1:
        return _malformed(
            MalformedReason.MULTIPLE_TOOL_USE,
            f"{len(tool_blocks)} chiamate a tool in un verbale che ne ammette una",
        )

    tool_block = tool_blocks[0]
    if tool_block["name"] != SUBMIT_TOOL_NAME:
        return _malformed(
            MalformedReason.WRONG_TOOL,
            f"atteso {SUBMIT_TOOL_NAME}, ricevuto {tool_block['name']!r}",
        )

    # L'ordine è il punto: il testo deve PRECEDERE il blocco strutturato.
    tool_index = normalized.index(tool_block)
    rationale = "\n\n".join(
        b["text"].strip()
        for b in normalized[:tool_index]
        if b["type"] == "text" and b["text"].strip()
    )
    if not rationale:
        return _malformed(
            MalformedReason.NO_RATIONALE_BEFORE,
            "nessun testo libero prima del blocco strutturato",
        )
    if len(rationale) < MIN_RATIONALE_CHARS:
        return _malformed(
            MalformedReason.RATIONALE_TOO_SHORT,
            f"razionale di {len(rationale)} caratteri, minimo {MIN_RATIONALE_CHARS}",
        )

    payload = tool_block["input"]
    if not isinstance(payload, dict):
        return _malformed(
            MalformedReason.INVALID_ARGUMENTS, "input del tool non è un oggetto"
        )
    if payload.get("asset") != expected_asset:
        return _malformed(
            MalformedReason.ASSET_MISMATCH,
            f"atteso asset {expected_asset!r}, ricevuto {payload.get('asset')!r}",
        )

    try:
        record = DecisionRecord(
            timestamp_decision=timestamp_decision,
            asset=payload["asset"],
            action=payload["action"],
            size_fraction=payload["size_fraction"],
            horizon=payload["horizon"],
            rationale_text=rationale,
            features_used=tuple(payload.get("features_used") or ()),
            confidence=payload["confidence"],
            invalidation_conditions=tuple(payload.get("invalidation_conditions") or ()),
            expected_holding=payload["expected_holding"],
            risk_checks=tuple(payload.get("risk_checks") or ()),
            tool_calls_ref=tool_calls_ref,
            model_version=model_version,
            prompt_sha=prompt_sha,
            context_git_sha=context_git_sha,
            replica_id=replica_id,
            snapshot_id=snapshot_id,
        )
    except (ValidationError, KeyError, TypeError) as exc:
        return _malformed(MalformedReason.INVALID_ARGUMENTS, str(exc)[:400])

    return ParsedVerbale(ok=True, record=record, rationale_text=rationale)


def _normalize_block(block: Any) -> dict[str, Any]:
    """Accetta blocchi dell'SDK o dizionari, ritorna sempre un dizionario."""
    if isinstance(block, dict):
        return {
            "type": block.get("type"),
            "text": block.get("text", ""),
            "name": block.get("name"),
            "input": block.get("input"),
        }
    return {
        "type": getattr(block, "type", None),
        "text": getattr(block, "text", "") or "",
        "name": getattr(block, "name", None),
        "input": getattr(block, "input", None),
    }
