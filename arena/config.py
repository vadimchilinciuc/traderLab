"""Configurazione dell'arena e caricamento dei context file congelati.

D1: tre repliche **identiche**. Stesso modello, stesso prompt, stessa
temperatura, stesso snapshot. L'unica cosa che le distingue è il `replica_id`,
che il Trader **non vede mai**.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from contracts.freeze import (
    FreezeManifest,
    SamplingPolicy,
    ThinkingDeclaration,
    ThinkingPolicy,
)
from contracts.hashing import sha256_of, sha256_of_text
from arena.risk_officer import RiskConfig
from arena.verbale import SUBMIT_DECISION_SCHEMA
from toolserver.registry import TOOL_SCHEMAS

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = REPO_ROOT / "agents" / "trader_v0"

# Percorso di default del manifest COMMITTATO che il runner carica. È
# parametrico: al rito del pin della stagione nuova si passa il percorso del
# manifest di quella stagione. Il default punta al manifest esistente perché
# il runner debba comunque incontrare un file vero e rifiutare per il motivo
# giusto (`pin_commit` assente), invece di non trovarne nessuno.
DEFAULT_MANIFEST_PATH = REPO_ROOT / "manifests" / "trader_v0_freeze_manifest.json"

# D1: tre repliche identiche.
DEFAULT_REPLICA_IDS: tuple[str, ...] = ("r1", "r2", "r3")

# TL-002 supera D2 di TL-001: il Trader e' pinnato sul modello piu' capace
# disponibile via API. Gli ID dei modelli Claude correnti sono completi cosi'
# come sono: per Fable NON esiste una variante datata e aggiungere un suffisso
# data produce 404. Questa e' quindi la model string piu' specifica possibile.
DEFAULT_MODEL_STRING = "claude-fable-5"
DEFAULT_MODEL_NOTE = (
    "TL-002: pin sul modello piu' capace disponibile via API. La string e' "
    "completa cosi' com'e': per claude-fable-5 non esiste una variante datata "
    "e un suffisso data produce 404, quindi questa E' la forma piu' specifica "
    "disponibile. Verificare con scripts/verify_pin.py contro l'endpoint il "
    "giorno del pin."
)

# Fable ha il thinking SEMPRE ATTIVO e non disattivabile, e i token di
# ragionamento consumano max_tokens insieme alla risposta. Un tetto tarato su
# un modello senza thinking tronca la risposta a meta'.
#
# Tuning (rito max_tokens, diagnosi C): con max_tokens=32_000 Fable veniva
# scartato dallo shedding lato server nei picchi di carico (overloaded
# in-stream); con un budget ridotto la chiamata passa. Decisione owner: tetto
# a 8_000, dichiarato qui e nel FreezeManifest. Il rovescio della medaglia e'
# che un turno insolitamente lungo (razionale esteso o thinking prolungato)
# puo' troncare la risposta: la guardia in `arena/runner.py` intercetta
# `stop_reason="max_tokens"` e forza NO TRADE (`MalformedReason.TRUNCATED`),
# mai un verbale parziale silenzioso.
DEFAULT_MAX_TOKENS = 8_000
DEFAULT_MAX_TOOL_ITERATIONS = 10

# RITO CACHING: descrizione dei blocchi marcati `cache_control: ephemeral`
# in `arena/llm_client.py` (`_cached_system`, `_cached_tools`,
# `_cached_messages`). Solo costo e latenza — vedi il docstring di
# `FreezeManifest.caching_policy`.
DEFAULT_CACHING_POLICY = (
    "cache_control ephemeral su tre blocchi: (1) il system prompt, blocco "
    "unico, identico a ogni chiamata di ogni replica di ogni asset (D1); "
    "(2) l'ultima definizione di tool nell'elenco, che chiude il prefisso "
    "cacheabile di tutte le definizioni, anch'esse identiche a ogni "
    "chiamata; (3) l'ultimo tool_result della conversazione corrente "
    "(tipicamente il dossier dell'asset), che resta stabile da un turno al "
    "successivo negli scambi con più di due turni."
)
# Fable e' il modello piu' caro del listino: il tetto di chiamate non e' una
# formalita'.
DEFAULT_MAX_LLM_CALLS_PER_DAY = 200
# I turni di Fable possono durare minuti. Timeout esplicito, non implicito.
DEFAULT_REQUEST_TIMEOUT_SECONDS = 900.0


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


# --------------------------------------------------------------------------
# Caricamento del manifest committato (verbale RUN2 §A.2)
# --------------------------------------------------------------------------


class ManifestError(Exception):
    """Il manifest committato non è utilizzabile per far girare una giornata.

    È sempre un rifiuto, mai un ripiego: il runner che incontra questo errore
    non gira. La causa più comune non è la corruzione del file ma il suo
    contrario — un manifest sano che però **non è ancora stato pinnato**.
    """


def load_pinned_manifest(
    path: Path | str = DEFAULT_MANIFEST_PATH,
    *,
    require_pin: bool = True,
) -> FreezeManifest:
    """Carica il manifest committato, ricalcola il `freeze_id`, rifiuta se diverge.

    Questo sostituisce la ricostruzione a runtime che il rito Z1 del 18/08 ha
    accertato in `scripts/run_day.py` (verbale RUN2 §A.2, precondizione
    TL-007): il manifest ricostruito incorporava lo sha di git corrente, che
    cambia a ogni commit, e le tre giornate di Stagione 0 produssero tre
    `freeze_id` diversi, nessuno uguale a quello del manifest firmato e
    timbrato. Qui il manifest si **legge**, non si ricostruisce.

    Tre rifiuti, tutti espliciti:

    1. il file non esiste, non è JSON, o non contiene un `FreezeManifest`
       valido;
    2. il `freeze_id` ricalcolato dal contenuto diverge da quello scritto nel
       file — qualcuno ha toccato il manifest dopo la firma;
    3. `pin_commit` è assente o è un segnaposto — il rito del pin non è ancora
       avvenuto e non esiste una stagione da far girare.

    `require_pin=False` esiste per gli strumenti che devono **leggere** un
    manifest non ancora pinnato (per esempio per stamparlo). Il runner non lo
    usa mai.
    """
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise ManifestError(
            f"manifest committato assente: {manifest_path}. Il runner carica "
            f"il manifest, non lo ricostruisce (verbale RUN2 §A.2)."
        )
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"manifest illeggibile: {manifest_path} — {exc}") from exc

    if not isinstance(document, dict) or "freeze_manifest" not in document:
        raise ManifestError(f"manifest senza blocco 'freeze_manifest': {manifest_path}")
    try:
        manifest = FreezeManifest.model_validate(document["freeze_manifest"])
    except Exception as exc:  # noqa: BLE001 - ri-alzato tipizzato
        raise ManifestError(
            f"blocco 'freeze_manifest' non valido in {manifest_path}: {exc}"
        ) from exc

    declared = document.get("freeze_id")
    recomputed = manifest.freeze_id
    if declared != recomputed:
        raise ManifestError(
            f"freeze_id divergente in {manifest_path}: il file dichiara "
            f"{declared!r}, il ricalcolo sul contenuto dà {recomputed!r}. "
            f"Il manifest è stato modificato dopo la firma, oppure è stato "
            f"scritto da una versione diversa del contratto. Non si gira."
        )

    if require_pin and not manifest.is_pinned:
        raise ManifestError(
            f"pin_commit assente o segnaposto in {manifest_path} "
            f"(valore: {manifest.pin_commit!r}). Il commit del rito del pin è "
            f"ciò che rende il freeze_id fisso per la stagione (verbale RUN2 "
            f"§A.2): finché non c'è, non esiste una stagione da far girare."
        )
    return manifest


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
    caching_policy: str = DEFAULT_CACHING_POLICY,
    agent_dir: Path = AGENT_DIR,
    context_git_sha: str | None = None,
    pin_commit: str = "",
    season_budget_usd: float | None = None,
    season_expected_days: int | None = None,
    price_per_mtok_input: float | None = None,
    price_per_mtok_output: float | None = None,
    price_per_mtok_cache_write_5m: float | None = None,
    price_per_mtok_cache_read: float | None = None,
    thinking_declared: ThinkingDeclaration = ThinkingDeclaration.ALWAYS_ON_PARAM_OMITTED,
) -> FreezeManifest:
    """Compone il manifest dal contenuto realmente congelato.

    D4 su Fable (ri-verifica richiesta da TL-002): la policy resta **identica**
    e diventa l'unica forma di chiamata valida. Su `claude-fable-5` i parametri
    di sampling `temperature`, `top_p` e `top_k` sono **rimossi**: inviarli
    produce 400. Il default operativo si ottiene quindi per **omissione**,
    esattamente come dichiarato. I tre campi restano `None`: "default dell'API"
    non deve mai essere confuso con "0" o con "non registrato".

    `thinking_policy=api_default` è l'unico valore valido su Fable: il thinking
    è **sempre attivo e non disattivabile**, e sia `{"type": "disabled"}` sia
    `budget_tokens` producono 400. Anche qui la policy si realizza omettendo il
    parametro.

    `pin_commit`, `season_budget_usd`, `season_expected_days` e le quattro voci
    di listino (`price_per_mtok_*`) restano vuoti finché non li valorizza il
    **rito del pin**: sono i campi che trasformano una composizione di prova in
    un pin di stagione. Un manifest composto qui senza di loro è leggibile ma
    non fa girare niente — vedi `load_pinned_manifest` e
    `ledger.spend.check_season_terms`.

    Il listino sta nel manifest e non fra i default di questa funzione per la
    stessa ragione per cui non sta più fra le costanti di `ledger/spend.py`: un
    prezzo con un default sopravvive al cambio di modello senza che nessuno se
    ne accorga, ed è precisamente quello che è successo fra TL-002 (Fable,
    $10/$50) e TL-007 (Opus 5, $5/$25).
    """
    context = load_context(agent_dir)
    return FreezeManifest(
        pinned_at_utc=pinned_at,
        model_string=model_string,
        model_string_note=model_note,
        sampling_policy=SamplingPolicy.API_DEFAULT_OMITTED,
        max_tokens=max_tokens,
        thinking_policy=ThinkingPolicy.API_DEFAULT,
        thinking_declared=thinking_declared,
        system_prompt_sha=context.system_prompt_sha,
        persona_sha=context.persona_sha,
        tool_schemas_sha=all_tool_schemas_sha(),
        context_git_sha=context_git_sha or current_git_sha(),
        pin_commit=pin_commit,
        season_budget_usd=season_budget_usd,
        season_expected_days=season_expected_days,
        price_per_mtok_input=price_per_mtok_input,
        price_per_mtok_output=price_per_mtok_output,
        price_per_mtok_cache_write_5m=price_per_mtok_cache_write_5m,
        price_per_mtok_cache_read=price_per_mtok_cache_read,
        caching_policy=caching_policy,
        ots_pending=True,
    )
