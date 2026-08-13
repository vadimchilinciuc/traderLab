"""Client del Trader: Anthropic reale e MockLLM deterministico.

D2/D4 in codice:

- La model string viene **dal FreezeManifest**, mai da una costante sparsa nel
  runner.
- I parametri di sampling **non vengono inviati**. Sui modelli Claude Sonnet
  correnti `temperature`, `top_p` e `top_k` non-default sono rifiutati con 400:
  il "default operativo dell'API" (D4) si ottiene per omissione. Il client
  verifica il manifest e si rifiuta di partire se qualcuno prova a passarli.
- La API key arriva **solo** da ambiente.

MockLLM esiste perché l'intera pipeline deve girare end-to-end **senza API**:
un test che ha bisogno della rete non è un test di regressione, è un
esperimento.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from contracts.freeze import FreezeManifest, SamplingPolicy, ThinkingPolicy


class LLMError(Exception):
    """Errore di una chiamata al modello.

    Porta con sé la telemetria del tentativo (CLAUDE.md §9: cosa il Trader
    chiede è un dato, alla pari di cosa decide — e qui "chiede" include
    quante volte ha dovuto chiedere). `retryable` distingue un errore che il
    client ha classificato come transitorio ma per cui ha comunque esaurito
    la propria pazienza corta (`max_retries`) da un errore definitivo: solo
    il primo caso vale la pena ritentarlo a un livello più alto (il rito).
    """

    def __init__(
        self,
        message: str,
        *,
        error_type: str | None = None,
        retryable: bool = False,
        attempts: int = 1,
        attempt_errors: tuple[str | None, ...] = (),
        duration_seconds: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable
        self.attempts = attempts
        self.attempt_errors = attempt_errors
        self.duration_seconds = duration_seconds


class BudgetExceeded(LLMError):
    """Superato il tetto di chiamate dichiarato per la giornata."""


class MissingApiKey(LLMError):
    pass


# Contratto fra `scripts/run_day.py` (produttore) e `arena/daily_ritual.py`
# (consumatore): quando il processo delle decisioni esce con questo codice,
# il rito sa che il fallimento è un `LLMError` classificato ritentabile — un
# errore di rete/capacità per cui il client ha già esaurito la propria
# pazienza corta — e vale la pena ritentare l'intero passo con pazienza
# lunga, invece di trattarlo come un fallimento definitivo.
RETRYABLE_PROCESS_EXIT_CODE = 10


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Risposta normalizzata: blocchi di contenuto nell'ordine ricevuto.

    `attempts`, `attempt_errors` e `duration_seconds` sono la telemetria del
    tentativo (CLAUDE.md §9): quante chiamate HTTP ha richiesto questa
    risposta, con quale `type` di errore ciascun tentativo fallito prima del
    successo, e quanto tempo è passato in tutto — retry e attese di backoff
    inclusi. Il MockLLM non fa rete: i default (un tentativo, nessun errore,
    durata zero) sono corretti così come sono.
    """

    content: list[Any]
    stop_reason: str | None
    model: str
    refusal_category: str | None = None
    attempts: int = 1
    attempt_errors: tuple[str | None, ...] = ()
    duration_seconds: float = 0.0

    def tool_uses(self) -> list[Any]:
        return [b for b in self.content if _block_type(b) == "tool_use"]

    @property
    def is_refusal(self) -> bool:
        """Rifiuto dei classificatori: HTTP 200, `stop_reason='refusal'`.

        Non è un errore di rete e non è un verbale malformato: è il modello che
        declina. Va contato a parte, altrimenti inquina il tasso di verbali
        malformati con qualcosa che non riguarda il protocollo.
        """
        return self.stop_reason == "refusal"


class LLMClient(Protocol):
    """Cosa serve al runner. Reale e mock implementano la stessa forma."""

    model_version: str

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse: ...


# --------------------------------------------------------------------------
# Guardia di budget
# --------------------------------------------------------------------------


@dataclass(slots=True)
class CallBudget:
    """Tetto di chiamate per giornata. Superarlo è un errore, non un warning."""

    max_calls: int
    used: int = 0

    def consume(self) -> None:
        if self.used >= self.max_calls:
            raise BudgetExceeded(
                f"tetto di {self.max_calls} chiamate/giorno raggiunto"
            )
        self.used += 1

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.used)


