"""Verifica il pin contro l'endpoint, il giorno del pin (TL-002).

Fa tre cose e le dichiara tutte:

1. **Model string**: `models.retrieve` sulla string del manifest. Se l'ID non
   esiste l'endpoint risponde 404 e il pin non si fa.
2. **D4 ri-verificata su Fable**: manda una chiamata minima *senza* parametri
   di sampling (deve passare) e una *con* `temperature` (deve fallire con 400).
   È la prova operativa che il default si ottiene per omissione.
3. **Thinking — impronta della superficie API**, non più un invariante.
   Fino al 20/08/2026 questa sonda pretendeva che `thinking={"type":
   "disabled"}` fosse **rifiutato**, cioè che su questo modello il
   ragionamento non fosse disattivabile. Era un'aspettativa scritta per
   `claude-fable-5` e trattata come universale: su `claude-opus-5` quella
   chiamata risponde **200**, e il rito del pin del 20/08 si fermò su un rosso
   che non era un difetto del modello ma dell'aspettativa.

   Dalla firma **F11** la sonda non pretende più un esito: **confronta** le
   risposte con l'impronta misurata il 20/08/2026 (`THINKING_BASELINE`). Le
   tre forme e i loro esiti sono la fotografia di come il modello era servito
   quel giorno. Uno **scarto** da quella fotografia non è un pin da non fare
   per ragioni di merito: è un **cambio di serving**, ed è esito rosso perché
   il pin descriverebbe un modello che non è più quello.

Consuma budget reale: cinque chiamate minime, due delle quali rifiutate con
400 e quindi non fatturate.

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

#: Data in cui l'impronta della superficie API qui sotto è stata misurata. Non
#: è la data del pin: è la data della **fotografia** con cui ogni esecuzione
#: futura si confronta.
THINKING_BASELINE_DATE = "2026-08-20"

#: Le tre forme del parametro `thinking` e l'esito misurato su
#: `claude-opus-5` alla data qui sopra. `True` = la chiamata passa (200),
#: `False` = la chiamata è rifiutata (400).
#:
#: Le tre righe vengono da due riti dello stesso giorno:
#:
#: - parametro **omesso** → 200 (sonda del rito T2, evidenza §7, e probe 2 di
#:   questo script). È la forma pinnata;
#: - `enabled` + `budget_tokens` → 400, «`thinking.type.enabled` is not
#:   supported for this model» (sonda T2 con budget 400, 1024 e 16000);
#: - `disabled` → **200, accettato** (rito del pin del 20/08, riprodotto due
#:   volte). È il reperto che ha fatto nascere F11.
#:
#: La documentazione ufficiale concorda, letta il 2026-08-20: la tabella
#: «Configurations each model rejects» di
#: https://platform.claude.com/docs/en/build-with-claude/thinking-troubleshooting
#: dà per «Claude Opus 5» modalità «Adaptive only», default «On», e rifiuta
#: `"enabled"` e `"disabled"`, con la nota 2 «Claude Opus 5 accepts
#: "disabled" at effort high or below» — e `high` è il default dell'API.
THINKING_BASELINE: tuple[tuple[str, dict[str, object] | None, bool], ...] = (
    ("thinking assente (la forma pinnata)", None, True),
    ("thinking.type='enabled', budget 1024", {"type": "enabled", "budget_tokens": 1024}, False),
    ("thinking.type='disabled'", {"type": "disabled"}, True),
)


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

    # 3. Thinking: l'impronta della superficie API, non un invariante (F11).
    print(
        f"\n== 3. Thinking — impronta della superficie API "
        f"(baseline {THINKING_BASELINE_DATE}) =="
    )
    for etichetta, thinking, atteso_passa in THINKING_BASELINE:
        extra = {} if thinking is None else {"thinking": dict(thinking)}
        try:
            client.messages.create(**base, **extra)
            passa, dettaglio = True, "200"
        except Exception as exc:  # noqa: BLE001
            passa, dettaglio = False, str(exc)[:110]
        coincide = passa is atteso_passa
        atteso = "200" if atteso_passa else "400"
        _line(
            coincide,
            f"{etichetta}: {'200' if passa else '400'}",
            dettaglio
            if coincide
            else (
                f"SCARTO dalla baseline {THINKING_BASELINE_DATE} (atteso "
                f"{atteso}): il modello non e' piu' servito come quando "
                f"il pin e' stato firmato — {dettaglio}"
            ),
        )
        if not coincide:
            ok = False

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
        "\nPROMEMORIA (annotato il 2026-08-20, F11): il vincolo di 30 "
        "giorni di data retention era scritto per claude-fable-5, che "
        "sotto zero-data-retention non e' disponibile. Per claude-opus-5 "
        "la documentazione ufficiale NON pone lo stesso vincolo. La riga "
        "resta come promemoria di verificare la configurazione "
        "dell'organizzazione prima del pin: e' lo smoke live a "
        "dimostrarlo di fatto, non questo script."
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
