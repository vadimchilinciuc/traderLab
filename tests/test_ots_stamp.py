"""scripts/ots_stamp.py — stamper OpenTimestamps locale, senza otsclient.

I test unitari mockano i calendar (nessuna rete, nessuna API key). Il test
di integrazione parla con i calendar pubblici veri e gira solo dietro
`TRADERLAB_ALLOW_NETWORK=1`, come da disciplina di rete del Lab (CLAUDE.md
§7): la suite normale (`uv run pytest`) resta verde senza rete.
"""

from __future__ import annotations

import os

import pytest

from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation
from opentimestamps.core.serialize import StreamDeserializationContext
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

from scripts.ots_stamp import (
    DEFAULT_CALENDAR_URLS,
    StampingError,
    network_allowed,
    stamp_file,
    upgrade_file,
)


class FakeCalendar:
    """Sostituto di RemoteCalendar: nessuna richiesta HTTP.

    `on_submit`/`on_get_timestamp` sono funzioni (digest) -> Timestamp,
    oppure un'eccezione da sollevare, così ogni test controlla esattamente
    cosa "risponde" ciascun calendar.
    """

    def __init__(self, url, on_submit=None, on_get_timestamp=None):
        self.url = url
        self._on_submit = on_submit
        self._on_get_timestamp = on_get_timestamp

    def submit(self, digest, timeout=None):
        if isinstance(self._on_submit, Exception):
            raise self._on_submit
        return self._on_submit(digest)

    def get_timestamp(self, commitment, timeout=None):
        if isinstance(self._on_get_timestamp, Exception):
            raise self._on_get_timestamp
        return self._on_get_timestamp(commitment)


def _pending_response(digest, uri):
    ts = Timestamp(digest)
    ts.attestations.add(PendingAttestation(uri))
    return ts


def _bitcoin_response(digest, height=800_000):
    ts = Timestamp(digest)
    ts.attestations.add(BitcoinBlockHeaderAttestation(height))
    return ts


def _factory_from_map(calendars: dict[str, FakeCalendar]):
    return lambda url: calendars[url]


def test_network_allowed_legge_solo_la_env_var(monkeypatch):
    monkeypatch.delenv("TRADERLAB_ALLOW_NETWORK", raising=False)
    assert network_allowed() is False

    monkeypatch.setenv("TRADERLAB_ALLOW_NETWORK", "1")
    assert network_allowed() is True

    monkeypatch.setenv("TRADERLAB_ALLOW_NETWORK", "0")
    assert network_allowed() is False


def test_stamp_scrive_un_ots_valido(tmp_path):
    target = tmp_path / "manifest.json"
    target.write_text('{"hello": "world"}', encoding="utf-8")

    calendars = {
        url: FakeCalendar(url, on_submit=lambda digest, u=url: _pending_response(digest, u))
        for url in DEFAULT_CALENDAR_URLS
    }

    result = stamp_file(target, calendar_factory=_factory_from_map(calendars))

    assert result.ots_path == target.with_name("manifest.json.ots")
    assert result.ots_path.exists()
    assert set(result.succeeded) == set(DEFAULT_CALENDAR_URLS)
    assert result.failed == ()

    raw = result.ots_path.read_bytes()
    assert raw.startswith(DetachedTimestampFile.HEADER_MAGIC)

    with open(result.ots_path, "rb") as fd:
        detached = DetachedTimestampFile.deserialize(StreamDeserializationContext(fd))
    assert detached.file_digest.hex() == result.digest_hex

    pending_uris = {
        attestation.uri
        for _, attestation in detached.timestamp.all_attestations()
        if isinstance(attestation, PendingAttestation)
    }
    assert pending_uris == set(DEFAULT_CALENDAR_URLS)


def test_stamp_fallisce_sotto_min_responses_e_non_scrive_file(tmp_path):
    target = tmp_path / "prereg.md"
    target.write_text("# PREREG", encoding="utf-8")

    calendars = {
        DEFAULT_CALENDAR_URLS[0]: FakeCalendar(
            DEFAULT_CALENDAR_URLS[0],
            on_submit=lambda digest: _pending_response(digest, DEFAULT_CALENDAR_URLS[0]),
        ),
        DEFAULT_CALENDAR_URLS[1]: FakeCalendar(
            DEFAULT_CALENDAR_URLS[1], on_submit=ConnectionError("timeout")
        ),
        DEFAULT_CALENDAR_URLS[2]: FakeCalendar(
            DEFAULT_CALENDAR_URLS[2], on_submit=ConnectionError("timeout")
        ),
    }

    with pytest.raises(StampingError, match=r"1/2"):
        stamp_file(target, calendar_factory=_factory_from_map(calendars))

    assert not target.with_name("prereg.md.ots").exists()


