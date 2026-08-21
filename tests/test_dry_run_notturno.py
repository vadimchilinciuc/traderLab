"""`scripts/run_day.py --dry-run` — la strada della notte, meno il client.

Perché questo file esiste. Il 2026-08-20 il preflight del controllo mattutino
rispose **PRONTO PER STANOTTE: SI** con otto righe verdi, e la notte seguente
il rito uscì **4** al primo dei cinque controlli di `run_day.py`: il preflight
verificava che il manifest *esistesse*, non che si *caricasse*. Un controllo
che non percorre la strada del rito non sta verificando il rito (DIAGNOSI_G1
§1-bis, reperto A).

`--dry-run` è quella strada: le stesse cinque guardie, lo stesso manifest, lo
stesso ledger, e un arresto **un passo prima** dell'istanziazione del client.
Quello che questi test devono difendere sono due proprietà opposte e
ugualmente necessarie:

1. che il dry run **rifiuti** esattamente quando la notte rifiuterebbe — se
   tacesse sarebbe il PASS finto di prima, con un nome nuovo;
2. che il dry run **non chiami mai il modello** e **non scriva mai una riga**
   — se lo facesse, il controllo del mattino consumerebbe budget di stagione
   e sporcherebbe il ledger ogni giorno alle 07:00.

I sottoprocessi qui sono veri (`sys.executable`), ma non toccano né la rete né
l'API: il ramo si ferma prima che un client esista. Nessun test di questo file
richiede `ANTHROPIC_API_KEY`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.factories import PREZZI_OPUS5, manifest_con_prezzi, prezzi_senza

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_DAY = REPO_ROOT / "scripts" / "run_day.py"
PIN = "a" * 40


def _scrivi_manifest(path: Path, manifest) -> Path:
    """Un documento di pin sintetico, nella forma che `load_pinned_manifest` legge."""
    documento = {
        "freeze_manifest": manifest.canonical_payload(),
        "freeze_id": manifest.freeze_id,
        "rito_config": {"nota": "documento sintetico per i test"},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(documento, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _pinnato(**kwargs):
    parametri = {
        "pin_commit": PIN,
        "season_budget_usd": 89.90,
        "season_expected_days": 28,
        "prezzi": PREZZI_OPUS5,
    }
    parametri.update(kwargs)
    return manifest_con_prezzi(datetime.now(tz=timezone.utc), **parametri)


def _dry_run(tmp_path: Path, manifest_path: Path, *, extra: list[str] | None = None):
    """Esegue il comando del preflight. Rete spenta, nessuna chiave in ambiente.

    `TRADERLAB_ALLOW_LIVE_API` entra **solo** qui, nell'ambiente di questo
    sotto-processo, esattamente come fa `scripts/preflight.py`: è il flag che
    apre il ramo delle cinque guardie, e il ramo si ferma comunque prima di
    chiamare qualcuno.
    """
    ambiente = {
        k: v
        for k, v in os.environ.items()
        if k not in ("TRADERLAB_ALLOW_NETWORK", "ANTHROPIC_API_KEY")
    }
    ambiente["TRADERLAB_ALLOW_LIVE_API"] = "1"
    comando = [
        sys.executable,
        str(RUN_DAY),
        "--dry-run",
        "--live",
        "--manifest",
        str(manifest_path),
        "--ledger",
        str(tmp_path / "ledger" / "segmento.jsonl"),
        "--toolcalls-dir",
        str(tmp_path / "toolcalls"),
    ]
    comando.extend(extra or [])
    return subprocess.run(
        comando,
        cwd=str(REPO_ROOT),
        env=ambiente,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )


# --------------------------------------------------------------------------
# Il lato verde: le cinque guardie passano e il client non nasce
# --------------------------------------------------------------------------


def test_un_manifest_pinnato_e_completo_passa_le_cinque_guardie(tmp_path):
    manifest = _scrivi_manifest(tmp_path / "pinnato.json", _pinnato())

    esito = _dry_run(tmp_path, manifest)

    assert esito.returncode == 0, esito.stderr
    assert "dry-run" in esito.stdout
    assert "nessun client" in esito.stdout
    # I valori che giustificano il verde sono stampati, non sottintesi.
    assert "modello pinnato :" in esito.stdout
    assert "freeze_id       :" in esito.stdout
    assert "termini stagione:" in esito.stdout
    assert "spesa stagione  :" in esito.stdout


def test_il_dry_run_non_scrive_nulla(tmp_path):
    """Gira ogni mattina: se scrivesse, sporcherebbe il ledger 28 volte a stagione.

    Il ledger dei verbali non deve **esistere** dopo la passata. `TraderLedger`
    crea la cartella nel costruttore e apre il file solo al primo `append`: il
    dry run si ferma molto prima, e questo test è ciò che tiene ferma quella
    proprietà.
    """
    manifest = _scrivi_manifest(tmp_path / "pinnato.json", _pinnato())

    esito = _dry_run(tmp_path, manifest)

    assert esito.returncode == 0, esito.stderr
    assert not (tmp_path / "ledger" / "segmento.jsonl").exists()
    assert list((tmp_path / "toolcalls").glob("*.jsonl")) == []


def test_il_dry_run_non_chiede_lo_snapshot(tmp_path):
    """Di mattina lo snapshot di stanotte non esiste ancora.

    Pretenderlo renderebbe il controllo impossibile da eseguire nell'unico
    momento in cui serve — e una precondizione inventata è un FAIL falso, che
    insegna a ignorare la tabella tanto quanto un PASS falso.
    """
    manifest = _scrivi_manifest(tmp_path / "pinnato.json", _pinnato())

    esito = _dry_run(tmp_path, manifest)

    assert esito.returncode == 0, esito.stderr
    assert "--snapshot-id" not in esito.stderr


# --------------------------------------------------------------------------
# Il lato rosso: rifiuta dove rifiuterebbe la notte
# --------------------------------------------------------------------------


def test_il_freeze_id_divergente_e_rifiutato_come_di_notte(tmp_path):
    """Il rifiuto letterale della notte del 2026-08-21, anticipato di 17 ore."""
    manifest = _pinnato()
    documento = {
        "freeze_manifest": manifest.canonical_payload(),
        # Il valore dichiarato non corrisponde al ricalcolo: è il caso del
        # manifest di Stagione 0 sotto il contratto evoluto.
        "freeze_id": "f" * 64,
        "rito_config": {},
    }
    percorso = tmp_path / "divergente.json"
    percorso.write_text(json.dumps(documento), encoding="utf-8")

    esito = _dry_run(tmp_path, percorso)

    assert esito.returncode == 2
    assert "freeze_id divergente" in esito.stderr


def test_il_pin_commit_assente_e_rifiutato(tmp_path):
    manifest = _scrivi_manifest(tmp_path / "non_pinnato.json", _pinnato(pin_commit=""))

    esito = _dry_run(tmp_path, manifest)

    assert esito.returncode == 2
    assert "pin_commit" in esito.stderr


def test_un_termine_economico_mancante_e_rifiutato(tmp_path):
    """D5: il listino incompleto non è un conto approssimativo, è nessun conto."""
    manifest = _scrivi_manifest(
        tmp_path / "senza_listino.json",
        _pinnato(prezzi=prezzi_senza("price_per_mtok_output")),
    )

    esito = _dry_run(tmp_path, manifest)

    assert esito.returncode == 2
    assert "guardia economica" in esito.stderr


def test_un_manifest_assente_e_rifiutato(tmp_path):
    esito = _dry_run(tmp_path, tmp_path / "non_esiste.json")

    assert esito.returncode == 2
    assert "assente" in esito.stderr


# --------------------------------------------------------------------------
# Le due precondizioni del flag
# --------------------------------------------------------------------------


def test_il_dry_run_senza_live_e_un_errore_di_uso(tmp_path):
    """Le cinque guardie vivono nel ramo `--live`: un dry run mock non verifica nulla."""
    manifest = _scrivi_manifest(tmp_path / "pinnato.json", _pinnato())
    esito = subprocess.run(
        [sys.executable, str(RUN_DAY), "--dry-run", "--manifest", str(manifest)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert esito.returncode == 2
    assert "--dry-run" in esito.stderr and "--live" in esito.stderr


def test_una_giornata_vera_pretende_ancora_lo_snapshot():
    """`--snapshot-id` resta obbligatorio fuori dal dry run.

    Renderlo opzionale per il preflight non doveva renderlo opzionale per la
    notte: una giornata senza snapshot dichiarato è la porta da cui rientra la
    lettura di dati non congelati (CLAUDE.md §5 e §7).
    """
    esito = subprocess.run(
        [sys.executable, str(RUN_DAY)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert esito.returncode == 2
    assert "--snapshot-id" in esito.stderr


# --------------------------------------------------------------------------
# Il manifest pinnato del RUN2, quello vero
# --------------------------------------------------------------------------


MANIFEST_RUN2 = REPO_ROOT / "manifests" / "trader_v1_run2_freeze_manifest.json"


@pytest.mark.skipif(
    not MANIFEST_RUN2.exists(), reason="il manifest pinnato del RUN2 non è nel repo"
)
def test_il_manifest_pinnato_del_run2_e_raggiungibile_e_verde(tmp_path):
    """Il reperto A, in forma di test: la configurazione pinnata è raggiungibile.

    Questo test guarda il manifest **committato**, non una copia sintetica, ed
    è deliberato: il difetto del 2026-08-21 non era che il codice sbagliasse a
    caricare un manifest, era che il manifest giusto non fosse raggiungibile da
    nessun percorso del rito. Un test su un manifest finto non l'avrebbe visto.

    Se un giorno questo test diventasse rosso perché il contratto
    `FreezeManifest` è cambiato sotto il pin, quel rosso è l'informazione che
    serve: significa che il `freeze_id` firmato non è più riproducibile, cioè
    che la stagione in corso non può più girare — la stessa cosa che il
    2026-08-21 si è scoperta a mezzanotte.
    """
    esito = _dry_run(tmp_path, MANIFEST_RUN2)

    assert esito.returncode == 0, esito.stderr
    assert "claude-opus-5" in esito.stdout
    assert "2136b199210dd9f231ba8faef3bd764161585167256640373c4ddc1e23d03f02" in esito.stdout
    # Ledger nuovo e vuoto: la spesa del segmento parte da zero.
    assert "$0.00" in esito.stdout or "0.00" in esito.stdout
