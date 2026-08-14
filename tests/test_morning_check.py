"""scripts/morning_check.py — il controllo delle 08:00, senza scheduler e senza rete.

Cosa è testabile qui: la rilevazione della giornata di stanotte, l'avviso
quando manca, l'upgrade OTS settimanale con i due sottoprocessi finti al posto
dei calendar veri, e la disciplina di rete (`TRADERLAB_ALLOW_NETWORK` iniettata
solo per quel sottoprocesso). Cosa non è testabile qui: il wrapper PowerShell
e la registrazione del task, che le fa l'owner a mano
(`docs/OPERATIONS.md`).
"""

from __future__ import annotations

from collections import namedtuple
from datetime import date, timezone
from datetime import datetime as dt

import pytest

from contracts.decision import Action
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict
from ledger.ops_ledger import OpsLedger
from ledger.trader_ledger import LedgerKey, TraderLedger
from scripts.morning_check import (
    EXIT_NO_VERBALI,
    EXIT_OK,
    default_alert,
    log_path_for,
    run_morning_check,
)
from tests.factories import make_decision

OGGI = date(2026, 8, 17)  # un lunedi'
SNAPSHOT_ID = "a" * 64

Completed = namedtuple("Completed", "returncode stdout stderr")


class FakeRunner:
    """Finto esecutore di sottoprocessi: registra i comandi, restituisce esiti."""

    def __init__(self, *results: Completed) -> None:
        self._results = list(results)
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(self, command, env):
        self.calls.append((list(command), dict(env)))
        if not self._results:
            raise AssertionError(f"comando inatteso: {command}")
        return self._results.pop(0)

    @property
    def commands(self) -> list[list[str]]:
        return [c for c, _ in self.calls]


class FakeAlert:
    """Finto avviso visibile: registra i messaggi invece di aprire un popup."""

    def __init__(self, shown: bool = True, exc: Exception | None = None) -> None:
        self.shown = shown
        self.exc = exc
        self.messages: list[str] = []

    def __call__(self, message: str) -> bool:
        self.messages.append(message)
        if self.exc is not None:
            raise self.exc
        return self.shown


def _verdetto() -> RiskVerdict:
    return RiskVerdict(
        outcome=RiskOutcome.APPROVED,
        rule=RiskRule.NONE,
        action_in=Action.LONG,
        action_out=Action.LONG,
        size_fraction_in=0.05,
        size_fraction_out=0.05,
    )


@pytest.fixture
def percorsi(tmp_path):
    return {
        "repo_root": tmp_path / "repo",
        "ledger_path": tmp_path / "ledger" / "season0.jsonl",
        "ops_path": tmp_path / "ledger" / "ops.jsonl",
        "log_dir": tmp_path / "logs",
        "toolcalls_dir": tmp_path / "toolcalls",
    }


def _scrivi_giornata(ledger: TraderLedger, giorno: date) -> None:
    asof = dt(giorno.year, giorno.month, giorno.day, 0, 0, tzinfo=timezone.utc)
    for replica in ("r1", "r2", "r3"):
        ledger.append(
            key=LedgerKey.of(giorno, replica, "BTC"),
            verdict=_verdetto(),
            decision=make_decision(SNAPSHOT_ID, replica_id=replica, timestamp=asof),
            snapshot_id=SNAPSHOT_ID,
            run_id=f"run-{giorno.isoformat()}",
        )


def _controllo(percorsi, **kwargs):
    parametri = {
        "repo_root": percorsi["repo_root"],
        "today": OGGI,
        "ledger_path": percorsi["ledger_path"],
        "ops_path": percorsi["ops_path"],
        "log_dir": percorsi["log_dir"],
        "toolcalls_dir": percorsi["toolcalls_dir"],
        "python_executable": "python",
        "is_monday": False,
        "runner": FakeRunner(),
        "alert": FakeAlert(),
        "env": {},
        "echo": False,
    }
    parametri.update(kwargs)
    return run_morning_check(**parametri)


# --------------------------------------------------------------------------
# Nome del file di log
# --------------------------------------------------------------------------


