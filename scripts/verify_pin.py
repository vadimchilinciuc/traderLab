"""Verifica il pin contro l'endpoint, il giorno del pin (TL-002).

Fa tre cose e le dichiara tutte:

1. **Model string**: `models.retrieve` sulla string del manifest. Se l'ID non
   esiste l'endpoint risponde 404 e il pin non si fa.
2. **D4 ri-verificata su Fable**: manda una chiamata minima *senza* parametri
   di sampling (deve passare) e una *con* `temperature` (deve fallire con 400).
   È la prova operativa che il default si ottiene per omissione.
3. **Thinking**: verifica che `thinking={"type": "disabled"}` sia rifiutato,
   cioè che su questo modello il ragionamento non sia disattivabile.

Consuma budget reale: due o tre chiamate minime.

    TRADERLAB_ALLOW_LIVE_API=1 uv run python scripts/verify_pin.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.config import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL_STRING,
    build_freeze_manifest,
    current_git_sha,
)
from toolserver.config import live_api_allowed

PROBE = [{"role": "user", "content": "Rispondi con la sola parola: ok"}]


def _line(ok: bool, label: str, detail: str = "") -> None:
    mark = "OK  " if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL_STRING)
    parser.add_argument(
        "--skip-probes",
        action="store_true",
        help="solo lookup della model string, nessuna chiamata di inferenza",
    )
    args = parser.parse_args()

    if not live_api_allowed():
        print(
            "ERRORE: verifica del pin richiede TRADERLAB_ALLOW_LIVE_API=1.",
            file=sys.stderr,
        )
        return 2

    import anthropic

    client = anthropic.Anthropic()
    ok = True

    # 1. La model string esiste?
    print(f"\n== 1. Model string: {args.model} ==")
    try:
        info = client.models.retrieve(args.model)
        _line(True, "esiste sull'endpoint", getattr(info, "display_name", ""))
        for field in ("max_input_tokens", "max_tokens"):
            value = getattr(info, field, None)
            if value is not None:
                print(f"       {field}: {value}")
    except Exception as exc:  # noqa: BLE001
        _line(False, "model string non risolta", str(exc)[:200])
        return 1

    # Esiste una variante datata? Se sì, D2 chiederebbe quella.
    try:
        page = client.models.list()
        dated = [
            m.id
            for m in getattr(page, "data", [])
            if m.id.startswith(args.model) and m.id != args.model
        ]
        _line(
            not dated,
            "nessuna variante datata piu' specifica",
            f"trovate: {dated}" if dated else "la string e' gia' la piu' specifica",
        )
        if dated:
            ok = False
    except Exception as exc:  # noqa: BLE001
        _line(False, "elenco modelli non disponibile", str(exc)[:200])

    if args.skip_probes:
        print("\n(probe di inferenza saltate)")
        return 0 if ok else 1

    base = {"model": args.model, "max_tokens": 64, "messages": PROBE}

    # 2. D4: senza parametri di sampling deve passare.
    print("\n== 2. D4 — sampling per omissione ==")
    try:
        client.messages.create(**base)
        _line(True, "chiamata SENZA parametri di sampling accettata")
    except Exception as exc:  # noqa: BLE001
        _line(False, "chiamata senza sampling rifiutata", str(exc)[:200])
        ok = False

    # ...e con temperature deve fallire. Se passasse, la constatazione D4
    # andrebbe riscritta: significherebbe che il modello accetta override.
    try:
        client.messages.create(**base, temperature=0.7)
        _line(
            False,
            "temperature ACCETTATA",
            "la constatazione D4 va rivista: questo modello accetta override",
        )
        ok = False
    except Exception as exc:  # noqa: BLE001
        _line(True, "temperature rifiutata come atteso", str(exc)[:120])

    # 3. Thinking non disattivabile.
    print("\n== 3. Thinking sempre attivo ==")
    try:
        client.messages.create(**base, thinking={"type": "disabled"})
        _line(
            False,
            "thinking 'disabled' ACCETTATO",
            "rivedere la nota su thinking_policy in arena/config.py",
        )
        ok = False
    except Exception as exc:  # noqa: BLE001
        _line(True, "thinking 'disabled' rifiutato come atteso", str(exc)[:120])

    # 4. Il manifest che verrebbe congelato.
    manifest = build_freeze_manifest(
        datetime.now(tz=timezone.utc),
        model_string=args.model,
        max_tokens=DEFAULT_MAX_TOKENS,
        context_git_sha=current_git_sha(),
    )
    print("\n== 4. Manifest candidato ==")
    print(f"       model_string     : {manifest.model_string}")
    print(f"       sampling_policy  : {manifest.sampling_policy.value}")
    print(f"       thinking_policy  : {manifest.thinking_policy.value}")
    print(f"       max_tokens       : {manifest.max_tokens}")
    print(f"       prompt_sha       : {manifest.system_prompt_sha[:16]}...")
    print(f"       tool_schemas_sha : {manifest.tool_schemas_sha[:16]}...")
    print(f"       context_git_sha  : {manifest.context_git_sha}")
    print(f"       freeze_id        : {manifest.freeze_id}")
    print(f"       ots_pending      : {manifest.ots_pending}")

    print(
        "\nPROMEMORIA: claude-fable-5 richiede 30 giorni di data retention. "
        "Con l'organizzazione in zero-data-retention OGNI chiamata risponde "
        "400, indipendentemente dal payload. Verificare la configurazione "
        "dell'organizzazione prima del pin."
    )
    print(
        "PROMEMORIA: il fallback server-side NON e' attivo di proposito. "
        "Servirebbe un rifiuto con un altro modello, e D2 dice che un cambio "
        "di modello apre un nuovo track record."
    )

    print("\nESITO:", "pin verificabile" if ok else "PIN DA NON EFFETTUARE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
