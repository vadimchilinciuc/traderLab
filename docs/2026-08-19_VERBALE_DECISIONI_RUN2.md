# VERBALE — Decisioni di sessione 17-19/08/2026 per il disegno del RUN2

> **Provenienza.** Sessione di chat del 17-19/08/2026. Le decisioni qui
> trascritte sono dell'owner, prese sull'analisi del consigliere. Il materiale
> di supporto vive in referti gitignorati alla radice del repo
> (`.gitignore:25`, regola `*_REPORT.md`) e nei file di lavoro sotto
> `scratchpad/`: nessuno dei due entra nel track record, e quindi nessuno dei
> due sopravvive a una copia pulita del repository.
>
> **Natura.** Questo documento **registra, non firma**. Non è un
> pre-registration, non è un emendamento, non chiude pendenze. Le firme
> pendenti restano dove sono: la CODA di `zeroPipes` e le righe di firma dei
> documenti di ricerca. Nessuna voce qui dentro autorizza un'esecuzione.
>
> **Rimando.** Il disegno completo della stagione nuova andrà nel
> **`PREREG_LAB_S0_RUN2`**, che **non esiste ancora**. Questo verbale lo
> prepara: raccoglie in un posto solo, e in forma citabile, le decisioni che
> quel documento dovrà dichiarare prima del freeze.

**Data del verbale**: 2026-08-19
**Perimetro**: `traderLab`. Le voci che riguardano `zeroPipes` sono elencate
nella §C come rimandi, senza decisione presa qui.

---

## §A — Decisioni di disegno del RUN2

Tutte dell'owner. L'ordine è quello della sessione, non una priorità.

### A.1 — `max_tokens = 8000`

Il RUN2 gira con `max_tokens = 8_000`: **il valore che la Stagione 0 ha
effettivamente usato**, non quello che il registro dichiara.

- **Fonte del valore in vigore**: `arena/config.py:50`,
  `DEFAULT_MAX_TOKENS = 8_000`. Il commento sopra la costante (righe 42-49) ne
  dichiara la ragione: con `32_000` il modello veniva scartato dallo shedding
  lato server nei picchi di carico (overloaded in-stream); con un budget
  ridotto la chiamata passa.
- **Divergenza nota**: `DECISION_LOG.md:45` (tabella di TL-002, Decisione 1)
  afferma `DEFAULT_MAX_TOKENS` **alzato a 32.000**. Il registro e il codice
  dicono cose diverse.
- **Decisione**: la divergenza **si annota, non si ripara**. Il RUN2 cambia
  **una variabile sola** (§A.3) e questa non è quella. Il `PREREG_LAB_S0_RUN2`
  dichiarerà 8.000 come valore della stagione, citando questa annotazione.

> Nota di lettura. Il rito indicava `DECISION_LOG.md:43`; la riga effettiva del
> testo sui 32.000 è la **45**. Il contenuto è quello inteso.

### A.2 — Il runner carica il manifest committato

Il runner **carica il `FreezeManifest` committato**, ne **ricalcola il
`freeze_id`** e **si rifiuta di girare** se il ricalcolo diverge.

`context_git_sha` **esce dal calcolo del `freeze_id`**: al suo posto entra il
commit del rito del pin, **fisso per tutta la stagione**.

- **Precondizione già incisa**: `DECISION_LOG.md`, voce **TL-007**, paragrafo
  «Precondizione al rito del pin». Il rito Z1 del 18/08 ha accertato che
  `scripts/run_day.py` ricostruisce il manifest a runtime invece di caricare
  quello committato: i tre `freeze_id` delle giornate di S0 differiscono fra
  loro e nessuno coincide con quello del manifest firmato e timbrato OTS. La
  causa dichiarata è che il manifest ricostruito incorpora il git sha corrente,
  che cambia a ogni commit anche quando l'agente non è cambiato. TL-007
  conclude: «il pin della stagione nuova **non è valido** finché il runner non
  carica il manifest committato, ricalcola il `freeze_id` e si rifiuta di
  girare se diverge».
