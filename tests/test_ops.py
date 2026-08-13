"""Rito quotidiano e registro operativo, senza scheduler e senza rete.

Cosa è testabile qui: la rilevazione dei giorni mancati, la policy che vieta il
recupero retroattivo, il registro operativo append-only, e l'orchestrazione del
rito — con i due processi esterni sostituiti da un finto esecutore, così da
verificare *quali* comandi vengono lanciati, *con quale ambiente*, e *in che
ordine*.

Cosa non è testabile qui: la registrazione del task in Windows Task Scheduler,
che la fa l'owner a mano (docs/OPERATIONS.md). Il wrapper PowerShell è tenuto
apposta senza logica di dominio proprio perché quella parte non si può provare.
"""

from __future__ import annotations

from collections import namedtuple
from datetime import date, datetime, timedelta, timezone

import pytest

from arena.daily_ritual import (
    EXIT_ALREADY_DONE,
    EXIT_DECISIONS_FAILED,
    EXIT_DECISIONS_RETRY_EXHAUSTED,
    EXIT_MEANING,
    EXIT_OK,
    EXIT_PRECONDITION,
    EXIT_SNAPSHOT_FAILED,
    RITUAL_RETRY_MAX_ATTEMPTS,
    RITUAL_RETRY_WAIT_SECONDS,
    log_path_for,
    run_daily,
)
from arena.llm_client import RETRYABLE_PROCESS_EXIT_CODE
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict
from contracts.decision import Action
from ledger.ops_ledger import (
    DuplicateOpsEntry,
    OpsEvent,
    OpsKey,
    OpsLedger,
    last_recorded_day,
    mark_missing_days,
    missing_days,
    recorded_days,
)
from ledger.trader_ledger import LedgerKey, TraderLedger

OGGI = date(2026, 8, 13)
ADESSO = datetime(2026, 8, 13, 0, 30, tzinfo=timezone.utc)
SNAPSHOT_ID = "ab" * 32

Completed = namedtuple("Completed", "returncode stdout stderr")


def _build_output(snapshot_id: str = SNAPSHOT_ID) -> str:
    return (
        "asof_utc        : 2026-08-13T00:00:00+00:00\n"
        f"snapshot_id     : {snapshot_id}\n"
        "universo        : BTC, ETH\n"
    )


class FakeRunner:
    """Finto esecutore di processi: registra i comandi e restituisce esiti."""

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


def _verdetto() -> RiskVerdict:
    return RiskVerdict(
        outcome=RiskOutcome.APPROVED,
        rule=RiskRule.NONE,
        action_in=Action.FLAT,
        action_out=Action.FLAT,
        size_fraction_in=0.0,
        size_fraction_out=0.0,
    )


def _scrivi_giornata(ledger: TraderLedger, giorno: date, asset: str = "BTC") -> None:
    ledger.append(
        key=LedgerKey.of(giorno, "r1", asset),
        verdict=_verdetto(),
        snapshot_id="0" * 64,
        run_id=f"run-{giorno.isoformat()}",
    )


@pytest.fixture
def percorsi(tmp_path):
    return {
        "repo_root": tmp_path / "repo",
        "ledger_path": tmp_path / "ledger" / "season0.jsonl",
        "ops_path": tmp_path / "ledger" / "ops.jsonl",
        "log_dir": tmp_path / "logs",
    }


def _rito(percorsi, runner, **kwargs):
    parametri = {
        "repo_root": percorsi["repo_root"],
        "today": OGGI,
        "now_utc": ADESSO,
        "python_executable": "python",
        "ledger_path": percorsi["ledger_path"],
        "ops_path": percorsi["ops_path"],
        "log_dir": percorsi["log_dir"],
        "runner": runner,
        "env": {},
        "echo": False,
    }
    parametri.update(kwargs)
    return run_daily(**parametri)


# --------------------------------------------------------------------------
# Giorni mancati: aritmetica
# --------------------------------------------------------------------------


def test_ieri_registrato_significa_nessun_buco():
    assert missing_days(OGGI - timedelta(days=1), OGGI) == []


def test_oggi_gia_registrato_non_e_un_buco():
    assert missing_days(OGGI, OGGI) == []
    assert missing_days(OGGI + timedelta(days=1), OGGI) == []


def test_i_giorni_in_mezzo_sono_quelli_mancati():
    assert missing_days(OGGI - timedelta(days=4), OGGI) == [
        OGGI - timedelta(days=3),
        OGGI - timedelta(days=2),
        OGGI - timedelta(days=1),
    ]


