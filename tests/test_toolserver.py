"""Blocco 2 — Tool Server: determinismo, firewall, errori puliti."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from contracts.vocabulary import PRIMITIVE_FEATURES
from toolserver.config import SnapshotConfig
from toolserver.errors import (
    FirewallViolation,
    InvalidToolArguments,
    OutOfSnapshotRequest,
    SnapshotCorrupted,
    SnapshotNotFound,
    UnknownAsset,
    UnknownTool,
)
from toolserver.hyperliquid import HyperliquidPublicClient, NetworkDisabled
from toolserver.registry import MAX_OHLCV_BARS, ToolRegistry, tool_schemas_sha
from toolserver.snapshot_builder import SnapshotBuilder, SnapshotBuildError, normalized_asof
from toolserver.store import SnapshotStore
from toolserver.toollog import ToolCallLog
from tests.factories import ASOF, make_snapshot


@pytest.fixture
def store(tmp_path) -> SnapshotStore:
    return SnapshotStore(tmp_path / "snapshots")


@pytest.fixture
def log(tmp_path) -> ToolCallLog:
    return ToolCallLog(tmp_path / "toolcalls", run_id="test-run")


@pytest.fixture
def registry(store, log) -> ToolRegistry:
    return ToolRegistry(store, log)


@pytest.fixture
def saved(store):
    snap = make_snapshot()
    store.save(snap)
    return snap


# --------------------------------------------------------------------------
# Store: persistenza per snapshot_id e integrità
# --------------------------------------------------------------------------


def test_store_salva_e_ricarica_identico(store):
    snap = make_snapshot()
    store.save(snap)
    assert store.load(snap.snapshot_id) == snap


def test_store_e_idempotente_sullo_stesso_id(store):
    snap = make_snapshot()
    first = store.save(snap)
    before = first.read_bytes()
    store.save(make_snapshot())
    assert first.read_bytes() == before


def test_store_rifiuta_snapshot_manomesso(store):
    snap = make_snapshot()
    path = store.save(snap)
    store._cache.clear()
    path.write_text(path.read_text(encoding="utf-8").replace("60000.0", "61000.0"), encoding="utf-8")
    with pytest.raises(SnapshotCorrupted):
        store.load(snap.snapshot_id)


def test_store_snapshot_mancante_errore_pulito(store):
    with pytest.raises(SnapshotNotFound, match="non ricade su dati live"):
        store.load("a" * 64)


def test_store_id_malformato_errore_pulito(store):
    with pytest.raises(SnapshotNotFound, match="malformato"):
        store.load("non-un-hash")


# --------------------------------------------------------------------------
# Firewall: nessun path verso zeroPipes
# --------------------------------------------------------------------------


def test_store_rifiuta_percorso_verso_zeropipes(tmp_path):
    with pytest.raises(FirewallViolation, match="zeroPipes"):
        SnapshotStore(tmp_path / "zeroPipes" / "data")


def test_toollog_rifiuta_percorso_verso_zeropipes(tmp_path):
    with pytest.raises(FirewallViolation):
        ToolCallLog(tmp_path / "zeropipes", run_id="x")


def test_client_hyperliquid_senza_flag_non_apre_socket(monkeypatch):
    monkeypatch.delenv("TRADERLAB_ALLOW_NETWORK", raising=False)
    with pytest.raises(NetworkDisabled, match="TRADERLAB_ALLOW_NETWORK"):
        HyperliquidPublicClient().meta_and_asset_ctxs()


def test_il_tool_server_non_importa_il_client_di_rete():
    """Il firewall è strutturale: registry e store non conoscono httpx."""
    import inspect

    from toolserver import registry as registry_module
    from toolserver import store as store_module

    for module in (registry_module, store_module):
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "hyperliquid" not in source


# --------------------------------------------------------------------------
# Due repliche, stesso snapshot_id -> byte identici
# --------------------------------------------------------------------------


def test_due_repliche_ricevono_risposte_byte_identiche(registry, saved):
    import json

    for tool, args in (
        ("get_universe", {}),
        ("get_ohlcv", {"symbol": "BTC", "bars": 30}),
        ("get_funding", {"symbol": "BTC"}),
        ("get_rankings", {"metric": "all"}),
        ("get_costs", {"symbol": "ETH"}),
        ("get_asset_dossier", {"symbol": "BTC"}),
    ):
        a = registry.call(
            snapshot_id=saved.snapshot_id, replica_id="r1", name=tool, args=args
        )
        b = registry.call(
            snapshot_id=saved.snapshot_id, replica_id="r2", name=tool, args=args
        )
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), tool


def test_dossier_deterministico_tra_istanze_diverse_di_store(tmp_path):
    snap = make_snapshot()
    results = []
    for name in ("a", "b"):
        store = SnapshotStore(tmp_path / name)
        store.save(snap)
        reg = ToolRegistry(store, ToolCallLog(tmp_path / f"log{name}", run_id="r"))
        results.append(
            reg.call(
                snapshot_id=snap.snapshot_id,
                replica_id="r1",
                name="get_asset_dossier",
                args={"symbol": "BTC"},
            )
        )
    assert results[0] == results[1]


# --------------------------------------------------------------------------
# Errori puliti fuori snapshot
# --------------------------------------------------------------------------


def test_asset_fuori_universo_errore_pulito(registry, saved):
    with pytest.raises(UnknownAsset, match="non è nell'universo"):
        registry.call(
            snapshot_id=saved.snapshot_id,
            replica_id="r1",
            name="get_ohlcv",
            args={"symbol": "DOGE", "bars": 10},
        )


def test_snapshot_inesistente_errore_pulito(registry):
    with pytest.raises(SnapshotNotFound):
        registry.call(
            snapshot_id="c" * 64, replica_id="r1", name="get_universe", args={}
        )


def test_tool_inesistente_errore_pulito(registry, saved):
    with pytest.raises(UnknownTool, match="non esiste"):
        registry.call(
            snapshot_id=saved.snapshot_id, replica_id="r1", name="get_news", args={}
        )


def test_troppe_barre_richieste_errore_pulito(registry, saved):
    with pytest.raises(OutOfSnapshotRequest, match="massimo servibile"):
        registry.call(
            snapshot_id=saved.snapshot_id,
            replica_id="r1",
            name="get_ohlcv",
            args={"symbol": "BTC", "bars": MAX_OHLCV_BARS + 1},
        )


def test_argomenti_malformati_errore_pulito(registry, saved):
    with pytest.raises(InvalidToolArguments):
        registry.call(
            snapshot_id=saved.snapshot_id,
            replica_id="r1",
            name="get_ohlcv",
            args={"symbol": "BTC", "bars": "trenta"},
        )
    with pytest.raises(InvalidToolArguments):
        registry.call(
            snapshot_id=saved.snapshot_id,
            replica_id="r1",
            name="get_costs",
            args={},
        )


def test_metrica_di_ranking_inesistente_errore_pulito(registry, saved):
    with pytest.raises(InvalidToolArguments, match="non disponibile"):
        registry.call(
            snapshot_id=saved.snapshot_id,
            replica_id="r1",
            name="get_rankings",
            args={"metric": "alpha_segreto"},
        )


# --------------------------------------------------------------------------
# Logging totale
# --------------------------------------------------------------------------


def test_ogni_chiamata_riuscita_e_loggata(registry, saved, log):
    registry.call(
        snapshot_id=saved.snapshot_id, replica_id="r7", name="get_universe", args={}
    )
    entries = log.read_all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["replica_id"] == "r7"
    assert entry["tool"] == "get_universe"
    assert entry["snapshot_id"] == saved.snapshot_id
    assert entry["ok"] is True
    assert len(entry["response_sha256"]) == 64


def test_anche_le_chiamate_fallite_sono_loggate(registry, saved, log):
    with pytest.raises(UnknownAsset):
        registry.call(
            snapshot_id=saved.snapshot_id,
            replica_id="r1",
            name="get_costs",
            args={"symbol": "XRP"},
        )
    entry = log.read_all()[0]
    assert entry["ok"] is False
    assert entry["response_sha256"] is None
    assert "UnknownAsset" in entry["error"]


def test_il_log_registra_gli_argomenti(registry, saved, log):
    registry.call(
        snapshot_id=saved.snapshot_id,
        replica_id="r1",
        name="get_ohlcv",
        args={"symbol": "ETH", "bars": 5},
    )
    assert log.read_all()[0]["args"] == {"symbol": "ETH", "bars": 5}


def test_il_log_e_append_only(registry, saved, log):
    for _ in range(3):
        registry.call(
            snapshot_id=saved.snapshot_id, replica_id="r1", name="get_universe", args={}
        )
    assert len(log.read_all()) == 3


# --------------------------------------------------------------------------
# Schemi dei tool: neutri, strict, stabili
# --------------------------------------------------------------------------


def test_schemi_sono_strict_e_chiusi():
    for schema in ToolRegistry.schemas():
        assert schema["strict"] is True, schema["name"]
        assert schema["input_schema"]["additionalProperties"] is False
        assert set(schema["input_schema"]["required"]) <= set(
            schema["input_schema"]["properties"]
        )


def test_descrizioni_prive_di_verbi_valutativi():
    vietati = (
        "opportunit",
        "segnale forte",
        "conviene",
        "consigl",
        "miglior",
        "rischios",
        "promettente",
        "interessante",
        "gara",
        "replic",
        "valutaz",
        "punteggio",
        "performance",
    )
    for schema in ToolRegistry.schemas():
        testo = (schema["description"] + " " + str(schema["input_schema"])).lower()
        for parola in vietati:
            assert parola not in testo, f"{schema['name']} contiene '{parola}'"


def test_tool_schemas_sha_stabile():
    assert tool_schemas_sha() == tool_schemas_sha()
    assert len(tool_schemas_sha()) == 64


def test_dossier_espone_esattamente_il_vocabolario(registry, saved):
    out = registry.call(
        snapshot_id=saved.snapshot_id,
        replica_id="r1",
        name="get_asset_dossier",
        args={"symbol": "BTC"},
    )
    assert set(out["features"]) == set(PRIMITIVE_FEATURES)


# --------------------------------------------------------------------------
# SnapshotBuilder su sorgente deterministica
# --------------------------------------------------------------------------


class FakeSource:
    """Sorgente deterministica: nessuna rete, nessuna casualità."""

    def __init__(self, symbols: dict[str, float], asof: datetime, days: int = 40):
        self.symbols = symbols
        self.asof = asof
        self.days = days

    def meta_and_asset_ctxs(self):
        meta = [{"name": s} for s in self.symbols]
        ctxs = [
            {
                "dayNtlVlm": str(vol),
                "markPx": "100.0",
                "midPx": "100.0",
                "impactPxs": ["99.98", "100.02"],
            }
            for vol in self.symbols.values()
        ]
        return meta, ctxs

    def candles(self, coin, interval, start_ms, end_ms):
        out = []
        for i in range(self.days):
            ts = self.asof - timedelta(days=self.days - i)
            price = 100.0 + i
            out.append(
                {
                    "t": int(ts.timestamp() * 1000),
                    "o": price,
                    "h": price * 1.01,
                    "l": price * 0.99,
                    "c": price,
                    "v": 10.0,
                }
            )
        # Barra ancora in formazione: apre ad asof, non deve entrare.
        out.append(
            {
                "t": int(self.asof.timestamp() * 1000),
                "o": 999.0,
                "h": 999.0,
                "l": 999.0,
                "c": 999.0,
                "v": 1.0,
            }
        )
        return out

    def funding_history(self, coin, start_ms, end_ms):
        return [
            {
                "time": int((self.asof - timedelta(hours=8)).timestamp() * 1000),
                "fundingRate": "0.0001",
            },
            # Punto futuro: deve essere scartato.
            {
                "time": int((self.asof + timedelta(hours=8)).timestamp() * 1000),
                "fundingRate": "0.5",
            },
        ]


def test_builder_produce_snapshot_sigillato():
    source = FakeSource({"BTC": 9e9, "ETH": 5e9, "SOL": 1e9}, ASOF)
    snap = SnapshotBuilder(source, SnapshotConfig(top_n_by_volume=1)).build(ASOF)
    assert snap.universe_status == "pre_screen_ufficiale"
    assert snap.universe[:2] == ("BTC", "ETH")
    assert "SOL" in snap.universe
    assert len(snap.snapshot_id) == 64


def test_builder_esclude_la_barra_in_formazione():
    source = FakeSource({"BTC": 1e9, "ETH": 1e9}, ASOF)
    snap = SnapshotBuilder(source).build(ASOF)
    for asset in snap.assets:
        for bar in asset.ohlcv_daily:
            assert bar.ts_open_utc + timedelta(days=1) <= snap.asof_utc
            assert bar.close != 999.0


def test_builder_scarta_il_funding_futuro():
    source = FakeSource({"BTC": 1e9, "ETH": 1e9}, ASOF)
    snap = SnapshotBuilder(source).build(ASOF)
    for asset in snap.assets:
        for point in asset.funding:
            assert point.ts_utc <= snap.asof_utc
            assert point.rate != 0.5


def test_builder_e_deterministico():
    a = SnapshotBuilder(FakeSource({"BTC": 1e9, "ETH": 1e9}, ASOF)).build(ASOF)
    b = SnapshotBuilder(FakeSource({"BTC": 1e9, "ETH": 1e9}, ASOF)).build(ASOF)
    assert a.snapshot_id == b.snapshot_id


def test_builder_normalizza_asof_all_ora_fissa():
    config = SnapshotConfig(snapshot_hour_utc=6)
    momento = datetime(2026, 8, 12, 17, 43, 11, tzinfo=timezone.utc)
    assert normalized_asof(momento, config) == datetime(
        2026, 8, 12, 6, 0, tzinfo=timezone.utc
    )


def test_builder_marca_universo_ufficiale_per_default():
    """Il Pre-Screen ha consegnato: l'universo di default è quello ufficiale."""
    assert SnapshotConfig().universe_status == "pre_screen_ufficiale"


