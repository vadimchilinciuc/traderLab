"""Spesa cumulata di stagione e guardie economiche (D5).

Il ledger dei verbali dice **quali giornate** sono state eseguite e con quale
`run_id`; il log delle tool call, sotto `data/toolcalls/`, dice **quanti
token** ogni chiamata ha consumato. La spesa di stagione è il prodotto dei due,
e vive qui perché la leggono in due:

- il **runner**, prima di far girare una giornata: se la cumulata supera
  ``HARD_STOP_MULTIPLIER`` volte il preventivo di stagione, si rifiuta di
  partire;
- il **controllo del mattino**, che allerta — file ``ALLARME_<data>.txt`` —
  quando la cumulata supera ``ALARM_MULTIPLIER`` volte il pro-rata.

Due implementazioni della stessa somma divergerebbero il giorno in cui una
delle due venisse aggiornata e l'altra no, e la guardia che si fida della
versione sbagliata è peggio di nessuna guardia. Da qui, una sola.

Nessuna rete, nessuna API: solo lettura di file già scritti.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ledger.trader_ledger import TraderLedger
from toolserver.toollog import LLM_COMPLETE_TOOL

# --------------------------------------------------------------------------
# Listino
# --------------------------------------------------------------------------

# Prezzi di listino Claude Fable 5 (`claude-fable-5`), USD per milione di
# token — dal listino Anthropic consultato al momento della stesura
# (2026-08-14). DA AGGIORNARE se il listino cambia.
FABLE_INPUT_USD_PER_MTOK = 10.00
FABLE_OUTPUT_USD_PER_MTOK = 50.00
# Scrittura in cache: 1.25x il prezzo input, TTL 5 minuti — è il default del
# client (arena/llm_client.py, CACHE_CONTROL_EPHEMERAL non specifica un ttl
# esplicito). DA AGGIORNARE se il listino o il TTL di default cambiano.
FABLE_CACHE_WRITE_USD_PER_MTOK = FABLE_INPUT_USD_PER_MTOK * 1.25
# Lettura dalla cache: 0.1x il prezzo input. DA AGGIORNARE se il listino
# cambia.
FABLE_CACHE_READ_USD_PER_MTOK = FABLE_INPUT_USD_PER_MTOK * 0.1

TOKEN_KEYS: tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)

# --------------------------------------------------------------------------
# Soglie dichiarate (D5)
# --------------------------------------------------------------------------

#: Oltre questo multiplo del preventivo di stagione il runner NON parte.
HARD_STOP_MULTIPLIER = 1.5
#: Oltre questo multiplo del pro-rata il controllo del mattino allerta.
ALARM_MULTIPLIER = 1.25

# Le **giornate attese** della stagione non stanno più qui.
#
# Erano `SEASON_EXPECTED_DAYS = 42`, preso dal cap di calendario del verbale
# RUN2 §A.8. Una costante di modulo però vive per conto suo: il preventivo si
# firma al rito del pin e il denominatore del pro-rata restava qui, libero di
# non corrispondergli. Il caso che rende la cosa concreta: se il preventivo è
# tarato su **28** giornate e il pro-rata si calcola su **42**, la soglia
# d'allarme vale `1,25 x preventivo x g/42`, cioè `0,83 x` la spesa attesa al
# giorno `g` — sotto la spesa attesa. L'allarme suonerebbe **ogni giorno** di
# una stagione perfettamente in linea col preventivo, e un allarme che suona
# sempre insegna a ignorarlo.
#
# Numeratore e denominatore della stessa frazione si firmano insieme: entrambi
# vivono nel Freeze manifest (`season_budget_usd`, `season_expected_days`) e
# arrivano qui come argomenti. Vedi `check_season_terms`.


# --------------------------------------------------------------------------
# Token e costo
# --------------------------------------------------------------------------


def day_token_totals(
    run_ids: list[str], toolcalls_dir: Path
) -> tuple[int, int, int, int]:
    """Somma input/output/cache_read/cache_creation dal log delle tool call.

    Un campo assente nella telemetria vale 0 in questa somma: qui interessa il
    totale, non distinguere "zero token" da "non registrato" (quella
    distinzione vive in `arena.llm_client.LLMUsage`).
    """
    totals = {key: 0 for key in TOKEN_KEYS}
    for run_id in run_ids:
        path = Path(toolcalls_dir) / f"{run_id}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("tool") != LLM_COMPLETE_TOOL:
                continue
            meta = record.get("meta") or {}
            for key in TOKEN_KEYS:
                totals[key] += meta.get(key) or 0
    return (
        totals["input_tokens"],
        totals["output_tokens"],
        totals["cache_read_input_tokens"],
        totals["cache_creation_input_tokens"],
    )


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
) -> float:
    return (
        input_tokens * FABLE_INPUT_USD_PER_MTOK
        + output_tokens * FABLE_OUTPUT_USD_PER_MTOK
        + cache_read_tokens * FABLE_CACHE_READ_USD_PER_MTOK
        + cache_creation_tokens * FABLE_CACHE_WRITE_USD_PER_MTOK
    ) / 1_000_000.0


# --------------------------------------------------------------------------
# Spesa cumulata di stagione
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeasonSpend:
    """Quanto la stagione ha speso finora, e su quante giornate."""

    days_executed: int
    run_ids: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    usd: float


def season_spend(*, trader_ledger: TraderLedger, toolcalls_dir: Path) -> SeasonSpend:
    """Somma la spesa di TUTTE le giornate presenti nel ledger dei verbali.

    Le giornate si contano dal ledger — è quello il registro della stagione — e
    i `run_id` distinti che vi compaiono indicano quali file del log delle tool
    call vanno letti. Un `run_id` il cui file manca contribuisce zero e non è
    un errore: il log delle tool call è gitignorato e un clone pulito non ce
    l'ha. Chi legge la cifra deve sapere che è un **minimo**, non un totale
    garantito; per questo `run_ids` viaggia dentro il risultato.
    """
    entries = trader_ledger.read_all()
    giorni = {e["key"]["day"] for e in entries}
    run_ids: list[str] = []
    for entry in entries:
        run_id = entry.get("run_id")
        if run_id and run_id not in run_ids:
            run_ids.append(run_id)
    input_t, output_t, cache_read_t, cache_creation_t = day_token_totals(
        run_ids, toolcalls_dir
    )
    return SeasonSpend(
        days_executed=len(giorni),
        run_ids=tuple(run_ids),
        input_tokens=input_t,
        output_tokens=output_t,
        cache_read_tokens=cache_read_t,
        cache_creation_tokens=cache_creation_t,
        usd=estimate_cost_usd(input_t, output_t, cache_read_t, cache_creation_t),
    )


# --------------------------------------------------------------------------
# Le due guardie
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BudgetVerdict:
    """Esito di una guardia economica. `ok=False` non è un avviso: è un no."""

    ok: bool
    spent_usd: float
    threshold_usd: float | None
    detail: str

    @property
    def has_budget(self) -> bool:
        """Falso quando manca il preventivo: assenza, non superamento."""
        return self.threshold_usd is not None


@dataclass(frozen=True, slots=True)
class TermsVerdict:
    """I termini economici della stagione ci sono tutti? `ok=False` è un no."""

    ok: bool
    season_budget_usd: float | None
    season_expected_days: int | None
    detail: str


def check_season_terms(
    season_budget_usd: float | None, season_expected_days: int | None
) -> TermsVerdict:
    """Il pin porta entrambi i termini economici? (D5)

    Sono due, e servono entrambi: `season_budget_usd` è il numeratore della
    soglia dura e del pro-rata, `season_expected_days` è il denominatore del
    pro-rata. Il runner in `--live` li pretende tutti e due prima di chiamare
    il modello — un preventivo senza denominatore non è un preventivo, è metà
    di una frazione.

    Elenca **tutti** i campi mancanti, non solo il primo: chi legge il rifiuto
    deve poter valorizzarli in una passata sola invece di scoprirne uno per
    volta a ogni tentativo.
    """
    mancanti: list[str] = []
    if season_budget_usd is None:
        mancanti.append("season_budget_usd")
    if season_expected_days is None:
        mancanti.append("season_expected_days")
    if mancanti:
        return TermsVerdict(
            ok=False,
            season_budget_usd=season_budget_usd,
            season_expected_days=season_expected_days,
            detail=(
                f"termini economici assenti dal Freeze manifest: "
                f"{', '.join(mancanti)}. Si valorizzano al rito del pin (D5): "
                f"finché mancano non esiste una soglia da rispettare e la "
                f"giornata non parte."
            ),
        )
    return TermsVerdict(
        ok=True,
        season_budget_usd=season_budget_usd,
        season_expected_days=season_expected_days,
        detail=(
            f"preventivo di stagione ${season_budget_usd:.2f} su "
            f"{season_expected_days} giornate attese"
        ),
    )


def check_hard_stop(
    spend: SeasonSpend,
    season_budget_usd: float | None,
    *,
    multiplier: float = HARD_STOP_MULTIPLIER,
) -> BudgetVerdict:
    """Soglia dura: oltre `multiplier` volte il preventivo, non si gira.

    Un preventivo **assente** è a sua volta un rifiuto. Trattarlo come "nessun
    limite" trasformerebbe la dimenticanza di un campo in un budget infinito, e
    la guardia esisterebbe solo per chi si ricorda di configurarla.
    """
    if season_budget_usd is None:
        return BudgetVerdict(
            ok=False,
            spent_usd=spend.usd,
            threshold_usd=None,
            detail=(
                "season_budget_usd assente dal Freeze manifest: il preventivo "
                "vincolante si valorizza al rito del pin (D5). Senza, non "
                "esiste una soglia da rispettare e la giornata non parte."
            ),
        )
    threshold = season_budget_usd * multiplier
    if spend.usd > threshold:
        return BudgetVerdict(
            ok=False,
            spent_usd=spend.usd,
            threshold_usd=threshold,
            detail=(
                f"spesa cumulata di stagione ${spend.usd:.2f} oltre "
                f"{multiplier:g} x il preventivo di ${season_budget_usd:.2f} "
                f"(soglia ${threshold:.2f}), su {spend.days_executed} giornate "
                f"eseguite. La giornata non parte."
            ),
        )
    return BudgetVerdict(
        ok=True,
        spent_usd=spend.usd,
        threshold_usd=threshold,
        detail=(
            f"spesa cumulata ${spend.usd:.2f} entro la soglia dura di "
            f"${threshold:.2f} ({multiplier:g} x ${season_budget_usd:.2f})"
        ),
    )


def prorata_threshold_usd(
    season_budget_usd: float,
    days_executed: int,
    expected_days: int,
    *,
    multiplier: float = ALARM_MULTIPLIER,
) -> float:
    """`multiplier` x (preventivo x giornate_eseguite / giornate_attese).

    `expected_days` non ha default: viene dal Freeze manifest, e un default
    qui sarebbe di nuovo una costante nascosta che può divergere dal
    preventivo firmato.
    """
    if expected_days <= 0:
        raise ValueError("expected_days deve essere positivo")
    prorata = season_budget_usd * days_executed / expected_days
    return prorata * multiplier


def check_prorata_alarm(
    spend: SeasonSpend,
    season_budget_usd: float | None,
    *,
    expected_days: int | None,
    multiplier: float = ALARM_MULTIPLIER,
) -> BudgetVerdict:
    """Allarme di ritmo: la stagione sta bruciando più in fretta del pro-rata.

    Non ferma niente — è il controllo del mattino a leggerlo, e il suo compito
    è svegliare l'owner, non bloccare il rito. La soglia dura resta quella di
    `check_hard_stop`.

    A zero giornate eseguite il pro-rata è zero e qualunque spesa lo
    supererebbe: con zero giornate però non c'è ancora un ritmo da giudicare,
    e l'esito è "ok" con il motivo scritto.
    """
    if season_budget_usd is None or expected_days is None:
        mancante = (
            "season_budget_usd" if season_budget_usd is None else "season_expected_days"
        )
        return BudgetVerdict(
            ok=False,
            spent_usd=spend.usd,
            threshold_usd=None,
            detail=(
                f"{mancante} assente dal Freeze manifest: non esiste un "
                f"pro-rata da confrontare (D5)."
            ),
        )
    if spend.days_executed <= 0:
        return BudgetVerdict(
            ok=True,
            spent_usd=spend.usd,
            threshold_usd=None,
            detail="nessuna giornata eseguita: non c'è ancora un ritmo da giudicare",
        )
    threshold = prorata_threshold_usd(
        season_budget_usd, spend.days_executed, expected_days, multiplier=multiplier
    )
    if spend.usd > threshold:
        return BudgetVerdict(
            ok=False,
            spent_usd=spend.usd,
            threshold_usd=threshold,
            detail=(
                f"spesa cumulata ${spend.usd:.2f} oltre {multiplier:g} x il "
                f"pro-rata di ${threshold / multiplier:.2f} "
                f"(${season_budget_usd:.2f} x {spend.days_executed}/"
                f"{expected_days} giornate): la stagione sta spendendo piu' in "
                f"fretta del preventivo"
            ),
        )
    return BudgetVerdict(
        ok=True,
        spent_usd=spend.usd,
        threshold_usd=threshold,
        detail=(
            f"spesa cumulata ${spend.usd:.2f} entro {multiplier:g} x il "
            f"pro-rata (soglia ${threshold:.2f})"
        ),
    )