def test_oggi_non_e_mai_un_giorno_mancato():
    """Oggi non è saltato: sta per essere eseguito."""
    assert OGGI not in missing_days(OGGI - timedelta(days=5), OGGI)


# --------------------------------------------------------------------------
# Giorni mancati: scrittura nel registro operativo
# --------------------------------------------------------------------------


def test_ledger_vuoto_non_produce_giorni_mancati(percorsi):
    """Il primo giorno di una stagione non ha buchi alle spalle."""
    trader = TraderLedger(percorsi["ledger_path"])
    ops = OpsLedger(percorsi["ops_path"])
    assert last_recorded_day(trader) is None
    assert mark_missing_days(trader_ledger=trader, ops_ledger=ops, today=OGGI) == []
    assert len(ops) == 0


def test_i_giorni_mancati_finiscono_nel_registro_operativo(percorsi):
    trader = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(trader, OGGI - timedelta(days=3))
    ops = OpsLedger(percorsi["ops_path"])

    marcati = mark_missing_days(
        trader_ledger=trader, ops_ledger=ops, today=OGGI, detected_at_utc=ADESSO
    )
    assert marcati == [OGGI - timedelta(days=2), OGGI - timedelta(days=1)]
    assert ops.skipped_days() == marcati
    assert ops.verify().ok
    for entry in ops.events(OpsEvent.SKIPPED_DAY):
        assert entry["key"]["event"] == "skipped_day"
        assert "2026-08-10" in entry["detail"]


def test_marcare_i_giorni_mancati_e_idempotente(percorsi):
    """Il buco resta finché resta: ri-rilevarlo non è un errore nuovo."""
    trader = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(trader, OGGI - timedelta(days=3))
    ops = OpsLedger(percorsi["ops_path"])

    primi = mark_missing_days(trader_ledger=trader, ops_ledger=ops, today=OGGI)
    secondi = mark_missing_days(trader_ledger=trader, ops_ledger=ops, today=OGGI)
    assert primi and secondi == []
    assert len(ops) == len(primi)


def test_un_giorno_saltato_non_genera_decisioni(percorsi):
    """Policy: i verbali dei giorni saltati NON si recuperano, mai."""
    trader = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(trader, OGGI - timedelta(days=3))
    righe_prima = len(trader)
    ops = OpsLedger(percorsi["ops_path"])

    mark_missing_days(trader_ledger=trader, ops_ledger=ops, today=OGGI)

    assert len(TraderLedger(percorsi["ledger_path"])) == righe_prima
    assert recorded_days(trader) == [OGGI - timedelta(days=3)]
    assert all(e["decision"] is None for e in trader.read_all())


# --------------------------------------------------------------------------
# Registro operativo: append-only, write-once, catena
# --------------------------------------------------------------------------


def test_il_registro_operativo_e_write_once_per_giorno_ed_evento(percorsi):
    ops = OpsLedger(percorsi["ops_path"])
    chiave = OpsKey.of(OGGI, OpsEvent.SKIPPED_DAY)
    ops.append(key=chiave, detail="primo")
    with pytest.raises(DuplicateOpsEntry, match="write-once"):
        ops.append(key=chiave, detail="secondo")


def test_eventi_diversi_nello_stesso_giorno_convivono(percorsi):
    ops = OpsLedger(percorsi["ops_path"])
    ops.append(key=OpsKey.of(OGGI, OpsEvent.RUN_FAILED), detail="rete giu'")
    ops.append(key=OpsKey.of(OGGI, OpsEvent.DAY_COMPLETED), detail="ripartito")
    assert len(ops) == 2
    assert ops.verify().ok


def test_la_catena_del_registro_operativo_si_rompe_se_manomessa(percorsi):
    ops = OpsLedger(percorsi["ops_path"])
    for scarto in (5, 4, 3):
        ops.record_skipped_day(OGGI - timedelta(days=scarto))
    assert ops.verify().ok

    righe = ops.path.read_text(encoding="utf-8").splitlines()
    righe[1] = righe[1].replace('"detail": "', '"detail": "MANOMESSO ')
    ops.path.write_text("\n".join(righe) + "\n", encoding="utf-8")

    esito = OpsLedger(ops.path).verify()
    assert not esito.ok
    assert esito.broken_at == 1