def test_universo_di_default_e_esattamente_btc_eth():
    """Nessuna coda per volume: solo il perimetro P3 promosso dal Pre-Screen."""
    config = SnapshotConfig()
    assert config.core_universe == ("BTC", "ETH")
    assert config.top_n_by_volume == 0
    source = FakeSource({"BTC": 9e9, "ETH": 5e9, "SOL": 1e9}, ASOF)
    snap = SnapshotBuilder(source, config).build(ASOF)
    assert snap.universe == ("BTC", "ETH")


def test_builder_fallisce_pulito_senza_barre():
    class Vuota(FakeSource):
        def candles(self, coin, interval, start_ms, end_ms):
            return []

    with pytest.raises(SnapshotBuildError, match="nessuna barra chiusa"):
        SnapshotBuilder(Vuota({"BTC": 1e9}, ASOF)).build(ASOF)


class FundingSource(FakeSource):
    """Sorgente con funding a cadenza e ritardo controllati."""

    def __init__(self, symbols, asof, interval_hours=1.0, lag_hours=1.0, n=200):
        super().__init__(symbols, asof)
        self.interval_hours = interval_hours
        self.lag_hours = lag_hours
        self.n = n

    def funding_history(self, coin, start_ms, end_ms):
        last = self.asof - timedelta(hours=self.lag_hours)
        return [
            {
                "time": int(
                    (last - timedelta(hours=self.interval_hours * i)).timestamp() * 1000
                ),
                "fundingRate": "0.0001",
            }
            for i in reversed(range(self.n))
        ]