- **Cosa aggiunge questa voce**: la sostituzione esplicita di `context_git_sha`
  con il commit del rito del pin. TL-007 nomina la causa; la scelta del
  rimpiazzo è di questa sessione.

### A.3 — Una variabile sola

Fra Stagione 0 e RUN2 cambia **il modello** (`claude-opus-5`, TL-007) e
**nient'altro**: restano identici il prompt, la persona, lo snapshot builder e
il Tool Server.

Le riparazioni allo snapshot già individuate — **artefatto del weekend**,
**giorno-della-settimana** — **non entrano nel RUN2**: sono rimandate al RUN3.

### A.4 — `daily_dispersion` su intersezione vuota

Su intersezione vuota `daily_dispersion` deve restituire **null / indefinito**,
**mai `0,0000`**. Il log scrive **`n/d`**.

- **Stato del codice oggi**: `ledger/telemetry.py:292` — con meno di due
  repliche o con intersezione vuota la funzione restituisce
  `DailyDispersion(0, len(replica_ids), 0.0, 0.0, 0.0)`, cioè **tre zeri
  numerici**. L'informazione «non è definita» esiste già, ma solo come
  proprietà derivata, `DailyDispersion.is_degenerate`
  (`ledger/telemetry.py:285-289`), che nessun consumatore è obbligato a
  leggere.
- **Perché conta**: uno `0,0000` da intersezione vuota è indistinguibile, a
  valle, da un accordo perfetto fra repliche. È la stessa classe di errore
  della §A.5: due cose diverse contate nello stesso posto.

### A.5 — Il rifiuto del modello ha una contabilità sola

Il `model_refusal` ha **una contabilità sola**, **separata dai verbali
malformati**. Il gate **§7(ii)** del pre-registration conta **i soli malformati
veri**.

- **Stato del codice oggi**, come letto durante la Stagione 0 e riportato in
  `GIORNATA3_REPORT.md:163-168` (referto gitignorato): `arena/runner.py:81-82`
  definisce `malformed_count` come il numero di esiti con `malformed_reason`
  non nullo, quindi **il rifiuto vi rientra**, benché `arena/verbale.py:153-155`
  lo classifichi come categoria a sé e `ledger/telemetry.py:196` lo contabilizzi
  in `refusals_total`. Il conteggio è **doppio e incoerente**: due sorgenti di
  verità per lo stesso evento.
- **Reperto reale**: la giornata del 18/08 ha prodotto un `model_refusal`
  (r3 ETH) e un `no_tool_use` (r1 BTC) — vedi §A.8. Il log stampò
  «malformati: 2».

### A.6 — `morning_check` registrato come task pianificato

`scripts/morning_check.py` va **registrato come task pianificato**, con
**allarme effettivo** — non solo presente su disco.

- **Stato accertato**: `SCHEDULER_REPORT.md:57-60` (referto gitignorato)
  riporta che `docs/OPERATIONS.md` §«Registrare il task» descrive un secondo
  task per `scripts/morning_check.ps1`, ma **nel Task Scheduler non esiste**:
  nessun task con `morning` nel nome o nell'azione. Lo script esiste sul disco,
  **non lo lancia nessuno**.
- Il rilevatore c'è (`scripts/morning_check.py`, con test in
  `tests/test_morning_check.py`): mancano la registrazione e il canale
  d'allarme.

### A.7 — Token di thinking loggati a parte

I token di **thinking** si loggano **separati dall'output**. Se il payload non
contiene il blocco di thinking, **si logga l'assenza** — non si assume né si
tace.

- **Stato del codice oggi**: la struttura di `usage` costruita in
  `arena/llm_client.py:400-407` porta input, output e i due campi di cache
  (`cache_creation_input_tokens`, `cache_read_input_tokens`). **Non esiste un
  campo separato per il thinking**, che sul modello pinnato consuma lo stesso
  `max_tokens` della risposta (`DECISION_LOG.md:45`). Oggi il costo del
  ragionamento è indistinguibile dal costo del verbale.