def test_il_registro_riletto_da_disco_conosce_gli_eventi(percorsi):
    ops = OpsLedger(percorsi["ops_path"])
    ops.record_skipped_day(OGGI - timedelta(days=1))
    riletto = OpsLedger(percorsi["ops_path"])
    assert riletto.has(OpsKey.of(OGGI - timedelta(days=1), OpsEvent.SKIPPED_DAY))
    assert riletto.record_skipped_day(OGGI - timedelta(days=1)) is None


# --------------------------------------------------------------------------
# Orchestrazione del rito
# --------------------------------------------------------------------------


def test_giornata_completa_lancia_i_due_processi_nell_ordine(percorsi):
    runner = FakeRunner(
        Completed(0, _build_output(), ""),
        Completed(0, "decisioni       : 6\n", ""),
    )
    esito = _rito(percorsi, runner)

    assert esito.exit_code == EXIT_OK
    assert esito.snapshot_id == SNAPSHOT_ID
    assert len(runner.commands) == 2
    assert runner.commands[0][1].endswith("build_snapshot.py")
    assert runner.commands[1][1].endswith("run_day.py")
    assert "--snapshot-id" in runner.commands[1]
    assert SNAPSHOT_ID in runner.commands[1]


def test_la_rete_e_accesa_solo_per_lo_snapshot(percorsi):
    """CLAUDE.md §7: la rete si tocca in un processo separato, non altrove."""
    runner = FakeRunner(
        Completed(0, _build_output(), ""), Completed(0, "", "")
    )
    _rito(percorsi, runner, env={"TRADERLAB_ALLOW_NETWORK": "1", "PATH": "x"})

    ambiente_build = runner.calls[0][1]
    ambiente_decisioni = runner.calls[1][1]
    assert ambiente_build["TRADERLAB_ALLOW_NETWORK"] == "1"
    # Anche se l'ambiente di partenza aveva il flag, il processo che decide
    # non lo riceve: non si eredita per distrazione.
    assert "TRADERLAB_ALLOW_NETWORK" not in ambiente_decisioni


def test_il_rito_scrive_un_log_per_giornata(percorsi):
    runner = FakeRunner(Completed(0, _build_output(), ""), Completed(0, "", ""))
    esito = _rito(percorsi, runner)

    assert esito.log_path == log_path_for(OGGI, percorsi["log_dir"])
    testo = esito.log_path.read_text(encoding="utf-8")
    assert "rito quotidiano" in testo
    assert SNAPSHOT_ID in testo
    assert "giornata completata" in testo


def test_il_log_della_stessa_giornata_si_accoda(percorsi):
    """Due passate nello stesso giorno scrivono nello stesso file, in coda."""
    runner = FakeRunner(Completed(2, "", "rete irraggiungibile"))
    primo = _rito(percorsi, runner)
    runner2 = FakeRunner(Completed(2, "", "rete ancora irraggiungibile"))
    secondo = _rito(percorsi, runner2)

    assert primo.log_path == secondo.log_path
    testo = primo.log_path.read_text(encoding="utf-8")
    assert "rete irraggiungibile" in testo
    assert "rete ancora irraggiungibile" in testo


def test_snapshot_fallito_ferma_il_rito_prima_delle_decisioni(percorsi):
    runner = FakeRunner(Completed(2, "", "ERRORE: rete disabilitata"))
    esito = _rito(percorsi, runner)

    assert esito.exit_code == EXIT_SNAPSHOT_FAILED
    assert len(runner.commands) == 1, "le decisioni non devono partire"
    assert OpsLedger(percorsi["ops_path"]).events(OpsEvent.RUN_FAILED)


def test_snapshot_id_illeggibile_e_un_fallimento_non_un_tentativo(percorsi):
    """Senza snapshot_id non si tira a indovinare: il rito si ferma."""
    runner = FakeRunner(Completed(0, "asof_utc : 2026-08-13T00:00:00+00:00\n", ""))
    esito = _rito(percorsi, runner)

    assert esito.exit_code == EXIT_SNAPSHOT_FAILED
    assert esito.snapshot_id is None
    assert len(runner.commands) == 1