def test_builder_deriva_la_cadenza_del_funding_dai_dati():
    """8.0 fisso gonfierebbe di 8x l'annualizzato su funding orario."""
    for interval in (1.0, 8.0):
        source = FundingSource({"BTC": 1e9}, ASOF, interval_hours=interval)
        snap = SnapshotBuilder(source).build(ASOF)
        assert {p.interval_hours for p in snap.assets[0].funding} == {interval}


def test_builder_rifiuta_il_funding_stantio():
    """Una serie che si ferma settimane prima di asof non descrive il presente."""
    source = FundingSource({"BTC": 1e9}, ASOF, lag_hours=24 * 30)
    with pytest.raises(SnapshotBuildError, match="funding stantio"):
        SnapshotBuilder(source).build(ASOF)


def test_builder_deduplica_i_bordi_di_paginazione():
    class Doppioni(FundingSource):
        def funding_history(self, coin, start_ms, end_ms):
            page = super().funding_history(coin, start_ms, end_ms)
            return page + page[-1:]  # bordo ripetuto dalla pagina successiva

    snap = SnapshotBuilder(Doppioni({"BTC": 1e9}, ASOF)).build(ASOF)
    ts = [p.ts_utc for p in snap.assets[0].funding]
    assert len(ts) == len(set(ts))


