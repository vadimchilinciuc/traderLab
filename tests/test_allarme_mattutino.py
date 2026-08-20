"""Canale d'allarme del controllo mattutino — verbale RUN2 §A.6, decisione D3.

Il controllo del mattino scrive `ALLARME_<data>.txt` alla radice del repo su
exit ≠ 0 o su anomalia rilevata, con dentro il motivo. Qui si prova che il file
compare quando deve e **non** compare quando non deve: un allarme che c'è
sempre non è un allarme, e uno che non si è mai visto scattare non si distingue
da uno che non scatta.

Come per `tests/test_morning_check.py`: nessuno scheduler, nessuna rete,
nessuna API. Il wrapper PowerShell e la registrazione del task restano fuori —
li fa l'owner a mano (`docs/OPERATIONS.md`).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from arena.config import build_freeze_manifest
from contracts.decision import Action
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict
from ledger.trader_ledger import LedgerKey, TraderLedger
from scripts.morning_check import alarm_path_for, run_morning_check
from scripts.preflight import CheckResult, PreflightResult
from tests.factories import make_decision
from toolserver.toollog import LLM_COMPLETE_TOOL

OGGI = date(2026, 8, 20)
PIN = "1a2b3c4"
SNAPSHOT_ID = "a" * 64


# --------------------------------------------------------------------------
# Impalcatura
# --------------------------------------------------------------------------


def _verdetto_ok() -> RiskVerdict:
    return RiskVerdict(
        outcome=RiskOutcome.APPROVED,
        rule=RiskRule.NONE,
        action_in=Action.LONG,
        action_out=Action.LONG,
        size_fraction_in=0.05,
        size_fraction_out=0.05,
    )


def _preflight_pronto(**kwargs) -> PreflightResult:
    return PreflightResult(
        checks=(CheckResult("(a) finto", True, "pronto nei test"),), ready=True
    )


def _preflight_bloccato(**kwargs) -> PreflightResult:
    return PreflightResult(
        checks=(CheckResult("(a) finto", False, "manca la chiave"),),
        ready=False,
        blocking_detail="manca la chiave",
    )


def _scrivi_manifest(path: Path, *, season_budget_usd: float | None) -> Path:
    manifest = build_freeze_manifest(
        datetime.now(tz=timezone.utc),
        pin_commit=PIN,
        season_budget_usd=season_budget_usd,
    )
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


def _giornata_nel_ledger(path: Path, giorno: date, run_id: str) -> TraderLedger:
    ledger = TraderLedger(path)
    asof = datetime(giorno.year, giorno.month, giorno.day, 0, 0, tzinfo=timezone.utc)
    for replica in ("r1", "r2", "r3"):
        ledger.append(
            key=LedgerKey.of(giorno, replica, "BTC"),
            verdict=_verdetto_ok(),
            decision=make_decision(SNAPSHOT_ID, replica_id=replica, timestamp=asof),
            snapshot_id=SNAPSHOT_ID,
            run_id=run_id,
        )
    return ledger


def _controllo(tmp_path: Path, **kwargs):
    """Controllo del mattino con ogni sottoprocesso finto."""
    parametri = {
        "repo_root": tmp_path / "repo",
        "today": OGGI,
        "ledger_path": tmp_path / "ledger" / "season0.jsonl",
        "ops_path": tmp_path / "ledger" / "ops.jsonl",
        "log_dir": tmp_path / "logs",
        "toolcalls_dir": tmp_path / "toolcalls",
        "python_executable": "python",
        "is_monday": False,
        "runner": lambda command, env: None,
        "alert": lambda message: True,
        "preflight": _preflight_pronto,
        "env": {},
        "echo": False,
        # Percorso inesistente: il passo del budget si salta con il motivo
        # scritto nel log, e non e' quello che il test in questione prova.
        "manifest_path": tmp_path / "manifest_inesistente.json",
    }
    parametri.update(kwargs)
    return run_morning_check(**parametri)


# --------------------------------------------------------------------------
# Prova forzata del canale
# --------------------------------------------------------------------------


def test_force_alarm_crea_il_file_e_il_modo_normale_non_lo_crea(tmp_path):
    """A.6/D3, i due lati.

    In modo-allarme forzato il file compare, con dentro il motivo. In modo
    normale — giornata di stanotte a posto, preflight pronto — non compare
    affatto.
    """
    _giornata_nel_ledger(tmp_path / "ledger" / "season0.jsonl", OGGI, "run-x")
    atteso = alarm_path_for(OGGI, tmp_path / "repo")

    normale = _controllo(tmp_path)
    assert normale.exit_code == 0
    assert normale.alarm_file is None
    assert not normale.alarm_raised
    assert not atteso.exists()

    forzato = _controllo(tmp_path, force_alarm=True)
    assert forzato.alarm_raised
    assert forzato.alarm_file == atteso
    assert atteso.exists()
    testo = atteso.read_text(encoding="utf-8")
    assert "prova forzata" in testo
    assert "2026-08-20" in testo


# --------------------------------------------------------------------------
# Exit code
# --------------------------------------------------------------------------


def test_allarme_su_giornata_mancante_e_silenzio_su_giornata_presente(tmp_path):
    """A.6/D3: exit != 0 scrive l'allarme col motivo dentro; exit 0 no."""
    atteso = alarm_path_for(OGGI, tmp_path / "repo")

    # Ledger vuoto: la giornata di stanotte manca. Exit 1, allarme scritto.
    mancante = _controllo(tmp_path)
    assert mancante.exit_code == 1
    assert mancante.alarm_raised
    assert "exit 1" in atteso.read_text(encoding="utf-8")

    atteso.unlink()

    _giornata_nel_ledger(tmp_path / "ledger" / "season0.jsonl", OGGI, "run-x")
    presente = _controllo(tmp_path)
    assert presente.exit_code == 0
    assert not presente.alarm_raised
    assert not atteso.exists()


