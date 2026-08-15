"""scripts/preflight.py — precondizioni del rito, verificate senza rete e senza scheduler.

I sottoprocessi verso Task Scheduler e verso la rete sono sempre iniettati
tramite un `runner` finto: nessun test qui parla davvero con `schtasks`,
PowerShell o Hyperliquid.
"""

from __future__ import annotations

from collections import namedtuple
from datetime import date, timezone
from datetime import datetime as dt
from pathlib import Path

import pytest

from contracts.decision import Action
from contracts.risk import RiskOutcome, RiskRule, RiskVerdict
from ledger.ops_ledger import OpsLedger
from ledger.trader_ledger import LedgerKey, TraderLedger
from scripts.preflight import (
    TaskInfo,
    check_api_key,
    check_disk_and_writable,
    check_freeze_manifest,
    check_ledger_chains,
    check_live_flag,
    check_network_reachable,
    check_task_registration,
    check_user_session,
    format_table,
    query_scheduled_task,
    run_preflight,
)
from tests.factories import make_decision

Completed = namedtuple("Completed", "returncode stdout stderr")


class FakeRunner:
    """Finto esecutore di sottoprocessi: registra le chiamate, restituisce esiti in ordine."""

    def __init__(self, *results: Completed) -> None:
        self._results = list(results)
        self.calls: list[tuple[list[str], dict, dict]] = []

    def __call__(self, command, env=None, **kwargs):
        self.calls.append((list(command), dict(env) if env else {}, kwargs))
        if not self._results:
            raise AssertionError(f"comando inatteso: {command}")
        return self._results.pop(0)


# --------------------------------------------------------------------------
# (a) ANTHROPIC_API_KEY
# --------------------------------------------------------------------------


def test_api_key_assente():
    esito = check_api_key({})
    assert esito.ok is False
    assert "assente" in esito.detail


def test_api_key_formato_inatteso():
    esito = check_api_key({"ANTHROPIC_API_KEY": "not-a-real-key"})
    assert esito.ok is False
    assert "formato inatteso" in esito.detail


def test_api_key_valida_mai_stampa_il_valore():
    chiave = "sk-ant-api03-" + "x" * 40
    esito = check_api_key({"ANTHROPIC_API_KEY": chiave})
    assert esito.ok is True
    assert chiave not in esito.detail
    assert str(len(chiave)) in esito.detail


# --------------------------------------------------------------------------
# (b) risoluzione del flag -Live
# --------------------------------------------------------------------------


def test_live_flag_attivo_da_assegnazione_inline_nel_comando(tmp_path):
    comando = "-Command \"$env:TRADERLAB_ALLOW_LIVE_API='1'; & run_daily.ps1 -Live\""
    env = {"ANTHROPIC_API_KEY": "sk-ant-x"}
    esito = check_live_flag(env, tmp_path / ".env", comando)
    assert esito.ok is True
    assert "fonte: comando" in esito.detail


def test_live_flag_attivo_da_ambiente_di_processo(tmp_path):
    env = {"ANTHROPIC_API_KEY": "sk-ant-x", "TRADERLAB_ALLOW_LIVE_API": "1"}
    esito = check_live_flag(env, tmp_path / ".env", "-Live")
    assert esito.ok is True
    assert "fonte: ambiente di processo" in esito.detail


def test_live_flag_non_attivo_se_switch_assente_dal_comando(tmp_path):
    env = {"ANTHROPIC_API_KEY": "sk-ant-x", "TRADERLAB_ALLOW_LIVE_API": "1"}
    esito = check_live_flag(env, tmp_path / ".env", "-IgnoreConfiguredHour")
    assert esito.ok is False
    assert "switch -Live nel comando: no" in esito.detail


def test_live_flag_non_attivo_se_chiave_assente(tmp_path):
    env = {"TRADERLAB_ALLOW_LIVE_API": "1"}
    esito = check_live_flag(env, tmp_path / ".env", "-Live")
    assert esito.ok is False
    assert "ANTHROPIC_API_KEY presente: no" in esito.detail


def test_env_file_non_e_una_fonte_reale_ma_solo_diagnostica(tmp_path):
    """La trappola delle due notti perse: .env dice una cosa, il rito ne fa un'altra."""
    dotenv = tmp_path / ".env"
    dotenv.write_text("TRADERLAB_ALLOW_LIVE_API=1\n", encoding="utf-8")
    env = {"ANTHROPIC_API_KEY": "sk-ant-x"}  # TRADERLAB_ALLOW_LIVE_API NON e' nell'ambiente

    esito = check_live_flag(env, dotenv, "-Live")

    assert esito.ok is False  # .env non basta: il rito non lo legge
    assert "il rito NON legge .env" in esito.detail
    assert "IGNORATO" in esito.detail


