"""scripts/freeze_pin.py — persistenza del manifest definitivo, senza rete.

`build_pin_document` non chiama l'API: legge i context file promossi da
disco e calcola gli sha. La suite deve poter girare senza rete e senza
API key (CLAUDE.md), quindi questi test lo verificano importando ed
eseguendo la funzione direttamente, mai lo script come sottoprocesso reale.
"""

from __future__ import annotations

import json

from contracts.freeze import FreezeManifest, SamplingPolicy, ThinkingPolicy
from scripts.freeze_pin import PREREG_REF, build_pin_document


def test_il_documento_di_pin_e_completo(tmp_path):
    document = build_pin_document(out=tmp_path / "manifest.json")

    manifest = FreezeManifest.model_validate(document["freeze_manifest"])
    assert manifest.model_string == "claude-fable-5"
    assert manifest.sampling_policy is SamplingPolicy.API_DEFAULT_OMITTED
    assert manifest.thinking_policy is ThinkingPolicy.API_DEFAULT
    assert manifest.max_tokens == 8_000
    assert manifest.ots_pending is True
    assert manifest.ots_proof_path is None
    assert manifest.freeze_id == document["freeze_id"]

    config = document["rito_config"]
    assert config["universe"] == ["BTC", "ETH"]
    assert len(config["replica_ids"]) == 3
    assert config["snapshot_schedule_utc"] == "00:00"
    assert config["prereg_ref"] == PREREG_REF


def test_il_documento_e_json_serializzabile_e_riletto_identico(tmp_path):
    out = tmp_path / "manifest.json"
    document = build_pin_document(out=out)
    testo = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
    riletto = json.loads(testo)
    assert riletto == document


def test_main_scrive_il_file_e_lo_lascia_ricaricabile(tmp_path):
    from scripts.freeze_pin import main

    out = tmp_path / "sub" / "manifest.json"
    exit_code = _run_main_with_out(main, out)
    assert exit_code == 0
    assert out.is_file()

    data = json.loads(out.read_text(encoding="utf-8"))
    manifest = FreezeManifest.model_validate(data["freeze_manifest"])
    assert manifest.freeze_id == data["freeze_id"]


def _run_main_with_out(main, out) -> int:
    import sys

    argv = sys.argv
    sys.argv = ["freeze_pin.py", "--out", str(out)]
    try:
        return main()
    finally:
        sys.argv = argv
