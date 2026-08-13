"""Timbratura locale OpenTimestamps (stamp/upgrade).

Bypassa il client `ots` ufficiale (pacchetto `opentimestamps-client`), rotto
su questa macchina Windows: `otsclient.cmds` importa `bitcoin.rpc`, che a
cascata importa `bitcoin.wallet` -> `bitcoin.core.key`. Quel modulo fa una
lookup ctypes per una DLL OpenSSL
(`ctypes.util.find_library('ssl.35' | 'ssl' | 'libeay32')`) che su questa
installazione Python/Windows restituisce `None`, e
`ctypes.cdll.LoadLibrary(None)` solleva `TypeError` prima ancora che parta
una qualunque richiesta di rete.

Questo script usa direttamente la libreria `opentimestamps` (mai
`otsclient`) e non ha alcun bisogno di `bitcoin.rpc`/`bitcoin.wallet`: quei
moduli servono solo a verificare timbri contro un nodo Bitcoin locale, cosa
che qui non facciamo (l'upgrade interroga solo i calendar remoti via HTTP).

Uso:
    TRADERLAB_ALLOW_NETWORK=1 uv run python scripts/ots_stamp.py stamp <file>
    TRADERLAB_ALLOW_NETWORK=1 uv run python scripts/ots_stamp.py upgrade <file|file.ots>

La rete pubblica si tocca solo con `TRADERLAB_ALLOW_NETWORK=1`, mai in
silenzio (stessa disciplina di scripts/build_snapshot.py, CLAUDE.md §7).
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# --- guardia difensiva sull'import -----------------------------------------
# `opentimestamps.core.timestamp` importa solo `bitcoin.core` (CTransaction,
# SerializationError, b2lx, b2x), che NON tocca `bitcoin.core.key` e quindi
# non innesca il crash ctypes descritto sopra: è stato verificato che con la
# versione attuale della libreria questo script si importa pulito. Se una
# futura versione di `opentimestamps` iniziasse a importare `bitcoin.wallet`
# o `bitcoin.rpc` (es. per supporto wallet locale), li sostituiamo qui con
# uno stub che fallisce in modo esplicito e leggibile, invece di far
# esplodere ctypes con un TypeError criptico in un punto imprevedibile dello
# stack.
class _BlockedBitcoinModule:
    """Stub per bitcoin.wallet/bitcoin.rpc: questo script non deve usarli."""

    def __getattr__(self, name: str):
        raise ImportError(
            "ots_stamp.py blocca bitcoin.wallet/bitcoin.rpc di proposito: "
            "importano bitcoin.core.key, che su questa macchina fallisce "
            "nella lookup ctypes della DLL OpenSSL. Questo script non ha "
            "bisogno di un wallet o di un nodo Bitcoin locale — solo di "
            "richieste HTTP ai calendar OpenTimestamps."
        )


sys.modules.setdefault("bitcoin.wallet", _BlockedBitcoinModule())
sys.modules.setdefault("bitcoin.rpc", _BlockedBitcoinModule())

from opentimestamps.calendar import CommitmentNotFoundError, RemoteCalendar  # noqa: E402
from opentimestamps.core.notary import (  # noqa: E402
    BitcoinBlockHeaderAttestation,
    PendingAttestation,
)
from opentimestamps.core.op import OpAppend, OpSHA256  # noqa: E402
from opentimestamps.core.serialize import (  # noqa: E402
    StreamDeserializationContext,
    StreamSerializationContext,
)
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp  # noqa: E402

DEFAULT_CALENDAR_URLS = (
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://alice.btc.calendar.opentimestamps.org",
)
DEFAULT_MIN_RESPONSES = 2
DEFAULT_TIMEOUT_SECONDS = 30.0


def network_allowed() -> bool:
    """La rete pubblica si tocca solo con il flag esplicito (CLAUDE.md §7)."""
    return os.environ.get("TRADERLAB_ALLOW_NETWORK") == "1"


class StampingError(RuntimeError):
    """Sollevato quando non si raggiunge il numero minimo di calendar."""


@dataclass(frozen=True)
class StampResult:
    ots_path: Path
    digest_hex: str
    succeeded: tuple[str, ...]
    failed: tuple[tuple[str, str], ...]  # (url, errore)


@dataclass(frozen=True)
class UpgradeResult:
    changed: bool
    complete: bool
    upgraded_from: tuple[str, ...]
    still_pending: tuple[str, ...]
    failed: tuple[tuple[str, str], ...]


def _leaf_stamps(stamp: Timestamp):
    """Sotto-timestamp che portano direttamente delle attestazioni (foglie)."""
    if stamp.attestations:
        yield stamp
    else:
        for sub_stamp in stamp.ops.values():
            yield from _leaf_stamps(sub_stamp)


def stamp_file(
    file_path: Path | str,
    calendar_urls=DEFAULT_CALENDAR_URLS,
    min_responses: int = DEFAULT_MIN_RESPONSES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    calendar_factory=RemoteCalendar,
) -> StampResult:
    """Timbra `file_path`, scrive `<file_path>.ots` accanto e ritorna l'esito."""
    file_path = Path(file_path)

    with open(file_path, "rb") as fd:
        file_timestamp = DetachedTimestampFile.from_fd(OpSHA256(), fd)

    # Nonce prima dell'hash finale sottomesso ai calendar: evita di esporre
    # l'hash nudo del file (stessa pratica del client ufficiale `ots stamp`).
    nonce_appended = file_timestamp.timestamp.ops.add(OpAppend(os.urandom(16)))
    merkle_tip = nonce_appended.ops.add(OpSHA256())

    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []
    for url in calendar_urls:
        calendar = calendar_factory(url)
        try:
            response = calendar.submit(merkle_tip.msg, timeout=timeout)
        except Exception as exc:  # calendar/network failures sono tutte non fatali qui
            failed.append((url, f"{type(exc).__name__}: {exc}"))
            continue
        merkle_tip.merge(response)
        succeeded.append(url)

    if len(succeeded) < min_responses:
        raise StampingError(
            f"solo {len(succeeded)}/{min_responses} calendar hanno risposto "
            f"(tentati {len(calendar_urls)}): {failed}"
        )

    ots_path = file_path.with_name(file_path.name + ".ots")
    with open(ots_path, "xb") as ots_fd:
        file_timestamp.serialize(StreamSerializationContext(ots_fd))

    return StampResult(
        ots_path=ots_path,
        digest_hex=file_timestamp.file_digest.hex(),
        succeeded=tuple(succeeded),
        failed=tuple(failed),
    )