def test_il_nome_del_log_e_per_giornata(percorsi):
    assert log_path_for(OGGI, percorsi["log_dir"]) == percorsi["log_dir"] / "morning-2026-08-17.log"


# --------------------------------------------------------------------------
# Giornata trovata: rapporto scritto, exit 0
# --------------------------------------------------------------------------


def test_giornata_trovata_scrive_il_rapporto_ed_esce_0(percorsi):
    ledger = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(ledger, OGGI)
    allarme = FakeAlert()

    esito = _controllo(percorsi, alert=allarme)

    assert esito.exit_code == EXIT_OK
    assert esito.day_found is True
    assert allarme.messages == []  # nessun avviso quando la giornata c'e'
    testo = esito.log_path.read_text(encoding="utf-8")
    assert "RAPPORTO DEL MATTINO" in testo
    assert "accordo 3/3" in testo


def test_il_log_del_controllo_e_per_giornata(percorsi):
    ledger = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(ledger, OGGI)

    esito = _controllo(percorsi)

    assert esito.log_path == log_path_for(OGGI, percorsi["log_dir"])
    assert esito.log_path.exists()


# --------------------------------------------------------------------------
# Giornata NON trovata: avviso visibile, exit 1
# --------------------------------------------------------------------------


def test_giornata_non_trovata_mostra_l_avviso_ed_esce_1(percorsi):
    TraderLedger(percorsi["ledger_path"])  # ledger vuoto
    allarme = FakeAlert(shown=True)

    esito = _controllo(percorsi, alert=allarme)

    assert esito.exit_code == EXIT_NO_VERBALI
    assert esito.day_found is False
    assert esito.alert_shown is True
    assert len(allarme.messages) == 1
    messaggio = allarme.messages[0]
    assert "NON ha prodotto verbali" in messaggio
    assert "daily-2026-08-17.log" in messaggio

    testo = esito.log_path.read_text(encoding="utf-8")
    assert "STOP:" in testo
    assert "NON ha prodotto verbali" in testo


def test_giornata_di_un_altro_giorno_non_conta(percorsi):
    """Un buco onesto: verbali di ieri non bastano per la giornata di oggi."""
    ledger = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(ledger, date(2026, 8, 16))

    esito = _controllo(percorsi)

    assert esito.exit_code == EXIT_NO_VERBALI
    assert esito.day_found is False


def test_avviso_fallito_non_blocca_il_controllo(percorsi):
    TraderLedger(percorsi["ledger_path"])
    allarme = FakeAlert(exc=RuntimeError("msg.exe non disponibile"))

    esito = _controllo(percorsi, alert=allarme)

    assert esito.exit_code == EXIT_NO_VERBALI
    assert esito.alert_shown is False
    testo = esito.log_path.read_text(encoding="utf-8")
    assert "avviso NON mostrato" in testo or "eccezione" in testo


# --------------------------------------------------------------------------
# Upgrade OTS: solo il lunedi', mai bloccante
# --------------------------------------------------------------------------


def test_upgrade_ots_gira_solo_il_lunedi(percorsi):
    ledger = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(ledger, OGGI)
    runner = FakeRunner(
        Completed(0, "stato: confermato su Bitcoin", ""),
        Completed(0, "stato: ancora pending, nessun aggiornamento", ""),
    )

    esito = _controllo(percorsi, is_monday=True, runner=runner)

    assert esito.ots_attempted is True
    assert len(runner.commands) == 2
    assert runner.commands[0][1].endswith("ots_stamp.py")
    assert runner.commands[0][2] == "upgrade"
    assert str(percorsi["repo_root"] / "manifests" / "trader_v0_freeze_manifest.json") in (
        runner.commands[0]
    )
    assert str(percorsi["repo_root"] / "docs" / "PREREG_LAB_S0.md") in runner.commands[1]
    testo = esito.log_path.read_text(encoding="utf-8")
    assert "upgrade OTS" in testo
    assert "confermato su Bitcoin" in testo