def test_client_pagina_il_funding_oltre_il_limite_di_pagina():
    """Una pagina piena significa 'ce n'è ancora': senza paginare si
    otterrebbero i record più VECCHI e il funding corrente sparirebbe."""
    from toolserver.hyperliquid import FUNDING_PAGE_LIMIT

    start, total = 1_000_000, FUNDING_PAGE_LIMIT + 137
    chiamate: list[int] = []

    class ClientFinto(HyperliquidPublicClient):
        def _post(self, payload):
            cursor = payload["startTime"]
            chiamate.append(cursor)
            righe = [
                {"time": start + i * 3_600_000, "fundingRate": "0.0001"}
                for i in range(total)
                if start + i * 3_600_000 >= cursor
            ]
            return righe[:FUNDING_PAGE_LIMIT]

    out = ClientFinto().funding_history("BTC", start, start + total * 3_600_000)
    assert len(chiamate) > 1
    assert len(out) == total
    assert out[-1]["time"] == start + (total - 1) * 3_600_000


def test_builder_calcola_i_ranking_cross_sezionali():
    source = FakeSource({"BTC": 9e9, "ETH": 5e9}, ASOF)
    snap = SnapshotBuilder(source).build(ASOF)
    for asset in snap.assets:
        assert asset.rankings
        for rank in asset.rankings:
            assert 1 <= rank.rank <= rank.universe_size
