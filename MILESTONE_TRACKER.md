# MILESTONE_TRACKER — Trader Lab

> **Nessuna stagione parte da qui.** Questo repo è un cantiere. Il cronometro
> della Stagione 0 si avvia **solo** dopo il GO del Pre-Screen (che gira in
> `zeroPipes`) e con autorizzazione esplicita dell'owner.

---

## Decisioni owner congelate (D1-D4)

Non riaperte in Fase 0. Dettaglio e conseguenze in `DECISION_LOG.md` (TL-001).

| ID | Decisione | Dove vive nel codice |
| --- | --- | --- |
| **D1** | 3 repliche **identiche**: stesso modello, stesso prompt, stessa temperatura, stesso snapshot | `arena/runner.py`, `arena/config.py` |
| **D2** | ⚠️ **Superata da TL-002** → modello pinnato **`claude-fable-5`**. Principio invariato: model string più specifica disponibile, registrata nel Freeze manifest, **cambio modello = nuovo track record** | `contracts/freeze.py`, `arena/llm_client.py` |
| **D3** | Stagione 0 = **4 settimane shadow a size FISSA**; il Trader decide solo direzione e dentro/fuori; `confidence` loggata dal giorno uno per il Brier score | `arena/risk_officer.py`, `ledger/telemetry.py` |
| **D4** | Temperatura = **default operativo dell'API**, nessun override, **MAI 0**; ogni parametro di sampling dichiarato nel manifest | `contracts/freeze.py`, `arena/llm_client.py` |

**Nota D2 (TL-002, 2026-08-13).** Il Trader è pinnato su **`claude-fable-5`**,
il modello più capace disponibile via API: il Lab chiede se un agente LLM sa
battere la macchina, e la domanda merita il cervello più forte. Anche qui la
string è **completa così com'è**: non esiste una variante datata e un suffisso
data produce 404. Il pin **non è ancora effettuato** (`ots_pending=True`);
`scripts/verify_pin.py` ri-verifica la string contro l'endpoint il giorno del
pin. Il **fallback server-side è deliberatamente disattivato**: servirebbe un
rifiuto con un altro modello, cioè produrre track record con un modello diverso
da quello pinnato.

**Nota D4 (ri-verificata su Fable, TL-002).** **Policy identica e confermata.**
Su `claude-fable-5` i parametri di sampling non-default sono rifiutati con 400,
quindi il default operativo si ottiene **per omissione** — il client non invia
`temperature`, `top_p`, `top_k`. Lo stesso vale per `thinking`, che su Fable è
sempre attivo e non disattivabile: `thinking_policy=api_default` è l'unico
valore ammesso e il client rifiuta gli altri.

**Precondizione operativa nuova (Fable).** `claude-fable-5` richiede **30
giorni di data retention**: con l'organizzazione in zero-data-retention *ogni*
chiamata risponde 400, indipendentemente dal payload. Da verificare prima del
pin.

---

## Fase 0 — stato per blocco

| # | Blocco | Stato | Commit |
| --- | --- | --- | --- |
| 1 | Scaffold + contratti Pydantic v2 | ✅ fatto | `feat(blocco1)` |
| 2 | Tool Server con snapshot congelato | ✅ fatto | `feat(blocco2)` |
| 3 | Decision Record enforcement + Risk Officer | ✅ fatto | `feat(blocco3)` |
| 4 | Ledger + telemetria + e-process | ✅ fatto | `feat(blocco4)` |
| 5 | Orchestratore repliche | ✅ fatto | `feat(blocco5)` |
| 6 | Suite di regressione comportamentale (design + scheletro) | ✅ fatto | `feat(blocco6)` |

**Suite**: 213 test verdi, 1 skipped (lo smoke con API reale, dietro flag).
La suite gira **senza rete e senza API key**.

### Blocco 1 — Scaffold + contratti ✅

- `pyproject.toml` (uv, Python 3.13), struttura del repo, `.env.example`.
- `CLAUDE.md`: le 11 regole del Lab.
- Contratti frozen / `extra="forbid"`: `MarketSnapshot` (con `snapshot_id` =
  sha256 del contenuto canonico), `DecisionRecord` (schema v1),
  `RiskVerdict`, `ShadowFill`, `OutcomeAnnotation`, `FreezeManifest`.
- Vocabolario chiuso delle feature primitive (`contracts/vocabulary.py`).
- Test: round-trip di serializzazione, immutabilità, rifiuto dei campi extra,
  determinismo dello `snapshot_id`, disciplina point-in-time.