def test_upgrade_ots_non_gira_fuori_dal_lunedi(percorsi):
    ledger = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(ledger, OGGI)
    runner = FakeRunner()  # nessun comando ammesso

    esito = _controllo(percorsi, is_monday=False, runner=runner)

    assert esito.ots_attempted is False
    assert runner.commands == []


def test_la_rete_e_iniettata_solo_per_l_upgrade_ots(percorsi):
    ledger = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(ledger, OGGI)
    runner = FakeRunner(Completed(0, "", ""), Completed(0, "", ""))

    _controllo(percorsi, is_monday=True, runner=runner, env={"PATH": "x"})

    for _, ambiente in runner.calls:
        assert ambiente["TRADERLAB_ALLOW_NETWORK"] == "1"
        assert ambiente["PATH"] == "x"


def test_upgrade_ots_fallito_non_blocca_il_controllo(percorsi):
    """Un calendar irraggiungibile finisce nel log, non ferma il controllo."""
    ledger = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(ledger, OGGI)
    runner = FakeRunner(
        Completed(1, "", "ERRORE: calendar irraggiungibile"),
        Completed(0, "stato: ancora pending", ""),
    )

    esito = _controllo(percorsi, is_monday=True, runner=runner)

    assert esito.exit_code == EXIT_OK  # l'esito della giornata resta quello vero
    assert esito.ots_attempted is True
    testo = esito.log_path.read_text(encoding="utf-8")
    assert "calendar irraggiungibile" in testo


def test_upgrade_ots_che_solleva_non_blocca_il_controllo(percorsi):
    ledger = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(ledger, OGGI)

    def runner_che_solleva(command, env):
        raise ConnectionError("rete irraggiungibile")

    esito = _controllo(percorsi, is_monday=True, runner=runner_che_solleva)

    assert esito.exit_code == EXIT_OK
    testo = esito.log_path.read_text(encoding="utf-8")
    assert "eccezione" in testo


def test_upgrade_ots_e_la_giornata_mancante_convivono(percorsi):
    """Lunedi' senza verbali: sia l'avviso sia il tentativo di upgrade partono."""
    TraderLedger(percorsi["ledger_path"])
    runner = FakeRunner(Completed(0, "", ""), Completed(0, "", ""))
    allarme = FakeAlert()

    esito = _controllo(percorsi, is_monday=True, runner=runner, alert=allarme)

    assert esito.exit_code == EXIT_NO_VERBALI
    assert esito.ots_attempted is True
    assert len(allarme.messages) == 1
    assert len(runner.commands) == 2


# --------------------------------------------------------------------------
# default_alert: msg.exe con fallback al popup PowerShell
# --------------------------------------------------------------------------


class FakeSubprocessRun:
    """Finto `subprocess.run`: stessa forma di chiamata (comando, kwargs)."""

    def __init__(self, *results: Completed) -> None:
        self._results = list(results)
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs):
        self.commands.append(list(command))
        if not self._results:
            raise AssertionError(f"comando inatteso: {command}")
        return self._results.pop(0)


def test_default_alert_usa_msg_exe_se_riesce():
    runner = FakeSubprocessRun(Completed(0, "", ""))
    assert default_alert("prova", runner=runner) is True
    assert runner.commands[0][0] == "msg.exe"


def test_default_alert_ricade_sul_popup_powershell():
    runner = FakeSubprocessRun(Completed(1, "", "msg.exe non disponibile"), Completed(0, "", ""))
    assert default_alert("prova", runner=runner) is True
    assert runner.commands[1][0] == "powershell.exe"


def test_default_alert_fallisce_con_grazia_se_entrambi_falliscono():
    runner = FakeSubprocessRun(Completed(1, "", ""), Completed(1, "", ""))
    assert default_alert("prova", runner=runner) is False


def test_default_alert_gestisce_eccezioni_di_entrambi_i_tentativi():
    def runner_che_solleva(*args, **kwargs):
        raise FileNotFoundError("msg.exe non trovato")

    assert default_alert("prova", runner=runner_che_solleva) is False
