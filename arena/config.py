"""Configurazione dell'arena e caricamento dei context file congelati.

D1: tre repliche **identiche**. Stesso modello, stesso prompt, stessa
temperatura, stesso snapshot. L'unica cosa che le distingue è il `replica_id`,
che il Trader **non vede mai**.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from contracts.freeze import FreezeManifest, SamplingPolicy, ThinkingPolicy
from contracts.hashing import sha256_of, sha256_of_text
from arena.risk_officer import RiskConfig
from arena.verbale import SUBMIT_DECISION_SCHEMA
from toolserver.registry import TOOL_SCHEMAS

AGENT_DIR = Path(__file__).resolve().parents[1] / "agents" / "trader_v0"

# D1: tre repliche identiche.
DEFAULT_REPLICA_IDS: tuple[str, ...] = ("r1", "r2", "r3")

# D2. Gli ID dei modelli Claude correnti sono completi cosi' come sono: per la
# Sonnet corrente NON esiste una variante datata e aggiungere un suffisso data
# produce 404. Questa e' quindi la model string piu' specifica disponibile.
DEFAULT_MODEL_STRING = "claude-sonnet-5"
DEFAULT_MODEL_NOTE = (
    "Model string piu' specifica disponibile al momento del pin: per la Sonnet "
    "corrente non esiste una variante datata (un suffisso data produce 404). "
    "L'unica alternativa 'datata' sarebbe scendere di generazione a "
    "claude-sonnet-4-5-20250929, cioe' pinnare un modello legacy."
)

DEFAULT_MAX_TOKENS = 8_000
DEFAULT_MAX_TOOL_ITERATIONS = 10
DEFAULT_MAX_LLM_CALLS_PER_DAY = 200


@dataclass(frozen=True, slots=True)
class ContextFiles:
    """I file di context congelati, con i loro sha.

    `system_prompt` e `persona` sono i file **come stanno su disco** — ed è su
    quelli che si calcolano gli sha, perché è il file che viene congelato.
    `rendered_system` è ciò che il modello riceve davvero.
    """

    system_prompt: str
    persona: str
    system_prompt_sha: str
    persona_sha: str
    rendered_system: str
    rendered_sha: str


def strip_editorial(text: str) -> str:
    """Rimuove le note editoriali (righe che iniziano con '>').

    Convenzione del repo: i blockquote nei context file sono note **per chi
    mantiene il Lab**, non per il Trader. Senza questo filtro finirebbero nel
    prompt — e la nota che dice "questo testo non parla di repliche" sarebbe
    essa stessa un riferimento alle repliche dentro il contesto del modello.
    """
    kept = [line for line in text.splitlines() if not line.lstrip().startswith(">")]
    out: list[str] = []
    for line in kept:
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line)
    return "\n".join(out).strip() + "\n"


def load_context(agent_dir: Path = AGENT_DIR) -> ContextFiles:
    """Carica prompt e persona e compone il system prompt effettivo."""
    system_raw = (agent_dir / "system_prompt.md").read_text(encoding="utf-8")
    persona_raw = (agent_dir / "persona.md").read_text(encoding="utf-8")
    rendered = strip_editorial(system_raw).replace(
        "{PERSONA}", strip_editorial(persona_raw).strip()
    )
    return ContextFiles(
        system_prompt=system_raw,
        persona=persona_raw,
        system_prompt_sha=sha256_of_text(system_raw),
        persona_sha=sha256_of_text(persona_raw),
        rendered_system=rendered,
        rendered_sha=sha256_of_text(rendered),
    )


def all_tool_schemas() -> list[dict]:
    """Tool di lettura + tool di registrazione, nell'ordine inviato all'API.

    L'ordine è fisso: cambiarlo cambierebbe il `tool_schemas_sha` e quindi il
    segmento di track record.
    """
    return [*(dict(s) for s in TOOL_SCHEMAS), dict(SUBMIT_DECISION_SCHEMA)]


def all_tool_schemas_sha() -> str:
    return sha256_of(all_tool_schemas())


def current_git_sha(default: str = "0000000") -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return out.stdout.strip() or default
    except (subprocess.SubprocessError, OSError):
        return default


@dataclass(frozen=True, slots=True)
class ArenaConfig:
    """Parametri della giornata di decisioni."""

    replica_ids: tuple[str, ...] = DEFAULT_REPLICA_IDS
    max_tool_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS
    # Un solo retry su verbale malformato, dichiarato (CLAUDE.md §8).
    malformed_retries: int = 1
    max_llm_calls_per_day: int = DEFAULT_MAX_LLM_CALLS_PER_DAY
    risk: RiskConfig = field(default_factory=RiskConfig)
    # Ipotesi di esecuzione shadow: si assume liquidity taker, il caso peggiore
    # tra i due, e slippage pari a mezzo spread stimato.
    assume_taker: bool = True
    slippage_as_half_spread: bool = True

    def __post_init__(self) -> None:
        if len(set(self.replica_ids)) != len(self.replica_ids):
            raise ValueError("replica_ids contiene duplicati")
        if not self.replica_ids:
            raise ValueError("servono almeno una replica")
        if self.malformed_retries < 0:
            raise ValueError("malformed_retries negativo")


def build_freeze_manifest(
    pinned_at,
    *,
    model_string: str = DEFAULT_MODEL_STRING,
    model_note: str = DEFAULT_MODEL_NOTE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    agent_dir: Path = AGENT_DIR,
    context_git_sha: str | None = None,
) -> FreezeManifest:
    """Compone il manifest dal contenuto realmente congelato.

    D4: `sampling_policy=api_default_omitted`. Il client **non invia**
    `temperature`, `top_p`, `top_k` — sui Sonnet correnti i valori non-default
    sono rifiutati dall'API con 400, quindi il default operativo si ottiene per
    omissione. I tre campi restano `None`: "default dell'API" non deve mai
    essere confuso con "0" o con "non registrato".
    """
    context = load_context(agent_dir)
    return FreezeManifest(
        pinned_at_utc=pinned_at,
        model_string=model_string,
        model_string_note=model_note,
        sampling_policy=SamplingPolicy.API_DEFAULT_OMITTED,
        max_tokens=max_tokens,
        thinking_policy=ThinkingPolicy.API_DEFAULT,
        system_prompt_sha=context.system_prompt_sha,
        persona_sha=context.persona_sha,
        tool_schemas_sha=all_tool_schemas_sha(),
        context_git_sha=context_git_sha or current_git_sha(),
        ots_pending=True,
    )
