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

from contracts.freeze import FreezeManifest, SamplingPolicy


class LLMError(Exception):
    pass


class BudgetExceeded(LLMError):
    """Superato il tetto di chiamate dichiarato per la giornata."""


class MissingApiKey(LLMError):
    pass


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Risposta normalizzata: blocchi di contenuto nell'ordine ricevuto."""

    content: list[Any]
    stop_reason: str | None
    model: str

    def tool_uses(self) -> list[Any]:
        return [b for b in self.content if _block_type(b) == "tool_use"]


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
    """Client reale. Non viene mai istanziato dalla suite di test."""

    def __init__(
        self,
        manifest: FreezeManifest,
        *,
        budget: CallBudget | None = None,
        max_retries: int = 3,
        base_backoff_seconds: float = 1.0,
        sleep=time.sleep,
        client: Any | None = None,
    ) -> None:
        if manifest.sampling_policy is not SamplingPolicy.API_DEFAULT_OMITTED:
            raise LLMError(
                "questo client implementa solo sampling_policy="
                "api_default_omitted (D4): i parametri di sampling non vengono "
                "inviati affatto"
            )
        self._manifest = manifest
        self.model_version = manifest.model_string
        self._budget = budget or CallBudget(max_calls=200)
        self._max_retries = max_retries
        self._base_backoff = base_backoff_seconds
        self._sleep = sleep
        self._client = client or self._build_client()

    @staticmethod
    def _build_client() -> Any:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise MissingApiKey(
                "ANTHROPIC_API_KEY assente. La chiave si legge solo da ambiente."
            )
        import anthropic  # import locale: la suite non deve dipenderne

        return anthropic.Anthropic()

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
        # NOTA D4: nessun temperature / top_p / top_k. L'omissione E' la
        # policy, non una dimenticanza.
        payload = {
            "model": self._manifest.model_string,
            "max_tokens": self._manifest.max_tokens,
            "system": system,
            "messages": messages,
            "tools": tools,
        }
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.messages.create(**payload)
            except Exception as exc:  # noqa: BLE001 - classificato sotto
                if not _is_retryable(exc) or attempt == self._max_retries:
                    raise LLMError(f"chiamata al modello fallita: {exc}") from exc
                last_error = exc
                self._sleep(self._base_backoff * (2**attempt))
                continue
            return LLMResponse(
                content=list(response.content),
                stop_reason=getattr(response, "stop_reason", None),
                model=getattr(response, "model", self._manifest.model_string),
            )
        raise LLMError(f"chiamata al modello fallita: {last_error}")


def _is_retryable(exc: Exception) -> bool:
    """429 e 5xx sono ritentabili; un 400 è un errore di richiesta, non di rete."""
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if isinstance(status, int):
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
