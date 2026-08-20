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

import re
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


class ThinkingDeclaration(StrEnum):
    """Cosa il pin DICHIARA sul thinking (verbale RUN2 §A.7).

    `thinking_policy` dice quale configurazione è stata scelta; questa dice
    cosa il client ha il diritto di mettere nel payload. Sono due cose diverse
    e vanno tenute separate: la prima è una scelta di disegno, la seconda è un
    invariante verificabile a ogni chiamata. Il client confronta il payload
    che sta per inviare con questa dichiarazione e **rifiuta** se divergono —
    così una `thinking` comparsa nel payload per errore non passa in silenzio.
    """

    # Il thinking è sempre attivo e non disattivabile: il parametro NON si
    # invia. È l'unica forma valida sul modello pinnato in TL-002/TL-007.
    ALWAYS_ON_PARAM_OMITTED = "always_on_param_omitted"
    # Il parametro `thinking` viene inviato esplicitamente. Non è il caso del
    # modello pinnato: esiste perché la dichiarazione sia un'alternativa vera
    # e non un campo con un solo valore possibile.
    EXPLICIT_PARAM_SENT = "explicit_param_sent"


# `pin_commit` prende il posto di `context_git_sha` nel calcolo del
# `freeze_id` (verbale RUN2 §A.2). Questi valori sono segnaposto: dicono
# "non ancora pinnato", non un commit. Il runner li rifiuta.
PIN_COMMIT_PLACEHOLDERS: frozenset[str] = frozenset(
    {"", "0000000", "0" * 40, "PLACEHOLDER", "placeholder"}
)


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
    # Verbale RUN2 §A.7: quale forma di chiamata il pin autorizza sul
    # thinking. Il client la verifica a ogni chiamata (vedi
    # `ThinkingDeclaration`). Entra nel `freeze_id`: cambiarla è un cambio
    # del protocollo di chiamata, alla pari di `sampling_policy`.
    thinking_declared: ThinkingDeclaration = ThinkingDeclaration.ALWAYS_ON_PARAM_OMITTED

    # --- Contenuti congelati ---
    system_prompt_sha: str = Field(pattern=r"^[0-9a-f]{64}$")
    persona_sha: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_schemas_sha: str = Field(pattern=r"^[0-9a-f]{64}$")
    # Sha del repo al momento in cui il manifest è stato COMPOSTO. Resta nel
    # documento come dato di provenienza, ma **esce dal calcolo del
    # `freeze_id`** (verbale RUN2 §A.2): cambia a ogni commit anche quando
    # l'agente non è cambiato, e in Stagione 0 questo produsse tre `freeze_id`
    # diversi in tre giornate, nessuno dei quali coincideva con quello del
    # manifest firmato (TL-007).
    context_git_sha: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    # Commit del RITO DEL PIN: fisso per tutta la stagione. Prende il posto di
    # `context_git_sha` dentro il `freeze_id`. Finché è un segnaposto il pin
    # non esiste, e il runner si rifiuta di girare.
    pin_commit: str = Field(default="", max_length=40)

    # --- Guardia economica di stagione (D5) ---
    # Preventivo vincolante della stagione, valorizzato al rito del pin. Il
    # runner legge la spesa cumulata dal ledger e si rifiuta di girare oltre
    # il multiplo dichiarato in `ledger.spend`. Assente = nessun preventivo
    # firmato: anche quello è un rifiuto, non un via libera.
    season_budget_usd: float | None = Field(default=None, gt=0.0)
    # Giornate ATTESE della stagione: il denominatore del pro-rata che il
    # controllo del mattino usa per l'allarme di ritmo. Sta qui e non in una
    # costante di `ledger.spend` perché è un termine del pin, esattamente come
    # `season_budget_usd`: numeratore e denominatore della stessa frazione
    # devono essere firmati insieme. Un preventivo tarato su N giornate e un
    # pro-rata calcolato su M != N produce una soglia che non corrisponde a
    # nulla — e se M > N la soglia scende sotto la spesa attesa e l'allarme
    # suona ogni giorno. Assente = nessun pro-rata firmato: il runner in
    # `--live` rifiuta, come per `season_budget_usd`.
    season_expected_days: int | None = Field(default=None, gt=0)
    # Listino del modello pinnato, USD per milione di token, trascritto dalla
    # pagina di listino al rito del pin. Stanno qui per la stessa ragione di
    # `season_expected_days`: sono i **fattori** della spesa che il preventivo
    # confronta con se stessa, e un preventivo calcolato con una tariffa e
    # controllato con un'altra non controlla niente. Erano quattro costanti in
    # `ledger/spend.py`, ferme al listino di Claude Fable 5 ($10/$50) mentre il
    # modello pinnato in TL-007 e' `claude-opus-5` ($5/$25): entrambe le
    # guardie economiche contavano la spesa al **doppio** del vero, e con il
    # preventivo proposto di $89,90 la soglia dura sarebbe scattata al giorno
    # 21 invece che al 42 (evidenza
    # `docs/research/results/2026-08-20_PREREG-EVIDENCE_PREVENTIVO_RUN2.md`,
    # §8 punto 1).
    #
    # Entrano nel `freeze_id`, come il preventivo: cambiare il listino con cui
    # una stagione si misura cambia la stagione. La conseguenza dichiarata e'
    # che un ritocco di listino da parte del fornitore **non** si insegue a
    # stagione aperta — il manifest e' firmato e timbrato — e le guardie
    # continuano a contare con la tariffa con cui il preventivo e' stato
    # calcolato. E' la scelta coerente: le due cifre confrontate restano
    # omogenee.
    #
    # `cache_write_5m` e' il prezzo di scrittura in cache a TTL 5 minuti,
    # perche' e' quello che il client usa: `arena/llm_client.py` non specifica
    # `ttl` e il default e' 5 minuti. Un client che passasse a 1 ora userebbe
    # un'altra riga di listino, e sarebbe un altro pin.
    price_per_mtok_input: float | None = Field(default=None, gt=0.0)
    price_per_mtok_output: float | None = Field(default=None, gt=0.0)
    price_per_mtok_cache_write_5m: float | None = Field(default=None, gt=0.0)
    price_per_mtok_cache_read: float | None = Field(default=None, gt=0.0)

    # --- Caching (RITO CACHING) ---
    # Descrizione dei blocchi marcati con `cache_control`. Solo costo e
    # latenza: non cambia cosa il Trader vede né cosa decide, quindi non
    # tocca system_prompt_sha/persona_sha/tool_schemas_sha. Registrato qui
    # perché un cambio nella strategia di caching è comunque un cambio di
    # come la chiamata viene fatta, alla pari di sampling_policy e
    # thinking_policy: cambiarla apre un nuovo freeze_id.
    caching_policy: str = Field(default="", max_length=1000)

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

    @field_validator("pin_commit")
    @classmethod
    def _pin_commit_shape(cls, v: str) -> str:
        """Segnaposto o sha di commit. Nient'altro, e mai in silenzio."""
        if v in PIN_COMMIT_PLACEHOLDERS:
            return v
        if not re.fullmatch(r"[0-9a-f]{7,40}", v):
            raise ValueError(
                f"pin_commit deve essere uno sha di commit (7-40 esadecimali) "
                f"o un segnaposto dichiarato, ricevuto {v!r}"
            )
        return v

    @property
    def is_pinned(self) -> bool:
        """Vero solo se `pin_commit` porta davvero il commit del rito del pin."""
        return self.pin_commit not in PIN_COMMIT_PLACEHOLDERS

    @property
    def freeze_id(self) -> str:
        """Identificatore del segmento di track record aperto da questo pin.

        `context_git_sha` è **escluso** dal calcolo (verbale RUN2 §A.2). Al suo
        posto entra `pin_commit`, che è fisso per tutta la stagione: così il
        `freeze_id` di una giornata non cambia solo perché nel frattempo è
        stato fatto un commit qualsiasi nel repo.
        """
        return sha256_of(
            self.canonical_payload(
                exclude={"ots_pending", "ots_proof_path", "context_git_sha"}
            )
        )
