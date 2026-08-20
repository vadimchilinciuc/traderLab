"""Derivazioni di potenza del RUN2 — n=40 coppie, pavimenti della suite, gate A.9.

Nessuna rete, nessuna API, nessuna dipendenza fuori dalla libreria standard.
Si esegue e stampa tabelle:

    uv run python scripts/run2_power.py

Perche' questo script esiste. Il verbale RUN2 (§A.8, §A.9, §A.10) dichiara tre
numeri — 40 coppie, potenza 80%, errore standard 0,050 a 3 sigma — che al
2026-08-19 **non avevano una derivazione su disco**: il §F del verbale li elenca
ai punti 4, 5 e 7 fra le affermazioni non verificate. Questo file e' quella
derivazione. Non e' un backtest e non tocca dati di mercato (CLAUDE.md §5): e'
aritmetica su ipotesi dichiarate.

PROVENIENZA DI OGNI INGRESSO
============================

Ogni costante di questo file porta una marca. Le marche sono cinque:

  [VERBALE]  docs/2026-08-19_VERBALE_DECISIONI_RUN2.md, sezione citata.
             Decisione dell'owner. Non si discute qui, si usa.
  [S0]       reperto della Stagione 0, trascritto nel verbale §A.8 dal referto
             gitignorato GIORNATA3_REPORT.md:158-161.
  [RICERCA]  docs/research/2026-08-20_RICERCA_ACCORDO_REPLICHE_LITERATURE.md.
  [RATIFICA] decisione dell'owner del 2026-08-20, per delega, trascritta nel
             PREREG del RUN2 al §14 con la sua sigla (F1...F10). E' gia'
             firmata: questo file la esegue, non la propone.
  [RITO]     scelta di questo rito, dichiarata qui e da firmare nel PREREG.
             Sono le sole voci su cui questo file esercita un giudizio.

Un ingresso senza marca sarebbe un numero comparso dal nulla, ed e' la classe
di difetto che il §F del verbale contesta ai numeri che questo file deriva.

AUTO-VERIFICHE
==============

Le funzioni esatte sono verificate contro identita' che devono valere al
bit: somma delle masse di probabilita' a 1, coda destra calcolata nei due
versi, p-value di permutazione calcolato in aritmetica razionale esatta e in
log-spazio. Tolleranza `EXACT_TOL = 1e-9`: oltre, lo script **aborta** invece
di stampare tabelle sbagliate.

Le verifiche che confrontano una quantita' esatta con una stima Monte Carlo
hanno una tolleranza propria, dichiarata a parte (`MC_TOL_SIGMA`): un errore
di campionamento non e' un errore di calcolo e non puo' avere la stessa
soglia.
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# --------------------------------------------------------------------------
# Tolleranze e semi
# --------------------------------------------------------------------------

#: [RITO] Oltre questo scarto fra due vie di calcolo della STESSA quantita'
#: esatta lo script aborta. Non e' una tolleranza numerica generosa: le
#: identita' verificate sono esatte in aritmetica razionale, e 1e-9 e' il
#: margine per il passaggio in virgola mobile.
EXACT_TOL = 1e-9

#: [RITO] Le verifiche contro Monte Carlo passano se lo scarto sta entro
#: questo numero di errori standard della stima. Quattro sigma su un
#: confronto solo: la probabilita' di un falso allarme e' ~6e-5.
MC_TOL_SIGMA = 4.0

#: [RITO] Seme di ogni sorgente pseudocasuale di questo file. Dichiarato qui
#: perche' due esecuzioni dello stesso script devono dare la stessa tabella:
#: una potenza che cambia a ogni lancio non e' una potenza, e' un'opinione.
SEED = 20260820

#: [RITO] Seme proposto per la baseline coin-flip del §A.13 del verbale, che
#: chiede «seme dichiarato nel PREREG». E' un numero diverso da `SEED` perche'
#: e' un oggetto diverso: quello governa questa derivazione, questo governera'
#: una baseline della stagione. Va FIRMATO nel PREREG, non solo scritto qui.
COINFLIP_SEED_PROPOSTO = 20260913


#: A capo. Definito come costante perche' le stringhe di formato di questo
#: file sono gia' fitte di parentesi graffe.
NL = chr(10)


class SelfTestFailed(RuntimeError):
    """Un'identita' che doveva valere non vale. Lo script si ferma qui."""


def _assert_close(atteso: float, ottenuto: float, cosa: str) -> None:
    scarto = abs(atteso - ottenuto)
    if scarto > EXACT_TOL:
        raise SelfTestFailed(
            f"{cosa}: atteso {atteso!r}, ottenuto {ottenuto!r}, "
            f"scarto {scarto:.3e} > {EXACT_TOL:g}"
        )


# ==========================================================================
# PARTE A — la derivazione di n = 40 coppie
# ==========================================================================

#: [VERBALE §A.8] L'ipotesi nulla che la stagione deve poter rigettare: il
#: tasso vero di disaccordo fra le tre repliche e' al piu' il 10%.
Q_NULL = 0.10
#: [VERBALE §A.8] L'alternativa a cui si chiede potenza: tasso vero >= 25%.
Q_ALT = 0.25
#: [VERBALE §A.8] Livello del test, unilaterale.
ALPHA = 0.05
#: [VERBALE §A.8] Potenza richiesta.
POWER_TARGET = 0.80
#: [VERBALE §A.8] L'obiettivo dichiarato: 40 coppie giornata-asset valide.
N_PAIRS_DECLARED = 40
#: [VERBALE §A.8 / §A.3] Asset per giornata. L'universo del RUN2 e' BTC e ETH.
ASSETS_PER_DAY = 2
#: [VERBALE §A.8] Cap di calendario della stagione.
CALENDAR_CAP_DAYS = 42
#: [S0] Stima puntuale del disaccordo in Stagione 0: 1 coppia su 4.
S0_DISAGREEMENT = (1, 4)
#: [S0] Tasso di esiti mancanti osservato in Stagione 0: 2 su 18.
S0_FAILURE_RATE = 2 / 18
#: [VERBALE §A.8] I tre tassi di fallimento per cui il verbale dichiara
#: un'attesa di giornate.
FAILURE_RATES = (0.00, 0.05, S0_FAILURE_RATE)
#: [VERBALE §A.8] Repliche per coppia. Una coppia e' valida solo se tutte e
#: tre hanno prodotto un verbale.
REPLICAS = 3
#: [RATIFICA F3] Griglia della clausola sotto-40. Se a fine calendario le
#: coppie valide sono meno di 40, il test si esegue **all'n raggiunto**, col
#: valore critico prodotto da `critical_value` — la stessa funzione che deriva
#: il disegno a n=40 — e la potenza si riporta accanto all'esito. La griglia
#: parte da 30 perche' e' il punto in cui il verbale gia' tabellava la potenza
#: (§3.2 del PREREG); tabellare i valori critici PRIMA della raccolta e' cio'
#: che impedisce di sceglierli dopo aver visto quante coppie sono arrivate.
N_SOTTO_40_GRID = tuple(range(30, N_PAIRS_DECLARED + 1))


def binom_pmf(n: int, k: int, p: float) -> float:
    """P(X = k) con X ~ Bin(n, p). Esatta a meno del virgola mobile."""
    if k < 0 or k > n:
        return 0.0
    return math.comb(n, k) * p**k * (1.0 - p) ** (n - k)


def binom_sf(n: int, c: int, p: float) -> float:
    """P(X >= c). Somma diretta della coda: nessuna approssimazione normale."""
    return sum(binom_pmf(n, k, p) for k in range(max(c, 0), n + 1))


def critical_value(n: int, q0: float, alpha: float) -> int:
    """Il piu' piccolo `c` con P(X >= c | q0) <= alpha. Test esatto, unilaterale.

    Il valore critico e' un intero e la dimensione effettiva del test e' quindi
    <= alpha, quasi mai = alpha: con dati discreti non esiste un test esatto di
    dimensione esattamente 0,05, e fingere il contrario e' il modo in cui un
    test conservativo viene spacciato per calibrato.
    """
    for c in range(n + 2):
        if binom_sf(n, c, q0) <= alpha:
            return c
    raise AssertionError("irraggiungibile: c = n+1 da' coda 0")


@dataclass(frozen=True, slots=True)
class BinomialDesign:
    n: int
    critical: int
    alpha_effective: float
    power: float

    @property
    def ok(self) -> bool:
        return self.power >= POWER_TARGET


def design_for(n: int, q0: float = Q_NULL, q1: float = Q_ALT) -> BinomialDesign:
    c = critical_value(n, q0, ALPHA)
    return BinomialDesign(
        n=n,
        critical=c,
        alpha_effective=binom_sf(n, c, q0),
        power=binom_sf(n, c, q1),
    )


def smallest_n(q0: float = Q_NULL, q1: float = Q_ALT, n_max: int = 200) -> int:
    """Il piu' piccolo n che raggiunge la potenza richiesta.

    La potenza **non e' monotona in n** con un test esatto discreto: aggiungere
    un'osservazione puo' spostare il valore critico di un'unita' intera e far
    scendere la potenza. Il minimo si cerca quindi per scansione, non per
    inversione di una formula, e la non-monotonia si stampa invece di
    nasconderla.
    """
    for n in range(1, n_max + 1):
        if design_for(n, q0, q1).ok:
            return n
    raise AssertionError(f"nessun n <= {n_max} raggiunge la potenza richiesta")


def expected_days(n_pairs: int, failure_rate: float) -> float:
    """Giornate attese per raccogliere `n_pairs` coppie valide.

    Una coppia e' valida se **tutte e tre** le repliche hanno prodotto un
    verbale: a tasso di fallimento `f` per singolo esito, la probabilita' e'
    `(1 - f)**3`. Con `ASSETS_PER_DAY` coppie tentate al giorno, le giornate
    attese sono `n_pairs / (assets * (1-f)**3)`.

    E' un'attesa, non un quantile: meta' delle stagioni che seguono questo
    modello ne impieghera' di piu'. Il cap di calendario del §A.8 e' 42 giorni
    e va confrontato con la coda, non con questa media.
    """
    p_valid = (1.0 - failure_rate) ** REPLICAS
    if p_valid <= 0.0:
        return math.inf
    return n_pairs / (ASSETS_PER_DAY * p_valid)


def _selftest_binomial() -> None:
    for n, p in ((40, 0.10), (40, 0.25), (17, 0.5), (3, 0.111)):
        _assert_close(
            1.0,
            sum(binom_pmf(n, k, p) for k in range(n + 1)),
            f"massa binomiale n={n} p={p}",
        )
        c = min(7, n)
        diretta = binom_sf(n, c, p)
        complemento = 1.0 - sum(binom_pmf(n, k, p) for k in range(c))
        _assert_close(diretta, complemento, f"coda destra nei due versi n={n} p={p}")
    # Il valore critico e' il minimo che rispetta il livello: `c-1` non lo rispetta.
    c = critical_value(40, Q_NULL, ALPHA)
    if not binom_sf(40, c, Q_NULL) <= ALPHA < binom_sf(40, c - 1, Q_NULL):
        raise SelfTestFailed("valore critico non minimale a n=40")
    # [RATIFICA F3] La clausola sotto-40 verra' invocata a fine calendario,
    # quando non ci sara' modo di rifare questa verifica: la si fa ora, su
    # OGNI n della griglia, con le stesse identita' usate per n=40.
    for n in N_SOTTO_40_GRID:
        for p in (Q_NULL, Q_ALT):
            _assert_close(
                1.0,
                sum(binom_pmf(n, k, p) for k in range(n + 1)),
                f"massa binomiale sotto-40 n={n} p={p}",
            )
        d = design_for(n)
        _assert_close(
            d.alpha_effective,
            1.0 - sum(binom_pmf(n, k, Q_NULL) for k in range(d.critical)),
            f"alfa effettiva nei due versi n={n}",
        )
        _assert_close(
            d.power,
            1.0 - sum(binom_pmf(n, k, Q_ALT) for k in range(d.critical)),
            f"potenza nei due versi n={n}",
        )
        if d.alpha_effective > ALPHA:
            raise SelfTestFailed(f"dimensione effettiva sopra alfa a n={n}")
        if d.critical >= 1 and binom_sf(n, d.critical - 1, Q_NULL) <= ALPHA:
            raise SelfTestFailed(f"valore critico non minimale a n={n}")


# ==========================================================================
# PARTE B — i pavimenti della suite di regressione mordono?
# ==========================================================================

#: [VERBALE §A.10] Dimensione della suite di regressione.
SUITE_SNAPSHOTS = 15
SUITE_K = 5
#: [VERBALE §A.10 / DECISION_LOG TL-002] Le due regole di soglia e i pavimenti.
ALARM_DROP = 0.15
ALARM_FLOOR = 0.70
SUNSET_DROP = 0.30
SUNSET_FLOOR = 0.50
#: [RITO] Azioni distinte che una decisione puo' assumere nella simulazione.
#: Tre: long, short, flat. `close` esiste nel vocabolario ma non e' scelta su
#: uno snapshot senza posizione aperta, che e' la condizione della suite.
N_ACTIONS = 3
#: [RITO] Griglia dell'auto-accordo VERO su cui si valuta il morso del
#: pavimento. Dichiarata prima di guardare i risultati. Il valore vero non e'
#: misurabile finche' la baseline non esiste: la griglia serve a dire, per
#: ogni valore possibile, cosa succederebbe.
TRUE_AGREEMENT_GRID = (
    0.40,
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
    0.85,
    0.90,
    0.95,
    1.00,
)
#: [RITO] Ripetizioni Monte Carlo per ogni punto della griglia.
SUITE_TRIALS = 20_000


def _action_probs(p_pref: float) -> tuple[float, ...]:
    """Distribuzione delle azioni con `p_pref` sulla preferita.

    [RITO] Modello dichiarato: il modello ha un'azione preferita per snapshot,
    che sceglie con probabilita' `p_pref`; la massa restante si divide in parti
    uguali fra le altre due. E' il modello piu' semplice che produce un
    auto-accordo vero pari a `p_pref`, e la sua semplicita' e' una scelta, non
    una scoperta: una distribuzione a due modi darebbe pavimenti piu' severi.
    """
    resto = (1.0 - p_pref) / (N_ACTIONS - 1)
    return (p_pref,) + (resto,) * (N_ACTIONS - 1)


def _draw_snapshot(rng: random.Random, probs: tuple[float, ...], k: int) -> list[int]:
    """k campioni dalle azioni, come conteggi per azione."""
    counts = [0] * len(probs)
    for _ in range(k):
        u = rng.random()
        acc = 0.0
        for i, p in enumerate(probs):
            acc += p
            if u < acc:
                counts[i] += 1
                break
        else:
            counts[-1] += 1
    return counts


def thresholds(baseline: float) -> tuple[float, float, bool, bool]:
    """Le due soglie derivate dalla baseline, e se il pavimento ha morso.

    Riproduce `arena.regression.thresholds_from_baseline` senza importarlo:
    questo script deve poter girare anche se quel modulo cambia, e il confronto
    fra le due implementazioni e' esso stesso un'auto-verifica (vedi
    `_selftest_suite`).
    """
    alarm = max(baseline - ALARM_DROP, ALARM_FLOOR)
    sunset = max(baseline - SUNSET_DROP, SUNSET_FLOOR)
    return (
        alarm,
        sunset,
        alarm > baseline - ALARM_DROP,
        sunset > baseline - SUNSET_DROP,
    )


@dataclass(frozen=True, slots=True)
class SuiteOutcome:
    true_agreement: float
    mean_baseline: float
    mean_alarm: float
    mean_sunset: float
    floor_binds_alarm: float
    p_alarm_on_baseline: float
    p_sunset_on_baseline: float
    sd_monitoring: float


def simulate_suite(p_true: float, trials: int, rng: random.Random) -> SuiteOutcome:
    """Baseline e passata di controllo, entrambe simulate, sullo stesso modello.

    La domanda del §A.10: con quale probabilita' la suite allarma sul
    comportamento **di baseline**, cioe' quando NIENTE e' cambiato? Ogni
    ripetizione raccoglie una baseline (15 x 5), ne deriva le soglie con la
    regola TL-002, e poi fa girare una passata di controllo (15 x 5) sullo
    stesso identico modello. Un allarme li' dentro e' un falso allarme per
    costruzione.
    """
    probs = _action_probs(p_true)
    baselines: list[float] = []
    alarms: list[float] = []
    sunsets: list[float] = []
    floor_alarm = 0
    fired_alarm = 0
    fired_sunset = 0
    monitorings: list[float] = []

    for _ in range(trials):
        # --- raccolta della baseline -------------------------------------
        modal_actions: list[int] = []
        rates: list[float] = []
        for _ in range(SUITE_SNAPSHOTS):
            counts = _draw_snapshot(rng, probs, SUITE_K)
            top = max(range(len(counts)), key=lambda i: (counts[i], -i))
            modal_actions.append(top)
            rates.append(counts[top] / SUITE_K)
        baseline = sum(rates) / SUITE_SNAPSHOTS
        alarm, sunset, binds_a, _ = thresholds(baseline)

        # --- passata di controllo, stesso modello ------------------------
        obs: list[float] = []
        for idx in range(SUITE_SNAPSHOTS):
            counts = _draw_snapshot(rng, probs, SUITE_K)
            obs.append(counts[modal_actions[idx]] / SUITE_K)
        monitoring = sum(obs) / SUITE_SNAPSHOTS

        baselines.append(baseline)
        alarms.append(alarm)
        sunsets.append(sunset)
        monitorings.append(monitoring)
        floor_alarm += int(binds_a)
        fired_alarm += int(monitoring < alarm)
        fired_sunset += int(monitoring < sunset)

    media = sum(monitorings) / trials
    varianza = sum((m - media) ** 2 for m in monitorings) / trials
    return SuiteOutcome(
        true_agreement=p_true,
        mean_baseline=sum(baselines) / trials,
        mean_alarm=sum(alarms) / trials,
        mean_sunset=sum(sunsets) / trials,
        floor_binds_alarm=floor_alarm / trials,
        p_alarm_on_baseline=fired_alarm / trials,
        p_sunset_on_baseline=fired_sunset / trials,
        sd_monitoring=math.sqrt(varianza),
    )


def _selftest_suite() -> None:
    # La regola delle soglie coincide con quella del modulo di regressione.
    from arena.regression import thresholds_from_baseline

    for b in (0.40, 0.55, 0.70, 0.849, 0.85, 0.86, 0.95, 1.00):
        mio_alarm, mio_sunset, _, _ = thresholds(b)
        suo = thresholds_from_baseline(b).thresholds
        # `DriftThresholds` tiene i campi come `float | None`: None significa
        # "non ancora derivata dalla baseline". Qui la baseline c'e', quindi
        # non possono essere None, e se lo fossero l'auto-verifica deve
        # fallire invece di confrontare un None.
        if suo.agreement_alarm is None or suo.agreement_sunset is None:
            raise SelfTestFailed(f"soglie non derivate a baseline={b}")
        _assert_close(suo.agreement_alarm, mio_alarm, f"alarm a baseline={b}")
        _assert_close(suo.agreement_sunset, mio_sunset, f"sunset a baseline={b}")
    # A p_true = 1 il modello e' deterministico: baseline 1,0, nessun allarme.
    esito = simulate_suite(1.0, 200, random.Random(SEED))
    _assert_close(1.0, esito.mean_baseline, "baseline a p_true=1")
    _assert_close(0.0, esito.p_alarm_on_baseline, "allarmi a p_true=1")


# ==========================================================================
# PARTE C — il gate A.9: ponte k=30 -> k=3 e potenza del test di permutazione
# ==========================================================================

#: [VERBALE §A.9] k delle sonde e k della stagione.
K_PROBE = 30
K_SEASON = 3
#: [R-C, ratifica owner 20/08] `p_accordo` e' CATEGORIALE a tre livelli.
CATEGORIES = ("unanime", "maggioranza", "tutti_diversi")
#: [RICERCA, implicazioni operative Q3] Numero minimo di permutazioni da
#: dichiarare. Questo script calcola il p-value **esatto** per enumerazione
#: completa — che e' il limite a cui la procedura casuale tende — e usa il
#: campionamento solo per verificare l'enumerazione.
PERMUTATIONS_DECLARED = 10_000
#: [RITO] Ripetizioni Monte Carlo per ogni scenario di potenza.
GATE_TRIALS = 4_000


def bridge_k30_to_k3(counts30: tuple[int, int, int]) -> tuple[float, float, float]:
    """Ponte esatto k=30 -> k=3, per sottocampionamento senza reimmissione.

    [R-C] Da una sonda a k=30 con `counts30` campioni per azione, la
    distribuzione delle tre categorie di accordo quando se ne estraggono 3 e'
    ipergeometrica multivariata, e si calcola **enumerando**: nessuna
    simulazione, nessuna approssimazione.

      unanime       tutti e tre dalla stessa azione
      tutti_diversi uno per azione
      maggioranza   il complemento

    E' il ponte che rende confrontabile una sonda a k=30 con una stagione a
    k=3 senza rifare la sonda a k=3.
    """
    n = sum(counts30)
    if n < K_SEASON:
        raise ValueError(f"servono almeno {K_SEASON} campioni, ricevuti {n}")
    tot = math.comb(n, K_SEASON)
    unanime = sum(math.comb(c, K_SEASON) for c in counts30) / tot
    diversi = math.prod(counts30) / tot
    return unanime, 1.0 - unanime - diversi, diversi


def _tv(a: tuple[int, ...], pooled: tuple[int, ...], n1: int, n2: int) -> float:
    b = tuple(m - x for m, x in zip(pooled, a))
    return 0.5 * sum(abs(x / n1 - y / n2) for x, y in zip(a, b))


def _perm_pvalue_exact(real: tuple[int, ...], probe: tuple[int, ...]) -> float:
    """p-value ESATTO del test di permutazione a due campioni, in log-spazio.

    [R-C] Statistica dichiarata: **distanza in variazione totale** fra le due
    distribuzioni empiriche delle tre categorie,
    `T = 0,5 * somma_i |a_i/n1 - b_i/n2|`.

    Sotto l'ipotesi nulla di scambiabilita', i conteggi del primo gruppo
    seguono l'ipergeometrica multivariata sui conteggi aggregati. Il p-value e'
    quindi la somma delle masse delle tabelle con `T >= T_osservata`: una somma
    su al piu' `(n1+1)(n1+2)/2` termini, che si **enumera** invece di
    campionarla. E' lo stesso test dichiarato nel PREREG a >= 10.000
    permutazioni, calcolato al suo limite esatto.
    """
    n1, n2 = sum(real), sum(probe)
    pooled = tuple(a + b for a, b in zip(real, probe))
    n = n1 + n2

    t_obs = _tv(real, pooled, n1, n2)
    log_den = math.lgamma(n + 1) - math.lgamma(n1 + 1) - math.lgamma(n2 + 1)
    massa = 0.0
    totale = 0.0
    for a0 in range(min(n1, pooled[0]) + 1):
        for a1 in range(min(n1 - a0, pooled[1]) + 1):
            a2 = n1 - a0 - a1
            if a2 < 0 or a2 > pooled[2]:
                continue
            a = (a0, a1, a2)
            log_num = 0.0
            for m_i, a_i in zip(pooled, a):
                log_num += (
                    math.lgamma(m_i + 1)
                    - math.lgamma(a_i + 1)
                    - math.lgamma(m_i - a_i + 1)
                )
            w = math.exp(log_num - log_den)
            totale += w
            if _tv(a, pooled, n1, n2) >= t_obs - 1e-12:
                massa += w
    return massa / totale


def _perm_pvalue_rational(real: tuple[int, ...], probe: tuple[int, ...]) -> float:
    """Lo stesso p-value in aritmetica razionale esatta. Solo per l'auto-verifica.

    Non si usa nelle tabelle perche' su gruppi grandi e' lento; si usa per
    dimostrare che la versione in log-spazio non ha perso precisione.
    """
    n1, n2 = sum(real), sum(probe)
    pooled = tuple(a + b for a, b in zip(real, probe))

    def tv_exact(a: tuple[int, ...]) -> Fraction:
        b = tuple(m - x for m, x in zip(pooled, a))
        totale = Fraction(0)
        for x, y in zip(a, b):
            totale += abs(Fraction(x, n1) - Fraction(y, n2))
        return totale / 2

    t_obs = tv_exact(real)
    den = math.comb(n1 + n2, n1)
    massa = 0
    totale = 0
    for a0 in range(min(n1, pooled[0]) + 1):
        for a1 in range(min(n1 - a0, pooled[1]) + 1):
            a2 = n1 - a0 - a1
            if a2 < 0 or a2 > pooled[2]:
                continue
            a = (a0, a1, a2)
            w = math.prod(math.comb(m, x) for m, x in zip(pooled, a))
            totale += w
            if tv_exact(a) >= t_obs:
                massa += w
    if totale != den:
        raise SelfTestFailed(f"massa ipergeometrica {totale} != C(n,n1) {den}")
    return float(Fraction(massa, totale))


def _perm_pvalue_sampled(
    real: tuple[int, ...], probe: tuple[int, ...], rng: random.Random, m: int
) -> float:
    """Il p-value per permutazione CASUALE, la procedura dichiarata nel PREREG.

    Serve a mostrare che l'enumerazione esatta e la procedura dichiarata danno
    la stessa risposta: la prima e' il limite della seconda.
    """
    n1, n2 = sum(real), sum(probe)
    pooled = tuple(a + b for a, b in zip(real, probe))
    etichette = [i for i, c in enumerate(pooled) for _ in range(c)]
    t_obs = _tv(real, pooled, n1, n2)
    conta = 0
    for _ in range(m):
        rng.shuffle(etichette)
        a = [0, 0, 0]
        for e in etichette[:n1]:
            a[e] += 1
        if _tv(tuple(a), pooled, n1, n2) >= t_obs - 1e-12:
            conta += 1
    return conta / m


def _multinomial(rng: random.Random, n: int, p: tuple[float, ...]) -> tuple[int, ...]:
    counts = [0] * len(p)
    for _ in range(n):
        u = rng.random()
        acc = 0.0
        for i, pi in enumerate(p):
            acc += pi
            if u < acc:
                counts[i] += 1
                break
        else:
            counts[-1] += 1
    return tuple(counts)


def probe_counts_for(
    pi_probe: tuple[float, float, float], n_probe: int
) -> tuple[int, ...]:
    """I conteggi del gruppo sonda, arrotondati e richiusi sul totale."""
    grezzi = [round(n_probe * p) for p in pi_probe]
    grezzi[-1] = n_probe - sum(grezzi[:-1])
    if min(grezzi) < 0:
        raise ValueError(f"conteggi sonda negativi da {pi_probe} su {n_probe}")
    return tuple(grezzi)


def gate_power(
    pi_real: tuple[float, float, float],
    pi_probe: tuple[float, float, float],
    n_real: int,
    n_probe: int,
    trials: int,
    rng: random.Random,
    alpha: float = ALPHA,
) -> float:
    """Quota di stagioni in cui UN confronto rigetta, sotto lo scenario dichiarato.

    Il gruppo sonda si tiene FISSO ai suoi conteggi attesi: la sonda si fa una
    volta e il suo errore di campionamento non e' parte della variabilita' di
    una stagione. Il gruppo reale si ricampiona a ogni ripetizione.

    Questa e' la potenza **marginale** di un solo confronto. Il gate ne chiede
    due: vedi `gate_power_joint`.
    """
    probe = probe_counts_for(pi_probe, n_probe)
    cache: dict[tuple[int, ...], float] = {}
    rigetti = 0
    for _ in range(trials):
        real = _multinomial(rng, n_real, pi_real)
        p = cache.get(real)
        if p is None:
            p = _perm_pvalue_exact(real, probe)
            cache[real] = p
        rigetti += int(p < alpha)
    return rigetti / trials


def gate_power_joint(
    pi_real: tuple[float, float, float],
    pi_null: tuple[float, float, float],
    pi_blind: tuple[float, float, float],
    n_real: int,
    n_probe: int,
    trials: int,
    rng: random.Random,
    alpha: float = ALPHA,
) -> tuple[float, float, float]:
    """Potenza CONGIUNTA del gate: entrambi i confronti devono rigettare.

    [RITO — da firmare] Il §A.9 chiede che la distribuzione reale si distingua
    dalle sonde, e la ricerca del 20/08 (implicazioni operative, Q3) formula la
    regola cosi': se la distribuzione reale NON e' distinguibile da entrambe le
    sonde, `p_accordo` e' morto come oggetto di sizing. Le due sonde
    delimitano una banda: un accordo osservato e' informativo solo se sta
    **dentro** la banda e distinguibile da **tutti e due** i bordi. Un reale
    indistinguibile dal pavimento e' rumore; uno indistinguibile dal soffitto
    e' saturo e senza potere discriminante — il regime che Ding documenta sul
    modello frontier.

    La formulazione italiana del §A.9 ammette anche la lettura debole («basta
    distinguersi dalla nulla»): questa funzione calcola la lettura FORTE, che
    e' la piu' severa, e riporta anche le due marginali perche' la differenza
    fra le due letture sia visibile e firmabile.

    I due confronti condividono lo stesso gruppo reale e sono quindi
    correlati: la congiunta non e' il prodotto delle marginali, e per questo si
    simula invece di moltiplicare.
    """
    null_counts = probe_counts_for(pi_null, n_probe)
    blind_counts = probe_counts_for(pi_blind, n_probe)
    cache_n: dict[tuple[int, ...], float] = {}
    cache_b: dict[tuple[int, ...], float] = {}
    solo_nulla = solo_cieca = entrambi = 0
    for _ in range(trials):
        real = _multinomial(rng, n_real, pi_real)
        pn = cache_n.get(real)
        if pn is None:
            pn = _perm_pvalue_exact(real, null_counts)
            cache_n[real] = pn
        pb = cache_b.get(real)
        if pb is None:
            pb = _perm_pvalue_exact(real, blind_counts)
            cache_b[real] = pb
        rn, rb = pn < alpha, pb < alpha
        solo_nulla += int(rn)
        solo_cieca += int(rb)
        entrambi += int(rn and rb)
    return solo_nulla / trials, solo_cieca / trials, entrambi / trials


def _selftest_gate() -> None:
    # 1. Il ponte e' una distribuzione di probabilita'.
    for counts in ((30, 0, 0), (10, 10, 10), (28, 1, 1), (15, 14, 1), (20, 7, 3)):
        _assert_close(1.0, sum(bridge_k30_to_k3(counts)), f"ponte {counts}")
    # 2. Ponte su una sonda deterministica: 30 campioni uguali -> sempre unanime.
    _assert_close(1.0, bridge_k30_to_k3((30, 0, 0))[0], "ponte su sonda forzata")
    # 3. Ponte a caso: tre azioni equiprobabili con 10 campioni ciascuna.
    #    P(tutti diversi) = 10*10*10 / C(30,3) = 1000/4060.
    _assert_close(1000 / 4060, bridge_k30_to_k3((10, 10, 10))[2], "ponte equiprobabile")
    # 4. Log-spazio contro aritmetica razionale esatta.
    casi = (
        ((30, 10, 0), (300, 140, 10)),
        ((40, 0, 0), (400, 50, 0)),
        ((20, 15, 5), (200, 180, 70)),
        ((13, 13, 14), (150, 150, 150)),
    )
    for real, probe in casi:
        _assert_close(
            _perm_pvalue_rational(real, probe),
            _perm_pvalue_exact(real, probe),
            f"p-value esatto vs log-spazio su {real} / {probe}",
        )
    # 5. Enumerazione contro la procedura dichiarata a 10.000 permutazioni.
    rng = random.Random(SEED)
    for real, probe in casi:
        esatto = _perm_pvalue_exact(real, probe)
        campionato = _perm_pvalue_sampled(real, probe, rng, PERMUTATIONS_DECLARED)
        se = math.sqrt(max(esatto * (1 - esatto), 1e-12) / PERMUTATIONS_DECLARED)
        if abs(esatto - campionato) > MC_TOL_SIGMA * se:
            raise SelfTestFailed(
                f"permutazione campionata {campionato:.4f} lontana da "
                f"{esatto:.4f} oltre {MC_TOL_SIGMA} sigma ({se:.4f}) su {real}"
            )


# ==========================================================================
# Scenari dichiarati del gate
# ==========================================================================

#: [RITO] Distribuzioni della sonda. Nessuna sonda e' ancora stata eseguita:
#: questi sono scenari, non misure, e la tabella si legge come "se la sonda
#: cadesse qui, la potenza sarebbe questa".
PROBE_SCENARIOS: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("nulla ideale (forzata)", (1.00, 0.00, 0.00)),
    ("nulla con rumore", (0.95, 0.05, 0.00)),
    ("cieca, prior forte", (0.60, 0.35, 0.05)),
    ("cieca, prior debole", (0.40, 0.45, 0.15)),
)

#: [RITO, tranne dove marcato S0] Distribuzioni dei mondi reali.
REAL_SCENARIOS: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("S0 osservata (3 unanimi + 1 magg.) [S0]", (0.75, 0.25, 0.00)),
    ("quasi sempre unanime", (0.90, 0.10, 0.00)),
    ("unanime 4 volte su 5", (0.80, 0.20, 0.00)),
    ("un po' di disaccordo", (0.70, 0.25, 0.05)),
    ("disaccordo frequente", (0.60, 0.35, 0.05)),
    ("disaccordo dominante", (0.50, 0.40, 0.10)),
)

#: [RITO] Le due dimensioni del gruppo sonda, entrambe riportate.
#: - 450 = 15 mondi x 30 chiamate: il numero di chiamate al modello DAVVERO
#:   indipendenti. E' la lettura conservativa e va usata per firmare.
#: - 60.900 = 15 mondi x C(30,3): l'enumerazione di tutte le terne estraibili.
#:   Non sono osservazioni indipendenti — sono sottoinsiemi degli stessi 30
#:   campioni — e trattarle come tali rende il test anticonservativo. Si
#:   riporta per mostrare quanto la scelta pesa, non per usarla.
PROBE_SIZES = (450, 60_900)


# ==========================================================================
# Stampa
# ==========================================================================


def _riga(*celle: str) -> str:
    return " | ".join(celle)


def parte_a() -> None:
    print("=" * 78)
    print("PARTE A - la derivazione di n = 40 coppie giornata-asset")
    print("=" * 78)
    print(
        f"\nIpotesi [VERBALE A.8]: H0 q <= {Q_NULL:.2f} contro q = {Q_ALT:.2f}, "
        f"alfa = {ALPHA:.2f} unilaterale, potenza richiesta {POWER_TARGET:.0%}.\n"
    )
    print(_riga("   n", "c critico", "alfa effettiva", "potenza a q=0,25", "esito"))
    print("-" * 66)
    for n in (10, 20, 25, 30, 33, 34, 35, 36, 38, 40, 42, 45, 50):
        d = design_for(n)
        print(
            _riga(
                f"{d.n:4d}",
                f"{d.critical:9d}",
                f"{d.alpha_effective:14.4f}",
                f"{d.power:16.4f}",
                "  OK" if d.ok else "  --",
            )
        )
    n_min = smallest_n()
    d40 = design_for(N_PAIRS_DECLARED)
    dmin = design_for(n_min)
    print(
        f"\nMinimo n che raggiunge {POWER_TARGET:.0%}: {n_min} "
        f"(c = {dmin.critical}, potenza {dmin.power:.4f}, "
        f"dimensione effettiva {dmin.alpha_effective:.4f})."
    )
    print(
        f"A n = {N_PAIRS_DECLARED} [VERBALE A.8]: si rigetta H0 con "
        f">= {d40.critical} coppie in disaccordo su {N_PAIRS_DECLARED} "
        f"(= {d40.critical / N_PAIRS_DECLARED:.1%}); potenza {d40.power:.4f}, "
        f"dimensione effettiva {d40.alpha_effective:.4f}."
    )
    cali = [
        (n, design_for(n).power, design_for(n + 1).power)
        for n in range(20, 60)
        if design_for(n + 1).power < design_for(n).power
    ]
    print(
        f"\nNon-monotonia del test esatto: fra n=20 e n=60 la potenza SCENDE "
        f"passando a n+1 in {len(cali)} casi. Esempi: "
        + ", ".join(f"n={n} ({p0:.3f} -> {p1:.3f})" for n, p0, p1 in cali[:4])
        + "."
    )
    print(
        f"\nStima puntuale di S0 [S0]: {S0_DISAGREEMENT[0]} coppia su "
        f"{S0_DISAGREEMENT[1]} in disaccordo = "
        f"{S0_DISAGREEMENT[0] / S0_DISAGREEMENT[1]:.2f}. E' una stima su "
        f"quattro osservazioni: fonda il calcolo, non lo conferma."
    )
    print("\nGiornate attese per raccogliere 40 coppie valide:\n")
    print(
        _riga("tasso di fallimento", "P(coppia valida)", "giornate attese", "verbale")
    )
    print("-" * 70)
    attese_verbale = {0.00: 20, 0.05: 23, S0_FAILURE_RATE: 28}
    for f in FAILURE_RATES:
        g = expected_days(N_PAIRS_DECLARED, f)
        print(
            _riga(
                f"{f:19.4f}",
                f"{(1 - f) ** REPLICAS:16.4f}",
                f"{g:15.2f}",
                f"{attese_verbale[f]:7d}",
            )
        )
    atteso_s0 = expected_days(N_PAIRS_DECLARED, S0_FAILURE_RATE)
    print(
        f"\nLe tre attese del verbale (20 / 23 / 28) si riproducono arrotondando "
        f"all'intero piu' vicino. Cap di calendario {CALENDAR_CAP_DAYS} giorni "
        f"[VERBALE A.8]: al tasso di S0 l'attesa e' {atteso_s0:.1f} giornate, "
        f"cioe' il cap lascia un margine di "
        f"{CALENDAR_CAP_DAYS - atteso_s0:.1f} giornate sull'ATTESA, non sulla coda."
    )


def parte_a_sotto_40() -> None:
    """[RATIFICA F3] La clausola sotto-40, tabellata prima della raccolta."""
    print("\n" + "=" * 78)
    print("PARTE A.2 - la clausola sotto-40 (ratifica F3 dell'owner, 2026-08-20)")
    print("=" * 78)
    print(
        f"\nSe a fine calendario le coppie valide sono n < {N_PAIRS_DECLARED}, il "
        f"test si esegue all'n raggiunto,\ncol valore critico di questa tabella e "
        f"la potenza riportata ACCANTO all'esito.\nStesse ipotesi della Parte A: "
        f"H0 q <= {Q_NULL:.2f} contro q = {Q_ALT:.2f}, alfa = {ALPHA:.2f} "
        f"unilaterale.\n"
    )
    print(
        _riga(
            "   n",
            "c critico",
            " soglia %",
            "alfa effettiva",
            "potenza a q=0,25",
            "esito",
        )
    )
    print("-" * 78)
    for n in N_SOTTO_40_GRID:
        d = design_for(n)
        print(
            _riga(
                f"{d.n:4d}",
                f"{d.critical:9d}",
                f"{d.critical / d.n:9.1%}",
                f"{d.alpha_effective:14.4f}",
                f"{d.power:16.4f}",
                "  OK" if d.ok else "  --",
            )
        )
    sotto = [n for n in N_SOTTO_40_GRID if not design_for(n).ok]
    peggiore = min(N_SOTTO_40_GRID, key=lambda n: design_for(n).power)
    d_peggiore = design_for(peggiore)
    print(
        f"\nDei {len(N_SOTTO_40_GRID)} valori tabellati, {len(sotto)} NON "
        f"raggiungono la potenza {POWER_TARGET:.0%}: la clausola sotto-40 produce"
        f"\nquasi sempre un test sottopotenziato, ed e' il motivo per cui la "
        f"potenza va stampata accanto\nall'esito invece che in nota. Il punto "
        f"peggiore della griglia e' n = {peggiore} "
        f"(potenza {d_peggiore.power:.4f}, c = {d_peggiore.critical})."
    )
    cali = [
        (n, design_for(n).power, design_for(n + 1).power)
        for n in N_SOTTO_40_GRID
        if n + 1 <= N_PAIRS_DECLARED and design_for(n + 1).power < design_for(n).power
    ]
    if cali:
        print(
            "La non-monotonia morde anche dentro la griglia: "
            + ", ".join(
                f"n={n} -> {n + 1} ({p0:.4f} -> {p1:.4f})" for n, p0, p1 in cali
            )
            + "."
        )
    print(
        "Nessuna riga di questa tabella autorizza a fermare la raccolta prima "
        f"del cap: l'obiettivo resta {N_PAIRS_DECLARED} coppie."
    )


def parte_b() -> None:
    print("\n" + "=" * 78)
    print("PARTE B - i pavimenti della suite mordono sul comportamento di baseline?")
    print("=" * 78)
    print(
        f"\nSuite [VERBALE A.10]: {SUITE_SNAPSHOTS} snapshot x k={SUITE_K}. "
        f"Regola TL-002: allarme = max(baseline - {ALARM_DROP}, {ALARM_FLOOR}), "
        f"sunset = max(baseline - {SUNSET_DROP}, {SUNSET_FLOOR})."
    )
    print(
        f"Modello [RITO]: azione preferita con probabilita' p_vero, le altre due "
        f"in parti uguali. {SUITE_TRIALS:,} ripetizioni per punto, seme {SEED}.\n"
    )
    print(
        _riga(
            "p_vero",
            "baseline media",
            "allarme",
            "sunset",
            "pavim. morde",
            "P(allarme)",
            "P(sunset)",
        )
    )
    print("-" * 86)
    rng = random.Random(SEED)
    esiti = []
    for p in TRUE_AGREEMENT_GRID:
        e = simulate_suite(p, SUITE_TRIALS, rng)
        esiti.append(e)
        print(
            _riga(
                f"{p:6.2f}",
                f"{e.mean_baseline:14.4f}",
                f"{e.mean_alarm:7.4f}",
                f"{e.mean_sunset:6.4f}",
                f"{e.floor_binds_alarm:12.1%}",
                f"{e.p_alarm_on_baseline:10.4f}",
                f"{e.p_sunset_on_baseline:9.4f}",
            )
        )
    print(
        "\nLa colonna «baseline media» e' SEMPRE sopra p_vero: con k=5 e tre "
        "azioni la quota modale non puo' scendere sotto 2/5, quindi la baseline "
        "misurata e' una stima DISTORTA VERSO L'ALTO dell'auto-accordo vero. "
        "E' la ragione per cui il pavimento morde a valori di p_vero piu' bassi "
        "di quanto l'avvertenza del A.10 lascerebbe temere leggendo p_vero al "
        "posto della baseline."
    )
    peggiore = max(esiti, key=lambda e: e.p_alarm_on_baseline)
    print(
        f"\nCaso peggiore della griglia: p_vero = {peggiore.true_agreement:.2f}, "
        f"P(allarme sul comportamento di baseline) = "
        f"{peggiore.p_alarm_on_baseline:.4f}, P(sunset) = "
        f"{peggiore.p_sunset_on_baseline:.4f}."
    )
    sd_media = sum(e.sd_monitoring for e in esiti) / len(esiti)
    print(
        f"\nDeviazione standard della passata di controllo (15 snapshot x k=5), "
        f"per p_vero: min {min(e.sd_monitoring for e in esiti):.4f}, "
        f"media {sd_media:.4f}, max {max(e.sd_monitoring for e in esiti):.4f}."
    )
    peggiore_sd = max(esiti, key=lambda e: e.sd_monitoring)
    print(
        f"Il verbale A.10 dichiara un errore standard di 0,050 e un calo di 0,15 "
        f"come evento a 3,0 sigma. La simulazione da' un massimo di "
        f"{peggiore_sd.sd_monitoring:.4f} (a p_vero = "
        f"{peggiore_sd.true_agreement:.2f}), cioe' un calo di 0,15 vale "
        f"{0.15 / peggiore_sd.sd_monitoring:.1f} sigma nel caso piu' rumoroso "
        f"della griglia."
    )


def parte_c() -> None:
    print("\n" + "=" * 78)
    print("PARTE C - il gate A.9: ponte k=30 -> k=3 e potenza della permutazione")
    print("=" * 78)
    print(
        f"\nPonte esatto [R-C]: da una sonda a k={K_PROBE} si deriva per "
        f"sottocampionamento senza reimmissione la distribuzione delle "
        f"{len(CATEGORIES)} categorie a k={K_SEASON}. "
        f"C({K_PROBE},{K_SEASON}) = {math.comb(K_PROBE, K_SEASON)} terne.\n"
    )
    print(_riga("sonda a k=30 (long/short/flat)", "unanime", "maggioranza", "diversi"))
    print("-" * 74)
    for counts in (
        (30, 0, 0),
        (29, 1, 0),
        (27, 2, 1),
        (24, 5, 1),
        (20, 8, 2),
        (18, 9, 3),
        (15, 10, 5),
        (12, 10, 8),
        (10, 10, 10),
    ):
        u, m, d = bridge_k30_to_k3(counts)
        print(_riga(f"{counts!s:30s}", f"{u:7.4f}", f"{m:11.4f}", f"{d:7.4f}"))
    print(
        f"\nPotenza del gate. Test primario [R-C]: permutazione a due campioni "
        f"sulla distanza in variazione totale, dichiarata a >= "
        f"{PERMUTATIONS_DECLARED:,} permutazioni e qui calcolata al suo limite "
        f"esatto per enumerazione. n_reale = {N_PAIRS_DECLARED} coppie, "
        f"alfa = {ALPHA}, {GATE_TRIALS:,} stagioni simulate per cella, "
        f"seme {SEED}."
    )
    for n_probe in PROBE_SIZES:
        etichetta = (
            "chiamate indipendenti (15 x 30) - LETTURA CONSERVATIVA"
            if n_probe == 450
            else "terne enumerate (15 x C(30,3)) - anticonservativa"
        )
        print(f"\n--- n_sonda = {n_probe:,}: {etichetta} ---\n")
        print(
            _riga(
                f"{'scenario reale \\ sonda':42s}",
                *(f"{nome[:20]:>20s}" for nome, _ in PROBE_SCENARIOS),
            )
        )
        print("-" * (44 + 23 * len(PROBE_SCENARIOS)))
        rng = random.Random(SEED)
        for nome_r, pi_r in REAL_SCENARIOS:
            celle = [
                f"{gate_power(pi_r, pi_p, N_PAIRS_DECLARED, n_probe, GATE_TRIALS, rng):20.3f}"
                for _, pi_p in PROBE_SCENARIOS
            ]
            print(_riga(f"{nome_r:42s}", *celle))
        print("\ncontrollo di dimensione (reale = sonda, deve dare circa alfa):")
        for nome_p, pi_p in PROBE_SCENARIOS:
            pot = gate_power(pi_p, pi_p, N_PAIRS_DECLARED, n_probe, GATE_TRIALS, rng)
            print(f"    {nome_p:30s} -> {pot:.4f}")


def parte_c_congiunta() -> None:
    """La potenza che il gate ha DAVVERO: entrambi i confronti devono rigettare."""
    print(NL + "=" * 78)
    print("PARTE C.2 - potenza CONGIUNTA del gate (lettura forte)")
    print("=" * 78)
    print(
        f"{NL}Regola forte [RITO, da firmare]: p_accordo sopravvive solo se la "
        f"stagione si distingue da ENTRAMBE le sonde. n_sonda = 450 (lettura "
        f"conservativa), n_reale = {N_PAIRS_DECLARED}, alfa = {ALPHA}, "
        f"{GATE_TRIALS:,} stagioni per cella, seme {SEED}.{NL}"
    )
    coppie = (
        ("nulla ideale + cieca prior forte", (1.00, 0.00, 0.00), (0.60, 0.35, 0.05)),
        ("nulla ideale + cieca prior debole", (1.00, 0.00, 0.00), (0.40, 0.45, 0.15)),
        (
            "nulla con rumore + cieca prior forte",
            (0.95, 0.05, 0.00),
            (0.60, 0.35, 0.05),
        ),
        (
            "nulla con rumore + cieca prior debole",
            (0.95, 0.05, 0.00),
            (0.40, 0.45, 0.15),
        ),
    )
    rng = random.Random(SEED)
    for nome_coppia, pi_n, pi_b in coppie:
        print(f"--- {nome_coppia} ---")
        print(
            _riga(
                f"{'scenario reale':42s}",
                "vs nulla",
                "vs cieca",
                "CONGIUNTA",
                "perdita",
            )
        )
        print("-" * 88)
        for nome_r, pi_r in REAL_SCENARIOS:
            m_n, m_b, cong = gate_power_joint(
                pi_r, pi_n, pi_b, N_PAIRS_DECLARED, 450, GATE_TRIALS, rng
            )
            print(
                _riga(
                    f"{nome_r:42s}",
                    f"{m_n:8.3f}",
                    f"{m_b:8.3f}",
                    f"{cong:9.3f}",
                    f"{min(m_n, m_b) - cong:7.3f}",
                )
            )
        print()
    print(
        "La colonna «perdita» e' la differenza fra la marginale peggiore e la "
        "congiunta: quanto costa pretendere che ENTRAMBI i confronti rigettino "
        "sulla STESSA stagione. Non e' zero perche' i due confronti condividono "
        "il gruppo reale e sono correlati; non e' il prodotto delle marginali "
        "per la stessa ragione."
    )


def main() -> int:
    print("run2_power.py - derivazioni di potenza del RUN2")
    print(
        f"seme = {SEED} - tolleranza esatta = {EXACT_TOL:g} - "
        f"tolleranza Monte Carlo = {MC_TOL_SIGMA:g} sigma"
    )
    print("\nAUTO-VERIFICHE")
    for nome, fn in (
        ("binomiale esatta", _selftest_binomial),
        ("suite di regressione", _selftest_suite),
        ("ponte e permutazione", _selftest_gate),
    ):
        fn()
        print(f"  [ok] {nome}")
    print()
    parte_a()
    parte_a_sotto_40()
    parte_b()
    parte_c()
    parte_c_congiunta()
    print(
        f"\n\nSeme proposto per la baseline coin-flip del A.13: "
        f"{COINFLIP_SEED_PROPOSTO}. DA FIRMARE nel PREREG: questo file lo "
        f"propone, non lo decide."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
