"""FreezeManifest — il pin del track record.

Registra ESATTAMENTE cosa è stato congelato: model string, ogni parametro di
sampling, gli sha di prompt/persona/context/tool-schema, la data del pin.
Cambio di uno qualsiasi di questi valori = **nuovo track record** (D2).

Nota su temperatura e sampling (D4). L'owner ha deciso: temperatura = default
operativo dell'API, nessun override, MAI 0. Sui modelli Claude Sonnet correnti
i parametri di sampling non-default (`temperature`, `top_p`, `top_k`) sono
**rifiutati dall'API con 400**. Il client quindi non li invia affatto: il
default operativo è ottenuto per omissione, non per assegnazione. Il manifest
registra questo come `sampling_policy="api_default_omitted"` con i tre campi a
None, così che il valore effettivo non venga mai confuso con "0" o "non so".
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from contracts.base import FrozenModel, require_utc
from contracts.hashing import sha256_of


class SamplingPolicy(StrEnum):
    """Come sono stati determinati i parametri di sampling."""

    API_DEFAULT_OMITTED = "api_default_omitted"
    EXPLICIT = "explicit"


class ThinkingPolicy(StrEnum):
    """Configurazione del thinking. Registrata perché cambia il comportamento."""

    API_DEFAULT = "api_default"
    ADAPTIVE = "adaptive"
    DISABLED = "disabled"


class FreezeManifest(FrozenModel):
    """Manifesto di congelamento di una configurazione del Trader."""

    manifest_version: int = Field(default=1, ge=1)
    pinned_at_utc: datetime

    # --- Modello (D2) ---
    model_string: str = Field(min_length=1)
    model_string_note: str = Field(default="", max_length=1000)

    # --- Sampling (D4) ---
    sampling_policy: SamplingPolicy
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_tokens: int = Field(gt=0)
    thinking_policy: ThinkingPolicy = ThinkingPolicy.API_DEFAULT

    # --- Contenuti congelati ---
    system_prompt_sha: str = Field(pattern=r"^[0-9a-f]{64}$")
    persona_sha: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_schemas_sha: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_git_sha: str = Field(pattern=r"^[0-9a-f]{7,40}$")

    # --- Timestamping ---
    ots_pending: bool = True
    ots_proof_path: str | None = None

    @field_validator("pinned_at_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return require_utc(v, "pinned_at_utc")

    @model_validator(mode="after")
    def _sampling_coherent(self) -> Self:
        if self.sampling_policy is SamplingPolicy.API_DEFAULT_OMITTED:
            if (self.temperature, self.top_p, self.top_k) != (None, None, None):
                raise ValueError(
                    "sampling_policy=api_default_omitted implica temperature, "
                    "top_p e top_k a None: il client non li invia"
                )
        else:
            if self.temperature is None:
                raise ValueError(
                    "sampling_policy=explicit richiede una temperatura dichiarata"
                )
            # D4: mai 0. Un override a 0 è una violazione della decisione owner.
            if self.temperature == 0.0:
                raise ValueError("D4 vieta temperature=0")
        return self

    @model_validator(mode="after")
    def _ots_coherent(self) -> Self:
        if self.ots_pending and self.ots_proof_path is not None:
            raise ValueError("ots_pending=True non può avere una proof già presente")
        if not self.ots_pending and not self.ots_proof_path:
            raise ValueError("ots_pending=False richiede ots_proof_path")
        return self

    @property
    def freeze_id(self) -> str:
        """Identificatore del segmento di track record aperto da questo pin."""
        return sha256_of(self.canonical_payload(exclude={"ots_pending", "ots_proof_path"}))
