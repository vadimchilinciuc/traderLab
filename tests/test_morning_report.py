"""scripts/morning_report.py — rapporto del mattino, su ledger finti.

Zero rete, zero API: solo lettura di ledger e log delle tool call costruiti
in `tmp_path`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from contracts.decision import Action
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict
from ledger.eprocess import KillCriterionConfig
from ledger.ops_ledger import OpsEvent, OpsKey, OpsLedger
from ledger.spend import Pricing
from ledger.trader_ledger import LedgerKey, TraderLedger
from scripts.morning_report import (
    classify_outcome,
    day_token_totals,
    estimate_cost_usd,
    generate_report,
    last_touched_day,
    pricing_from_manifest,
    run_ids_for_day,
)
from tests.factories import (
    LISTINO_OPUS5,
    PREZZI_OPUS5,
    make_decision,
    manifest_con_prezzi,
)

OGGI = date(2026, 8, 14)
ASOF = datetime(2026, 8, 14, 0, 0, tzinfo=timezone.utc)
SNAPSHOT_ID = "a" * 64


def _verdetto(
    outcome: RiskOutcome = RiskOutcome.APPROVED,
    rule: RiskRule = RiskRule.NONE,
    action: Action = Action.LONG,
    size: float = 0.05,
) -> RiskVerdict:
    return RiskVerdict(
        outcome=outcome,
        rule=rule,
        action_in=action,
        action_out=Action.FLAT if outcome is RiskOutcome.REJECTED else action,
        size_fraction_in=size,
        size_fraction_out=0.0 if outcome is RiskOutcome.REJECTED else size,
    )


@pytest.fixture
def percorsi(tmp_path):
    return {
        "ledger": tmp_path / "ledger" / "season0.jsonl",
        "ops": tmp_path / "ledger" / "ops.jsonl",
        "toolcalls": tmp_path / "toolcalls",
    }


def _scrivi_manifest_su_disco(path: Path, *, prezzi: Mapping[str, float]) -> Path:
    """Un Freeze manifest committabile, col listino che gli si passa.

    Non e' pinnato di proposito: `pricing_from_manifest` legge il listino, non
    l'autorizzazione a far girare una giornata, e quella la pretende il runner.
    """
    manifest = manifest_con_prezzi(datetime.now(tz=timezone.utc), prezzi=prezzi)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "freeze_manifest": manifest.canonical_payload(),
                "freeze_id": manifest.freeze_id,
                "rito_config": {"nota": "documento sintetico per i test"},
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _scrivi_decisione(
    ledger: TraderLedger,
    *,
    day: date = OGGI,
    replica_id: str,
    asset: str = "BTC",
    action: Action = Action.LONG,
    confidence: float = 0.6,
    run_id: str = "run-1",
) -> None:
    ledger.append(
        key=LedgerKey.of(day, replica_id, asset),
        verdict=_verdetto(action=action),
        decision=make_decision(
            SNAPSHOT_ID,
            asset=asset,
            action=action,
            confidence=confidence,
            replica_id=replica_id,
            timestamp=ASOF,
        ),
        snapshot_id=SNAPSHOT_ID,
        run_id=run_id,
    )


def _scrivi_malformato(
    ledger: TraderLedger, *, day: date = OGGI, replica_id: str, run_id: str = "run-1"
) -> None:
    ledger.append(
        key=LedgerKey.of(day, replica_id, "BTC"),
        verdict=_verdetto(outcome=RiskOutcome.REJECTED, rule=RiskRule.MALFORMED_VERBALE),
        decision=None,
        malformed_reason="no_rationale_before_structured_block",
        snapshot_id=SNAPSHOT_ID,
        run_id=run_id,
    )


def _scrivi_toolcall_log(
    toolcalls_dir,
    run_id: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read: int,
    cache_creation: int,
    n_calls: int = 1,
) -> None:
    toolcalls_dir.mkdir(parents=True, exist_ok=True)
    path = toolcalls_dir / f"{run_id}.jsonl"
    lines = []
    for _ in range(n_calls):
        lines.append(
            json.dumps(
                {
                    "ts_utc": ASOF.isoformat(),
                    "run_id": run_id,
                    "replica_id": "r1",
                    "snapshot_id": SNAPSHOT_ID,
                    "tool": "llm_complete",
                    "args": {"asset": "BTC"},
                    "ok": True,
                    "response_sha256": "x",
                    "error": None,
                    "meta": {
                        "attempts": 1,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cache_read_input_tokens": cache_read,
                        "cache_creation_input_tokens": cache_creation,
                    },
                }
            )
        )
        # Una chiamata a tool diverso da llm_complete: non deve contare.
        lines.append(
            json.dumps(
                {
                    "ts_utc": ASOF.isoformat(),
                    "run_id": run_id,
                    "replica_id": "r1",
                    "snapshot_id": SNAPSHOT_ID,
                    "tool": "get_asset_dossier",
                    "args": {"symbol": "BTC"},
                    "ok": True,
                    "response_sha256": "y",
                    "error": None,
                    "meta": {},
                }
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Caso "nessuna giornata ancora"
# --------------------------------------------------------------------------


def test_nessuna_giornata_ancora(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])

    assert last_touched_day(ledger, ops) is None

    report = generate_report(
        trader_ledger=ledger,
        ops_ledger=ops,
        toolcalls_dir=percorsi["toolcalls"],
        pricing=LISTINO_OPUS5,
    )
    assert "nessuna giornata ancora" in report
    assert "esito                 : nessuna" in report
    assert "token (input/output/cache_read/cache_creation): 0/0/0/0" in report
    assert "costo stimato USD     : $0.0000" in report
    assert "catena ledger (verify): ok" in report
    assert "giornate registrate   : 0/20" in report


# --------------------------------------------------------------------------
# Classificazione dell'esito
# --------------------------------------------------------------------------


def test_esito_completata(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    for r in ("r1", "r2", "r3"):
        _scrivi_decisione(ledger, replica_id=r)
    ops.append(key=OpsKey.of(OGGI, OpsEvent.DAY_COMPLETED), detail=f"snapshot {SNAPSHOT_ID}")

    assert last_touched_day(ledger, ops) == OGGI
    assert classify_outcome(OGGI, ledger, ops) == "completata"


def test_esito_completata_senza_evento_operativo(percorsi):
    """Verbali presenti ma nessun evento ops corrispondente: contano comunque."""
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    _scrivi_decisione(ledger, replica_id="r1")

    assert classify_outcome(OGGI, ledger, ops) == "completata"


def test_esito_skipped_day(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    ops.record_skipped_day(OGGI, detail="nessuna decisione registrata per questo giorno")

    assert last_touched_day(ledger, ops) == OGGI
    assert classify_outcome(OGGI, ledger, ops) == "skipped_day"


def test_esito_failed_decisions(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    ops.append(
        key=OpsKey.of(OGGI, OpsEvent.FAILED_DECISIONS),
        detail="il rito e' partito e l'API non ha risposto",
    )

    assert classify_outcome(OGGI, ledger, ops) == "failed_decisions"


def test_esito_failed_decisions_da_run_failed(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    ops.append(key=OpsKey.of(OGGI, OpsEvent.RUN_FAILED), detail="snapshot fallito")

    assert classify_outcome(OGGI, ledger, ops) == "failed_decisions"


def test_ultima_giornata_e_la_piu_recente_tra_i_due_ledger(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    ieri = OGGI - timedelta(days=1)
    _scrivi_decisione(ledger, day=ieri, replica_id="r1")
    ops.record_skipped_day(OGGI)

    assert last_touched_day(ledger, ops) == OGGI


# --------------------------------------------------------------------------
# Decisioni delle repliche e accordo
# --------------------------------------------------------------------------


def test_accordo_totale_tre_su_tre(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    for r in ("r1", "r2", "r3"):
        _scrivi_decisione(ledger, replica_id=r, action=Action.LONG, confidence=0.6)

    report = generate_report(
        trader_ledger=ledger, ops_ledger=ops, toolcalls_dir=percorsi["toolcalls"]
    )
    assert "accordo 3/3" in report
    assert "r1=long " in report
    assert "conf=0.60" in report


def test_disaccordo_due_su_tre(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    _scrivi_decisione(ledger, replica_id="r1", action=Action.LONG)
    _scrivi_decisione(ledger, replica_id="r2", action=Action.LONG)
    _scrivi_decisione(ledger, replica_id="r3", action=Action.SHORT)

    report = generate_report(
        trader_ledger=ledger, ops_ledger=ops, toolcalls_dir=percorsi["toolcalls"]
    )
    assert "accordo 2/3" in report


def test_verbale_malformato_mostra_il_motivo_non_la_confidence(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    _scrivi_decisione(ledger, replica_id="r1")
    _scrivi_decisione(ledger, replica_id="r2")
    _scrivi_malformato(ledger, replica_id="r3")

    report = generate_report(
        trader_ledger=ledger, ops_ledger=ops, toolcalls_dir=percorsi["toolcalls"]
    )
    assert "no_rationale_before_structured_block" in report


def test_piu_asset_una_riga_ciascuno(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    for asset in ("BTC", "ETH"):
        for r in ("r1", "r2", "r3"):
            _scrivi_decisione(ledger, replica_id=r, asset=asset)

    report = generate_report(
        trader_ledger=ledger, ops_ledger=ops, toolcalls_dir=percorsi["toolcalls"]
    )
    assert report.count("accordo 3/3") == 2
    assert "BTC" in report and "ETH" in report


# --------------------------------------------------------------------------
# Token e costo stimato
# --------------------------------------------------------------------------


def test_run_ids_per_giornata_sono_quelli_del_ledger(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    _scrivi_decisione(ledger, replica_id="r1", run_id="run-abc")
    entries = ledger.read_all()
    assert run_ids_for_day(entries) == ["run-abc"]


def test_somma_token_dal_log_delle_tool_call(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    for r in ("r1", "r2", "r3"):
        _scrivi_decisione(ledger, replica_id=r, run_id="run-xyz")
    _scrivi_toolcall_log(
        percorsi["toolcalls"],
        "run-xyz",
        input_tokens=1000,
        output_tokens=200,
        cache_read=500,
        cache_creation=100,
        n_calls=2,
    )

    totals = day_token_totals(["run-xyz"], percorsi["toolcalls"])
    assert totals == (2000, 400, 1000, 200)

    report = generate_report(
        trader_ledger=ledger, ops_ledger=ops, toolcalls_dir=percorsi["toolcalls"]
    )
    assert "token (input/output/cache_read/cache_creation): 2000/400/1000/200" in report


def test_costo_stimato_usa_il_listino_del_pin(percorsi):
    """Il costo si calcola col listino firmato, non con una costante di modulo.

    1M di token per ciascuna delle quattro voci, al listino di `claude-opus-5`
    del §4 dell'evidenza del preventivo: $5 input + $25 output + $0.50 lettura
    da cache + $6.25 scrittura a 5 minuti = **$36.75**.

    Al listino di Fable che stava in `ledger/spend.py` — e che restava lì anche
    dopo il cambio di modello — gli stessi token davano $73.50: **il doppio**.
    Con un preventivo di stagione di $89,90 la soglia dura si sarebbe toccata
    al giorno 21 invece che al 42.
    """
    costo = estimate_cost_usd(
        1_000_000, 1_000_000, 1_000_000, 1_000_000, pricing=LISTINO_OPUS5
    )
    assert costo == pytest.approx(5.00 + 25.00 + 0.50 + 6.25)
    assert costo == pytest.approx(36.75)

    # Il lato opposto, e la ragione del rito: lo stesso conto al listino di
    # Fable vale esattamente il doppio.
    fable = Pricing(
        input_usd_per_mtok=10.00,
        output_usd_per_mtok=50.00,
        cache_write_usd_per_mtok=12.50,
        cache_read_usd_per_mtok=1.00,
    )
    assert estimate_cost_usd(
        1_000_000, 1_000_000, 1_000_000, 1_000_000, pricing=fable
    ) == pytest.approx(2 * costo)


def test_senza_listino_il_costo_e_dichiarato_non_calcolabile(percorsi):
    """Nessuna tariffa inventata per riempire la riga.

    Prima del rito del pin il manifest non porta il listino. Stampare un costo
    lo stesso richiederebbe una tariffa presa da qualche parte, e "qualche
    parte" è stata per due settimane il listino di un modello diverso da quello
    pinnato. I token restano stampati: è da quelli che si ricava il costo il
    giorno in cui il listino c'è.
    """
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])

    report = generate_report(
        trader_ledger=ledger, ops_ledger=ops, toolcalls_dir=percorsi["toolcalls"]
    )
    assert "costo stimato USD     : non calcolabile" in report
    assert "listino assente dal Freeze manifest" in report
    assert "token (input/output/cache_read/cache_creation): 0/0/0/0" in report

    # Lato opposto: col listino la riga porta una cifra.
    con_listino = generate_report(
        trader_ledger=ledger,
        ops_ledger=ops,
        toolcalls_dir=percorsi["toolcalls"],
        pricing=LISTINO_OPUS5,
    )
    assert "costo stimato USD     : $0.0000" in con_listino


def test_il_listino_del_rapporto_viene_dal_manifest_su_disco(tmp_path):
    """`pricing_from_manifest`: i tre casi, e nessuno di essi solleva.

    Il rapporto del mattino è di sola lettura e non deve fallire perché il pin
    non c'è ancora — è la condizione normale del cantiere.
    """
    # 1. File assente.
    assert pricing_from_manifest(tmp_path / "non_esiste.json") is None

    # 2. Manifest valido ma senza listino (composizione di prova).
    senza = _scrivi_manifest_su_disco(tmp_path / "senza.json", prezzi={})
    assert pricing_from_manifest(senza) is None

    # 3. Manifest col listino firmato: le quattro tariffe arrivano intatte.
    con = _scrivi_manifest_su_disco(tmp_path / "con.json", prezzi=PREZZI_OPUS5)
    listino = pricing_from_manifest(con)
    assert listino == LISTINO_OPUS5


def test_campo_di_telemetria_assente_conta_zero(percorsi):
    toolcalls_dir = percorsi["toolcalls"]
    toolcalls_dir.mkdir(parents=True)
    path = toolcalls_dir / "run-parziale.jsonl"
    path.write_text(
        json.dumps(
            {
                "ts_utc": ASOF.isoformat(),
                "run_id": "run-parziale",
                "replica_id": "r1",
                "snapshot_id": SNAPSHOT_ID,
                "tool": "llm_complete",
                "args": {},
                "ok": True,
                "response_sha256": "x",
                "error": None,
                "meta": {"input_tokens": 42, "output_tokens": None},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    totals = day_token_totals(["run-parziale"], toolcalls_dir)
    assert totals == (42, 0, 0, 0)


# --------------------------------------------------------------------------
# Integrità della catena
# --------------------------------------------------------------------------


def test_catena_rotta_e_segnalata(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    _scrivi_decisione(ledger, replica_id="r1")

    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["verdict"]["size_fraction_out"] = 0.99
    lines[0] = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = generate_report(
        trader_ledger=TraderLedger(ledger.path),
        ops_ledger=ops,
        toolcalls_dir=percorsi["toolcalls"],
    )
    assert "ROTTA" in report


# --------------------------------------------------------------------------
# Conteggio giornate sulla finestra del kill-criterion
# --------------------------------------------------------------------------


def test_conteggio_giornate_su_20(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    for offset in range(3):
        _scrivi_decisione(ledger, day=OGGI - timedelta(days=offset), replica_id="r1")

    report = generate_report(
        trader_ledger=ledger, ops_ledger=ops, toolcalls_dir=percorsi["toolcalls"]
    )
    assert "giornate registrate   : 3/20" in report


def test_finestra_configurabile(percorsi):
    ledger = TraderLedger(percorsi["ledger"])
    ops = OpsLedger(percorsi["ops"])
    _scrivi_decisione(ledger, replica_id="r1")

    report = generate_report(
        trader_ledger=ledger,
        ops_ledger=ops,
        toolcalls_dir=percorsi["toolcalls"],
        kill_window=KillCriterionConfig(window=10).window,
    )
    assert "giornate registrate   : 1/10" in report
