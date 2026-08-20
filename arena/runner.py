"""Runner giornaliero: carica lo snapshot congelato e lancia le repliche.

Isolamento (D1 + CLAUDE.md §3, §6): ogni replica parte da zero. Nuova lista di
messaggi, nuovo stato di portafoglio, nessun contesto condiviso, nessuna
traccia delle altre repliche o delle giornate precedenti. Il `replica_id` serve
al ledger e alla telemetria e **non entra mai** nel prompt.

Il ciclo di tool-use non forza `tool_choice`: forzarlo sopprimerebbe il testo
libero che deve precedere il blocco strutturato (vedi `arena/verbale.py`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contracts.decision import DecisionRecord
from contracts.fill import ShadowFill
from contracts.hashing import sha256_of
from contracts.risk import RiskOutcome, RiskVerdict
from contracts.snapshot import MarketSnapshot
from arena.config import ArenaConfig, ContextFiles, all_tool_schemas, load_context
from arena.llm_client import LLMClient, LLMError, LLMResponse
from arena.risk_officer import PortfolioState, RiskOfficer
from arena.shadow_fill import compute_shadow_fill
from arena.verbale import (
    SUBMIT_TOOL_NAME,
    MalformedReason,
    ParsedVerbale,
    is_true_malformed,
    parse_verbale,
)
from ledger.telemetry import BehavioralTelemetry, DailyDispersion, daily_dispersion
from ledger.trader_ledger import LedgerKey, TraderLedger
from toolserver.registry import ToolRegistry
from toolserver.store import SnapshotStore
from toolserver.toollog import LLM_COMPLETE_TOOL, ToolCallLog

__all__ = [
    "LLM_COMPLETE_TOOL",
    "AssetOutcome",
    "DailyRunResult",
    "DailyRunner",
    "RunnerError",
]

USER_TEMPLATE = (
    "Istante di riferimento dei dati: {asof}.\n"
    "ASSET: {asset}\n\n"
    "Esamina i dati disponibili per questo asset e registra la tua decisione."
)


class RunnerError(Exception):
    pass


@dataclass(slots=True)
class AssetOutcome:
    """Esito per un singolo (replica, asset)."""

    replica_id: str
    asset: str
    verdict: RiskVerdict
    decision: DecisionRecord | None = None
    fill: ShadowFill | None = None
    malformed_reason: MalformedReason | None = None
    attempts: int = 1


@dataclass(slots=True)
class DailyRunResult:
    run_id: str
    snapshot_id: str
    asof_utc: datetime
    outcomes: list[AssetOutcome] = field(default_factory=list)
    dispersion: DailyDispersion | None = None
    telemetry: BehavioralTelemetry | None = None
    # {replica_id: {asset: sha256 dell'input inviato}}
    request_fingerprints: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def decisions(self) -> list[DecisionRecord]:
        return [o.decision for o in self.outcomes if o.decision is not None]

    @property
    def malformed_count(self) -> int:
        """Verbali malformati **veri** (verbale RUN2 §A.5).

        Rifiuti del modello e risposte troncate da `max_tokens` sono esclusi:
        hanno ciascuno la propria contabilità, una sola, e finivano qui dentro
        producendo un doppio conteggio. La giornata del 18/08 di Stagione 0
        stampò «malformati: 2» avendo però un solo verbale malformato vero
        (`no_tool_use` su r1 BTC) e un rifiuto del modello (r3 ETH).
        """
        return sum(1 for o in self.outcomes if is_true_malformed(o.malformed_reason))

    @property
    def refusal_count(self) -> int:
        """Rifiuti del modello. Unica sede del conteggio insieme a
        `BehavioralTelemetry.refusals_total`, che misura la stessa cosa per
        replica invece che per giornata."""
        return sum(
            1
            for o in self.outcomes
            if o.malformed_reason is MalformedReason.MODEL_REFUSAL
        )

    @property
    def truncated_count(self) -> int:
        """Risposte tagliate da `max_tokens`. Contate a parte da entrambe."""
        return sum(
            1 for o in self.outcomes if o.malformed_reason is MalformedReason.TRUNCATED
        )

    def by_replica(self) -> dict[str, dict[str, DecisionRecord]]:
        out: dict[str, dict[str, DecisionRecord]] = {}
        for outcome in self.outcomes:
            if outcome.decision is not None:
                out.setdefault(outcome.replica_id, {})[outcome.asset] = outcome.decision
        return out


class DailyRunner:
    """Orchestratore di una giornata di decisioni."""

    def __init__(
        self,
        *,
        store: SnapshotStore,
        ledger: TraderLedger,
        tool_log: ToolCallLog,
        client_factory,
        config: ArenaConfig | None = None,
        context: ContextFiles | None = None,
        model_version: str | None = None,
        prompt_sha: str | None = None,
        context_git_sha: str = "0000000",
    ) -> None:
        self._store = store
        self._ledger = ledger
        self._tool_log = tool_log
        self._registry = ToolRegistry(store, tool_log)
        self._client_factory = client_factory
        self._config = config or ArenaConfig()
        self._context = context or load_context()
        self._officer = RiskOfficer(self._config.risk)
        self._model_version_override = model_version
        self._prompt_sha = prompt_sha or self._context.rendered_sha
        self._context_git_sha = context_git_sha
        self._tools = all_tool_schemas()

    # -- API principale ----------------------------------------------------

    def run_day(
        self,
        snapshot_id: str,
        run_id: str,
        telemetry: BehavioralTelemetry | None = None,
    ) -> DailyRunResult:
        """Esegue una giornata.

        `telemetry` accetta un accumulatore esterno: turnover e flip rate si
        misurano **tra** giornate, non dentro una. Con un accumulatore nuovo a
        ogni giorno il flip rate resterebbe zero per costruzione, perché non
        esisterebbe mai una posizione precedente da confrontare. Se non viene
        passato nulla si torna al comportamento di prima: un accumulatore per
        la sola giornata.
        """
        if run_id != self._tool_log.run_id:
            # Il `tool_calls_ref` scritto in ogni verbale viene dal tool log.
            # Con run_id diversi il ledger direbbe una giornata e il verbale ne
            # indicherebbe un'altra: l'attribuzione punterebbe al file
            # sbagliato, in silenzio. Errore pulito (CLAUDE.md §7, §9).
            raise RunnerError(
                f"run_id '{run_id}' non corrisponde al tool log "
                f"'{self._tool_log.run_id}': tool_calls_ref punterebbe a una "
                f"giornata diversa da quella scritta nel ledger"
            )
        snapshot = self._store.load(snapshot_id)
        telemetry = telemetry or BehavioralTelemetry(self._config.replica_ids)
        result = DailyRunResult(
            run_id=run_id,
            snapshot_id=snapshot_id,
            asof_utc=snapshot.asof_utc,
            telemetry=telemetry,
        )

        for replica_id in self._config.replica_ids:
            # Isolamento: client, stato e messaggi sono nuovi per ogni replica.
            client = self._client_factory(replica_id)
            state = PortfolioState(allowed_assets=frozenset(snapshot.universe))
            for asset in sorted(snapshot.universe):
                outcome = self._run_one(
                    snapshot=snapshot,
                    asset=asset,
                    replica_id=replica_id,
                    client=client,
                    state=state,
                    telemetry=telemetry,
                    run_id=run_id,
                    result=result,
                )
                result.outcomes.append(outcome)

        result.dispersion = daily_dispersion(result.by_replica())
        return result

    # -- una decisione -----------------------------------------------------

    def _run_one(
        self,
        *,
        snapshot: MarketSnapshot,
        asset: str,
        replica_id: str,
        client: LLMClient,
        state: PortfolioState,
        telemetry: BehavioralTelemetry,
        run_id: str,
        result: DailyRunResult,
    ) -> AssetOutcome:
        parsed: ParsedVerbale | None = None
        attempts = 0
        for attempt in range(self._config.malformed_retries + 1):
            attempts = attempt + 1
            parsed = self._one_conversation(
                snapshot=snapshot,
                asset=asset,
                replica_id=replica_id,
                client=client,
                result=result,
            )
            if parsed.ok:
                break
            if parsed.reason is MalformedReason.MODEL_REFUSAL:
                # Un rifiuto non si ritenta: l'input è identico, la risposta
                # sarebbe identica, e Fable è il modello più caro del listino.
                # Il retry singolo esiste per i verbali malformati, che sono
                # un inciampo di formato, non per i rifiuti.
                break

        assert parsed is not None
        if not parsed.ok:
            if parsed.reason is MalformedReason.MODEL_REFUSAL:
                verdict = RiskOfficer.reject_refusal(asset, parsed.detail)
                telemetry.observe_refusal(replica_id, verdict)
            elif parsed.reason is MalformedReason.TRUNCATED:
                verdict = RiskOfficer.reject_truncated(asset, parsed.detail)
                telemetry.observe_truncated(replica_id, verdict)
            else:
                verdict = RiskOfficer.reject_malformed(asset, parsed.detail)
                telemetry.observe_malformed(replica_id, verdict)
            self._write(
                snapshot=snapshot,
                replica_id=replica_id,
                asset=asset,
                verdict=verdict,
                decision=None,
                fill=None,
                malformed_reason=parsed.reason.value if parsed.reason else None,
                run_id=run_id,
            )
            return AssetOutcome(
                replica_id=replica_id,
                asset=asset,
                verdict=verdict,
                malformed_reason=parsed.reason,
                attempts=attempts,
            )

        decision = parsed.record
        assert decision is not None
        verdict = self._officer.review(decision, state)
        telemetry.observe_decision(decision, verdict)

        fill = None
        if verdict.is_executable and verdict.size_fraction_out > 0.0:
            asset_snapshot = next(a for a in snapshot.assets if a.symbol == asset)
            fill = compute_shadow_fill(
                asset=asset_snapshot,
                action=verdict.action_out,
                size_fraction=verdict.size_fraction_out,
                timestamp_utc=snapshot.asof_utc,
                snapshot_id=snapshot.snapshot_id,
                replica_id=replica_id,
                assume_taker=self._config.assume_taker,
                slippage_as_half_spread=self._config.slippage_as_half_spread,
            )
        if verdict.outcome is not RiskOutcome.REJECTED:
            state.register(asset, verdict.size_fraction_out)

        self._write(
            snapshot=snapshot,
            replica_id=replica_id,
            asset=asset,
            verdict=verdict,
            decision=decision,
            fill=fill,
            malformed_reason=None,
            run_id=run_id,
        )
        return AssetOutcome(
            replica_id=replica_id,
            asset=asset,
            verdict=verdict,
            decision=decision,
            fill=fill,
            attempts=attempts,
        )

    # -- ciclo di tool use -------------------------------------------------

    def _one_conversation(
        self,
        *,
        snapshot: MarketSnapshot,
        asset: str,
        replica_id: str,
        client: LLMClient,
        result: DailyRunResult,
    ) -> ParsedVerbale:
        system = self._context.rendered_system
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": USER_TEMPLATE.format(
                    asof=snapshot.asof_utc.isoformat(), asset=asset
                ),
            }
        ]
        # Impronta dell'input: serve a dimostrare che le repliche partono da
        # byte identici. Non contiene il replica_id, perche' il replica_id non
        # entra nell'input.
        result.request_fingerprints.setdefault(replica_id, {})[asset] = sha256_of(
            {"system": system, "tools": self._tools, "messages": messages}
        )

        response: LLMResponse | None = None
        for _ in range(self._config.max_tool_iterations):
            try:
                response = client.complete(
                    system=system, messages=messages, tools=self._tools
                )
            except LLMError as exc:
                # La telemetria del tentativo (CLAUDE.md §9) va loggata anche
                # quando la chiamata fallisce del tutto: è qui, prima che
                # l'errore risalga e faccia fallire il processo, l'unico
                # punto che conosce ancora replica e asset.
                self._tool_log.record(
                    replica_id=replica_id,
                    snapshot_id=snapshot.snapshot_id,
                    tool=LLM_COMPLETE_TOOL,
                    args={"asset": asset},
                    error=str(exc),
                    meta={
                        "attempts": exc.attempts,
                        "attempt_errors": list(exc.attempt_errors),
                        "duration_seconds": exc.duration_seconds,
                        "error_type": exc.error_type,
                        "retryable": exc.retryable,
                    },
                )
                raise
            self._tool_log.record(
                replica_id=replica_id,
                snapshot_id=snapshot.snapshot_id,
                tool=LLM_COMPLETE_TOOL,
                args={"asset": asset},
                response={"stop_reason": response.stop_reason},
                meta={
                    "attempts": response.attempts,
                    "attempt_errors": list(response.attempt_errors),
                    "duration_seconds": response.duration_seconds,
                    "input_tokens": (
                        response.usage.input_tokens if response.usage else None
                    ),
                    "output_tokens": (
                        response.usage.output_tokens if response.usage else None
                    ),
                    "cache_creation_input_tokens": (
                        response.usage.cache_creation_input_tokens
                        if response.usage
                        else None
                    ),
                    "cache_read_input_tokens": (
                        response.usage.cache_read_input_tokens
                        if response.usage
                        else None
                    ),
                    # Verbale RUN2 §A.7: il thinking si logga separato
                    # dall'output, e la sua ASSENZA si logga esplicitamente.
                    # Con `usage` assente entrambi i campi restano comunque
                    # presenti nel record: `None` per il conteggio, `True` per
                    # l'assenza, mai il silenzio.
                    "thinking_tokens": (
                        response.usage.thinking_tokens if response.usage else None
                    ),
                    "thinking_absent": (
                        response.usage.thinking_absent if response.usage else True
                    ),
                },
            )
            # Rifiuto dei classificatori: HTTP 200 con content vuoto o parziale.
            # Va intercettato qui, altrimenti il parser lo classificherebbe
            # come "nessun blocco strutturato" e finirebbe tra i malformati.
            if response.is_refusal:
                return ParsedVerbale(
                    ok=False,
                    reason=MalformedReason.MODEL_REFUSAL,
                    detail=(
                        "il modello ha declinato la richiesta"
                        + (
                            f" (categoria: {response.refusal_category})"
                            if response.refusal_category
                            else ""
                        )
                    ),
                )
            # Guardia troncamento: stop_reason="max_tokens" e' HTTP 200 con un
            # contenuto potenzialmente incompleto (testo a meta', tool_use con
            # argomenti tagliati). Va intercettato qui, prima di consegnare il
            # blocco al parser: un verbale tagliato non e' un verbale
            # malformato dal modello, e non deve mai finire in un tool_result
            # parziale interpretato come definitivo.
            if response.stop_reason == "max_tokens":
                return ParsedVerbale(
                    ok=False,
                    reason=MalformedReason.TRUNCATED,
                    detail="risposta troncata da max_tokens prima di un verbale completo",
                )
            tool_uses = response.tool_uses()
            if not tool_uses:
                break
            if any(_name(b) == SUBMIT_TOOL_NAME for b in tool_uses):
                break

            # RITO DIAGNOSI CACHING: l'id che l'API assegna a un blocco
            # tool_use cambia a ogni generazione anche a parita' di
            # asset/argomenti. Rimandarlo indietro cosi' com'e' (come
            # faceva prima questo punto) rende il prefisso della richiesta
            # di submit diverso a ogni chiamata, e il blocco degli ultimi
            # tool_result — identico per costruzione tra le repliche dello
            # stesso asset, D1 — non viene mai riletto dalla cache: viene
            # riscritto da zero a ogni chiamata. L'API non verifica l'id
            # contro nulla al di fuori del giro in cui compare: le basta che
            # l'id del tool_use nel turno dell'assistente coincida con il
            # tool_use_id del tool_result nello stesso turno. Sostituendolo
            # con uno derivato dal contenuto (nome, argomenti, posizione)
            # rende il prefisso riproducibile a parita' di asset,
            # indipendentemente da quale id il modello abbia scelto quella
            # volta.
            det_ids = [
                _deterministic_tool_id(_name(b), _input(b), i)
                for i, b in enumerate(tool_uses)
            ]
            # B.3 del verbale RUN2: il turno rimandato indietro porta i SOLI
            # blocchi tool_use. Il testo libero che il modello ha scritto prima
            # della chiamata cambia a ogni generazione: lasciarlo qui spezza il
            # prefisso di cache a ogni turno e, con esso, la comparabilita' fra
            # chiamate che per costruzione dovrebbero essere identiche (D1).
            # Rimuoverlo e' il rimedio misurato 8,8x sul costo per chiamata
            # (da ~$1,7809 a ~$0,2154) e la rimozione della fonte di divergenza
            # dei prefissi. Il razionale in testo libero resta obbligatorio nel
            # turno FINALE, quello che porta il verbale: quel turno non passa
            # di qui, va al parser (`arena/verbale.py`), e CLAUDE.md §8 e'
            # intatto.
            messages.append(
                {
                    "role": "assistant",
                    "content": _to_params(
                        response.content, tool_ids=det_ids, only_tool_use=True
                    ),
                }
            )
            tool_results = []
            for block, tool_use_id in zip(tool_uses, det_ids):
                tool_results.append(
                    self._execute_tool(
                        block=block,
                        snapshot_id=snapshot.snapshot_id,
                        replica_id=replica_id,
                        tool_use_id=tool_use_id,
                    )
                )
            messages.append({"role": "user", "content": tool_results})
        else:
            return ParsedVerbale(
                ok=False,
                reason=MalformedReason.NO_TOOL_USE,
                detail=(
                    f"raggiunto il tetto di {self._config.max_tool_iterations} "
                    f"iterazioni senza un verbale"
                ),
            )

        if response is None:
            return ParsedVerbale(
                ok=False, reason=MalformedReason.NO_TOOL_USE, detail="nessuna risposta"
            )

        return parse_verbale(
            response.content,
            expected_asset=asset,
            timestamp_decision=snapshot.asof_utc,
            replica_id=replica_id,
            snapshot_id=snapshot.snapshot_id,
            model_version=self._model_version_override or client.model_version,
            prompt_sha=self._prompt_sha,
            context_git_sha=self._context_git_sha,
            tool_calls_ref=self._tool_log.ref,
        )

    def _execute_tool(
        self, *, block: Any, snapshot_id: str, replica_id: str, tool_use_id: str
    ) -> dict[str, Any]:
        name = _name(block)
        args = _input(block) or {}
        try:
            payload = self._registry.call(
                snapshot_id=snapshot_id,
                replica_id=replica_id,
                name=name,
                args=args,
            )
            content = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            is_error = False
        except Exception as exc:  # noqa: BLE001 - l'errore torna al modello
            content = json.dumps(
                {"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False
            )
            is_error = True
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
            "is_error": is_error,
        }

    # -- persistenza -------------------------------------------------------

    def _write(
        self,
        *,
        snapshot: MarketSnapshot,
        replica_id: str,
        asset: str,
        verdict: RiskVerdict,
        decision: DecisionRecord | None,
        fill: ShadowFill | None,
        malformed_reason: str | None,
        run_id: str,
    ) -> None:
        self._ledger.append(
            key=LedgerKey.of(snapshot.asof_utc, replica_id, asset),
            verdict=verdict,
            decision=decision,
            fill=fill,
            malformed_reason=malformed_reason,
            snapshot_id=snapshot.snapshot_id,
            run_id=run_id,
        )


# --------------------------------------------------------------------------
# Normalizzazione dei blocchi (SDK o dizionari)
# --------------------------------------------------------------------------


def _name(block: Any) -> str | None:
    return block.get("name") if isinstance(block, dict) else getattr(block, "name", None)


def _input(block: Any) -> dict[str, Any] | None:
    return block.get("input") if isinstance(block, dict) else getattr(block, "input", None)


def _id(block: Any) -> str:
    value = block.get("id") if isinstance(block, dict) else getattr(block, "id", None)
    return value or "tool_use_missing_id"


def _deterministic_tool_id(name: str | None, args: dict[str, Any] | None, index: int) -> str:
    """Id stabile per un blocco tool_use, derivato dal suo contenuto.

    Sostituisce l'id assegnato dall'API alla generazione corrente, che
    cambia a ogni chiamata anche a parita' di tool e argomenti (RITO
    DIAGNOSI CACHING). `index` distingue due chiamate allo stesso tool con
    gli stessi argomenti nello stesso turno.
    """
    digest = sha256_of({"name": name, "args": args or {}, "index": index})
    return f"toolu_det_{digest[:32]}"


def _to_params(
    content: list[Any],
    tool_ids: list[str] | None = None,
    *,
    only_tool_use: bool = False,
) -> list[dict[str, Any]]:
    """Converte i blocchi di risposta in blocchi di richiesta per il turno dopo.

    Se `tool_ids` e' passato, sostituisce l'id di ogni blocco `tool_use` (in
    ordine di comparsa) con quello indicato invece di quello dell'API — vedi
    `_deterministic_tool_id`.

    Con `only_tool_use=True` i blocchi di testo vengono **scartati**: e' il
    rimedio B.3 del verbale RUN2, che rende il prefisso della richiesta
    riproducibile fra chiamate. Il default resta `False` perche' la funzione
    e' anche la conversione generica dei blocchi.
    """
    params: list[dict[str, Any]] = []
    tool_idx = 0
    for block in content:
        block_type = (
            block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        )
        if block_type == "text" and only_tool_use:
            continue
        if block_type == "text":
            text = (
                block.get("text") if isinstance(block, dict) else getattr(block, "text", "")
            )
            if text:
                params.append({"type": "text", "text": text})
        elif block_type == "tool_use":
            block_id = tool_ids[tool_idx] if tool_ids is not None else _id(block)
            tool_idx += 1
            params.append(
                {
                    "type": "tool_use",
                    "id": block_id,
                    "name": _name(block),
                    "input": _input(block) or {},
                }
            )
    return params