### A.8 — La stagione si conta in coppie, non in giornate

**L'unità di conto della stagione è la coppia giornata-asset con tutte e tre le
repliche valide.** Non la giornata.

| Grandezza | Valore |
| --- | --- |
| Obiettivo | **40 coppie** giornata-asset valide (tutte e tre le repliche) |
| Cap di calendario | **42 giorni** |
| Attesa a tasso di fallimento 0 | 20 giornate |
| Attesa al 5% | 23 giornate |
| Attesa all'11% | **28 giornate** |

L'**11%** è il tasso **osservato in Stagione 0**, non un'ipotesi.

- **Fonte**: `GIORNATA3_REPORT.md:158-161` (referto gitignorato). Le tre
  giornate hanno prodotto 3 giorni × 3 repliche × 2 asset = **18 esiti
  attesi**; due sono mancati (`no_tool_use` su r1 BTC il 18/08,
  `model_refusal` su r3 ETH lo stesso giorno). **2 su 18 = 11,1%**.
- La stessa tabella mostra perché l'unità è la coppia e non la giornata: il
  18/08 è una giornata «riuscita» a livello di ops ledger, ma **non produce
  nessuna coppia valida**, perché entrambi gli asset hanno perso una replica.
  Contando in giornate quel giorno vale 1; contando in coppie vale 0. Le coppie
  valide di S0 sono **4** (BTC ed ETH del 16/08, BTC ed ETH del 17/08).

**Potenza dichiarata**: **80%** ad **alfa = 0,05 unilaterale** per rigettare
**q ≤ 0,10** quando il tasso vero di disaccordo è **≥ 0,25**.

- La stima puntuale di S0 è **1 su 4**: delle quattro coppie valide, una sola
  mostra disaccordo fra le repliche (16/08 BTC: `flat` · `flat` · `short`; le
  altre tre sono unanimi). Stessa fonte, `GIORNATA3_REPORT.md:158-161`.
- Il numero è **una stima su quattro osservazioni** e va dichiarato come tale
  nel PREREG: fonda il calcolo di potenza, non lo conferma.

### A.9 — k della stagione, k delle sonde, e la domanda che la stagione può reggere

- **k della stagione = 3 repliche.**
- **k delle sonde = 30.**

La **calibrazione di `p_accordo`** richiede **≥ 125 mondi con esito**
(5 bin × 25) e **non è raggiungibile in una stagione**: è dichiarata come
**obiettivo pluri-stagionale**. Di conseguenza la **Stagione 1 parte a size
fissa**.

**Il gate che la stagione PUÒ rispondere**, senza bisogno di esiti di mercato:
*la distribuzione di `p_accordo` sui mondi reali si distingue da quella sulla
sonda nulla?* Se **no**, `p_accordo` è **morto come oggetto di sizing** e si
chiude con un numero.

### A.10 — Suite di regressione

**15 snapshot, k = 5.**

Con la soglia d'allarme a **baseline − 0,15**, l'errore standard **0,050**
rende il calo un evento a **3,0 sigma**.

- **Regola già a registro**: `DECISION_LOG.md:58-72`, TL-002 Decisione 2,
  esplicitamente **non superata** da TL-007 (`DECISION_LOG.md:300`).
  `agreement_alarm = baseline − 0.15`, pavimento `0.70`;
  `agreement_sunset = baseline − 0.30`, pavimento `0.50`.
- La stessa voce avverte che **il pavimento può mordere**: con auto-accordo
  ≤ 0,85 il pavimento 0,70 è più severo di `baseline − 0,15`, e con
  auto-accordo ≤ 0,70 la suite andrebbe in allarme sul comportamento **di
  baseline**. Con k = 5 non è un caso teorico. Il dimensionamento di questa
  voce (15 × 5) va letto insieme a quell'avvertenza.

### A.11 — Due sonde sintetiche dentro la suite

Le due sonde stanno **dentro** la suite di regressione, **per disegno**, non
accanto ad essa:

| Sonda | Costruzione | Cosa misura |
| --- | --- | --- |
| **nulla** | decisione meccanicamente forzata | il **pavimento del rumore** |
| **cieca** | informazione nulla | il **soffitto** |

Insieme delimitano la banda entro cui un accordo osservato è informativo.

### A.12 — Partenza entro il 13/09/2026

La stagione parte **entro il 13/09/2026**.

**Ragione**: il cambio d'ora è il **25/10/2026**, e il trigger alle **02:00
locali** coincide con le **00:00 UTC** solo in **CEST**. Una stagione che
attraversa il cambio d'ora sposta l'istante dello snapshot a metà corsa, cioè
cambia una variabile senza dichiararlo.

**Clausola da scrivere nel PREREG**: partenza entro il 13/09, oppure trigger
riancorato a UTC prima della partenza.

### A.13 — Quattro baseline meccaniche

Dichiarate **ora**, calcolate **a fine stagione**:

1. **sempre-long**
2. **sempre-short**
3. **sempre-flat**
4. **coin-flip**, con **seme dichiarato nel PREREG**

**Condizioni comuni**: stessi istanti, **stessa size fissa**, **stessi costi** —
round-trip taker misurato **9,16 bps**.

- **Fonte del costo**: `DECISIONE_CIECA_OPPUS_REPORT.md:53` e `:95` (referto
  gitignorato) — BTC **9,16 bps**, ETH **9,53 bps**, andata-e-ritorno taker.
  Lo stesso referto (riga 353) dichiara che si tratta di **un costo del
  momento**, misurato su un book puntuale, non di un costo strutturale.
- **Copertura**: le baseline si calcolano **anche sui giorni in cui l'agente
  non decide**. Il confronto si fa **sull'intersezione**, **dichiarando le
  coppie escluse**. Senza questa clausola, un agente che si astiene nei giorni
  difficili batterebbe la macchina per costruzione.
- **In più**: **decomposizione beta / selezione** via regressione del P&L
  giornaliero sul rendimento BTC. Dichiarata ora, non a posteriori.

### A.14 — ECE e Brier escono dal pannello primario

**ECE e Brier escono dalle misure primarie**: si **raccolgono**, non si
**riportano**.

**Regola candidata 51** (numerazione corretta dalla collisione col 50): *l'ECE
non si riporta mai senza la dispersione accanto; sotto soglia si marca **NON
INTERPRETABILE***.

> **La soglia numerica è ANCORA IN BIANCO. È dell'owner.** Questo verbale non
> la fissa e non ne propone una.

Se mai misurato: **bin a massa uguale**, **correzione jackknife**.

**Fondamento empirico**: §B.1. Con la confidence ancorata a 0,55 dal
contenitore, un ECE calcolato su quei valori misura l'ancoraggio, non la
calibrazione dell'agente.

### A.15 — HOLD nel denominatore

**HOLD sta sempre nel denominatore.** Il **tasso di astensione** si riporta.

Un metro calcolato sui soli giorni in cui l'agente ha agito premia l'astensione
selettiva senza mostrarla.

### A.16 — La dispersione si riporta come istogramma

La dispersione si riporta come **istogramma completo dei valori distinti**,
**mai** come sola media e deviazione standard.

- **Perché**: il reperto della Stagione 0. La media della confidence del 17/08
  è 0,55 e la deviazione standard è 0,0000 — ma anche una distribuzione
  larghissima con la stessa media si riassumerebbe in due numeri innocui. Il
  referto di elicitation (§B.1) mostra distribuzioni che **hanno la stessa
  media** e forme diverse: la forma A e la forma D stanno entrambe a 0,536 di
  media sul 17/08, e i loro conteggi per valore sono l'unica cosa che le
  distingue.

### A.17 — `n_eff` dichiarato per misura

`n_eff` si dichiara **PER MISURA** nel PREREG, non una volta per la stagione:

| Misura | `n_eff` atteso |
| --- | --- |
| dispersione | ~ n |
| coerenza dichiarativa | ~ n |
| astensione | ~ n |
| Brier | **molto minore di n** |
| decomposizione beta | **molto minore di n** |