def _resolve_ots_path(target: Path) -> Path:
    if target.suffix == ".ots":
        return target
    return target.with_name(target.name + ".ots")


def upgrade_file(
    target: Path | str,
    calendar_urls=None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    calendar_factory=RemoteCalendar,
) -> UpgradeResult:
    """Tenta di far avanzare il timbro di `target` da pending a confermato Bitcoin.

    `target` può essere il file originale o il suo `.ots`. Se `calendar_urls`
    non è passato, interroga il calendar indicato da ciascuna
    `PendingAttestation` trovata nel timbro (comportamento standard: sono gli
    stessi calendar pubblici usati in `stamp`).
    """
    ots_path = _resolve_ots_path(Path(target))

    with open(ots_path, "rb") as fd:
        detached = DetachedTimestampFile.deserialize(StreamDeserializationContext(fd))

    changed = False
    upgraded_from: list[str] = []
    still_pending: list[str] = []
    failed: list[tuple[str, str]] = []

    for leaf in _leaf_stamps(detached.timestamp):
        for attestation in list(leaf.attestations):
            if not isinstance(attestation, PendingAttestation):
                continue

            existing = set(leaf.attestations)
            urls = calendar_urls if calendar_urls else [attestation.uri]
            for url in urls:
                calendar = calendar_factory(url)
                try:
                    response = calendar.get_timestamp(leaf.msg, timeout=timeout)
                except CommitmentNotFoundError:
                    # Stato normale, non un errore: il calendar conosce il
                    # commitment ma non ha ancora un blocco Bitcoin da
                    # offrire (es. "Pending confirmation in Bitcoin
                    # blockchain"). Va riportato come pending, non come
                    # fallimento.
                    still_pending.append(url)
                    continue
                except Exception as exc:
                    failed.append((url, f"{type(exc).__name__}: {exc}"))
                    continue

                new_attestations = {a for _, a in response.all_attestations()} - existing
                if new_attestations:
                    leaf.merge(response)
                    changed = True
                    upgraded_from.append(url)
                else:
                    still_pending.append(url)

    if changed:
        with open(ots_path, "wb") as fd:
            detached.serialize(StreamSerializationContext(fd))

    complete = any(
        isinstance(attestation, BitcoinBlockHeaderAttestation)
        for _, attestation in detached.timestamp.all_attestations()
    )

    return UpgradeResult(
        changed=changed,
        complete=complete,
        upgraded_from=tuple(upgraded_from),
        still_pending=tuple(still_pending),
        failed=tuple(failed),
    )