def test_allarme_su_preflight_bloccato_e_silenzio_su_preflight_pronto(tmp_path):
    """A.6/D3: il preflight NO è un motivo d'allarme e **non** tocca l'exit code.

    Sono due notti diverse: l'exit code racconta quella passata, il preflight
    quella che deve ancora venire. Il canale d'allarme le segnala entrambe.
    """
    _giornata_nel_ledger(tmp_path / "ledger" / "season0.jsonl", OGGI, "run-x")
    atteso = alarm_path_for(OGGI, tmp_path / "repo")

    bloccato = _controllo(tmp_path, preflight=_preflight_bloccato)
    assert bloccato.exit_code == 0
    assert bloccato.preflight_ready is False
    assert bloccato.alarm_raised
    assert "preflight NO" in atteso.read_text(encoding="utf-8")

    atteso.unlink()
    pronto = _controllo(tmp_path, preflight=_preflight_pronto)
    assert pronto.preflight_ready is True
    assert not pronto.alarm_raised
    assert not atteso.exists()


# --------------------------------------------------------------------------
# Ritmo di spesa (D5)
# --------------------------------------------------------------------------


def _giornata_costosa(tmp_path: Path, output_tokens: int) -> None:
    """Una giornata nel ledger e il suo log delle tool call, con i token dentro."""
    _giornata_nel_ledger(tmp_path / "ledger" / "season0.jsonl", OGGI, "run-caro")
    toolcalls = tmp_path / "toolcalls"
    toolcalls.mkdir(parents=True, exist_ok=True)
    (toolcalls / "run-caro.jsonl").write_text(
        json.dumps(
            {
                "tool": LLM_COMPLETE_TOOL,
                "meta": {"input_tokens": 0, "output_tokens": output_tokens},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_allarme_sul_ritmo_di_spesa_e_silenzio_sotto_soglia(tmp_path):
    """D5 dentro il controllo del mattino, i due lati.

    Una giornata da 1.000.000 token di output costa $50 al listino dichiarato.
    Con un preventivo di stagione da $42 su 42 giornate il pro-rata di una
    giornata è $1 e la soglia d'allarme $1,25: $50 la sfonda. Con un preventivo
    da $42.000 la soglia è $1.250 e $50 ci sta sotto.
    """
    _giornata_costosa(tmp_path, output_tokens=1_000_000)
    atteso = alarm_path_for(OGGI, tmp_path / "repo")

    stretto = _scrivi_manifest(tmp_path / "stretto.json", season_budget_usd=42.0)
    sopra = _controllo(tmp_path, manifest_path=stretto)
    assert sopra.budget_ok is False
    assert sopra.alarm_raised
    assert "ritmo di spesa" in atteso.read_text(encoding="utf-8")

    atteso.unlink()

    largo = _scrivi_manifest(tmp_path / "largo.json", season_budget_usd=42_000.0)
    sotto = _controllo(tmp_path, manifest_path=largo)
    assert sotto.budget_ok is True
    assert not sotto.alarm_raised
    assert not atteso.exists()


def test_senza_preventivo_il_passo_si_salta_invece_di_allarmare(tmp_path):
    """D5: prima del rito del pin il preventivo non c'è, ed è la normalità.

    Trasformarlo in un allarme quotidiano insegnerebbe all'owner a ignorare il
    file — il modo più efficace di disattivare un allarme senza spegnerlo. Il
    lato opposto: col preventivo presente la domanda si pone e la risposta
    arriva.
    """
    _giornata_costosa(tmp_path, output_tokens=1_000)

    senza = _scrivi_manifest(tmp_path / "senza_budget.json", season_budget_usd=None)
    esito_senza = _controllo(tmp_path, manifest_path=senza)
    assert esito_senza.budget_ok is None
    assert not esito_senza.alarm_raised

    con = _scrivi_manifest(tmp_path / "con_budget.json", season_budget_usd=1_000.0)
    esito_con = _controllo(tmp_path, manifest_path=con)
    assert esito_con.budget_ok is True
    assert not esito_con.alarm_raised


def test_piu_motivi_finiscono_tutti_nello_stesso_file(tmp_path):
    """A.6/D3: il file porta l'elenco completo, non solo il primo motivo.

    Il lato opposto è già negli altri test: con un motivo solo, l'elenco ha una
    voce sola.
    """
    atteso = alarm_path_for(OGGI, tmp_path / "repo")
    # Ledger vuoto (exit 1) + preflight bloccato + prova forzata: tre motivi.
    esito = _controllo(tmp_path, preflight=_preflight_bloccato, force_alarm=True)
    assert len(esito.alarm_reasons) == 3
    testo = atteso.read_text(encoding="utf-8")
    assert "  1. " in testo and "  2. " in testo and "  3. " in testo
    assert "prova forzata" in testo
    assert "exit 1" in testo
    assert "preflight NO" in testo
