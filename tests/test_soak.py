"""Soak multi-giorno: 7 giornate consecutive end-to-end, senza rete.

Una giornata sola non dice se il Lab regge una stagione. Le proprietà che
contano — catena del ledger che non si rompe mai, write-once che tiene anche a
distanza di giorni, turnover e flip rate che si misurano **tra** giornate,
e-process che accumula su differenze appaiate — sono tutte proprietà
longitudinali: su un giorno solo sono invisibili o banalmente vere.

Il soak simula il rito reale: **un processo per giornata**. Runner nuovo, tool
log nuovo, client nuovi, stato di portafoglio nuovo. Le uniche cose che
attraversano i giorni sono ciò che deve attraversarli: il ledger su disco e
l'accumulatore di telemetria.

Zero rete, zero API key: solo MockLLM.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from arena.config import ArenaConfig, DEFAULT_REPLICA_IDS
from arena.llm_client import CallBudget, LLMResponse, MockLLM
from arena.runner import DailyRunner, RunnerError
from contracts.decision import Action
from contracts.snapshot import MarketSnapshot
from ledger.eprocess import (
    BettingEProcess,
    KillVerdict,
    evaluate_kill_criterion,
)
from ledger.telemetry import BehavioralTelemetry
from ledger.trader_ledger import DuplicateEntry, TraderLedger
from toolserver.store import SnapshotStore
from toolserver.toollog import ToolCallLog
from tests.factories import ASOF, make_snapshot

SOAK_DAYS = 7
ASSETS_PER_DAY = 2
ENTRIES_PER_DAY = len(DEFAULT_REPLICA_IDS) * ASSETS_PER_DAY


# --------------------------------------------------------------------------
# Client: MockLLM che alterna direzione di giorno in giorno
# --------------------------------------------------------------------------


class AlternatingMockLLM:
    """MockLLM che va long nei giorni pari e short in quelli dispari.

    Serve a esercitare i contatori che esistono **solo** tra giornate: senza un
    cambio di segno, flip e transizioni restano zero e il contatore non viene
    mai messo alla prova. La regola di alternanza non è una strategia: è un
    generatore di transizioni deterministico.
    """

    def __init__(self, day_index: int, budget: CallBudget | None = None) -> None:
        self._inner = MockLLM(budget=budget or CallBudget(max_calls=1000))
        self._go_short = day_index % 2 == 1
        self.model_version = self._inner.model_version

    @property
    def budget(self) -> CallBudget:
        return self._inner.budget

    def complete(self, *, system, messages, tools) -> LLMResponse:
        response = self._inner.complete(system=system, messages=messages, tools=tools)
        if not self._go_short:
            return response
        content = []
        for block in response.content:
            payload = getattr(block, "input", None)
            if getattr(block, "name", None) == "submit_decision" and payload:
                mutated = dict(payload)
                if mutated.get("action") == "long":
                    mutated["action"] = "short"
                block = replace(block, input=mutated)
            content.append(block)
        return LLMResponse(
            content=content,
            stop_reason=response.stop_reason,
            model=response.model,
        )


# --------------------------------------------------------------------------
# Esecuzione del soak
# --------------------------------------------------------------------------


def _snapshot_for(day: int) -> MarketSnapshot:
    """Snapshot sintetico del giorno: stesso costruttore, asof traslato."""
    return make_snapshot(ASOF + timedelta(days=day))


def _run_day(
    *,
    store: SnapshotStore,
    ledger: TraderLedger,
    tmp_path,
    day: int,
    telemetry: BehavioralTelemetry,
    snapshot: MarketSnapshot,
):
    """Una giornata come la eseguirebbe il rito: processo nuovo, log nuovo."""
    run_id = f"soak-d{day}"
    tool_log = ToolCallLog(tmp_path / "toolcalls", run_id=run_id)
    runner = DailyRunner(
        store=store,
        ledger=ledger,
        tool_log=tool_log,
        client_factory=lambda replica_id: AlternatingMockLLM(day),
        config=ArenaConfig(),
        context_git_sha="abcdef1",
    )
    return runner.run_day(snapshot.snapshot_id, run_id=run_id, telemetry=telemetry)


@pytest.fixture
def soak(tmp_path):
    """7 giornate consecutive. Ledger e telemetria sono gli unici stati condivisi."""
    store = SnapshotStore(tmp_path / "snapshots")
    ledger = TraderLedger(tmp_path / "ledger" / "soak.jsonl")
    telemetry = BehavioralTelemetry(DEFAULT_REPLICA_IDS)

    snapshots = []
    results = []
    for day in range(SOAK_DAYS):
        snapshot = _snapshot_for(day)
        store.save(snapshot)
        snapshots.append(snapshot)
        results.append(
            _run_day(
                store=store,
                ledger=ledger,
                tmp_path=tmp_path,
                day=day,
                telemetry=telemetry,
                snapshot=snapshot,
            )
        )
    return {
        "store": store,
        "ledger": ledger,
        "telemetry": telemetry,
        "results": results,
        "snapshots": snapshots,
        "tmp_path": tmp_path,
    }


# --------------------------------------------------------------------------
# Le 7 giornate girano davvero
# --------------------------------------------------------------------------


def test_sette_giornate_producono_verbali_conformi(soak):
    results = soak["results"]
    assert len(results) == SOAK_DAYS
    for day, result in enumerate(results):
        assert result.malformed_count == 0, f"giorno {day}: verbali malformati"
        assert len(result.decisions) == ENTRIES_PER_DAY
        atteso = Action.SHORT if day % 2 else Action.LONG
        assert {d.action for d in result.decisions} == {atteso}


def test_ogni_giornata_ha_il_suo_snapshot_e_il_suo_asof(soak):
    ids = {s.snapshot_id for s in soak["snapshots"]}
    assert len(ids) == SOAK_DAYS, "due giornate condividono lo snapshot"
    for day, result in enumerate(soak["results"]):
        assert result.asof_utc == ASOF + timedelta(days=day)
        assert result.snapshot_id == soak["snapshots"][day].snapshot_id


# --------------------------------------------------------------------------
# Ledger: catena integra su 7 giorni, write-once che tiene nel tempo
# --------------------------------------------------------------------------


def test_la_catena_del_ledger_regge_sette_giornate(soak):
    ledger = soak["ledger"]
    verifica = ledger.verify()
    assert verifica.ok, verifica.detail
    assert verifica.entries_checked == SOAK_DAYS * ENTRIES_PER_DAY
    assert len(ledger) == SOAK_DAYS * ENTRIES_PER_DAY


def test_le_chiavi_coprono_sette_giorni_distinti_senza_duplicati(soak):
    entries = soak["ledger"].read_all()
    chiavi = [
        (e["key"]["day"], e["key"]["replica_id"], e["key"]["asset"]) for e in entries
    ]
    assert len(chiavi) == len(set(chiavi))
    assert len({giorno for giorno, _, _ in chiavi}) == SOAK_DAYS


def test_riesecuzione_di_una_giornata_gia_scritta_e_rifiutata(soak):
    """Write-once: un secondo giro sullo stesso giorno non aggiorna, rifiuta."""
    ledger = soak["ledger"]
    prima = len(ledger)
    giorno_ripetuto = 3
    with pytest.raises(DuplicateEntry, match="write-once"):
        _run_day(
            store=soak["store"],
            ledger=ledger,
            tmp_path=soak["tmp_path"],
            day=giorno_ripetuto,
            telemetry=BehavioralTelemetry(DEFAULT_REPLICA_IDS),
            snapshot=soak["snapshots"][giorno_ripetuto],
        )
    # Il rifiuto non lascia macerie: nessuna riga nuova, catena ancora integra.
    assert len(ledger) == prima
    assert ledger.verify().ok


def test_il_ledger_riletto_da_disco_conosce_le_chiavi_gia_scritte(soak):
    """Il processo del giorno dopo riparte da zero e deve ricordare comunque."""
    ricaricato = TraderLedger(soak["ledger"].path)
    assert len(ricaricato) == SOAK_DAYS * ENTRIES_PER_DAY
    assert ricaricato.head_hash == soak["ledger"].head_hash
    assert ricaricato.verify().ok


# --------------------------------------------------------------------------
# Telemetria: accumula tra le giornate
# --------------------------------------------------------------------------


def test_la_telemetria_accumula_sulle_sette_giornate(soak):
    metriche = soak["telemetry"].all_metrics()
    assert set(metriche) == set(DEFAULT_REPLICA_IDS)
    for m in metriche.values():
        assert m.decisions_total == SOAK_DAYS * ASSETS_PER_DAY
        assert m.decisions_directional == SOAK_DAYS * ASSETS_PER_DAY
        assert m.malformed_total == 0
        assert m.refusals_total == 0
        assert m.mean_confidence == pytest.approx(0.58)


def test_flip_e_turnover_esistono_solo_perche_la_telemetria_attraversa_i_giorni(soak):
    """Con un accumulatore per giornata questi numeri sarebbero zero per costruzione."""
    for m in soak["telemetry"].all_metrics().values():
        # 6 transizioni per asset (giorno 0 apre, i 6 successivi invertono).
        assert m.flips == (SOAK_DAYS - 1) * ASSETS_PER_DAY
        assert m.flip_rate == pytest.approx(1.0)
        # 0.05 all'apertura + 0.10 per ogni inversione, su due asset.
        atteso = (0.05 + (SOAK_DAYS - 1) * 0.10) * ASSETS_PER_DAY
        assert m.turnover == pytest.approx(atteso)


def test_una_telemetria_nuova_ogni_giorno_non_vede_nessun_flip(soak):
    """Regressione del difetto: senza accumulatore condiviso il flip rate è cieco.

    Stesse identiche giornate del soak, ma con un accumulatore nuovo ogni
    giorno: le inversioni ci sono comunque, e nessuna viene vista. È questo il
    motivo per cui `run_day` accetta una telemetria dall'esterno.
    """
    ledger = TraderLedger(soak["tmp_path"] / "ledger" / "isolata.jsonl")
    per_giorno = []
    for day in range(3):
        isolata = BehavioralTelemetry(DEFAULT_REPLICA_IDS)
        _run_day(
            store=soak["store"],
            ledger=ledger,
            tmp_path=soak["tmp_path"] / f"iso{day}",
            day=day,
            telemetry=isolata,
            snapshot=soak["snapshots"][day],
        )
        per_giorno.append(isolata)

    for day, isolata in enumerate(per_giorno):
        for m in isolata.all_metrics().values():
            assert m.decisions_total == ASSETS_PER_DAY
            assert m.flips == 0, f"giorno {day}: flip visto da una telemetria cieca"
            assert m.flip_rate == pytest.approx(0.0)
            # Ogni giornata crede di aprire da zero: mai una chiusura.
            assert m.turnover == pytest.approx(0.05 * ASSETS_PER_DAY)

    # Le stesse tre giornate, con l'accumulatore condiviso, le inversioni le vede.
    condivisa = soak["telemetry"].all_metrics()
    assert all(m.flips > 0 for m in condivisa.values())


def test_la_dispersione_resta_nulla_ogni_giorno(soak):
    """Repliche identiche + mock deterministico: la dispersione è zero, sempre."""
    for day, result in enumerate(soak["results"]):
        d = result.dispersion
        assert d is not None and not d.is_degenerate
        assert d.replicas == len(DEFAULT_REPLICA_IDS)
        assert d.assets_compared == ASSETS_PER_DAY
        assert d.action_disagreement == pytest.approx(0.0), f"giorno {day}"
        assert d.confidence_dispersion == pytest.approx(0.0), f"giorno {day}"
        assert d.size_dispersion == pytest.approx(0.0), f"giorno {day}"


def test_gli_input_restano_identici_tra_repliche_ogni_giorno(soak):
    for day, result in enumerate(soak["results"]):
        for asset in ("BTC", "ETH"):
            impronte = {
                result.request_fingerprints[rid][asset] for rid in DEFAULT_REPLICA_IDS
            }
            assert len(impronte) == 1, f"giorno {day}, {asset}: input divergenti"


# --------------------------------------------------------------------------
# Il run_id del ledger e quello del tool log non possono divergere
# --------------------------------------------------------------------------


def test_un_run_id_diverso_dal_tool_log_e_un_errore_pulito(soak, tmp_path):
    """Regressione: `tool_calls_ref` viene dal tool log, `run_id` dal ledger.

    Se divergono, ogni verbale della giornata punta al file di un'altra
    giornata — e lo fa in silenzio.
    """
    ledger = TraderLedger(tmp_path / "ledger" / "mismatch.jsonl")
    runner = DailyRunner(
        store=soak["store"],
        ledger=ledger,
        tool_log=ToolCallLog(tmp_path / "toolcalls", run_id="soak-d0"),
        client_factory=lambda replica_id: MockLLM(),
        context_git_sha="abcdef1",
    )
    with pytest.raises(RunnerError, match="non corrisponde al tool log"):
        runner.run_day(soak["snapshots"][0].snapshot_id, run_id="soak-d1")
    assert len(ledger) == 0


def test_i_tool_call_di_ogni_giornata_stanno_nel_file_di_quella_giornata(soak):
    for day in range(SOAK_DAYS):
        log = ToolCallLog(soak["tmp_path"] / "toolcalls", run_id=f"soak-d{day}")
        entries = log.read_all()
        assert entries, f"giorno {day}: nessuna tool call registrata"
        assert {e["run_id"] for e in entries} == {f"soak-d{day}"}
        assert {e["snapshot_id"] for e in entries} == {
            soak["snapshots"][day].snapshot_id
        }
        assert {e["replica_id"] for e in entries} == set(DEFAULT_REPLICA_IDS)


# --------------------------------------------------------------------------
# E-process su differenze appaiate sintetiche
# --------------------------------------------------------------------------


def _synthetic_paired_differences(results) -> list[float]:
    """Differenze giornaliere appaiate agente-macchina, SINTETICHE.

    In Fase 0 la gamba meccanica **non esiste**: questi numeri non misurano
    nulla del mercato. Servono a verificare che il capitale dell'e-process
    avanzi giorno per giorno quando le differenze sono coerentemente positive.
    Sono derivati dall'esposizione lorda decisa, così da avere una serie
    deterministica e legata all'esecuzione reale del soak.
    """
    differenze = []
    for result in results:
        lorda = sum(abs(d.signed_size) for d in result.decisions)
        differenze.append(round(lorda / 100.0, 6))
    return differenze


def test_e_process_avanza_giorno_per_giorno(soak):
    differenze = _synthetic_paired_differences(soak["results"])
    assert len(differenze) == SOAK_DAYS
    assert all(d > 0.0 for d in differenze)

    e = BettingEProcess(bound=0.05)  # bound dichiarato PRIMA di guardare i dati
    storia = [e.update(d) for d in differenze]

    assert e.n_observations == SOAK_DAYS
    assert e.n_truncated == 0
    # Il primo giorno non muove capitale: la scommessa parte da lambda = 0.
    assert storia[0] == pytest.approx(1.0)
    # Dal secondo in poi il capitale cresce in modo monotono.
    assert all(b >= a for a, b in zip(storia, storia[1:]))
    assert storia[-1] > storia[1]
    assert e.max_e_value == pytest.approx(e.e_value)
    # Sette giorni di differenze minuscole non bastano a rifiutare nulla.
    assert not e.rejected


def test_e_process_tronca_le_differenze_oltre_il_bound_dichiarato(soak):
    differenze = _synthetic_paired_differences(soak["results"])
    e = BettingEProcess(bound=0.0001)
    e.update_many(differenze)
    assert e.n_truncated == SOAK_DAYS


def test_kill_criterion_su_sette_giorni_dice_dati_insufficienti(soak):
    """La finestra pre-registrata è 20: sette giorni non si commentano."""
    gaps = _synthetic_paired_differences(soak["results"])
    dispersioni = [r.dispersion.action_disagreement for r in soak["results"]]
    esito = evaluate_kill_criterion(gaps, dispersioni)
    assert esito.verdict is KillVerdict.INSUFFICIENT_DATA
    assert esito.window_used == SOAK_DAYS
    assert not esito.is_kill