# --------------------------------------------------------------------------
# Client Anthropic
# --------------------------------------------------------------------------


class AnthropicTraderClient:
    """Client reale. Non viene mai istanziato dalla suite di test.

    Scelte specifiche del modello pinnato in TL-002 (`claude-fable-5`):

    - **Nessun parametro di sampling** (D4). Su Fable `temperature`, `top_p` e
      `top_k` sono rimossi e inviarli produce 400: la policy dichiarata è anche
      l'unica chiamata valida.
    - **Nessuna configurazione di `thinking`.** Su Fable il thinking è sempre
      attivo; `{"type": "disabled"}` e `budget_tokens` producono entrambi 400.
      Si omette il parametro.
    - **Streaming di default.** I turni di Fable possono durare minuti e
      `max_tokens` è alto perché il thinking consuma lo stesso budget: senza
      streaming si rischia il timeout HTTP dell'SDK.
    - **Nessun `fallbacks`.** La guida generale dell'API consiglia di attivare
      il fallback server-side su Fable, ma qui sarebbe **dannoso**: un rifiuto
      verrebbe servito in silenzio da un altro modello, e D2 dice che un
      cambio di modello apre un nuovo track record. Un rifiuto deve restare un
      rifiuto, visibile e loggato.
    """

    def __init__(
        self,
        manifest: FreezeManifest,
        *,
        budget: CallBudget | None = None,
        max_retries: int = 3,
        base_backoff_seconds: float = 1.0,
        timeout_seconds: float = 900.0,
        use_streaming: bool = True,
        sleep=time.sleep,
        client: Any | None = None,
    ) -> None:
        if manifest.sampling_policy is not SamplingPolicy.API_DEFAULT_OMITTED:
            raise LLMError(
                "questo client implementa solo sampling_policy="
                "api_default_omitted (D4): i parametri di sampling non vengono "
                "inviati affatto"
            )
        if manifest.thinking_policy is not ThinkingPolicy.API_DEFAULT:
            raise LLMError(
                f"thinking_policy={manifest.thinking_policy.value} non è "
                f"inviabile: su claude-fable-5 il thinking è sempre attivo e "
                f"sia 'disabled' sia budget_tokens producono 400. L'unica "
                f"policy valida è api_default (parametro omesso)."
            )
        self._manifest = manifest
        self.model_version = manifest.model_string
        self._budget = budget or CallBudget(max_calls=200)
        self._max_retries = max_retries
        self._base_backoff = base_backoff_seconds
        self._timeout = timeout_seconds
        self._use_streaming = use_streaming
        self._sleep = sleep
        self._client = client or self._build_client(timeout_seconds)

    @staticmethod
    def _build_client(timeout_seconds: float) -> Any:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise MissingApiKey(
                "ANTHROPIC_API_KEY assente. La chiave si legge solo da ambiente."
            )
        import anthropic  # import locale: la suite non deve dipenderne

        return anthropic.Anthropic(timeout=timeout_seconds)

    @property
    def budget(self) -> CallBudget:
        return self._budget

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        self._budget.consume()
        # NOTA D4: nessun temperature / top_p / top_k. Nessun `thinking`.
        # Nessun `fallbacks`. Ogni omissione qui e' una policy, non una
        # dimenticanza: vedi il docstring della classe.
        payload = {
            "model": self._manifest.model_string,
            "max_tokens": self._manifest.max_tokens,
            "system": system,
            "messages": messages,
            "tools": tools,
        }
        started = time.monotonic()
        attempt_errors: list[str | None] = []
        for attempt in range(self._max_retries + 1):
            try:
                response = self._invoke(payload)
            except Exception as exc:  # noqa: BLE001 - classificato sotto
                error_type = _error_type(exc)
                retryable = _is_retryable(exc)
                attempt_errors.append(error_type or exc.__class__.__name__)
                if not retryable or attempt == self._max_retries:
                    raise LLMError(
                        f"chiamata al modello fallita: {exc}",
                        error_type=error_type,
                        retryable=retryable,
                        attempts=attempt + 1,
                        attempt_errors=tuple(attempt_errors),
                        duration_seconds=time.monotonic() - started,
                    ) from exc
                self._sleep(self._base_backoff * (2**attempt))
                continue
            return _normalize_response(
                response,
                self._manifest.model_string,
                attempts=attempt + 1,
                attempt_errors=tuple(attempt_errors),
                duration_seconds=time.monotonic() - started,
            )
        raise LLMError("chiamata al modello fallita: nessun tentativo eseguito")

    def _invoke(self, payload: dict[str, Any]) -> Any:
        """Streaming di default; `create` solo se esplicitamente disattivato."""
        if not self._use_streaming:
            return self._client.messages.create(**payload)
        with self._client.messages.stream(**payload) as stream:
            return stream.get_final_message()