def _cmd_stamp(args: argparse.Namespace) -> int:
    if not network_allowed():
        print(
            "ERRORE: rete disabilitata. Esegui con TRADERLAB_ALLOW_NETWORK=1 "
            "solo per timbrare, mai durante una decisione.",
            file=sys.stderr,
        )
        return 2

    calendar_urls = tuple(args.calendar_urls) if args.calendar_urls else DEFAULT_CALENDAR_URLS
    try:
        result = stamp_file(
            args.file,
            calendar_urls=calendar_urls,
            min_responses=args.min_responses,
            timeout=args.timeout,
        )
    except StampingError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1

    print(f"file            : {args.file}")
    print(f"sha256          : {result.digest_hex}")
    print(f"scritto         : {result.ots_path}")
    print(f"calendar OK     : {', '.join(result.succeeded)}")
    if result.failed:
        print(f"calendar falliti: {result.failed}")
    return 0


def _cmd_upgrade(args: argparse.Namespace) -> int:
    if not network_allowed():
        print(
            "ERRORE: rete disabilitata. Esegui con TRADERLAB_ALLOW_NETWORK=1 "
            "solo per timbrare, mai durante una decisione.",
            file=sys.stderr,
        )
        return 2

    try:
        result = upgrade_file(args.file, timeout=args.timeout)
    except FileNotFoundError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1

    if result.complete:
        print("stato            : confermato su Bitcoin")
    elif result.changed:
        print("stato            : aggiornato, ancora pending")
    else:
        print(
            "stato            : ancora pending, nessun aggiornamento "
            "(normale, riprova tra qualche ora)"
        )
    if result.upgraded_from:
        print(f"aggiornato da    : {', '.join(result.upgraded_from)}")
    if result.still_pending:
        print(f"ancora pending su: {', '.join(result.still_pending)}")
    if result.failed:
        print(f"errori           : {result.failed}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    stamp_p = sub.add_parser("stamp", help="Timbra un file sui calendar OpenTimestamps")
    stamp_p.add_argument("file", type=Path)
    stamp_p.add_argument(
        "--calendar",
        dest="calendar_urls",
        action="append",
        help="URL calendar (ripetibile); default: i 3 calendar pubblici standard.",
    )
    stamp_p.add_argument("--min-responses", type=int, default=DEFAULT_MIN_RESPONSES)
    stamp_p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    stamp_p.set_defaults(func=_cmd_stamp)

    upgrade_p = sub.add_parser(
        "upgrade", help="Tenta l'upgrade di un timbro pending a confermato Bitcoin"
    )
    upgrade_p.add_argument("file", type=Path, help="File originale o il suo .ots")
    upgrade_p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    upgrade_p.set_defaults(func=_cmd_upgrade)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