**Ragione**: gli **esiti** sono autocorrelati; le **decisioni** su snapshot
congelati distinti non lo sono allo stesso modo. Un `n_eff` unico per la
stagione sovrastimerebbe la precisione delle misure basate su esito.

### A.18 — Limite di Console

| Voce | Valore deciso |
| --- | --- |
| Limite mensile | **500 USD/mese** |
| Notifica | **300 USD** |
| Ricaricamento automatico | **SPENTO** |

**STATO: deciso in chat, NON verificato.** La sera del 18/08 il ricaricamento
automatico risultava **ancora ATTIVO**. **Da eseguire e verificare in Console**:
è una pendenza operativa, non una decisione già applicata.

Questo verbale non può verificarla: la Console non lascia traccia nel repo.

### A.19 — Livello P

Livello **P** — elicitation avanzata, pre-screen delle architetture, arena di
cadenza.

- **Nessun tetto fissato ora.**
- **Trigger dichiarato**: **la chiusura del RUN2.**

---

## §B — Esiti empirici che fondano le decisioni (sessione 18-19/08)

### B.1 — A/B di elicitation su `claude-opus-5`

**Disegno**: 100 chiamate, **5 forme × 2 snapshot × k = 10**. Solo BTC.

**Referto**: `ELICITATION_OPUS_REPORT.md`, alla radice del repo,
**gitignorato** (`.gitignore:25`, regola `*_REPORT.md`). Verificato presente al
2026-08-19. **Materiale grezzo** sotto `scratchpad/elicitation/` (100 file
`call_*.json` con `usage` completo turno per turno, più l'ordine randomizzato
col seme in `_ordine.json`): anch'esso fuori da git.

**Esito**:

- La **forma A** (controllo) **riproduce l'ancoraggio 0,55 anche su Opus**:
  modo **0,55**, **6/10 su entrambi gli snapshot**
  (`ELICITATION_OPUS_REPORT.md:420`).
- La **forma D** — stessa scala, **prosa diversa**, **`sha` di schema identico
  `5ecbd8ca76a2`** (riga 202) — è **indistinguibile da A**: distanza in
  variazione totale **0,10-0,20** (righe 409-415).
- Le forme **B, C, E** — che cambiano **lo schema del campo** — producono
  distribuzioni **disperse e lontane da A**.

**Lettura di sessione**: **l'ancoraggio è del CONTENITORE** — il campo
`confidence` in [0,1] con **un'ancora sola a 0,5** — **non del modello né della
prosa**. Cambiare le parole non muove il numero; cambiare la forma del campo lo
muove.

**Conseguenza diretta**: **§A.14**.

La **forma B** (distribuzione sulle tre azioni) è la **candidata per
l'elicitation della Stagione 1** — **NON del RUN2**, che cambia una variabile
sola (§A.3).

### B.2 — Reperto non previsto: la forma C sposta le azioni

La **forma C** (elicitation in **quote**) **non muove solo il numero: muove
l'azione**. Sullo snapshot del 17/08 produce **`flat` 8 volte su 9**, dove le
tre repliche reali della Stagione 0 avevano prodotto **`short` 3 su 3**.

- **Fonte**: `ELICITATION_OPUS_REPORT.md:444` per il conteggio delle azioni per
  forma; `GIORNATA3_REPORT.md:160` per le azioni reali del 17/08 su BTC
  (`short 0.55` × 3). Entrambi gitignorati.