def _normalize_response(
    response: Any,
    fallback_model: str,
    *,
    attempts: int = 1,
    attempt_errors: tuple[str | None, ...] = (),
    duration_seconds: float = 0.0,
) -> LLMResponse:
    stop_reason = getattr(response, "stop_reason", None)
    category = None
    if stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) if details else None
    return LLMResponse(
        content=list(getattr(response, "content", []) or []),
        stop_reason=stop_reason,
        model=getattr(response, "model", fallback_model),
        refusal_category=category,
        attempts=attempts,
        attempt_errors=attempt_errors,
        duration_seconds=duration_seconds,
    )


# Classificazione per `type` del corpo dell'errore API. Serve perché un errore
# transitorio può arrivare **dentro** lo stream: l'HTTP è già 200, quindi lo
# status code non dice nulla e da solo farebbe passare per definitivo un
# overloaded. Il `type` invece è lo stesso in-stream e fuori stream.
_RETRYABLE_ERROR_TYPES = frozenset(
    {
        "overloaded_error",  # 529
        "rate_limit_error",  # 429
        "api_error",  # 500
        "timeout_error",
    }
)
_FATAL_ERROR_TYPES = frozenset(
    {
        "invalid_request_error",  # 400
        "authentication_error",  # 401
        "permission_error",  # 403
        "not_found_error",  # 404
        "request_too_large",  # 413
        "billing_error",
    }
)


def _error_type(exc: Exception) -> str | None:
    """Il campo `type` dell'errore API, ovunque l'SDK lo abbia messo.

    Fuori stream l'SDK espone `.type` sulle sottoclassi di `APIStatusError`.
    Dentro lo stream l'evento `error` diventa un `APIError` nudo che porta il
    corpo in `.body`, a volte già spacchettato (`{"type": ...}`), a volte
    ancora avvolto (`{"error": {"type": ...}}`).
    """
    declared = getattr(exc, "type", None)
    if isinstance(declared, str):
        return declared
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        inner = body.get("error")
        if isinstance(inner, dict) and isinstance(inner.get("type"), str):
            return inner["type"]
        if isinstance(body.get("type"), str):
            return body["type"]
    return None


def _is_retryable(exc: Exception) -> bool:
    """Ritentabile se lo dice il `type`; altrimenti 429 e 5xx; altrimenti classe.

    Il `type` viene per primo perché è l'unico segnale valido quando l'errore
    arriva a stream aperto: lì `response.status_code` vale 200 e classificare
    per status trasformerebbe ogni overloaded in un errore definitivo.
    """
    error_type = _error_type(exc)
    if error_type in _RETRYABLE_ERROR_TYPES:
        return True
    if error_type in _FATAL_ERROR_TYPES:
        return False

    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if isinstance(status, int) and status != 200:
        return status == 429 or status >= 500
    return exc.__class__.__name__ in {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
        "OverloadedError",
    }


# --------------------------------------------------------------------------
# MockLLM deterministico
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MockBlock:
    """Blocco di contenuto compatibile con il parser del verbale."""

    type: str
    text: str = ""
    name: str | None = None
    input: dict[str, Any] | None = None
    id: str = "mock_tool_use"


