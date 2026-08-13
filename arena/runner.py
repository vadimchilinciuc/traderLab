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
from arena.llm_client import LLMClient, LLMResponse
from arena.risk_officer import PortfolioState, RiskOfficer
from arena.shadow_fill import compute_shadow_fill
from arena.verbale import SUBMIT_TOOL_NAME, MalformedReason, ParsedVerbale, parse_verbale
from ledger.telemetry import BehavioralTelemetry, DailyDispersion, daily_dispersion
from ledger.trader_ledger import LedgerKey, TraderLedger
from toolserver.registry import ToolRegistry
from toolserver.store import SnapshotStore
from toolserver.toollog import ToolCallLog

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
        return sum(1 for o in self.outcomes if o.malformed_reason is not None)

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

    def run_day(self, snapshot_id: str, run_id: str) -> DailyRunResult:
        snapshot = self._store.load(snapshot_id)
        telemetry = BehavioralTelemetry(self._config.replica_ids)
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
            is_refusal = parsed.reason is MalformedReason.MODEL_REFUSAL
            if is_refusal:
                verdict = RiskOfficer.reject_refusal(asset, parsed.detail)
                telemetry.observe_refusal(replica_id, verdict)
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
            response = client.complete(
                system=system, messages=messages, tools=self._tools
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
            tool_uses = response.tool_uses()
            if not tool_uses:
                break
            if any(_name(b) == SUBMIT_TOOL_NAME for b in tool_uses):
                break

            messages.append({"role": "assistant", "content": _to_params(response.content)})
            tool_results = []
            for block in tool_uses:
                tool_results.append(
                    self._execute_tool(
                        block=block, snapshot_id=snapshot.snapshot_id, replica_id=replica_id
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
        self, *, block: Any, snapshot_id: str, replica_id: str
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
            "tool_use_id": _id(block),
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


def _to_params(content: list[Any]) -> list[dict[str, Any]]:
    """Converte i blocchi di risposta in blocchi di richiesta per il turno dopo."""
    params: list[dict[str, Any]] = []
    for block in content:
        block_type = (
            block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        )
        if block_type == "text":
            text = (
                block.get("text") if isinstance(block, dict) else getattr(block, "text", "")
            )
            if text:
                params.append({"type": "text", "text": text})
        elif block_type == "tool_use":
            params.append(
                {
                    "type": "tool_use",
                    "id": _id(block),
                    "name": _name(block),
                    "input": _input(block) or {},
                }
            )
    return params
