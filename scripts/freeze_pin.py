"""Compone e persiste il FreezeManifest definitivo (rito del pin, TL-002).

Non tocca la rete: usa solo ciò che `scripts/verify_pin.py` ha già verificato
contro l'endpoint in una chiamata separata. Questo script si limita a leggere
i context file promossi, calcolarne gli sha, e scrivere su disco il documento
di pin che l'owner dovrà timbrare con OpenTimestamps.

Il file scritto ha due parti, deliberatamente separate:

- `freeze_manifest`: la serializzazione esatta del contratto
  `contracts.freeze.FreezeManifest` — ciò che è **crittograficamente pinnato**
  (model string, sampling_policy, gli sha). `freeze_id` ne è l'hash.
- `rito_config`: dati descrittivi del rito (universo, schedule, riferimento
  alla pre-registrazione) che NON fanno parte del contratto `FreezeManifest`
  (che resta `frozen=True, extra="forbid"`: estenderlo con campi come
  "universo" cambierebbe cosa significa il pin per ogni track record
  esistente, non solo per questo). Vivono accanto al manifest per dare
  all'owner il quadro completo nello stesso file.

    uv run python scripts/freeze_pin.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena.config import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL_STRING,
    DEFAULT_REPLICA_IDS,
    build_freeze_manifest,
    current_git_sha,
)
from arena.risk_officer import DEFAULT_FIXED_SIZE_FRACTION
from toolserver.config import DEFAULT_CORE_UNIVERSE

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "manifests" / "trader_v0_freeze_manifest.json"

PREREG_REF = {
    "file": "docs/PREREG_LAB_S0.md",
    "commit": "9ef5681",
    "note": (
        "PREREG_LAB_S0 congelata prima di ogni baseline (§8: rito del pin come "
        "precondizione al primo giorno di S0)."
    ),
}


def build_pin_document(*, out: Path) -> dict:
    manifest = build_freeze_manifest(
        datetime.now(tz=timezone.utc),
        model_string=DEFAULT_MODEL_STRING,
        max_tokens=DEFAULT_MAX_TOKENS,
        context_git_sha=current_git_sha(),
    )
    return {
        "freeze_manifest": manifest.canonical_payload(),
        "freeze_id": manifest.freeze_id,
        "rito_config": {
            "universe": list(DEFAULT_CORE_UNIVERSE),
            "replica_ids": list(DEFAULT_REPLICA_IDS),
            "snapshot_schedule_utc": "00:00",
            "size_policy": (
                f"fissa a rischio unitario ({DEFAULT_FIXED_SIZE_FRACTION}), "
                "normalizzata dal Risk Officer (D3)"
            ),
            "prereg_ref": PREREG_REF,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    document = build_pin_document(out=args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"manifest scritto : {args.out}")
    print(f"freeze_id        : {document['freeze_id']}")
    print(f"ots_pending      : {document['freeze_manifest']['ots_pending']}")
    print(
        "\nPROMEMORIA: ots_pending resta True finché l'owner non timbra questo "
        "file con OpenTimestamps e non registra la proof."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
