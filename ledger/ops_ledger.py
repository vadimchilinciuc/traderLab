"""OpsLedger — telemetria del RITO, non delle decisioni.

Il `TraderLedger` risponde a "cosa ha deciso il Trader". Questo risponde a
"cosa è successo al Lab": una giornata saltata, un rito che non è partito, una
finestra in cui nessuno ha deciso nulla.

Perché serve un registro separato e non una riga in più nel ledger dei verbali:
una giornata saltata **non ha decisioni**, e il ledger dei verbali è write-once
per (giorno, replica, asset). Scriverci dentro un segnaposto significherebbe
occupare quella chiave — e quindi impedire per sempre di distinguere "non ho
deciso perché il rito non è partito" da "ho deciso flat". Sono due fatti
diversi e vanno in due registri diversi.

**Un giorno saltato resta saltato.** Non si recuperano decisioni a posteriori:
una decisione presa oggi su dati di tre giorni fa non è una decisione, è un
backtest travestito (CLAUDE.md §5) e vede un futuro che il Trader di allora non
aveva. Il rito registra il buco e va avanti.

Stesse regole del ledger dei verbali: append-only, hash-chain, write-once per
(giorno, evento).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from ledger.trader_ledger import GENESIS_HASH, TraderLedger, entry_hash
from toolserver.store import assert_path_allowed


class OpsLedgerError(Exception):
    pass


class DuplicateOpsEntry(OpsLedgerError):
    """Violazione del write-once su (giorno, evento)."""


class OpsEvent(StrEnum):
    """Elenco chiuso: ogni evento è una categoria di telemetria."""

    # Nessuna decisione registrata per quel giorno, e il giorno è passato.
    SKIPPED_DAY = "skipped_day"
    # Il rito è partito e la giornata è stata scritta.
    DAY_COMPLETED = "day_completed"
    # Il rito è partito ma si è fermato prima di scrivere le decisioni.
    RUN_FAILED = "run_failed"


@dataclass(frozen=True, slots=True)
class OpsKey:
    day: str
    event: str

    @classmethod
    def of(cls, day: date | datetime | str, event: OpsEvent | str) -> OpsKey:
        if isinstance(day, datetime):
            day_str = day.astimezone(timezone.utc).date().isoformat()
        elif isinstance(day, date):
            day_str = day.isoformat()
        else:
            day_str = day
        return cls(day=day_str, event=str(event))

    def as_dict(self) -> dict[str, str]:
        return {"day": self.day, "event": self.event}


class OpsLedger:
    """Registro operativo su file JSONL."""

    def __init__(self, path: Path | str) -> None:
        self.path = assert_path_allowed(Path(path).parent) / Path(path).name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._keys: set[OpsKey] = set()
        self._last_hash = GENESIS_HASH
        self._count = 0
        for entry in self.read_all():
            self._keys.add(OpsKey(**entry["key"]))
            self._last_hash = entry["entry_hash"]
            self._count += 1

    # -- stato -------------------------------------------------------------

    def __len__(self) -> int:
        return self._count

    @property
    def head_hash(self) -> str:
        return self._last_hash

    def has(self, key: OpsKey) -> bool:
        return key in self._keys

    # -- scrittura ---------------------------------------------------------

    def append(
        self,
        *,
        key: OpsKey,
        detail: str = "",
        detected_at_utc: datetime | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if key in self._keys:
                raise DuplicateOpsEntry(
                    f"({key.day}, {key.event}) è già nel registro operativo: "
                    f"write-once, la storia non si riscrive"
                )
            moment = detected_at_utc or datetime.now(tz=timezone.utc)
            entry: dict[str, Any] = {
                "seq": self._count,
                "ts_utc": moment.astimezone(timezone.utc).isoformat(),
                "key": key.as_dict(),
                "detail": detail[:500],
                "payload": payload or {},
                "prev_hash": self._last_hash,
            }
            entry["entry_hash"] = entry_hash(entry)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            self._keys.add(key)
            self._last_hash = entry["entry_hash"]
            self._count += 1
            return entry

    def record_skipped_day(
        self, day: date, *, detail: str = "", detected_at_utc: datetime | None = None
    ) -> dict[str, Any] | None:
        """Marca un giorno come saltato. Idempotente.

        Idempotente per necessità, non per comodità: finché il buco resta nel
        ledger dei verbali, ogni rito successivo lo ri-rileva. Ri-sollevare
        ogni volta trasformerebbe un buco vecchio in un fallimento nuovo.
        """
        key = OpsKey.of(day, OpsEvent.SKIPPED_DAY)
        if self.has(key):
            return None
        return self.append(
            key=key,
            detail=detail or "nessuna decisione registrata per questo giorno",
            detected_at_utc=detected_at_utc,
        )

    # -- lettura -----------------------------------------------------------

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def events(self, event: OpsEvent) -> list[dict[str, Any]]:
        return [e for e in self.read_all() if e["key"]["event"] == str(event)]

    def skipped_days(self) -> list[date]:
        return sorted(
            date.fromisoformat(e["key"]["day"])
            for e in self.events(OpsEvent.SKIPPED_DAY)
        )

    def verify(self):
        """Stessa verifica della catena del ledger dei verbali."""
        from ledger.trader_ledger import VerifyResult

        expected_prev = GENESIS_HASH
        entries = self.read_all()
        for index, entry in enumerate(entries):
            if entry.get("prev_hash") != expected_prev:
                return VerifyResult(
                    ok=False,
                    entries_checked=index,
                    broken_at=index,
                    detail=f"riga {index}: prev_hash non corrisponde",
                )
            if entry_hash(entry) != entry.get("entry_hash"):
                return VerifyResult(
                    ok=False,
                    entries_checked=index,
                    broken_at=index,
                    detail=f"riga {index}: contenuto alterato",
                )
            if entry.get("seq") != index:
                return VerifyResult(
                    ok=False,
                    entries_checked=index,
                    broken_at=index,
                    detail=f"riga {index}: seq fuori sequenza",
                )
            expected_prev = entry["entry_hash"]
        return VerifyResult(ok=True, entries_checked=len(entries))


# --------------------------------------------------------------------------
# Rilevazione dei giorni mancati
# --------------------------------------------------------------------------


def recorded_days(ledger: TraderLedger) -> list[date]:
    """Giorni per cui esiste almeno una riga nel ledger dei verbali."""
    return sorted({date.fromisoformat(e["key"]["day"]) for e in ledger.read_all()})


def last_recorded_day(ledger: TraderLedger) -> date | None:
    days = recorded_days(ledger)
    return days[-1] if days else None


def missing_days(last_day: date, today: date) -> list[date]:
    """Giorni tra l'ultimo registrato e oggi, esclusi entrambi.

    `today` è escluso perché la giornata di oggi non è saltata: sta per essere
    eseguita. `last_day` è escluso perché è stato registrato. Se l'ultima
    giornata è ieri non manca nulla, ed è il caso normale.
    """
    if today <= last_day:
        return []
    return [
        last_day + timedelta(days=n) for n in range(1, (today - last_day).days)
    ]


def mark_missing_days(
    *,
    trader_ledger: TraderLedger,
    ops_ledger: OpsLedger,
    today: date,
    detected_at_utc: datetime | None = None,
) -> list[date]:
    """Scrive uno `skipped_day` per ogni giorno mancato. Non recupera nulla.

    Ritorna i giorni marcati **in questa passata**: quelli già marcati non
    vengono riscritti e non compaiono nel risultato.
    """
    last = last_recorded_day(trader_ledger)
    if last is None:
        # Ledger vuoto: non esiste un "prima" da cui misurare un buco. Il primo
        # giorno di una stagione non ha giorni saltati alle spalle.
        return []
    marcati: list[date] = []
    for day in missing_days(last, today):
        written = ops_ledger.record_skipped_day(
            day,
            detail=(
                f"nessuna decisione registrata; ultimo giorno con verbali: "
                f"{last.isoformat()}"
            ),
            detected_at_utc=detected_at_utc,
        )
        if written is not None:
            marcati.append(day)
    return marcati