def test_stamp_non_sovrascrive_un_ots_esistente(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("dato", encoding="utf-8")
    (tmp_path / "file.txt.ots").write_bytes(b"gia' presente")

    calendars = {
        url: FakeCalendar(url, on_submit=lambda digest, u=url: _pending_response(digest, u))
        for url in DEFAULT_CALENDAR_URLS
    }

    with pytest.raises(FileExistsError):
        stamp_file(target, calendar_factory=_factory_from_map(calendars))


def _stamp_with_pending(tmp_path, name="doc.txt"):
    target = tmp_path / name
    target.write_text("contenuto", encoding="utf-8")
    calendars = {
        url: FakeCalendar(url, on_submit=lambda digest, u=url: _pending_response(digest, u))
        for url in DEFAULT_CALENDAR_URLS
    }
    stamp_file(target, calendar_factory=_factory_from_map(calendars))
    return target


def test_upgrade_senza_novita_resta_pending(tmp_path):
    target = _stamp_with_pending(tmp_path)

    # Ogni calendar risponde con lo stesso identico PendingAttestation:
    # nessuna attestazione nuova, quindi nessun cambiamento.
    calendars = {
        url: FakeCalendar(
            url, on_get_timestamp=lambda commitment, u=url: _pending_response(commitment, u)
        )
        for url in DEFAULT_CALENDAR_URLS
    }

    before = target.with_name(target.name + ".ots").read_bytes()
    result = upgrade_file(target, calendar_factory=_factory_from_map(calendars))
    after = target.with_name(target.name + ".ots").read_bytes()

    assert result.changed is False
    assert result.complete is False
    assert result.upgraded_from == ()
    assert len(result.still_pending) == len(DEFAULT_CALENDAR_URLS)
    assert before == after


def test_upgrade_promuove_a_confermato_bitcoin_e_riscrive_il_file(tmp_path):
    target = _stamp_with_pending(tmp_path)

    calendars = {
        url: FakeCalendar(url, on_get_timestamp=lambda commitment: _bitcoin_response(commitment))
        for url in DEFAULT_CALENDAR_URLS
    }

    result = upgrade_file(target, calendar_factory=_factory_from_map(calendars))

    assert result.changed is True
    assert result.complete is True
    # I 3 calendar attestano lo stesso blocco Bitcoin: dopo il primo merge
    # l'attestazione è già presente, quindi solo il primo calendar che
    # risponde con la novità finisce in upgraded_from (deduplica corretta,
    # non un bug — non avrebbe senso contare 3 volte la stessa conferma).
    assert 1 <= len(result.upgraded_from) <= len(DEFAULT_CALENDAR_URLS)

    ots_path = target.with_name(target.name + ".ots")
    with open(ots_path, "rb") as fd:
        detached = DetachedTimestampFile.deserialize(StreamDeserializationContext(fd))
    assert any(
        isinstance(attestation, BitcoinBlockHeaderAttestation)
        for _, attestation in detached.timestamp.all_attestations()
    )


def test_upgrade_accetta_sia_il_file_originale_che_il_ots(tmp_path):
    target = _stamp_with_pending(tmp_path)
    ots_path = target.with_name(target.name + ".ots")

    calendars = {
        url: FakeCalendar(
            url, on_get_timestamp=lambda commitment, u=url: _pending_response(commitment, u)
        )
        for url in DEFAULT_CALENDAR_URLS
    }

    result_from_original = upgrade_file(target, calendar_factory=_factory_from_map(calendars))
    result_from_ots = upgrade_file(ots_path, calendar_factory=_factory_from_map(calendars))

    assert result_from_original.complete == result_from_ots.complete is False


def test_upgrade_commitment_not_found_e_pending_non_un_errore(tmp_path):
    from opentimestamps.calendar import CommitmentNotFoundError

    target = _stamp_with_pending(tmp_path)
    calendars = {
        url: FakeCalendar(
            url, on_get_timestamp=CommitmentNotFoundError("Pending confirmation in Bitcoin blockchain")
        )
        for url in DEFAULT_CALENDAR_URLS
    }

    result = upgrade_file(target, calendar_factory=_factory_from_map(calendars))

    assert result.changed is False
    assert result.failed == ()
    assert len(result.still_pending) == len(DEFAULT_CALENDAR_URLS)


def test_upgrade_registra_solo_errori_veri_come_fallimento(tmp_path):
    target = _stamp_with_pending(tmp_path)
    calendars = {
        url: FakeCalendar(url, on_get_timestamp=ConnectionError("timeout"))
        for url in DEFAULT_CALENDAR_URLS
    }

    result = upgrade_file(target, calendar_factory=_factory_from_map(calendars))

    assert result.changed is False
    assert result.still_pending == ()
    assert len(result.failed) == len(DEFAULT_CALENDAR_URLS)


@pytest.mark.skipif(
    os.environ.get("TRADERLAB_ALLOW_NETWORK") != "1",
    reason="integrazione con i calendar OpenTimestamps veri: richiede TRADERLAB_ALLOW_NETWORK=1",
)
def test_integrazione_stamp_reale_contro_i_calendar_pubblici(tmp_path):
    target = tmp_path / "documento_reale.txt"
    target.write_text("traderLab OTS integration test", encoding="utf-8")

    result = stamp_file(target)

    assert len(result.succeeded) >= 2
    assert result.ots_path.exists()

    raw = result.ots_path.read_bytes()
    assert raw.startswith(DetachedTimestampFile.HEADER_MAGIC)

    with open(result.ots_path, "rb") as fd:
        detached = DetachedTimestampFile.deserialize(StreamDeserializationContext(fd))
    assert detached.file_digest.hex() == result.digest_hex

    upgrade_result = upgrade_file(target)
    # Una conferma Bitcoin richiede ore: qui verifichiamo solo che l'upgrade
    # parli con i calendar veri senza errori fatali (un commitment non ancora
    # confermato è "pending", non un fallimento), non che sia completo.
    assert upgrade_result.complete is False
    assert upgrade_result.failed == ()
    assert upgrade_result.still_pending != ()
