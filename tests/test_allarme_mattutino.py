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
from collections.abc import Mapping
from datetime import date, datetime, timezone
from pathlib import Path

from contracts.decision import Action
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict
from ledger.ops_ledger import OpsEvent, OpsKey, OpsLedger
from ledger.trader_ledger import LedgerKey, TraderLedger
from scripts.morning_check import alarm_path_for, run_morning_check
from scripts.preflight import CheckResult, PreflightResult
from tests.factories import (
    PREZZI_OPUS5,
    make_decision,
    manifest_con_prezzi,
    prezzi_senza,
)
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


def _scrivi_manifest(
    path: Path,
    *,
    season_budget_usd: float | None = None,
    season_expected_days: int | None = None,
    pin_commit: str = PIN,
    prezzi: Mapping[str, float] | None = None,
) -> Path:
    """Un Freeze manifest su disco. `pin_commit` decide se la stagione e' attiva.

    Il listino c'e' per default (quello di `claude-opus-5`): quasi tutti questi
    test provano il ritmo di spesa **dentro** una stagione, dove le tariffe
    sono firmate. Chi prova il caso opposto passa `prezzi={}` esplicitamente.
    """
    manifest = manifest_con_prezzi(
        datetime.now(tz=timezone.utc),
        pin_commit=pin_commit,
        season_budget_usd=season_budget_usd,
        season_expected_days=season_expected_days,
        prezzi=PREZZI_OPUS5 if prezzi is None else prezzi,
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
        # Manifest PINNATO ma senza termini economici: la stagione risulta
        # ATTIVA — che e' il contesto in cui una giornata mancante e'
        # un'anomalia — e il passo del budget si salta con il motivo scritto
        # nel log, perche' non e' quello che il test in questione prova.
        "manifest_path": _scrivi_manifest(tmp_path / "manifest_stagione.json"),
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


#: Costo di una giornata "tipo" in questi test: 1.000.000 token di output al
#: listino di `claude-opus-5` firmato nel manifest ($25/Mtok) fanno esattamente
#: 25 USD. Chiamarlo `D` permette di scrivere le soglie come multipli di una
#: giornata invece che come numeri magici.
#:
#: Era 50 USD finché il listino viveva fra le costanti di `ledger/spend.py`
#: con i prezzi di Fable ($50/Mtok in output). Il valore è cambiato perché è
#: cambiato il modello pinnato, ed è esattamente il legame che una costante di
#: modulo non poteva rappresentare.
D_USD = 25.0
TOKEN_PER_GIORNATA = 1_000_000


def test_allarme_sul_ritmo_di_spesa_e_silenzio_sotto_soglia(tmp_path):
    """D5 dentro il controllo del mattino, i due lati, tarati sul preventivo.

    Preventivo `28 x D` su **28** giornate attese: al giorno `g` il pro-rata
    vale esattamente `g x D`, cioè la spesa attesa, e la soglia d'allarme vale
    `1,25 x g x D`. Qui `g = 1`.

    - spesa `1,0 x D` → **nessun allarme**: la stagione è in linea;
    - spesa `1,3 x D` → **allarme**: 1,3 supera 1,25.

    **Perché le giornate attese devono venire dal manifest e non da una
    costante.** Con lo stesso preventivo tarato su 28 giornate e un pro-rata
    calcolato sulle 42 del cap di calendario, la soglia varrebbe
    `1,25 x 28D x g/42 = 0,83 x g x D` — **sotto** la spesa attesa. Una
    stagione perfettamente in linea col proprio preventivo suonerebbe
    l'allarme ogni singolo giorno, e un allarme che suona sempre è un allarme
    spento. Numeratore e denominatore si firmano insieme, al rito del pin.
    """
    atteso = alarm_path_for(OGGI, tmp_path / "repo")
    preventivo = 28 * D_USD
    attese = 28

    # -- lato "in linea": spesa esattamente 1,0 x D al giorno 1 -------------
    in_linea = tmp_path / "in_linea"
    _giornata_costosa(in_linea, output_tokens=TOKEN_PER_GIORNATA)
    manifest_in_linea = _scrivi_manifest(
        in_linea / "manifest.json",
        season_budget_usd=preventivo,
        season_expected_days=attese,
    )
    sotto = _controllo(
        tmp_path,
        ledger_path=in_linea / "ledger" / "season0.jsonl",
        toolcalls_dir=in_linea / "toolcalls",
        manifest_path=manifest_in_linea,
    )
    assert sotto.budget_ok is True
    assert not sotto.alarm_raised
    assert not atteso.exists()

    # -- lato "in fretta": spesa 1,3 x D al giorno 1 ------------------------
    in_fretta = tmp_path / "in_fretta"
    _giornata_costosa(in_fretta, output_tokens=int(1.3 * TOKEN_PER_GIORNATA))
    manifest_in_fretta = _scrivi_manifest(
        in_fretta / "manifest.json",
        season_budget_usd=preventivo,
        season_expected_days=attese,
    )
    sopra = _controllo(
        tmp_path,
        ledger_path=in_fretta / "ledger" / "season0.jsonl",
        toolcalls_dir=in_fretta / "toolcalls",
        manifest_path=manifest_in_fretta,
    )
    assert sopra.budget_ok is False
    assert sopra.alarm_raised
    assert "ritmo di spesa" in atteso.read_text(encoding="utf-8")


def test_senza_i_termini_economici_il_passo_si_salta_invece_di_allarmare(tmp_path):
    """D5: prima del rito del pin i termini non ci sono, ed è la normalità.

    I termini sono **sei** — `season_budget_usd`, `season_expected_days` e le
    quattro voci di listino — e la mancanza di uno solo basta a rendere il
    conto indefinito: senza denominatore non c'è pro-rata, senza tariffa non
    c'è spesa da confrontargli. In tutti i casi mancanti il passo si salta con
    il motivo scritto nel log:
    trasformarlo in un allarme quotidiano insegnerebbe all'owner a ignorare il
    file, che è il modo più efficace di disattivare un allarme senza
    spegnerlo. Il lato opposto: con entrambi i termini la domanda si pone e la
    risposta arriva.
    """
    _giornata_costosa(tmp_path, output_tokens=1_000)

    incompleti: dict[str, dict] = {
        "nessuno": {"season_budget_usd": None, "season_expected_days": None},
        "solo_giornate": {"season_budget_usd": None, "season_expected_days": 28},
        "solo_preventivo": {"season_budget_usd": 1_000.0, "season_expected_days": None},
        # Preventivo e giornate ci sono entrambi, manca il **listino**: senza
        # tariffe la spesa cumulata non è calcolabile, e una guardia che
        # confronta un preventivo con un numero che non sa costruire non è una
        # guardia. Anche questo è un passo saltato, non un allarme.
        "senza_listino": {
            "season_budget_usd": 1_000.0,
            "season_expected_days": 28,
            "prezzi": {},
        },
        # Listino a tre voci su quattro: manca la lettura da cache. Un conto
        # parziale sembra un numero e non lo è.
        "listino_monco": {
            "season_budget_usd": 1_000.0,
            "season_expected_days": 28,
            "prezzi": prezzi_senza("price_per_mtok_cache_read"),
        },
    }
    for nome, termini in incompleti.items():
        manifest = _scrivi_manifest(tmp_path / f"{nome}.json", **termini)
        esito = _controllo(tmp_path, manifest_path=manifest)
        assert esito.budget_ok is None, nome
        assert not esito.alarm_raised, nome

    completo = _scrivi_manifest(
        tmp_path / "completo.json",
        season_budget_usd=1_000.0,
        season_expected_days=28,
    )
    esito_completo = _controllo(tmp_path, manifest_path=completo)
    assert esito_completo.budget_ok is True
    assert not esito_completo.alarm_raised


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


# --------------------------------------------------------------------------
# Consapevolezza della stagione
# --------------------------------------------------------------------------
#
# Il rito notturno gira solo dentro una stagione. Fuori da una stagione e'
# spento per costruzione, e i verbali che non produce non sono un'anomalia:
# sono la normalita'. Prima di questa regola il controllo del mattino scriveva
# un ALLARME al giorno per tutta la durata del cantiere, e un allarme che
# suona ogni mattina insegna a non guardarlo — cioe' si disattiva da solo
# senza che nessuno lo abbia spento.
#
# Cio' che NON cambia: ogni altra anomalia allarma comunque, dentro o fuori
# stagione. Il preflight che dice NO e il ritmo di spesa oltre soglia
# restano motivi validi.


def _senza_stagione(tmp_path: Path) -> Path:
    """Manifest leggibile ma NON pinnato: nessuna stagione attiva."""
    return _scrivi_manifest(tmp_path / "non_pinnato.json", pin_commit="")


def test_verbali_mancanti_allarmano_in_stagione_e_tacciono_fuori(tmp_path):
    """I due lati della regola, a parita' di tutto il resto.

    Stesso ledger vuoto, stesso preflight pronto, stesso giorno: cambia solo
    se il manifest porta un `pin_commit` vero.
    """
    atteso = alarm_path_for(OGGI, tmp_path / "repo")

    # -- lato "stagione attiva": la giornata manca ed e' un'anomalia --------
    in_stagione = _controllo(tmp_path)  # manifest pinnato, vedi _controllo
    assert in_stagione.season_active is True
    assert in_stagione.exit_code == 1
    assert in_stagione.alarm_raised
    assert "exit 1" in atteso.read_text(encoding="utf-8")

    atteso.unlink()

    # -- lato "nessuna stagione": la stessa assenza non e' un'anomalia ------
    fuori = _controllo(tmp_path, manifest_path=_senza_stagione(tmp_path))
    assert fuori.season_active is False
    assert fuori.day_found is False
    assert fuori.exit_code == 0
    assert fuori.alert_shown is None  # nessun avviso visibile mostrato
    assert not fuori.alarm_raised
    assert not atteso.exists()
    assert "nessuna stagione attiva" in fuori.detail


def test_fuori_stagione_le_altre_anomalie_allarmano_lo_stesso(tmp_path):
    """La regola sospende UN motivo, non il canale.

    Fuori stagione, con la stessa giornata mancante che sopra non allarma, un
    preflight NO produce comunque il file — e ne produce **uno solo**, perche'
    il motivo dei verbali mancanti non e' entrato nell'elenco.
    """
    atteso = alarm_path_for(OGGI, tmp_path / "repo")
    fuori = _senza_stagione(tmp_path)

    esito = _controllo(tmp_path, manifest_path=fuori, preflight=_preflight_bloccato)

    assert esito.season_active is False
    assert esito.exit_code == 0
    assert esito.preflight_ready is False
    assert esito.alarm_raised
    assert len(esito.alarm_reasons) == 1
    testo = atteso.read_text(encoding="utf-8")
    assert "preflight NO" in testo
    assert "exit 1" not in testo


def test_un_manifest_illeggibile_vale_nessuna_stagione_e_ALLARMA(tmp_path):
    """Terzo caso: il manifest c'e' ma non si carica.

    Assente, illeggibile o con `freeze_id` divergente sono la stessa risposta
    alla domanda «c'e' una stagione attiva?» — no — e la distinzione fra loro
    sta nel motivo, che finisce nel log.

    **Questo test diceva il contrario fino al 2026-08-21**, e la riga che
    diceva era: «Non e' un allarme: un manifest rotto e' un problema del rito
    del pin, non della notte appena passata, e il runner lo rifiuta gia' da
    se'». La misura l'ha smentita. Il 20/08 il manifest di default era gia'
    irricevibile per `freeze_id` divergente; il controllo del mattino lo
    scrisse nel log come «stagione: nessuna», rispose PRONTO PER STANOTTE: SI
    e conclude' exit 0 **senza allarme**, due volte nella stessa giornata. La
    notte seguente il rito uscì 4 sulla stessa causa (DIAGNOSI_G1 §1-bis).

    Il difetto del ragionamento vecchio: «il runner lo rifiuta gia' da se'» e'
    vero e irrilevante. Il rifiuto del runner arriva a mezzanotte, quando non
    c'e' piu' tempo per ripararlo; il controllo del mattino esiste proprio per
    anticiparlo di diciassette ore. Un guasto che il sistema conosce e non
    dice e' peggio di un guasto che non conosce.

    Resta muto, e deve restare muto, il manifest **sano ma non ancora
    pinnato**: quello e' il cantiere fermo, non un guasto — ed e' il caso di
    `test_verbali_mancanti_allarmano_in_stagione_e_tacciono_fuori`.
    """
    rotto = tmp_path / "rotto.json"
    rotto.write_text("{ questo non e' JSON", encoding="utf-8")

    esito = _controllo(tmp_path, manifest_path=rotto)

    assert esito.season_active is False
    # L'exit code resta governato dalla sola domanda sui verbali di stanotte:
    # e' l'ALLARME il canale del guasto (verbale RUN2 §A.6 / D3).
    assert esito.exit_code == 0
    assert esito.alarm_raised
    motivi = " ".join(esito.alarm_reasons)
    assert "manifest del rito inutilizzabile" in motivi
    assert "NON puo' girare" in motivi
    testo = esito.log_path.read_text(encoding="utf-8")
    assert "stagione: nessuna" in testo


def test_un_manifest_sano_ma_non_pinnato_resta_muto(tmp_path):
    """Il contro-test del precedente, e il confine fra i due.

    Senza questo, la riparazione del 21/08 sarebbe indistinguibile da «allarma
    sempre quando non c'e' stagione», che e' il modo piu' efficace di
    disattivare un allarme senza spegnerlo. Un manifest che si **carica** e
    non e' ancora pinnato e' lo stato normale di un cantiere prima del rito
    del pin: non e' un guasto e non suona.
    """
    esito = _controllo(tmp_path, manifest_path=_senza_stagione(tmp_path))

    assert esito.season_active is False
    assert not esito.alarm_raised


def test_il_rito_notturno_fallito_allarma_dal_registro_operativo(tmp_path):
    """L'esito ≠ 0 della notte si legge dal registro operativo del Lab.

    Non dal `LastTaskResult` del Task Scheduler: quello e' un solo numero che
    la passata successiva sovrascrive, mentre il registro operativo e'
    append-only con hash-chain. La notte del 2026-08-21 scrisse `run_failed` e
    la mattina non aveva modo di accorgersene.
    """
    # Lo stesso percorso che `_controllo` passa al controllo del mattino.
    ops = OpsLedger(tmp_path / "ledger" / "ops.jsonl")
    ops.append(
        key=OpsKey.of(OGGI, OpsEvent.RUN_FAILED),
        detail="run_day.py ha restituito 2",
    )

    esito = _controllo(tmp_path)

    assert esito.alarm_raised
    motivi = " ".join(esito.alarm_reasons)
    assert "esito del rito di stanotte" in motivi
    assert "run_failed" in motivi


def test_un_preflight_che_solleva_e_un_NO_non_un_silenzio(tmp_path):
    """La dottrina, in una riga: un controllo non eseguibile e' FAIL, mai PASS.

    Prima, un'eccezione nel preflight lasciava `preflight_ready` a `None`: il
    controllo spariva dalla tabella, non entrava nei motivi d'allarme e la
    mattina concludeva exit 0. Un controllo che non gira non e' un controllo
    verde.
    """

    def _preflight_che_esplode(**kwargs):
        raise RuntimeError("il sotto-processo non parte")

    esito = _controllo(tmp_path, preflight=_preflight_che_esplode)

    assert esito.preflight_ready is False
    assert esito.alarm_raised
    motivi = " ".join(esito.alarm_reasons)
    assert "preflight NO per stanotte" in motivi
    assert "non eseguibile" in motivi