def test_decisioni_fallite_hanno_un_codice_proprio(percorsi):
    runner = FakeRunner(
        Completed(0, _build_output(), ""),
        Completed(1, "", "DuplicateEntry: write-once"),
    )
    esito = _rito(percorsi, runner)

    assert esito.exit_code == EXIT_DECISIONS_FAILED
    assert esito.snapshot_id == SNAPSHOT_ID
    assert "DuplicateEntry" in esito.log_path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# PASSO 2: retry a livello di rito su errore ritentabile (pazienza lunga)
# --------------------------------------------------------------------------


def _retry_wait_events(ops: OpsLedger) -> list[dict]:
    """`ops.events()` confronta l'evento per uguaglianza esatta, ma ogni
    attesa ha il proprio numero di tentativo in coda alla chiave (write-once
    per (giorno, evento): più attese ricadono sullo stesso giorno). Qui si
    filtra per prefisso."""
    prefix = f"{OpsEvent.DECISIONS_RETRY_WAIT}:"
    return [e for e in ops.read_all() if e["key"]["event"].startswith(prefix)]


def test_un_errore_ritentabile_fa_ripetere_l_intero_passo_e_poi_riesce(percorsi):
    """Codice dedicato dal client (RETRYABLE_PROCESS_EXIT_CODE): il rito
    attende e riprova l'intero passo, senza toccare lo snapshot già congelato."""
    runner = FakeRunner(
        Completed(0, _build_output(), ""),
        Completed(RETRYABLE_PROCESS_EXIT_CODE, "", "overloaded_error"),
        Completed(0, "decisioni       : 6\n", ""),
    )
    dormite = []
    esito = _rito(percorsi, runner, sleep=dormite.append)

    assert esito.exit_code == EXIT_OK
    assert dormite == [RITUAL_RETRY_WAIT_SECONDS]
    # Lo snapshot NON viene ricostruito al retry: solo il passo 2 si ripete.
    assert len(runner.commands) == 3
    assert runner.commands[0][1].endswith("build_snapshot.py")
    assert runner.commands[1][1].endswith("run_day.py")
    assert runner.commands[2][1].endswith("run_day.py")
    ops = OpsLedger(percorsi["ops_path"])
    assert _retry_wait_events(ops)
    assert not ops.events(OpsEvent.FAILED_DECISIONS)


def test_un_errore_non_ritentabile_non_fa_attendere_il_rito(percorsi):
    """Un codice di uscita diverso da RETRYABLE_PROCESS_EXIT_CODE resta il
    fallimento definitivo di sempre: nessuna attesa, nessun retry."""
    runner = FakeRunner(
        Completed(0, _build_output(), ""),
        Completed(1, "", "DuplicateEntry: write-once"),
    )
    dormite = []
    esito = _rito(percorsi, runner, sleep=dormite.append)

    assert esito.exit_code == EXIT_DECISIONS_FAILED
    assert dormite == []
    assert len(runner.commands) == 2


def test_l_errore_ritentabile_esaurisce_la_finestra_e_ha_un_codice_dedicato(percorsi):
    """Finestra ~45 min: 3 attese da 15 minuti, poi un esito distinto sia da
    skipped_day sia dal fallimento generico — il rito e' partito, l'API no."""
    runner = FakeRunner(
        Completed(0, _build_output(), ""),
        *(
            Completed(RETRYABLE_PROCESS_EXIT_CODE, "", "overloaded_error")
            for _ in range(1 + RITUAL_RETRY_MAX_ATTEMPTS)
        ),
    )
    dormite = []
    esito = _rito(percorsi, runner, sleep=dormite.append)

    assert esito.exit_code == EXIT_DECISIONS_RETRY_EXHAUSTED
    assert esito.snapshot_id == SNAPSHOT_ID
    assert dormite == [RITUAL_RETRY_WAIT_SECONDS] * RITUAL_RETRY_MAX_ATTEMPTS
    assert sum(dormite) == pytest.approx(45 * 60.0)
    # snapshot + 1 tentativo iniziale + RITUAL_RETRY_MAX_ATTEMPTS retry.
    assert len(runner.commands) == 1 + 1 + RITUAL_RETRY_MAX_ATTEMPTS

    ops = OpsLedger(percorsi["ops_path"])
    assert len(_retry_wait_events(ops)) == RITUAL_RETRY_MAX_ATTEMPTS
    falliti = ops.events(OpsEvent.FAILED_DECISIONS)
    assert len(falliti) == 1
    assert "API non ha risposto" in falliti[0]["detail"]
    # skipped_day resta un fatto diverso: nessuno scritto per questa giornata.
    assert not ops.events(OpsEvent.SKIPPED_DAY)


