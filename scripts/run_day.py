"""Esegue una giornata di decisioni sulle 3 repliche.

Di default usa il **MockLLM**: gira senza rete e senza API key. Con `--live`
usa il modello pinnato nel Freeze manifest e consuma budget vero.

    uv run python scripts/run_day.py --snapshot-id <sha256>
    uv run python scripts/run_day.py --snapshot-id <sha256> --live
    uv run python scripts/run_day.py --snapshot-id <sha256> --live
        --manifest manifests/<manifest della stagione>.json

In modalita' `--live` il manifest **si carica**, non si ricostruisce (verbale
RUN2 §A.2). Prima di qualunque chiamata al modello questo script:

1. legge il `FreezeManifest` committato dal percorso indicato da `--manifest`;
2. ne **ricalcola** il `freeze_id` e si ferma se diverge da quello scritto nel
   file;
3. si ferma se `pin_commit` e' assente o e' un segnaposto — il rito del pin non
   e' avvenuto e non esiste una stagione da far girare;
4. si ferma se il manifest non porta ENTRAMBI i termini economici della
   stagione, `season_budget_usd` e `season_expected_days` (D5);
5. legge la **spesa cumulata di stagione** dal ledger e si ferma se supera la
   soglia dura dichiarata in `ledger/spend.py` (D5).

Ognuno dei cinque e' un rifiuto pulito con exit code 2, mai un ripiego.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.config import (
    DEFAULT_MANIFEST_PATH,
    ArenaConfig,
    ManifestError,
    current_git_sha,
    load_pinned_manifest,
)
from arena.llm_client import (
    AnthropicTraderClient,
    CallBudget,
    LLMError,
    MockLLM,
    RETRYABLE_PROCESS_EXIT_CODE,
)
from arena.runner import DailyRunner
from ledger.spend import check_hard_stop, check_season_terms, season_spend
from ledger.telemetry import DailyDispersion
from ledger.trader_ledger import TraderLedger
from toolserver.config import ToolServerConfig, live_api_allowed
from toolserver.store import SnapshotStore
from toolserver.toollog import ToolCallLog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--ledger", default="data/ledger/season0.jsonl")
    parser.add_argument("--live", action="store_true", help="usa l'API reale")
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST_PATH),
        help=(
            "percorso del FreezeManifest COMMITTATO della stagione. Usato solo "
            "con --live: viene caricato, il suo freeze_id ricalcolato, e la "
            "giornata non parte se diverge (verbale RUN2 §A.2)."
        ),
    )
    parser.add_argument(
        "--toolcalls-dir",
        default=None,
        help=(
            "cartella dei log delle tool call da cui leggere la spesa cumulata "
            "di stagione (default: quella della configurazione)."
        ),
    )
    args = parser.parse_args()

    run_id = args.run_id or datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths = ToolServerConfig()
    store = SnapshotStore(paths.snapshot_dir)
    tool_log = ToolCallLog(paths.toolcall_log_dir, run_id=run_id)
    ledger = TraderLedger(args.ledger)

    if args.live:
        if not live_api_allowed():
            print(
                "ERRORE: --live richiede TRADERLAB_ALLOW_LIVE_API=1.",
                file=sys.stderr,
            )
            return 2
        # Verbale RUN2 §A.2 / TL-007. Il manifest si CARICA dal file
        # committato e il suo freeze_id si ricalcola: ricostruirlo a runtime,
        # come faceva questo punto in Stagione 0, incorporava lo sha di git
        # corrente e produceva un freeze_id diverso a ogni giornata, nessuno
        # uguale a quello firmato e timbrato.
        try:
            manifest = load_pinned_manifest(args.manifest)
        except ManifestError as exc:
            print(f"ERRORE: manifest non utilizzabile — {exc}", file=sys.stderr)
            return 2

        # D5, primo passo: il pin porta ENTRAMBI i termini economici?
        # `season_budget_usd` e `season_expected_days` si firmano insieme al
        # rito del pin. Il secondo stava in una costante di `ledger/spend.py`
        # e poteva divergere dal primo in silenzio: adesso e' un campo del
        # manifest e la sua assenza e' un rifiuto, esattamente come per il
        # preventivo.
        termini = check_season_terms(
            manifest.season_budget_usd, manifest.season_expected_days
        )
        if not termini.ok:
            print(
                f"ERRORE: guardia economica di stagione — {termini.detail}",
                file=sys.stderr,
            )
            return 2

        # D5, secondo passo: la spesa cumulata di stagione si legge dal ledger
        # dei verbali (le giornate e i loro run_id) incrociato col log delle
        # tool call (i token). Oltre la soglia dura non si gira: una guardia
        # che avvisa e lascia partire non e' una guardia.
        toolcalls_dir = (
            Path(args.toolcalls_dir) if args.toolcalls_dir else paths.toolcall_log_dir
        )
        spesa = season_spend(trader_ledger=ledger, toolcalls_dir=toolcalls_dir)
        verdetto = check_hard_stop(spesa, manifest.season_budget_usd)
        if not verdetto.ok:
            print(
                f"ERRORE: guardia economica di stagione — {verdetto.detail}",
                file=sys.stderr,
            )
            return 2

        budget = CallBudget(max_calls=ArenaConfig().max_llm_calls_per_day)
        print(f"manifest        : {args.manifest}")
        print(f"modello pinnato : {manifest.model_string}")
        print(f"sampling        : {manifest.sampling_policy.value} (D4)")
        print(f"thinking        : {manifest.thinking_declared.value} (§A.7)")
        print(f"pin_commit      : {manifest.pin_commit}")
        print(f"freeze_id       : {manifest.freeze_id}")
        print(f"termini stagione: {termini.detail}")
        print(f"spesa stagione  : {verdetto.detail}")

        def factory(replica_id: str):
            return AnthropicTraderClient(manifest, budget=budget)
    else:
        print("modello         : MockLLM deterministico (nessuna API)")

        def factory(replica_id: str):
            return MockLLM()

    runner = DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=factory,
        context_git_sha=current_git_sha(),
    )
    try:
        result = runner.run_day(args.snapshot_id, run_id=run_id)
    except LLMError as exc:
        # Un rifiuto resta un rifiuto e un 400 resta un 400: qui distinguiamo
        # solo se vale la pena che il rito ritenti l'intero passo (pazienza
        # lunga) da un fallimento definitivo. Nessun fallback di modello, mai
        # (CLAUDE.md §10): questo blocco classifica, non nasconde, l'errore.
        print(f"ERRORE: chiamata al modello fallita — {exc}", file=sys.stderr)
        print(
            f"tentativi       : {exc.attempts}  errori: {list(exc.attempt_errors)}  "
            f"durata: {exc.duration_seconds:.1f}s",
            file=sys.stderr,
        )
        if exc.retryable:
            print(
                "classificazione: errore transitorio (rete/capacita'), "
                "ritentabile a livello di rito",
                file=sys.stderr,
            )
            return RETRYABLE_PROCESS_EXIT_CODE
        print("classificazione: errore non ritentabile", file=sys.stderr)
        return 1

    print(f"\nrun_id          : {result.run_id}")
    print(f"asof_utc        : {result.asof_utc.isoformat()}")
    print(f"decisioni       : {len(result.decisions)}")
    # Verbale RUN2 §A.5: tre conteggi, tre righe. Il rifiuto del modello e la
    # risposta troncata non sono verbali malformati e non stanno nello stesso
    # numero: sommarli rendeva illeggibili tutte e tre le grandezze.
    print(f"malformati veri : {result.malformed_count}")
    print(f"rifiuti modello : {result.refusal_count}")
    print(f"troncati        : {result.truncated_count}")
    if result.dispersion is not None:
        d = result.dispersion
        # §A.4: `n/d` quando la dispersione non e' definita, mai `0.0000` —
        # che a valle sarebbe indistinguibile da un accordo perfetto.
        print(
            f"dispersione     : azioni "
            f"{DailyDispersion.format_value(d.action_disagreement)}, "
            f"confidence "
            f"{DailyDispersion.format_value(d.confidence_dispersion)}"
            + ("" if d.is_defined else "   (intersezione vuota o < 2 repliche)")
        )
    print(f"catena ledger   : {'ok' if ledger.verify().ok else 'ROTTA'}")
    print(f"tool call log   : {tool_log.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
