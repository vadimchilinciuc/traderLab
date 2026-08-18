# APPENDICE DATATA — CADENZA DECISIONALE E SISTEMI INTRADAY — 2026-08-18 (parte B)

> **Tipo di documento**: appendice di ricerca + ponte tra chat. **Parte B.**
> **Presuppone la lettura di** `2026-08-18_RICERCA_ARCHITETTURE_AGENTE.md` (parte A), che
> contiene: la verifica di AMA, il reperto *The Alpha Illusion* con la tabella P1–P6, il
> Parametric Prior Lock-in, la mappatura di traderLab sui sei stadi modulari, la questione
> del sizing sulla confidence in Stagione 1, e l'Idea #13 (Pre-Screen di architetture).
> **Nulla di quel materiale è ripetuto qui.**
>
> Ordine di lettura per una chat nuova: handoff principale 16/08 → addendum notte 16 →
> giorno 16 → sera 16 → notte 16/17 → sera 17 → `CODA.md` → **parte A** → **questo file**.
>
> **Contenuto nuovo**: seconda annotazione di errore del consigliere (i "quattro rossi"
> sul daytrading), il ribaltamento alpha↔cognizione, l'analisi forense di QuantAgent alla
> fonte, tre reperti nuovi sulla cadenza, la tassonomia dei sistemi con verdetto di
> riuso, e il disegno dell'**Arena a due cadenze** (Idea #13-bis).
>
> **Nessun file di S0 toccato. Nessuna modifica a `src/`. Nessun commit. Nessun rito CLI.**
> **Metrica di fase invariata: "verdetti prodotti, non idee aggiunte."**
> La storia non si riscrive, si annota.

---

## §11 — SECONDA ANNOTAZIONE DI ERRORE DEL CONSIGLIERE

**Cosa è stato detto (18/08, in chat):** *"il daytrading coi modelli l'abbiamo già testato
quattro volte — Kronos, M5/ProFiT a 1h, M3.5, traderLab S0"*, usato come argomento contro
l'apertura di un filone intraday con agenti LLM.

**Cosa è vero:** Kronos, M5/ProFiT a 1h e M3.5 erano **gambe meccaniche o ibride**. Nessuna
delle tre era un agente LLM che decide a cadenza intraday. traderLab S0 gira a **cadenza
daily**.

**Conclusione:** *"l'abbiamo già testato"* è **falso** nella forma proposta dall'owner. Il
programma non ha mai fatto girare un agente LLM a cadenza intraday. Zero volte.