### Blocco 2 — Tool Server con snapshot congelato ✅

- `SnapshotBuilder`: snapshot del giorno costruito UNA volta, a ora UTC fissa,
  da API pubblica Hyperliquid. Universo placeholder marcato **dentro** lo
  snapshot. Filtro anti look-ahead strutturale (solo barre chiuse).
- `SnapshotStore`: persistenza per `snapshot_id`, ri-validazione in lettura.
- `ToolRegistry`: sei tool read-only, strict e chiusi, con descrizioni neutre.
- Log JSONL append-only di ogni tool call, anche di quelle fallite.
- Firewall: store e registry non importano `httpx` né il client Hyperliquid;
  ogni path contenente `zeropipes` è rifiutato; la rete richiede un flag.

### Blocco 3 — Decision Record enforcement + Risk Officer ✅

- Parser che impone **razionale libero PRIMA, blocco strutturato DOPO**.
  `tool_choice` deliberatamente **non** forzato: forzarlo sopprimerebbe il
  testo che deve precedere.
- Verbale non conforme = NO TRADE (`rejected_malformed`), con motivo
  categorizzato e un solo retry dichiarato.
- `RiskOfficer` puro: asset ammesso → un cambio al giorno → size fissa (D3) →
  cap leva 3x → anti-martingala (dormiente con size fissa, testata comunque).

### Blocco 4 — Ledger + telemetria + e-process ✅

- Ledger JSONL append-only con hash-chain e `verify()` che dice **dove** si
  rompe; write-once per (giorno, replica, asset), persistente tra riaperture.
- Telemetria per replica: turnover, flip rate, tentativi bloccati per regola,
  tasso di malformati, dispersione inter-repliche, componenti del Brier.
- E-process anytime-valid (betting + ONS), **unilaterale** per costruzione.
- Kill-criterion pre-registrato **in codice**.

### Blocco 5 — Orchestratore repliche ✅

- Runner giornaliero: snapshot congelato → 3 repliche in isolamento → verbali
  → Risk Officer → ShadowFill → ledger.
- Client Anthropic con model string dal manifest, **nessun parametro di
  sampling inviato** (D4), API key solo da env, retry/backoff sui soli errori
  ritentabili, budget guard giornaliero.
- `MockLLM` deterministico: la pipeline gira end-to-end **senza API**.
- Smoke con API reale isolato dietro `TRADERLAB_ALLOW_LIVE_API=1`.

### Blocco 6 — Suite di regressione comportamentale ✅ (design + scheletro)

- Set di 10-15 Decision Snapshot congelabile **una volta e mai più**
  (`freeze()` rifiuta di sovrascrivere), k=5 campioni per snapshot, cadenza
  settimanale.
- Metrica di deriva **dichiarata ora**, prima di ogni baseline.
- Soglie `TODO-owner`: `collect_baseline()` e `evaluate()` **sollevano** se non
  sono state fissate. Nessun default silenzioso.
- Un verbale malformato conta come **disaccordo**, non come campione da
  scartare: un modello che smette di rispettare il protocollo è derivato.

---

## Dopo Fase 0 — stato per milestone

### Pre-Volo S0 ✅ (`3bc9a9c`)

- Primo snapshot **reale** Hyperliquid collaudato (non più placeholder).
- Universo promosso a **ufficiale**: BTC + ETH, perimetro P3 della campagna
  carry, dal Pre-Screen C2 (`zeroPipes`). Chiude la voce 1 di "cosa manca"
  sotto.
- Tre difetti nel percorso del funding, trovati dal primo snapshot vero e
  corretti: paginazione di `fundingHistory` (si fermava dopo ~20 giorni su
  120 di lookback), `interval_hours` osservato dai dati invece che fissato a
  8.0, `funding_rate_mean_7d` derivato da `interval_hours` invece di 21 punti
  fissi.
- Guardrail in codice (`CLAUDE.md` §2/§7): il builder rifiuta il funding più
  vecchio di `max_funding_staleness_hours` (default **48h**,
  `toolserver/config.py`) invece di servirlo.

### Hardening ✅ (`1ff152a`, `67acd77`, `a820732`, `6c8998e`, `4a97522`, `e2205a4`, `9172b29`)

- Retry sugli errori in-stream (`overloaded`/`rate_limit`), trovato dallo
  smoke test.
- Telemetria dei tentativi + retry a livello di rito, finestra di 45 minuti
  (exit code 7 dedicato, vedi `docs/OPERATIONS.md` §3).