def test_gli_eventi_di_attesa_sono_scritti_nell_ops_ledger_per_ogni_tentativo(percorsi):
    runner = FakeRunner(
        Completed(0, _build_output(), ""),
        *(
            Completed(RETRYABLE_PROCESS_EXIT_CODE, "", "overloaded_error")
            for _ in range(RITUAL_RETRY_MAX_ATTEMPTS)
        ),
        Completed(0, "decisioni       : 6\n", ""),
    )
    esito = _rito(percorsi, runner, sleep=lambda _: None)

    assert esito.exit_code == EXIT_OK
    ops = OpsLedger(percorsi["ops_path"])
    eventi = sorted(e["key"]["event"] for e in _retry_wait_events(ops))
    assert eventi == [
        f"{OpsEvent.DECISIONS_RETRY_WAIT}:{n}" for n in range(1, RITUAL_RETRY_MAX_ATTEMPTS + 1)
    ]
    assert ops.verify().ok


def test_gli_exit_code_restano_distinti_con_il_nuovo_codice():
    assert len(set(EXIT_MEANING)) == len(EXIT_MEANING)
    assert EXIT_DECISIONS_RETRY_EXHAUSTED not in (
        EXIT_OK,
        EXIT_PRECONDITION,
        EXIT_SNAPSHOT_FAILED,
        EXIT_DECISIONS_FAILED,
        EXIT_ALREADY_DONE,
    )


def test_una_giornata_gia_nel_ledger_non_riparte(percorsi):
    trader = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(trader, OGGI)
    runner = FakeRunner()  # nessun comando ammesso

    esito = _rito(percorsi, runner)
    assert esito.exit_code == EXIT_ALREADY_DONE
    assert runner.commands == []


def test_il_rito_marca_i_giorni_mancati_prima_di_decidere(percorsi):
    trader = TraderLedger(percorsi["ledger_path"])
    _scrivi_giornata(trader, OGGI - timedelta(days=3))
    runner = FakeRunner(Completed(0, _build_output(), ""), Completed(0, "", ""))

    esito = _rito(percorsi, runner)

    assert esito.exit_code == EXIT_OK
    assert esito.skipped_marked == (
        OGGI - timedelta(days=2),
        OGGI - timedelta(days=1),
    )
    assert OpsLedger(percorsi["ops_path"]).skipped_days() == list(esito.skipped_marked)
    testo = esito.log_path.read_text(encoding="utf-8")
    assert "NON vengono recuperate" in testo


def test_ora_sbagliata_ferma_il_task_schedulato(percorsi):
    runner = FakeRunner()
    esito = _rito(
        percorsi,
        runner,
        now_utc=datetime(2026, 8, 13, 9, 0, tzinfo=timezone.utc),
        require_configured_hour=True,
    )
    assert esito.exit_code == EXIT_PRECONDITION
    assert runner.commands == []
    assert "09:00 UTC" in esito.detail


def test_ora_sbagliata_a_mano_e_permessa(percorsi):
    runner = FakeRunner(Completed(0, _build_output(), ""), Completed(0, "", ""))
    esito = _rito(
        percorsi,
        runner,
        now_utc=datetime(2026, 8, 13, 9, 0, tzinfo=timezone.utc),
        require_configured_hour=False,
    )
    assert esito.exit_code == EXIT_OK


def test_live_senza_flag_non_parte(percorsi):
    runner = FakeRunner()
    esito = _rito(percorsi, runner, live=True, env={})
    assert esito.exit_code == EXIT_PRECONDITION
    assert runner.commands == []


def test_live_passa_il_flag_al_processo_delle_decisioni(percorsi):
    runner = FakeRunner(Completed(0, _build_output(), ""), Completed(0, "", ""))
    esito = _rito(
        percorsi, runner, live=True, env={"TRADERLAB_ALLOW_LIVE_API": "1"}
    )
    assert esito.exit_code == EXIT_OK
    assert "--live" in runner.commands[1]
    assert "--live" not in runner.commands[0]


def test_gli_exit_code_sono_distinti_e_documentati():
    assert len(set(EXIT_MEANING)) == len(EXIT_MEANING)
    assert EXIT_OK == 0
    # Il codice 1 resta libero: e' quello che Python usa per un'eccezione non
    # gestita, e non deve confondersi con un esito dichiarato del rito.
    assert 1 not in EXIT_MEANING