**Chiedere in quote rende l'agente più prudente.** Non era un'ipotesi del
disegno: è un reperto. **Da tenere per la Stagione 1**, perché tocca la misura
primaria (l'azione), non solo il campo accessorio.

### B.3 — Rimedio al caching, misurato

**Il rimedio**: rimandare indietro il turno dell'assistente con i **soli
blocchi `tool_use`** — id deterministici, **testo libero rimosso**.

| | costo per chiamata |
| --- | ---: |
| prima | **~ $1,78** (`$1,7809`) |
| dopo | **~ $0,21** (`$0,2154`) |
| rapporto | **8,8×** |

**Fonte**: `ELICITATION_OPUS_REPORT.md:85-91` (gitignorato).

**Effetto collaterale, verificato**: sotto protocollo normalizzato il **percorso
di raccolta dati** è risultato **IDENTICO in 100 chiamate su 100** —
`get_universe > get_asset_dossier > get_ohlcv > get_funding`, nessuna
divergenza, in nessuna forma, su nessuno dei due snapshot (righe 262-265).

**DA PORTARE nel runner del RUN2**, con **doppia motivazione**:

1. **costo** — 8,8× non è un'ottimizzazione, è un ordine di grandezza;
2. **rimozione della fonte di divergenza dei prefissi** — il testo libero
   variabile nel turno rimandato indietro spezza il prefisso di cache e, con
   esso, la comparabilità delle chiamate.

> Cautela dichiarata dal referto stesso (riga 540 e seguenti): la
> normalizzazione **è stata introdotta per il costo** e si applica identica a
> tutte le forme, quindi non confonde il confronto A/B — ma resta una modifica
> al protocollo di chiamata, e come tale va dichiarata nel PREREG.

### B.4 — Tasso di `overloaded_error` su `claude-opus-5`

La sera del **18/08**, al primo passaggio del giro di elicitation, **23
chiamate** sono fallite con **`overloaded_error`**
(`ELICITATION_OPUS_REPORT.md:251-254`). Tutte **transitorie**, tutte **riuscite
al ritentativo**: a fine giro, 300 turni di cui 296 al primo tentativo e 4 dopo
ritentativi (uno a 1, due a 3, uno a 5), **zero errori residui**. Le richieste
fallite non sono fatturate.

- **Il client di S0 già ritenta**: `arena/llm_client.py:414-421` classifica
  `overloaded_error` fra i tipi ritentabili, insieme a `rate_limit_error`,
  `api_error` e `timeout_error`. Verificato nel codice al 2026-08-19. Lo script
  del rito di elicitation, invece, non ritentava: da lì i 23 buchi.
- **[FONTE NON TROVATA] — il denominatore.** Il rito dichiara «23 su 40
  chiamate (~57%)». Il numeratore **23** è nel referto; **il denominatore 40
  non compare**, né come conteggio né come percentuale. Sul disco restano **39
  file `scratchpad/elicitation/errore_*.txt`**, che non coincidono con nessuno
  dei due numeri. **Il tasso non è ricostruibile da questo repo**: si registra
  il conteggio assoluto e si dichiara la percentuale come non verificata.

**Da monitorare come rischio di calendario per la stagione**: un tasso di
questo ordine, su un rito che gira una volta al giorno con cap di calendario a
42 giorni (§A.8), è una voce di rischio operativo, non un fastidio.

### B.5 — Costi misurati e proiezione

**Misurato**, sul giro definitivo di 100 chiamate normalizzate:

| voce | valore |
| --- | ---: |
| totale 100 chiamate | **$56,2387** |
| **media per chiamata** | **$0,5624** |
| chiamate servite **a cache fredda** | **~ 22 su 100** |
| chiamata **a caldo** | ~ **$0,21** |
| chiamata **a freddo** | ~ **$1,78** |
| TTL della cache nel rito | **1 h** |

**Fonte**: `ELICITATION_OPUS_REPORT.md`, PASSO 7 (righe 465-490) e SEZIONE G.
La media $0,5624 è il quoziente diretto $56,2387 / 100. Il referto segnala
anche che, con il **TTL a 1 h**, ogni scrittura in cache è tariffata al
**doppio** dell'input e **non a 1,25×**: la voce «scrittura 1,25×» non compare
affatto nel conto.

**PROIEZIONE per la stagione** (TTL **5 m** del runner, non 1 h):

- **~ $3 al giorno**
- **banda $70-120 per 28 giornate**

> **MARCATA COME PROIEZIONE.** Non è un preventivo. **Il preventivo vincolante
> è un rito obbligatorio pre-freeze** (regola 50), da eseguire con
> `count_tokens` **sulla configurazione vera** — non per estrapolazione da un
> rito con TTL e protocollo diversi.
>
> Il precedente è documentato: TL-007 aveva stimato «~$4,90 al giorno, ~$98 per
> venti giornate, incertezza ±20%»; il referto di elicitation registra un
> preventivo iniziale di $34, uno rivisto a ~$45 e un **effettivo di $56,24**
> sulle stesse 100 chiamate. Le proiezioni su questa macchina hanno sbagliato
> per difetto tre volte su tre.

---

## §C — Rimandi a `zeroPipes` (nessuna decisione presa qui)

Queste voci vivono nell'altro repository. Sono elencate perché la sessione le
ha toccate, **non** perché questo verbale le decida o le chiuda.

> **[FONTE NON VERIFICABILE DA QUI]** — `zeroPipes` non è raggiungibile da
> questo repo e il §7 del CLAUDE.md vieta qualunque path verso di esso. Quanto
> segue è trascrizione della sessione, non verifica.

- **P1 (calibrazione del funding)** — da **rimisurare sul funding storico
  reale**. Dichiarato dal consigliere come **debito proprio**, **priorità
  alta**. Dati reali visti in sessione: **~10,95% / 10,70%** istantaneo,
  **9,58% / 8,29%** media a 7 giorni, contro una **calibrazione sintetica del
  3,4%**. L'ordine di grandezza dello scarto è il motivo della priorità.
- **Cinque firme di CODA §2 pendenti.** La proposta **B-primo** (costo
  **18,74 bps**) **NON è firmata**: l'ordine deciso è **P1 prima**.
- **`PREREG_CARRY`** — **non esiste ancora**.
- **Fascia 8-10 USD** — il trigger **ha funzionato**: è scattato, la questione è
  stata riaperta e decisa. **La chiusura formale in CODA non è ancora annotata.
  Da fare.**

---

## §D — Nota di integrità

Il **conteggio degli errori del consigliere** citato nei documenti
(**quattordici**) **non ha fonte in questo repo**: la progressione esiste solo
nella chat. Una ricerca sui documenti del repository non produce l'elenco che
sosterrebbe il numero.

**CODA lo registra già come voce aperta.**

**Questo verbale non stabilisce il numero.** Lo cita come pendenza e si ferma.

---

## §E — Cosa questo verbale NON fa

- **Non firma.** Le cinque firme di CODA §2, le righe di firma dei documenti di
  ricerca e la soglia numerica della regola candidata 51 (§A.14) restano
  pendenti e restano dove sono.
- **Non pre-registra.** Il `PREREG_LAB_S0_RUN2` non esiste; niente qui dentro
  può essere citato come artefatto pre-registrato.
- **Non autorizza.** Nessun rito del pin, nessun freeze, nessuna esecuzione.
- **Non ripara.** Le divergenze accertate nelle §A.1, §A.4, §A.5, §A.6 e §A.7
  sono **registrate**, non corrette: la correzione è codice e vive nei riti che
  seguiranno.
- **Non legge misure di S0.** Il §5 del `PREREG_LAB_S0` le riserva alla fine
  della stagione e TL-006 dichiara che la clausola è stata rispettata. I numeri
  citati nella §A.8 (11%, 1 su 4) provengono dal **conteggio degli esiti
  operativi**, non dalle misure primarie del §4.

---

## §F — Cosa non ho potuto verificare

Sezione mai vuota per compiacenza.

**Referti citati: quali esistono su disco.**

| Referto citato | Stato |
| --- | --- |
| `ELICITATION_OPUS_REPORT.md` | **presente** alla radice, **gitignorato** (`.gitignore:25`) |
| `GIORNATA3_REPORT.md` | **presente** alla radice, **gitignorato** |
| `DECISIONE_CIECA_OPPUS_REPORT.md` | **presente** alla radice, **gitignorato** |
| `SCHEDULER_REPORT.md` | **presente** alla radice, **gitignorato** |
| `CHIUSURA_S0_REPORT.md` | **presente** alla radice, **gitignorato** |
| `DECISION_LOG.md` | **presente**, **committato** |
| `docs/PREREG_LAB_S0.md` | **presente**, **committato**, con `.ots` |
| `PREREG_LAB_S0_RUN2` | **NON ESISTE** — è ciò che questo verbale prepara |
| `PREREG_CARRY` (`zeroPipes`) | **non verificabile da qui** |
| `zeroPipes/docs/program/CODA.md` | **non verificabile da qui** (§7 vieta il path) |

**Tutti i referti sopra sono gitignorati.** Le citazioni di questo verbale
puntano quindi a file che **non sopravvivono a un clone pulito**: chi legge
questo documento fra sei mesi, da una copia del repository, **non potrà
riaprire le fonti**. È un limite strutturale della citazione, non un difetto di
questo verbale, ed è la ragione per cui i numeri sono trascritti qui per esteso
invece che rimandati.

**Affermazioni che non ho potuto verificare:**

1. **Il denominatore del tasso di `overloaded_error`** (§B.4). «23 su 40» — il
   23 è nel referto, il 40 non c'è. Sul disco ci sono 39 file `errore_*.txt`.
   Il tasso ~57% **resta non verificato**.
2. **La proiezione di costo della stagione** (§B.5): ~$3/giorno, banda $70-120.
   **Nessuna fonte su disco**: è un calcolo di sessione. Il referto fornisce
   solo i costi misurati a TTL 1 h; la proiezione a TTL 5 m non è documentata
   da nessuna parte nel repo.
3. **Lo stato del limite di Console** (§A.18). Deciso in chat; la Console non
   lascia traccia nel repository. **Da eseguire e verificare fuori da qui.**
4. **Il calcolo di potenza** (§A.8): 80% ad alfa = 0,05 unilaterale contro
   q ≤ 0,10 con tasso vero ≥ 0,25. **Il calcolo non esiste su disco**: non ho
   trovato né lo script né il foglio che lo produce. Ho verificato solo gli
   input osservati (11%, 1 su 4), non la derivazione della potenza né la
   dimensione 40.
5. **La derivazione di «40 coppie»** (§A.8) e delle attese 20 / 23 / 28
   giornate. Le attese sono coerenti con l'aritmetica elementare (40 coppie /
   2 asset = 20 giornate, gonfiate del tasso di fallimento), ma il documento
   che le calcola non esiste nel repo.