- Soak: 7 giornate simulate end-to-end con `MockLLM` (zero rete), +2 fix
  (telemetria cross-giornata, `run_id` disallineato dal tool log).
- Rito quotidiano schedulabile + policy dei giorni mancati (`skipped_day`).
- `max_tokens` alzato a 8000 (anti-shedding) + guardia sulla troncamento.
- Fix dell'harness di smoke (sha reale, budget 16 — multi-turn osservato).

### Pin ✅ (`1a12fb0`, `c2d2be6`)

- Persona `trader_v0` promossa dalla bozza `trader_v0_proposta` (revisione
  HR del 13/08/2026); manifest congelato: `pinned_at_utc =
  2026-08-13T16:25:58Z`, `model_string = claude-fable-5`, `sampling_policy =
  api_default_omitted`, `thinking_policy = api_default`, `max_tokens = 8000`
  (`manifests/trader_v0_freeze_manifest.json`, `freeze_id`
  `f37b8c2c98351e…`).
- Prompt caching aggiunto pre-timbro: tre blocchi `cache_control: ephemeral`
  (system prompt, ultima definizione di tool, ultimo `tool_result`).
- `scripts/verify_pin.py` dichiara 4 controlli: model string risolta
  sull'endpoint, nessuna variante datata più specifica, D4 (chiamata senza
  sampling accettata / `temperature` esplicita rifiutata), `thinking:
  disabled` rifiutato.
- **Nota non ancora chiusa**: il campo `ots_pending` dentro il manifest legge
  ancora `true` — non risulta aggiornato dopo il timbro OTS. I file
  `.ots` (sotto) esistono e sono committati; una proof OTS "pending" in
  attesa di conferma su Bitcoin è comportamento normale della libreria, ma
  resta da eseguire l'`upgrade` e verificare che il campo nel manifest venga
  aggiornato di conseguenza.

### PREREG_LAB_S0 congelata ✅ (`9ef5681`) + OTS ✅ (`b1ee4d8`)

- `docs/PREREG_LAB_S0.md` congelata il 13/08/2026, prima di ogni baseline.
  §8 fissa il rito del pin come precondizione al primo giorno di S0.
- Timbro OTS locale (`scripts/ots_stamp.py`, libreria `opentimestamps`
  diretta — `otsclient` risultava rotto su questa macchina) prodotto per
  `docs/PREREG_LAB_S0.md.ots` e `manifests/trader_v0_freeze_manifest.json.ots`.

### Stagione 0 autorizzata — TL-003 ✅ (`1852dbe`)

La firma dell'owner ("Stagione 0: via", PREREG_LAB_S0 §8) è **già a
registro** in `DECISION_LOG.md` (voce TL-003, commit `1852dbe`); questa
voce la referenzia, non la duplica.

### Stato del primo giorno (verificato il 14/08/2026, pomeriggio)

`data/logs/daily-2026-08-14.log` registra **due tentativi, entrambi fermati
con exit 2** (precondizione non soddisfatta) — non una prova di cablaggio
superata:

1. `00:00:02Z` — STOP: `-Live richiede TRADERLAB_ALLOW_LIVE_API=1` (variabile
   assente nell'ambiente in cui girava il task schedulato).
2. `14:37:49Z` — STOP: guardia sull'ora UTC (passata lanciata a mano alle
   14:37 invece delle 00:00 configurate — la guardia ha fatto il suo lavoro,
   non è un difetto).

Il task di Windows Task Scheduler (`traderLab — rito quotidiano`) risulta
`Ready`, con `LastTaskResult = 2`: **nessuna passata a esito 0 è registrata
finora**. `NextRunTime` = 15/08/2026 02:00 locale (CEST) = 15/08 00:00 UTC.

Le variabili d'ambiente **utente** `TRADERLAB_ALLOW_LIVE_API=1` e
`ANTHROPIC_API_KEY` risultano ora presenti sulla macchina (verificato
direttamente). Restano da confermare **al prossimo passaggio schedulato**:
il fallimento delle 00:00:02Z è compatibile con un task registrato *"Run
whether user is logged on or not"* che non eredita variabili d'ambiente
utente impostate fuori da una sessione interattiva — vedi la nota operativa
in `docs/OPERATIONS.md` §4.

**Correzione rispetto alla stima informale circolata**: il primo giorno con
verbali non è confermato per il 15/08 in base a una "prova di cablaggio
superata" — nessuna passata a esito 0 risulta nei log consultati. 15/08
00:00 UTC è la data del prossimo slot schedulato; resta da verificare che
quella passata vada a buon fine prima di trattare il giorno come acquisito.