@dataclass(slots=True)
class MockLLM:
    """Trader simulato, deterministico e senza rete.

    Comportamento fisso in due turni, identico a quello di un modello che
    rispetta il protocollo:

    1. consulta `get_asset_dossier` per l'asset chiesto;
    2. scrive il razionale in testo libero e chiama `submit_decision`.

    La regola di decisione è una soglia sul dossier: serve a far girare la
    pipeline end-to-end, **non** è una strategia.
    """

    model_version: str = "mock-llm-0"
    budget: CallBudget = field(default_factory=lambda: CallBudget(max_calls=1000))
    # Comportamenti iniettabili per i test: "ok", "malformed", "flat".
    behaviour: str = "ok"
    calls: int = 0

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        self.budget.consume()
        self.calls += 1
        asset = _asset_from_messages(messages)
        dossier = _dossier_from_messages(messages)

        if dossier is None:
            return LLMResponse(
                content=[
                    MockBlock(type="text", text="Consulto le grandezze disponibili."),
                    MockBlock(
                        type="tool_use",
                        name="get_asset_dossier",
                        input={"symbol": asset},
                        id=f"mock_dossier_{asset}",
                    ),
                ],
                stop_reason="tool_use",
                model=self.model_version,
            )

        if self.behaviour == "malformed":
            # Blocco strutturato senza razionale: deve essere rifiutato.
            return LLMResponse(
                content=[
                    MockBlock(
                        type="tool_use",
                        name="submit_decision",
                        input=_decision_payload(asset, dossier, force_flat=False),
                        id=f"mock_submit_{asset}",
                    )
                ],
                stop_reason="tool_use",
                model=self.model_version,
            )

        force_flat = self.behaviour == "flat"
        payload = _decision_payload(asset, dossier, force_flat=force_flat)
        return LLMResponse(
            content=[
                MockBlock(type="text", text=_rationale(asset, dossier, payload)),
                MockBlock(
                    type="tool_use",
                    name="submit_decision",
                    input=payload,
                    id=f"mock_submit_{asset}",
                ),
            ],
            stop_reason="tool_use",
            model=self.model_version,
        )


def _decision_payload(
    asset: str, dossier: dict[str, Any], *, force_flat: bool
) -> dict[str, Any]:
    features = dossier.get("features", {})
    trend = features.get("price_vs_sma_20")
    volume = features.get("volume_ratio_20")
    go_long = (not force_flat) and isinstance(trend, (int, float)) and trend > 0.0

    used = [{"name": "price_vs_sma_20", "value": float(trend or 0.0)}]
    if isinstance(volume, (int, float)):
        used.append({"name": "volume_ratio_20", "value": float(volume)})

    return {
        "asset": asset,
        "action": "long" if go_long else "flat",
        "size_fraction": 0.05 if go_long else 0.0,
        "horizon": "1-3d",
        "expected_holding": "1-3d",
        "confidence": 0.58 if go_long else 0.5,
        "features_used": used,
        "invalidation_conditions": [
            "Chiusura giornaliera sotto la media mobile a 20 barre.",
        ],
        "risk_checks": [
            {"name": "costi_considerati", "passed": True, "note": ""},
        ],
    }


def _rationale(asset: str, dossier: dict[str, Any], payload: dict[str, Any]) -> str:
    features = dossier.get("features", {})
    return (
        f"Il prezzo di {asset} si trova a "
        f"{features.get('price_vs_sma_20')} rispetto alla media mobile a 20 "
        f"barre, e il rapporto tra il volume dell'ultima barra e la media a 20 "
        f"barre vale {features.get('volume_ratio_20')}. Il funding corrente e' "
        f"{features.get('funding_rate_current')}, quindi il costo di "
        f"mantenimento non annulla il movimento osservato sull'orizzonte "
        f"considerato. Su questa base la decisione e' "
        f"{payload['action']}."
    )


def _asset_from_messages(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        content = message.get("content")
        if isinstance(content, str) and "ASSET:" in content:
            return content.split("ASSET:", 1)[1].split()[0].strip()
        if isinstance(content, list):
            for block in content:
                text = block.get("text") if isinstance(block, dict) else None
                if isinstance(text, str) and "ASSET:" in text:
                    return text.split("ASSET:", 1)[1].split()[0].strip()
    raise LLMError("il MockLLM non trova l'asset nel messaggio")


def _dossier_from_messages(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Cerca a ritroso l'ultimo tool_result contenente un dossier."""
    import json

    for message in reversed(messages):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            payload = block.get("content")
            if isinstance(payload, list):
                payload = "".join(
                    p.get("text", "") for p in payload if isinstance(p, dict)
                )
            if not isinstance(payload, str):
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "features" in parsed:
                return parsed
    return None


def _block_type(block: Any) -> str | None:
    if isinstance(block, dict):
        return block.get("type")
    return getattr(block, "type", None)