**Classificazione:** aggregazione indebita di esiti eterogenei sotto un'etichetta comune
("daytrading") per sostenere una conclusione già formata. Terzo esemplare in tre giorni
dello stesso difetto di famiglia (cfr. §1 della parte A, §8 dell'addendum sera 17/08).

**Cosa resta valido del "no":** solo **SR_min = z₀,₉₀/√anni**, che è aritmetica e non
opinione. Ma vincola **una sola domanda** — vedi §12.

**Correttivo aggiuntivo proposto (regola candidata 49-bis):** quando il consigliere cita
esiti passati come argomento contro una proposta nuova, deve elencare **quale esito, quale
gamba, quale cadenza** — non l'etichetta aggregata. Se non riesce a farlo dai file, non è
un argomento.

---

## §12 — IL RIBALTAMENTO: DUE DOMANDE, DUE POTENZE

Il difetto di tutta l'istruttoria precedente è stato rispondere a una domanda economica
quando l'owner ne poneva una cognitiva (*"come ragionano gli LLM in day trade e non"*).

| | domanda di **alpha** | domanda **cognitiva** |
|---|---|---|
| variabile misurata | Sharpe differenziale, P&L netto | Brier, ECE, dispersione, coerenza dichiarativa, turnover, composizione delle feature |
| unità di campione | **anni di osservazione** | **decisioni** |
| vincolo | SR_min = z₀,₉₀/√anni — invariante alla frequenza | nessuno equivalente |
| n disponibile in 20 giornate a cadenza daily | ~0,055 anni → **inutilizzabile** | 120 decisioni |
| n disponibile in 20 giornate a cadenza 4h | ~0,055 anni → **inutilizzabile** | **720 decisioni** |
| verdetto in 4 settimane? | **no, per teorema** | **sì** |

**Il punto centrale**: la cadenza non compra nulla sulla prima colonna e moltiplica per sei
la seconda. Un braccio intraday è quindi **inutile per l'alpha e potente per la cognizione**.

Questo cambia il verdetto del filtro da *"no al day trading"* a:
> **no alla domanda di alpha (per teorema), sì alla domanda cognitiva (con disegno
> pre-registrato e tetto di spesa dichiarato).**

---

## §13 — REPERTI NUOVI SULLA CADENZA (tre)

### 13.1 — Le firme cognitive sono misurabili — arXiv:2605.28850

*Representation Signatures and Risk-Feedback Alignment in LLM Trading Agents.*

Esperimenti su scenari storici, sintetici, **intraday** e di crisi (drawdown Tech/Rates
2022, shock SVB/banche regionali 2023). Reperto degli autori: l'evidenza forte **non è che
gli LLM tradino in profitto, ma che i loro fallimenti lasciano tracce misurabili**.

Nello specifico riportano: le rappresentazioni di pianificazione si spostano **prima** dei
drawdown; gli ancoraggi rolling pre-fallimento mostrano contrazione di rango effettivo in
più spazi di rappresentazione (hash, LSA, BGE-M3, stati nascosti white-box); controlli
lessicali escludono il semplice collasso per ripetizione di token; perturbazioni rumorose
degli OHLCV non cancellano l'accuratezza di allarme precoce; **feedback di rischio
strutturato altera l'intento successivo**; feedback placebo e contrarian espongono un
allineamento mal calibrato.

**Perché conta per noi**: è la prova di esistenza che la variabile dipendente proposta
dall'owner (*"come ragionano"*) è **misurabile e informativa anche quando il P&L non lo è**.
È il pivot metodologico che rende il filone intraday legittimo.

**Riserva**: parte delle misure richiede accesso agli stati nascosti (white-box). Su Fable
5 via API non è disponibile. Le nostre misure devono essere **comportamentali** (azione,
confidence, feature dichiarate, tool chiamati), non rappresentazionali.

### 13.2 — La cadenza è già stata misurata, e il collo di bottiglia è il turnover — arXiv:2608.09988

*OpenPM: Auditable Point-in-Time Evaluation for LLM Portfolio-Management Agents* (agosto 2026).

Disegno: sweep di cadenza esplicito, **44 ribilanciamenti dal 2026-03-02 al 2026-05-01**,
mandato bilanciato, analisti DeepSeek-V3.2, cinque costruttori.

Reperti strutturali (gli autori insistono di leggere la struttura, non la classifica —
i ranking per modello sono sensibili a regime e date, e sono stime a singola corsa):

1. **Il collo di bottiglia non è lo spread, è il turnover.** Il gate sui candidati filtra su
   un pool ordinato per liquidità, quindi lo spread non morde.
2. In modalità *once-then-hold* il libro gira solo alla costruzione → **netto ≈ lordo**.
3. In modalità daily i costi si pagano a **ognuno dei 44 ribilanciamenti**: alcuni modelli
   perdono ~2,5 punti percentuali di cost drag e **scivolano sotto l'S&P**.
4. Il pattern vincente sintetizzato dagli autori: **selezionare bene e tradare poco.**
5. Basso turnover da solo non basta: gpt-5 ha il turnover più basso ed è comunque
   un'eccezione a basso rendimento.
6. La cadenza **daily-o-più-lenta** risulta praticabile per costruttori disciplinati.
7. Certificato di contaminazione PASS per tutti e cinque (cutoff precedenti alla finestra
   2026; gpt-5 col margine più sottile, ~2026-01). Tutte le corse pulite su causalità,
   cronologia e parità.

**Perché conta per noi**: è la misura di cadenza che mancava, ed è indipendente. Non dice
"l'intraday non funziona" — dice **dove sta il costo**, e lo quantifica. E ha una struttura
di audit (gate di disponibilità uniforme, punteggio per leakage, ottimismo sui costi,
aderenza al mandato) che vale la pena studiare a parte.

**Attenzione all'estrapolazione**: è portfolio management su equity, non perp crypto
delta-neutrale. Il meccanismo (turnover × costo per giro) trasferisce; i numeri no.

### 13.3 — Il campo non è confrontabile con se stesso — arXiv:2605.19337

*Agentic Trading: When LLM Agents Meet Financial Markets* — mappa d'evidenza orientata
all'audit, 77 studi inclusi, snapshot codificato per protocollo, screening fino al
**09/03/2026**.

Il sottoinsieme empirico primario (n=19) è quello che soddisfa il confine minimo
"Action Output + Closed-Loop Evaluation". Gli altri 58 restano come contesto di design.

**Il reperto centrale è l'incomparabilità di protocollo:**

| criterio | studi conformi (su 19) |
|---|---|
| protocollo di split temporalmente consistente ed estraibile | **2 / 19** |
| modello esplicito dei costi di transazione | **1 / 19** |
| gestione documentata di universo / survivorship | **1 / 19** |
| timing o semantica di esecuzione riportati | 11 / 19 |
| codificati al livello di riproducibilità più basso (R0) | 15 / 19 |
| che raggiungono il livello R3 di riproducibilità | **0 / 19** |

**Perché conta per noi — ed è l'argomento più forte a favore dell'owner, non del
consigliere**: non è vero che "si è già dimostrato che l'intraday con LLM non funziona".
È vero che **non si è dimostrato niente**, perché uno studio su diciannove modella i costi
e nessuno è riproducibile a livello pieno.

Il programma ha già, oggi, ciò che 18 studi su 19 non hanno: costi misurati sul venue reale
(11,0 bps quattro gambe maker + 3,0 per gamba taker su Hyperliquid), ledger append-only con
hash-chain, ancoraggio OTS, valutazione forward-only per costruzione. **Il buco esiste ed è
esattamente della nostra forma.**

---

## §14 — ANALISI FORENSE DI QUANTAGENT (arXiv:2509.09995)

Letto alla fonte: abstract arXiv, corpo del paper (sezione 4 Esperimenti), pagina
OpenReview, repo `Y-Research-SBU/QuantAgent`.

**Stato del documento** — tre fatti da registrare:
- **Ritirato da ICLR 2026** (sottomesso 08/09/2025, modificato 12/11/2025, stato
  "Withdrawn Submission"). Il ritiro non prova un difetto — gli autori ritirano per molte
  ragioni — ma significa che **non ha mai superato peer review**.
- **Rinominato** in `QuantHarness` nella v4 di arXiv (27/07/2026). Il passaggio da "Agent"
  a "Harness" è un riposizionamento da *sistema che trada* a *impalcatura di valutazione*.
  **Interpretazione flaggata, non confermata dagli autori.**
- È l'**unico** framework d'agente LLM esplicitamente intraday nella letteratura censita.

### 14.1 — L'architettura (la parte buona)

| agente | funzione dichiarata |
|---|---|
| **IndicatorAgent** | condensa barre OHLC grezze in indicatori tecnici robusti — sintesi resistente al rumore |
| **PatternAgent** | formazioni grafiche (picchi, minimi, consolidamenti) sfruttando il ragionamento multimodale su immagini di grafico |
| **TrendAgent** | bias direzionale dalle dinamiche di prezzo a orizzonte breve |
| **RiskAgent** | integra i segnali in un profilo rischio-rendimento coerente |
| **DecisionAgent** | integra le tre prospettive a monte → decisione direzionale (LONG o SHORT) |

Output: **report di trade strutturato** con predizione direzionale, breve rationale
testuale, e rapporto rischio-rendimento stimato. Il prompt del DecisionAgent istruisce a
dare priorità all'evidenza concorde, evitare output speculativi, e fornire giustificazione
strutturata.

**Nota decisiva già registrata nella parte A (§3.6)**: *The Alpha Illusion* riclassifica
QuantAgent come sistema **già vicino al confine modulare** — l'LLM emette ragionamento
strutturato sui ruoli, mentre **esecuzione e stop-loss a 5 bp sono componenti fuori
dall'LLM**. Quindi i "ruoli" non sono agenti autonomi: sono **slot di ragionamento
strutturato**, con l'esecuzione fuori. È il pattern da rubare.

### 14.2 — Il protocollo di valutazione (la parte che non regge) — otto rilievi

**(1) La difesa anti-leakage è inadeguata per un LLM.**
Il paper raccoglie 5.000 barre storiche per asset via API pubblica di estrazione
TradingView, campiona 100 segmenti da 100 candele consecutive, e **trattiene le ultime tre
barre per prevenire il leakage di test**.

Trattenere tre barre protegge dal look-ahead **a livello di prompt**. Non fa **nulla**
contro il leakage **parametrico**: i pesi del modello contengono già il percorso di prezzo
storico di SPX, QQQ e BTC. È il modo di fallimento P1 nella sua forma da manuale
(*Profit Mirage*: crollo Sharpe 51–62% fuori finestra; Lopez-Lira: richiamo dei prezzi
S&P con <1% di errore dentro la finestra di training). *The Alpha Illusion* segnala infatti
il gap P1 (dichiarazione del cutoff) come residuo aperto su QuantAgent.

**(2) Nessun costo di transazione nella valutazione.**
Le metriche sono accuratezza direzionale e metriche di rendimento. Nella matrice di
copertura delle frizioni dell'*Alpha Illusion*, QuantAgent modella **le sole commissioni**.
A barre 1h su crypto, un'accuratezza direzionale del 55–60% è priva di significato senza il
netto: i costi misurati in casa sulla nostra stessa venue sono **11,0 bps per quattro gambe
maker + 3,0 bps per gamba taker**. È la stessa aritmetica con cui in questo programma è
stato **escluso lo scalping**.

**(3) HOLD viene scartato.**
La regola di voto a maggioranza produce LONG / SHORT / **HOLD**, e la decisione HOLD è
**disregarded** in valutazione.

Questo è il rilievo più sottile e più grave. Scartare gli HOLD condiziona il campione di
valutazione ai casi in cui l'agente aveva un'opinione — cioè **rimuove dal denominatore
proprio i casi di minor confidenza**, che in un sistema reale sono quelli in cui non si
perde nulla. Un'accuratezza direzionale calcolata su un sottoinsieme auto-selezionato non
è accuratezza direzionale.

È anche l'**esatto opposto** del disegno di casa: in Gate Concordia l'astensione è l'output
azionabile, non lo scarto.

**(4) L'n effettivo è vicino a 1, non a 10.**
Il paper testa la consistenza di predizione a orizzonte breve su un segmento SPX di 100
barre scelto a caso, usando **10 finestre sovrapposte, ognuna sfalsata di 5 barre**.

Finestre da 100 barre sfalsate di 5 si sovrappongono al **95%**. Non sono 10 osservazioni
indipendenti: sono ~1 osservazione guardata dieci volte.

**È esattamente il problema che il programma ha già incontrato in casa**: 10 cicli di carry
in 3 finestre di mercato correlate → **n effettivo = 3** (`CODA.md` §4). Stessa patologia,
altro laboratorio.

**(5) La dimostrazione "80% di accuratezza" è su n=10.**
Il materiale del repo riporta accuratezza direzionale campionata su SPX: **10 segnali
generati dall'LLM**, con le predizioni corrette evidenziate, per un 80% "nel periodo
evidenziato". Dieci segnali, in un periodo selezionato. Non è un risultato, è
un'illustrazione.

**(6) I baseline sono deboli, e manca quello che conta.**
Tre baseline: casuale (LONG/SHORT a caso con rischio-rendimento in [1,2 – 1,8]); regressione
lineare (pendenza su finestra di 40 barre, >0 → LONG); XGBoost su indicatori TA-Lib (RSI,
MACD, SMA), addestrato su centinaia di campioni a finestra scorrevole in 50 file csv
selezionati a caso e testato sugli altri 50.

**Non c'è buy-and-hold. Non c'è "sempre LONG".** Su BTC e SPX in un campione storico con
drift positivo, "sempre LONG" batte quasi tutto. La riproduzione indipendente
dell'*Alpha Illusion* — che il buy-and-hold ce l'ha — colloca QuantAgent a **Sharpe netto
−1,15**, con NVDA a **−59,30% netto** e il B&H netto davanti su 4 ticker su 5.

**(7) Non è HFT.** Il paper parla di *High-Frequency Trading* in tutto il testo, ma le
risoluzioni valutate sono **1 ora e 4 ore**. Nella microstruttura di mercato l'HFT è
sub-secondo. 1h/4h è swing/intraday.

E per noi c'è una coincidenza che vale una riga a registro: **1h e 4h sono esattamente le
bande in cui il programma ha già ottenuto rosso in casa** — M5/ProFiT a 1h (esito E2) e
M3.5 (15m in perdita, 1h zero, 4h non misurabile). Non è una prova, ma è un prior locale
misurato, sullo stesso mercato, con i nostri costi.

**(8) Molteplicità non dichiarata.** Nove-dieci strumenti × due risoluzioni × più metriche,
con la vittoria rivendicata "su most metrics and markets" e picchi dichiarati su SPX, QQQ e
BTC. Nessun aggiustamento per test multipli è riportato. È la griglia che il DSR esiste per
punire.

### 14.3 — Verdetto su QuantAgent

| aspetto | verdetto |
|---|---|
| **Architettura** (ruoli come slot strutturati, esecuzione e stop fuori dall'LLM) | **DA RUBARE** — è il pattern del braccio C dell'Idea #13 |
| **Evidenza di performance** | **DA RESPINGERE** — otto rilievi sopra, riproduzione indipendente negativa |
| **Idea che l'LLM possa emettere un rapporto rischio-rendimento strutturato** | **interessante, non validata**: è un numero auto-dichiarato, stesso problema del P4 |
| **Scelta di scartare HOLD** | **DA INVERTIRE** — l'astensione è informazione, per noi è il segnale principale |
| **Uso di grafici come input (PatternAgent multimodale)** | **fuori scopo per ora**: richiede emendamento al principio #6 e apre superficie di contaminazione |

---

## §15 — TASSONOMIA DEI SISTEMI: COSA RUBARE, COSA RESPINGERE

Sintesi di tutti i sistemi emersi nell'istruttoria. La colonna "riuso" è il verdetto del
consigliere, non degli autori.

### 15.1 — Sistemi end-to-end (l'LLM decide)

| sistema | forma | cadenza | riuso per noi |
|---|---|---|---|
| **TradingAgents** (2412.20138) | analisti + ricercatori Bull/Bear in dibattito + trader + risk team, LangGraph, ~11 chiamate LLM/decisione | daily | **respinto come scheletro** (già deciso 13/08). Riproduzione a 1 anno: Sharpe 0,43→0,22 netto, sotto il B&H. Rubare: report strutturati invece di dialogo libero |
| **FinMem** (2311.13743) | profiling + memoria a strati (working + long-term con recency/relevance/importance) + decisione | daily | **rilevante per la Scuola del Trader**. Ma FINSABER mostra inversione di segno con finestra e costi diversi |
| **FinAgent** (2402.18485) | multimodale (numerico, testuale, visuale/Kline), dual-level reflection | daily | **respinto**: rivendica +36% medio e fino a 92% dove il leakage è più probabile |
| **FinCon** (2407.06567, NeurIPS 2024 main) | gerarchia manager–analista + rinforzo verbale concettuale, controllo CVaR | daily | **la gerarchia manager–analista è il modello più vicino all'idea originale dell'owner.** Sharpe per titolo fino a 2,37, portafoglio 3,27 — ma finestra ott 2022–giu 2023, vincolata da P1 e P5 |
| **QuantAgent / QuantHarness** (2509.09995) | 4 ruoli + decisore, esecuzione e stop fuori dall'LLM | **1h / 4h** | vedi §14: **architettura sì, evidenza no** |
| **FLAG-Trader** (2502.11433) | fine-tune PPO di un LLM da 135M con reward su incremento di Sharpe | daily | **fuori scopo**: richiede training, rompe il pin del modello e il track record |
| **AlphaCrafter** (2605.05580) | multi-agente cross-sezionale full-stack | daily | **da studiare per il protocollo**: 10 trial indipendenti per configurazione, metriche mediate sull'intervallo interquartile, più una fase live fuori dal cutoff di tutti i backbone |
| **QuantAgents** (2510.04643, *diverso da QuantAgent*) | sistema multi-agente via simulated trading, NASDAQ-100 2010–2023 | daily | **respinto**: finestra interamente dentro il training window |

### 15.2 — Benchmark e arene (misurano, non tradano)

| sistema | cosa misura | riuso per noi |
|---|---|---|
| **AMA / When Agents Trade** (2510.11695) | 4 architetture × 5 backbone, live multi-mercato | vedi parte A §2. **Reperto**: architettura d'agente > backbone. Riserva: 80 celle, nessun aggiustamento |
| **StockBench** (2510.02209) | contamination-free, 20 titoli DJIA, 82 giorni post-cutoff | **modello di rigore**. Reperto: la maggior parte degli agenti non batte il buy-and-hold |
| **Alpha Arena / nof1** | sei modelli, capitale reale su Hyperliquid | S1 chiusa nov 2025, S1.5 chiusa dic 2025, **nessuna S2**. Multi-agente in roadmap, mai eseguito |
| **OpenPM** (2608.09988) | sweep di cadenza + certificato di contaminazione | vedi §13.2. **Il più vicino al nostro metodo di chiunque altro** |
| **TraderBench** (2603.00285) | robustezza in mercati avversariali, task di conoscenza statica e ragionamento | reperto: il thinking esteso migliora molto i task di retrieval e **quasi nulla la performance di trading**; gap concettuale-vs-computazionale sulle opzioni |
| **Agent Trading Arena** (2502.17967) | mercato virtuale a somma zero, comprensione numerica | reperto: gli agenti fanno **meglio col grafico che col testo** sullo stesso stato numerico → il collo di bottiglia è l'esecuzione numerica, non il vocabolario finanziario |

### 15.3 — Lavori metodologici (i più utili di tutti)

| lavoro | contributo | riuso |
|---|---|---|
| **The Alpha Illusion** (2605.16895) | protocolli P1–P6, riproduzione a 1 anno, PPL, alternativa modulare | vedi parte A §3. **Checklist di pre-registrazione già scritta** |
| **Agentic Trading** (2605.19337) | mappa d'evidenza su 77 studi, incomparabilità di protocollo | vedi §13.3. **La prova che il campo è vuoto, non chiuso** |
| **Representation Signatures** (2605.28850) | le firme di fallimento sono misurabili anche senza profitto | vedi §13.1. **Legittima il pivot cognitivo** |
| **Stop Overvaluing Multi-Agent Debate** (2502.08788) | dibattito vince <20% su 36 configurazioni; round e agenti in più non migliorano | argomento chiave contro il braccio multi-agente |
| **Your AI, Not Your View** (2507.20957) | base empirica del PPL, tassi di inversione sotto evidenza contraria | vedi parte A §3.4 |
| **Let Me Speak Freely?** (2408.02442) | format tax fino a ~27 punti sotto vincolo di formato | vincolo sul braccio C: scratchpad prima, struttura dopo |

---

## §16 — IDEA #13-bis: ARENA A DUE CADENZE (registrata, non costruita)

**Nome**: Arena a due cadenze — "LLM MODE".
**Origine**: proposta dell'owner, 18/08.
**Trigger**: chiusura di Stagione 0. Condivide il banco di prova con l'Idea #13.
**Stato**: registrata. Nessun codice, nessun repo, nessun prompt CLI.

### 16.1 — Struttura appaiata

Stesso cervello (Fable 5 pinnato), stesse tre repliche, stesso asset. Due bracci:

- **MODE-D** — 1 decisione/giorno all'ora UTC fissa. È il protocollo S0.
- **MODE-I** — k decisioni/giorno a slot UTC fissi (a 4h → 6 slot).

**L'ancoraggio**: la decisione daily e la decisione intraday dello **slot 0** vedono lo
**stesso identico snapshot**. Confronto appaiato a mondo identico — la forma con più
potenza disponibile, la stessa usata dall'Idea #13.

### 16.2 — Variabili dipendenti, dichiarate prima. Il P&L non è tra queste.

| # | misura | domanda a cui risponde |
|---|---|---|
| 1 | **Brier + ECE per cadenza** | la calibrazione degrada con la frequenza? |
| 2 | **Dispersione della confidence** | il 0,55 degenere si rompe intraday, o è una proprietà del modello e non del compito? |
| 3 | **Dispersione inter-repliche** | il metro del rumore cresce con la cadenza, e di quanto? |
| 4 | **Coerenza dichiarativa (Idea #6)** | i `features_used` corrispondono ai tool effettivamente chiamati, o si sfilacciano intraday? |
| 5 | **Composizione dei `features_used`** | il mix scivola da strutturale (funding, base, carry) a rumore (ultime N candele, momentum breve)? |
| 6 | **Turnover e flip rate** | la firma del gambling già in Telemetria — e il collo di bottiglia identificato da OpenPM |
| 7 | **Costo per decisione × cadenza** | il P5, misurabile in una settimana |
| 8 | **Tasso di astensione (flat)** | contato, **mai scartato** — correttivo esplicito al rilievo §14.2(3) |

**La #2 è la più interessante del programma in questo momento.** Se la confidence resta a
0,55 anche a cadenza intraday, è dimostrato che è una proprietà del modello e non del
compito: reperto che la letteratura sulla calibrazione non ha.

### 16.3 — Kill gate, dichiarati prima

1. Se la dispersione inter-repliche di MODE-I supera il divario MODE-D↔MODE-I →
   **"nessuna cognizione distinguibile dal rumore"**, filone chiuso.
2. Se la coerenza dichiarativa in MODE-I scende sotto [soglia owner] →
   `features_used` inutilizzabili a quella cadenza, chiuso per il mining di ipotesi.
3. Se il costo per decisione × cadenza sfonda [tetto owner] → chiuso per economia,
   indipendentemente dalla cognizione.

### 16.4 — Cosa NON produce (dichiarato in anticipo)

**Un verdetto di alpha.** Vincolato da SR_min, non acquistabile con nessun disegno né con
nessuna cadenza. Qualunque numero di P&L prodotto dall'arena è **descrittivo**, e va
etichettato come tale in ogni output.

### 16.5 — Costo (stima derivata, non misura)

Base: **$1,63 per ciclo decisionale**, dai $9,80 misurati della giornata 2 su 6 cicli.

| forma | conto | ordine di grandezza |
|---|---|---|
| Stagione intraday **viva** | 3 repliche × 2 asset × 6 slot = 36 decisioni/gg | **~$59/gg → ~$1.180 su 20 gg** — fuori scala |
| **Replay offline bounded**, BTC solo | 10 giornate × 6 slot × 3 repliche = 180 decisioni | **~$290** una tantum |
| Braccio daily appaiato | 10 giornate × 1 slot × 3 repliche = 30 decisioni | **~$48** |
| **Totale replay** | 210 decisioni | **~$340**, non ricorrente |

**Riserva onesta**: la stima assume che la struttura di cache regga. Slot intraday con
snapshot diversi hanno prefissi diversi → la cache condivisa tra repliche regge, quella
tra slot no. Il numero vero può essere più alto. Va misurato su una giornata pilota prima
di autorizzare il lotto intero.

### 16.6 — I tre vincoli da sciogliere prima del "sì"

1. **Post-cutoff (P1).** La finestra di replay deve stare **strettamente dopo** il knowledge
   cutoff dichiarato di Fable 5 nel FreezeManifest. *Il consigliere non conosce quel valore
   e non lo inventa*: va letto dal manifest prima di scegliere la finestra. Se il margine è
   sottile, si usano solo giornate recentissime.
2. **Codice nuovo.** MODE-I richiede snapshot intraday che il SnapshotBuilder oggi non
   costruisce. È codice nuovo → **regola 10** lo tiene fuori dai percorsi di verdetto finché
   S0 è viva. Non parte prima della chiusura della stagione.
3. **Conteggio dei trial.** Ogni braccio di cadenza entra nel denominatore del DSR, come
   ogni braccio d'architettura (parte A §7). Il numero di cadenze testate si dichiara prima
   ed è piccolo: **due**, non uno sweep.

---

## §17 — COSA NON È STATO DECISO (parte B)

Nessuna decisione presa. In particolare **non** sono stati decisi:

1. se avviare l'Arena a due cadenze (**Idea #13-bis è registrata, non approvata**);
2. le tre soglie dei kill gate del §16.3 — sono in bianco, le fissa l'owner;
3. il tetto di spesa del §16.5;
4. l'adozione della regola candidata 49-bis del §11;
5. qualunque modifica a S0, al prompt, ai context file, al FreezeManifest, allo snapshot.

**Restano prioritari e invariati** (da `CODA.md`, 17/08):
- verdetto costo giornata 3 di S0 — **prossimo passo dichiarato**;
- cinque firme pronte su sei;
- la domanda che blocca il PREREG_CARRY: la finestra di legging è costo strutturale
  ricorrente, sì o no (A′ 13,72 bps vs B′ 18,74 bps);
- le tre voci con scadenza pre-fine-S0;
- holdout **0/2**, intoccabile.

---

## §18 — RIFERIMENTI NUOVI (non presenti nella parte A né nei file di casa)

| id | titolo | rilevanza |
|---|---|---|
| arXiv:2509.09995 | *QuantAgent / QuantHarness: Price-Driven Multi-Agent LLMs for High-Frequency Trading* (Xiong, Zhang, Feng, Sun, You) | **letto alla fonte**. Unico agente intraday. Ritirato da ICLR 2026. Otto rilievi in §14 |
| arXiv:2608.09988 | *OpenPM: Auditable Point-in-Time Evaluation for LLM Portfolio-Management Agents* | sweep di cadenza misurato; il turnover è il collo di bottiglia |
| arXiv:2605.19337 | *Agentic Trading: When LLM Agents Meet Financial Markets* | mappa d'evidenza 77 studi; 1/19 modella i costi; 0/19 a R3 |
| arXiv:2605.28850 | *Representation Signatures and Risk-Feedback Alignment in LLM Trading Agents* | le firme di fallimento sono misurabili senza profitto; include intraday |
| arXiv:2605.05580 | *AlphaCrafter: A Full-Stack Multi-Agent Framework for Cross-Sectional Quantitative Trading* | protocollo: 10 trial per configurazione, mediana interquartile, fase live post-cutoff |
| arXiv:2510.04643 | *QuantAgents: Towards Multi-agent Financial System via Simulated Trading* | **da non confondere con QuantAgent**. NASDAQ-100 2010–2023, dentro il training window |
| arXiv:2603.00285 | *TraderBench* | il thinking esteso migliora il retrieval, quasi non migliora il trading |
| arXiv:2502.17967 | *Agent Trading Arena* | il collo di bottiglia è l'esecuzione numerica; meglio col grafico che col testo |

---

## §19 — PROTOCOLLO DI VERIFICA PER UNA CHAT NUOVA

Prima di procedere su questa materia, recitare:
1. **§11** — la seconda annotazione di errore (i "quattro rossi" non erano LLM intraday);
2. **§12** — il ribaltamento alpha↔cognizione e la tabella delle due potenze;
3. **§16.4** — cosa l'arena **non** produce;
4. **§17** — cosa non è stato deciso.

E tenere fermo: questo documento **non modifica la fase, non apre riti, non autorizza
commit**. Idea #13-bis è registrata con trigger, non costruita. Le tre soglie del §16.3
sono in bianco per costruzione: le fissa solo l'owner, e le fissa **prima** di guardare
qualunque dato.

---

*Ogni firma è dell'owner. Il consigliere propone, calcola, avverte, filtra — non firma mai.*

**Firma owner (registrazione Idea #13-bis, §16)**: ______________________ data: __________

**Firma owner (regola candidata 49-bis, §11)**: ______________________ data: __________

**Soglie §16.3 — da fissare prima di qualunque raccolta dati:**
- kill gate 1, rapporto dispersione: ____________
- kill gate 2, coerenza dichiarativa minima: ____________
- kill gate 3, tetto di spesa: ____________