---

## Cosa manca per la Stagione 0

Nessuna di queste voci è risolvibile dentro `traderLab`: sono precondizioni.

| # | Manca | Chi/dove | Blocca |
| --- | --- | --- | --- |
| # | Manca | Chi/dove | Blocca |
| --- | --- | --- | --- |
| 2 | **Gamba meccanica per il confronto appaiato** | da costruire | Senza di essa l'e-process non ha un secondo braccio: gira solo su dati sintetici. Il kill-criterion non è valutabile. Non blocca S0 (PREREG_LAB_S0 §1: S0 non misura skill), blocca il gate S0→S1 (PREREG_LAB_S0 §7). |

~~1. Universo ufficiale dal Pre-Screen~~ → **chiusa dal Pre-Volo** (`3bc9a9c`): BTC + ETH, perimetro P3.

~~3. PREREG_LAB_S0~~ → **chiusa**: congelata in `9ef5681`, timbrata OTS in `b1ee4d8`.

~~4. Pin effettivo del modello + OTS del FreezeManifest~~ → **pin effettuato** (`1a12fb0`, manifest con
`pinned_at_utc` valorizzato) e **proof OTS committata** (`b1ee4d8`); resta l'incongruenza aperta sul
campo `ots_pending` del manifest, vedi nota "Pin" sopra.

~~5. Data retention a 30 giorni sull'organizzazione~~ → implicitamente verificata dal pin riuscito
(`verify_pin.py` richiede una chiamata live che fallirebbe con 400 in zero-data-retention); nessuna
prova esplicita del contrario nei log consultati.

~~5. Soglie della suite di regressione~~ → **chiuse da TL-002** (vedi sotto).

### Soglie della suite di regressione — fissate da TL-002 ✅

I quattro `TODO-owner` sono **chiusi**. L'owner ha fissato una regola, che
`arena.regression.thresholds_from_baseline` applica meccanicamente.

| Parametro | Valore | Stato |
| --- | --- | --- |
| Metrica di deriva primaria | **action agreement rate** | ✅ dichiarata |
| Metrica di deriva secondaria | **distanza assoluta media sulla confidence** | ✅ dichiarata |
| Numero di Decision Snapshot congelati | 10-15, **una volta e mai più toccati** | ✅ dichiarato |
| Campioni per snapshot (k) | 5 | ✅ dichiarato |
| Cadenza di rigioco | settimanale | ✅ dichiarata |
| Soglia di **ALLARME** su agreement | `baseline − 0.15`, pavimento **0.70** | ✅ TL-002 |
| Soglia di **SUNSET** su agreement | `baseline − 0.30`, pavimento **0.50** | ✅ TL-002 |
| Soglia di **ALLARME** su distanza confidence | **+0.10** | ✅ TL-002 |
| Soglia di **SUNSET** su distanza confidence | **+0.20** | ✅ TL-002 |

**Cosa resta da fare il giorno della baseline**: applicare la regola e
trascrivere i quattro valori assoluti in `arena/config.py`.
`ThresholdDerivation.as_config_literal()` li produce già formattati.

**Due punti di interpretazione dichiarati** (dettaglio in `DECISION_LOG.md`
TL-002): "baseline" è l'**auto-accordo** della baseline
(`Baseline.self_agreement_rate`), non 1.0; e il **pavimento può mordere** —
con auto-accordo ≤ 0.70 la suite allarmerebbe sul comportamento di baseline, e
la derivazione segnala il caso (`is_degenerate`) invece di nasconderlo.

**Pre-registrazione**: ora che le soglie si derivano dalla baseline,
l'artefatto pre-registrato è la **regola**. La sua impronta è incisa nella
`Baseline` alla raccolta, e `evaluate(report, baseline=...)` solleva
`ThresholdRuleChanged` se la regola è cambiata dopo aver visto i dati.

**Aggancio al model sunset**: deriva oltre la soglia di sunset ⇒ il track record
si chiude **pulito** in quel punto e ne inizia uno nuovo. Non si "aggiusta" un
track record che ha attraversato una deriva.

### Kill-criterion pre-registrato

Se la **dispersione inter-repliche domina il gap agente-macchina** sulla
finestra dichiarata, il verdetto è **"no skill misurabile"**. Il criterio è
codificato in `ledger/eprocess.py` e non è negoziabile a posteriori.
