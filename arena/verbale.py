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
from contracts.vocabulary import FEATURE_NAMES, MAX_FEATURES_USED

SUBMIT_TOOL_NAME = "submit_decision"


def _descrizione_features_used(tetto: int) -> str:
    """La riga che dichiara il tetto di `features_used` dentro lo schema.

    Il numero è un **parametro**, non una costante scritta nel testo: chi
    aggiunge una primitiva al vocabolario alza il tetto e la descrizione lo
    segue, senza che nessuno debba ricordarsene. È la seconda proiezione
    della stessa fonte di verità che il contratto applica (F12-bis).
    """
    return (
        "Grandezze del vocabolario primitivo che hanno determinato "
        "questa decisione, con il valore letto. "
        f"Al più {tetto} voci, con nomi distinti."
    )


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
                # Il tetto è DICHIARATO qui in una sola sede: la riga di
                # descrizione, generata alla costruzione dello schema da
                # `MAX_FEATURES_USED` (= `len(PRIMITIVE_FEATURES)`), mai
                # scritta a mano. Firma **F12-bis** (owner, 2026-08-20), che
                # supersede F12(b): quella prescriveva `maxItems`, e la sua
                # premessa è falsificata dall'endpoint — sotto `strict: true`
                # l'API rifiuta `maxItems` su un array con 400 («For 'array'
                # type, property 'maxItems' is not supported»), mentre lo
                # accetta senza `strict` e accetta `minItems` con `strict`.
                # `strict: true` non è negoziabile (CLAUDE.md §8), quindi
                # cade `maxItems`, non lo strict. Il tetto resta APPLICATO dal
                # contratto (`contracts.decision`, F12(a) intatta): una sola
                # fonte di verità, due proiezioni — il contratto la applica,
                # la descrizione la rende conoscibile dove si decide.
                "description": _descrizione_features_used(MAX_FEATURES_USED),
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
    # Il modello ha declinato (stop_reason='refusal'). Categoria a se': non e'
    # il protocollo ad aver fallito.
    MODEL_REFUSAL = "model_refusal"
    # La risposta e' stata tagliata da max_tokens (stop_reason='max_tokens').
    # Rilevato in `arena/runner.py` prima del parsing: un verbale troncato non
    # arriva nemmeno a questo modulo con un blocco strutturato completo.
    TRUNCATED = "truncated"


# I due motivi che NON sono verbali malformati (verbale RUN2 §A.5). Il tasso
# di malformati misura la tenuta del PROTOCOLLO: un rifiuto dei classificatori
# e un troncamento da `max_tokens` non ne dicono niente. Ciascuno ha la propria
# contabilita', una sola, in `ledger.telemetry` — `refusals_total` e
# `truncated_total`. Sommarli renderebbe illeggibili tutte e tre le metriche, e
# il gate §7(ii) del pre-registration conta i soli malformati veri.
NON_MALFORMED_REASONS: frozenset[MalformedReason] = frozenset(
    {MalformedReason.MODEL_REFUSAL, MalformedReason.TRUNCATED}
)


def is_true_malformed(reason: MalformedReason | None) -> bool:
    """Vero solo per un verbale che il protocollo ha davvero rifiutato."""
    return reason is not None and reason not in NON_MALFORMED_REASONS


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