6. **Il requisito «≥ 125 mondi con esito (5 bin × 25)»** (§A.9). **Nessuna
   fonte su disco.**
7. **L'errore standard 0,050 e i 3,0 sigma** della suite di regressione
   (§A.10). Ho verificato **la regola delle soglie** (`DECISION_LOG.md:58-72`),
   **non** il calcolo dell'errore standard su 15 snapshot × k = 5.
8. **Il conteggio «quattordici errori del consigliere»** (§D). **Nessuna fonte
   nel repo.**
9. **Tutta la §C.** `zeroPipes` non è ispezionabile da questo repository: i
   numeri del funding (10,95% / 10,70% / 9,58% / 8,29% / 3,4%) e il costo di
   B-primo (18,74 bps) sono trascrizione di sessione.
10. **Il numero di riga citato dal rito per la divergenza dei token**
    (`DECISION_LOG.md:43`). La riga effettiva è la **45**: ho corretto il
    riferimento e lasciato traccia della correzione in §A.1.
11. **Le riparazioni allo snapshot rimandate al RUN3** (§A.3): «artefatto
    weekend» e «giorno-della-settimana». Non ho cercato né verificato la
    diagnosi che le fonda; le registro come rimandate, senza giudicarle.

**Nota di metodo.** Tutte le verifiche di questa sessione sono state fatte in
**sola lettura** su file già presenti sul disco. Nessuna chiamata all'API,
nessuna esecuzione della suite, nessuna rete.