def test_env_file_coerente_non_genera_avviso(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("TRADERLAB_ALLOW_LIVE_API=1\n", encoding="utf-8")
    env = {"ANTHROPIC_API_KEY": "sk-ant-x", "TRADERLAB_ALLOW_LIVE_API": "1"}

    esito = check_live_flag(env, dotenv, "-Live")

    assert esito.ok is True
    assert "ATTENZIONE" not in esito.detail


# --------------------------------------------------------------------------
# (c) rete verso Hyperliquid, in sotto-processo
# --------------------------------------------------------------------------


def test_network_check_iniettato_solo_nel_sottoprocesso(tmp_path):
    runner = FakeRunner(Completed(0, "OK universe=2", ""))
    base_env = {"PATH": "x"}

    esito = check_network_reachable(
        python_executable="python",
        repo_root=tmp_path,
        base_env=base_env,
        runner=runner,
    )

    assert esito.ok is True
    assert base_env == {"PATH": "x"}  # non mutato
    comando, env_usato, kwargs = runner.calls[0]
    assert env_usato["TRADERLAB_ALLOW_NETWORK"] == "1"
    assert env_usato["PATH"] == "x"
    assert kwargs["cwd"] == str(tmp_path)


def test_network_check_fallito(tmp_path):
    runner = FakeRunner(Completed(1, "", "ERRORE: connessione rifiutata"))
    esito = check_network_reachable(
        python_executable="python", repo_root=tmp_path, base_env={}, runner=runner
    )
    assert esito.ok is False
    assert "connessione rifiutata" in esito.detail


def test_network_check_eccezione_non_fa_crashare(tmp_path):
    def runner_che_solleva(command, env=None, **kwargs):
        raise TimeoutError("rete assente")

    esito = check_network_reachable(
        python_executable="python", repo_root=tmp_path, base_env={}, runner=runner_che_solleva
    )
    assert esito.ok is False
    assert "TimeoutError" in esito.detail


# --------------------------------------------------------------------------
# query_scheduled_task / (d) registrazione del task
# --------------------------------------------------------------------------


def test_query_scheduled_task_trovato():
    payload = (
        '{"found":true,"TaskName":"traderLab - rito quotidiano",'
        '"Arguments":"-Command \\"$env:TRADERLAB_ALLOW_LIVE_API=\'1\'; & x -Live\\"",'
        '"LogonType":"Interactive","NextRunTime":"16/08/2026 02:00:00",'
        '"LastRunTime":"15/08/2026 02:00:00","LastTaskResult":"0"}'
    )
    runner = FakeRunner(Completed(0, payload, ""))
    info = query_scheduled_task("*rito*quotidiano*", runner=runner)
    assert info.found is True
    assert "TRADERLAB_ALLOW_LIVE_API" in info.arguments
    assert info.next_run_time == "16/08/2026 02:00:00"


def test_query_scheduled_task_non_trovato():
    runner = FakeRunner(Completed(0, '{"found":false}', ""))
    info = query_scheduled_task("*qualcosa*", runner=runner)
    assert info.found is False


def test_query_scheduled_task_powershell_fallito():
    runner = FakeRunner(Completed(1, "", "powershell non disponibile"))
    info = query_scheduled_task("*qualcosa*", runner=runner)
    assert info.found is False
    assert "powershell non disponibile" in info.error


def test_check_task_registration_ok():
    info = TaskInfo(
        found=True,
        task_name="traderLab - rito quotidiano",
        arguments="-Command \"$env:TRADERLAB_ALLOW_LIVE_API='1'; & run_daily.ps1 -Live\"",
        next_run_time="16/08/2026 02:00:00",
    )
    esito = check_task_registration(info)
    assert esito.ok is True
    assert "16/08/2026 02:00:00" in esito.detail


def test_check_task_registration_manca_l_assegnazione_inline():
    """Questo e' esattamente il bug della prima notte persa: -Live c'e', la var no."""
    info = TaskInfo(found=True, task_name="x", arguments="-Live")
    esito = check_task_registration(info)
    assert esito.ok is False
    assert "TRADERLAB_ALLOW_LIVE_API='1' inline: no" in esito.detail


def test_check_task_registration_non_trovato():
    esito = check_task_registration(TaskInfo(found=False))
    assert esito.ok is False
    assert "nessun task trovato" in esito.detail


# --------------------------------------------------------------------------
# (e) spazio disco e scrivibilita'
# --------------------------------------------------------------------------


def test_disco_e_scrivibile_ok(tmp_path):
    data_dir = tmp_path / "data"
    esito = check_disk_and_writable(tmp_path, data_dir)
    assert esito.ok is True
    assert not (data_dir / ".preflight_write_test").exists()  # ripulito


def test_disco_poco_spazio(tmp_path, monkeypatch):
    from scripts import preflight as preflight_module

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(
        preflight_module.shutil, "disk_usage", lambda path: Usage(0, 0, 100)
    )
    esito = check_disk_and_writable(tmp_path, tmp_path / "data")
    assert esito.ok is False
    assert "liberi" in esito.detail


def test_data_dir_non_scrivibile(tmp_path, monkeypatch):
    from scripts import preflight as preflight_module

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    def rompi_scrittura(*args, **kwargs):
        raise OSError("permesso negato")

    monkeypatch.setattr(Path, "write_text", rompi_scrittura)
    esito = check_disk_and_writable(tmp_path, data_dir)
    assert esito.ok is False
    assert "non scrivibile" in esito.detail


# --------------------------------------------------------------------------
# (f) verify() delle catene ledger
# --------------------------------------------------------------------------


def _verdetto() -> RiskVerdict:
    return RiskVerdict(
        outcome=RiskOutcome.APPROVED,
        rule=RiskRule.NONE,
        action_in=Action.LONG,
        action_out=Action.LONG,
        size_fraction_in=0.05,
        size_fraction_out=0.05,
    )


def test_catene_ledger_ok(tmp_path):
    ledger_path = tmp_path / "season0.jsonl"
    ops_path = tmp_path / "ops.jsonl"
    ledger = TraderLedger(ledger_path)
    giorno = date(2026, 8, 15)
    asof = dt(2026, 8, 15, 0, 0, tzinfo=timezone.utc)
    ledger.append(
        key=LedgerKey.of(giorno, "r1", "BTC"),
        verdict=_verdetto(),
        decision=make_decision("a" * 64, replica_id="r1", timestamp=asof),
        snapshot_id="a" * 64,
        run_id="run-1",
    )
    OpsLedger(ops_path)

    esito = check_ledger_chains(ledger_path, ops_path)
    assert esito.ok is True
    assert "1 righe" in esito.detail


def test_catena_verbali_rotta(tmp_path):
    ledger_path = tmp_path / "season0.jsonl"
    ops_path = tmp_path / "ops.jsonl"
    ledger = TraderLedger(ledger_path)
    ledger.append(
        key=LedgerKey.of(date(2026, 8, 15), "r1", "BTC"),
        verdict=_verdetto(),
        snapshot_id="a" * 64,
        run_id="run-1",
    )
    OpsLedger(ops_path)
    testo = ledger_path.read_text(encoding="utf-8").replace('"seq": 0', '"seq": 0, "manomesso": true', 1)
    ledger_path.write_text(testo, encoding="utf-8")

    esito = check_ledger_chains(ledger_path, ops_path)
    assert esito.ok is False
    assert "ROTTA" in esito.detail


def test_ledger_mancante_e_letto_come_vuoto_ok(tmp_path):
    esito = check_ledger_chains(tmp_path / "season0.jsonl", tmp_path / "ops.jsonl")
    assert esito.ok is True
    assert "0 righe" in esito.detail


# --------------------------------------------------------------------------
# (g) FreezeManifest + i due .ots
# --------------------------------------------------------------------------


def test_freeze_manifest_completo(tmp_path):
    manifest = tmp_path / "manifest.json"
    prereg = tmp_path / "PREREG.md"
    for p in (manifest, manifest.with_name(manifest.name + ".ots"), prereg, prereg.with_name(prereg.name + ".ots")):
        p.write_text("x", encoding="utf-8")

    esito = check_freeze_manifest(manifest, prereg)
    assert esito.ok is True


def test_freeze_manifest_ots_mancante(tmp_path):
    manifest = tmp_path / "manifest.json"
    prereg = tmp_path / "PREREG.md"
    manifest.write_text("x", encoding="utf-8")
    prereg.write_text("x", encoding="utf-8")
    prereg.with_name(prereg.name + ".ots").write_text("x", encoding="utf-8")
    # manca manifest.json.ots

    esito = check_freeze_manifest(manifest, prereg)
    assert esito.ok is False
    assert "manifest.json.ots" in esito.detail


# --------------------------------------------------------------------------
# (h) sessione utente — sempre promemoria, mai FAIL
# --------------------------------------------------------------------------


def test_sessione_utente_e_sempre_promemoria():
    esito = check_user_session(TaskInfo(found=False))
    assert esito.ok is None
    assert esito.status == "PROMEMORIA"


def test_sessione_utente_avvisa_se_logon_type_non_interactive():
    esito = check_user_session(TaskInfo(found=True, logon_type="S4U"))
    assert esito.ok is None
    assert "non e' Interactive" in esito.detail


# --------------------------------------------------------------------------
# Orchestratore: run_preflight + format_table
# --------------------------------------------------------------------------


def test_run_preflight_tutto_verde_e_pronto(tmp_path):
    repo_root = tmp_path
    (repo_root / "manifests").mkdir()
    (repo_root / "docs").mkdir()
    manifest = repo_root / "manifests" / "trader_v0_freeze_manifest.json"
    prereg = repo_root / "docs" / "PREREG_LAB_S0.md"
    for p in (manifest, manifest.with_name(manifest.name + ".ots"), prereg, prereg.with_name(prereg.name + ".ots")):
        p.write_text("x", encoding="utf-8")

    task_payload = (
        '{"found":true,"TaskName":"traderLab - rito quotidiano",'
        '"Arguments":"-Command \\"$env:TRADERLAB_ALLOW_LIVE_API=\'1\'; & x -Live\\"",'
        '"LogonType":"Interactive","NextRunTime":"16/08/2026 02:00:00",'
        '"LastRunTime":"15/08/2026 02:00:00","LastTaskResult":"0"}'
    )
    task_runner = FakeRunner(Completed(0, task_payload, ""))
    process_runner = FakeRunner(Completed(0, "OK universe=2", ""))

    result = run_preflight(
        repo_root=repo_root,
        env={"ANTHROPIC_API_KEY": "sk-ant-" + "x" * 40},
        python_executable="python",
        ledger_path=Path("ledger.jsonl"),
        ops_path=Path("ops.jsonl"),
        data_dir=Path("data"),
        manifest_path=Path("manifests/trader_v0_freeze_manifest.json"),
        prereg_path=Path("docs/PREREG_LAB_S0.md"),
        dotenv_path=Path(".env"),
        task_query_runner=task_runner,
        process_runner=process_runner,
    )

    assert result.ready is True
    assert result.blocking_detail == ""
    testo = format_table(result)
    assert "PRONTO PER STANOTTE: SI" in testo
    assert all(c.status in ("PASS", "PROMEMORIA") for c in result.checks)


def test_run_preflight_riporta_la_prima_causa_di_blocco(tmp_path):
    repo_root = tmp_path
    task_runner = FakeRunner(Completed(0, '{"found":false}', ""))
    process_runner = FakeRunner(Completed(0, "OK universe=2", ""))

    result = run_preflight(
        repo_root=repo_root,
        env={},  # niente ANTHROPIC_API_KEY: (a) fallisce per prima
        python_executable="python",
        ledger_path=Path("ledger.jsonl"),
        ops_path=Path("ops.jsonl"),
        data_dir=Path("data"),
        manifest_path=Path("manifests/x.json"),
        prereg_path=Path("docs/x.md"),
        dotenv_path=Path(".env"),
        task_query_runner=task_runner,
        process_runner=process_runner,
    )

    assert result.ready is False
    assert "(a) ANTHROPIC_API_KEY" in result.blocking_detail
    testo = format_table(result)
    assert "PRONTO PER STANOTTE: NO" in testo


def test_format_table_ha_una_riga_per_precondizione(tmp_path):
    task_runner = FakeRunner(Completed(0, '{"found":false}', ""))
    process_runner = FakeRunner(Completed(1, "", "ERRORE"))
    result = run_preflight(
        repo_root=tmp_path,
        env={},
        python_executable="python",
        ledger_path=Path("ledger.jsonl"),
        ops_path=Path("ops.jsonl"),
        data_dir=Path("data"),
        manifest_path=Path("manifests/x.json"),
        prereg_path=Path("docs/x.md"),
        dotenv_path=Path(".env"),
        task_query_runner=task_runner,
        process_runner=process_runner,
    )
    testo = format_table(result)
    for lettera in "abcdefgh":
        assert f"({lettera})" in testo
