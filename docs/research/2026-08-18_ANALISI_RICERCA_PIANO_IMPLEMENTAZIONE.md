# APPENDICE DATATA — ANALISI DELLA RICERCA E PIANO DI IMPLEMENTAZIONE — 2026-08-18 (parte C)

> **Tipo di documento**: analisi critica + piano operativo. **Parte C.**
> **Presuppone**: `2026-08-18_RICERCA_ARCHITETTURE_AGENTE.md` (parte A),
> `2026-08-18_RICERCA_CADENZA_SISTEMI_INTRADAY.md` (parte B), e il report di ricerca
> estesa *"Qualità decisionale degli agenti LLM in funzione della cadenza decisionale:
> censimento delle baseline pubblicate"* (18/08/2026).
> **Nessun contenuto di A e B è ripetuto.**
>
> **Contenuto nuovo**: sette reperti che nascono dall'incrocio fra il report e il design
> di traderLab (non stanno né nel report né nei file di casa), due correzioni al report
> stesso, la scala di implementazione ordinata per valore/costo, e le tre voci con
> **scadenza pre-chiusura S0**.
>
> **Nessun file di S0 toccato. Nessuna modifica a `src/`. Nessun commit. Nessun rito CLI.**
> **Metrica di fase invariata: "verdetti prodotti, non idee aggiunte."**
> La storia non si riscrive, si annota.

---

## §20 — DUE CORREZIONI AL REPORT DI RICERCA

Il report è solido, ma va letto con la stessa diffidenza che applichiamo a tutto il resto.
Due punti non reggono.

### 20.1 — L'ECE è NON INTERPRETABILE quando la confidenza è degenere. Ed è una trappola.

Il report raccomanda (Fase 1): *"ECE daily ≤ 0,15 sarebbe sorprendentemente buono;
ECE > 0,25 conferma la degradazione attesa."*

**Non è eseguibile con i dati che abbiamo, e peggio: produrrebbe un numero falsamente
rassicurante.**

L'ECE è definito come
`ECE = Σ_m (|B_m|/n) · |acc(B_m) − conf(B_m)|`
dove `{B_m}` partiziona i campioni per confidenza predetta.

Con la confidenza ancorata a 0,55 e dispersione 0,0167, **tutti i campioni cadono in un
solo bin**. L'ECE degenera a `|accuratezza − 0,55|`. E l'accuratezza direzionale su crypto
è per costruzione vicina a 0,50.

**Conseguenza aritmetica: ECE ≈ |0,50 − 0,55| = 0,05.**

Cioè: un valore che nel censimento del report si legge come *calibrazione eccellente*
— migliore di Claude Opus 4.1 sul FOMC (0,09/0,17), migliore di GPT-5 (0,20/0,14),
in linea col miglior valore NLP di Tian et al. (0,05).

**È un artefatto.** Non misura calibrazione: misura la coincidenza fra dove sta l'àncora e
dove sta il tasso base. Una curva di affidabilità con un solo punto non è una curva.

**Regola candidata (50): l'ECE non si riporta mai senza la dispersione della confidenza
accanto. Sotto una soglia di dispersione dichiarata, l'ECE si marca esplicitamente
"NON INTERPRETABILE" e non entra in nessun confronto.**

Questo è il tipo di numero che, entrato una volta in un pannello, ci convince di avere
una calibrazione che non abbiamo. Va bloccato prima, non dopo.

### 20.2 — Un non-sequitur nella previsione falsificabile #3

Il report scrive (Punto C, previsione 3): *"la dispersione inter-repliche per-decisione è
statisticamente indistinguibile tra daily e 4-ore (**la potenza sullo Sharpe dipende solo
da Sharpe annualizzato e tempo, non dal numero di trade — il principio SR_min del
laboratorio**)"*.

La parentesi non sostiene la previsione. SR_min riguarda la **potenza statistica sulla
stima dello Sharpe**; non dice nulla su se la **dispersione decisionale per-decisione**
vari con la cadenza. Sono due grandezze diverse: una è una proprietà dello stimatore, l'altra
è una proprietà del comportamento del modello.

La previsione può benissimo essere vera — ma la giustificazione è un aggancio plausibile a
un principio di casa, non una derivazione. **È esattamente il difetto che il §8
dell'addendum sera 17/08 ha diagnosticato nel consigliere**, riprodotto qui da uno strumento
di ricerca.

**Correttivo**: la previsione 3 va ri-motivata o declassata a ipotesi senza meccanismo
dichiarato. Non si pre-registra un'ipotesi con una giustificazione sbagliata: l'errore
sopravvive dentro la pre-registrazione e la contamina.

---

## §21 — IL REPERTO PRINCIPALE: L'OGGETTO PROBABILITÀ CHE CI SERVE ESISTE GIÀ

Questo è il pezzo che cambia una decisione, e nasce dall'incrocio di cinque fatti che nel
report stanno in sezioni diverse.

### 21.1 — La catena

1. **P4** (*The Alpha Illusion*, parte A §3.2): la confidenza auto-dichiarata dell'LLM
   **non deve controllare il sizing**.
2. **Reperto locale**: la confidenza verbalizzata è degenere a 0,55 → inutilizzabile come
   input di sizing anche volendo.
3. **Fase 3 del report**: fra i rimedi proposti all'ancoraggio c'è *"self-consistency come
   stima alternativa"*.
4. **Huang et al., ICLR 2024** (arXiv:2310.01798): il dibattito multi-agente sottoperforma
   la **semplice self-consistency** a parità di risposte. La self-consistency è il metodo
   che regge.
5. **D1**: il programma fa già girare **tre repliche identiche ogni giorno**, e ne logga
   l'accordo. Giorno 1: BTC accordo 2/3, ETH 3/3.

### 21.2 — La conclusione

**Il tasso di accordo inter-repliche È uno stimatore di confidenza per self-consistency.
E lo produciamo già, ogni giorno, a costo zero.**

D1 è stato costruito per rispondere a *"quanto rumore fa un cervello con se stesso"*.
Nel farlo ha costruito **l'unico oggetto-probabilità ammissibile per il sizing che esista
in tutto il sistema**.

Perché è ammissibile dove la confidenza verbalizzata non lo è:

| proprietà | `confidence` verbalizzata | accordo inter-repliche |
|---|---|---|
| natura | **auto-riferita** — l'LLM dichiara un numero su sé stesso | **comportamentale** — si conta cosa ha fatto |
| esposta al problema di fedeltà (Turpin, Lanham, arXiv:2503.08679) | **sì**, pienamente | **no** — non è una dichiarazione, è un conteggio |
| chi la produce | l'LLM | **il codice che conta i voti** |
| stadio 4 del confine modulare | posseduto dall'LLM → **rompe P4** | posseduto dal codice → **P4 soddisfatto per costruzione** |
| dispersione osservata | 0,0167 (degenere) | reale: 2/3 e 3/3 già al giorno 1 |
| costo marginale | zero | **zero** |

**Il metro del rumore e lo stimatore di confidenza sono lo stesso strumento.**

### 21.3 — Riserve oneste, tutte e quattro

**(a) L'accordo NON è una probabilità.** È un punteggio grezzo. Diventa una probabilità
solo dopo essere stato **calibrato** contro gli esiti realizzati — che è precisamente il
lavoro del meta-layer. La buona notizia: la calibrazione **non richiede indipendenza**,
richiede una relazione monotona con la frequenza realizzata.

**(b) Granularità grossolana.** Con k=3 repliche l'accordo ha 4 livelli possibili
(0, 1/3, 2/3, 1); la suite di regressione gira già a k=5 → 6 livelli. È poco.
**Ma** *Rescaling Confidence* (arXiv:2603.09309) trova che **le scale più grossolane
battono la 0–100 sulla sensibilità metacognitiva**. La grossolanità potrebbe essere una
caratteristica, non un difetto. Da misurare, non da assumere.

**(c) PPL — il prior è condiviso.** Le tre repliche sono lo stesso modello: il loro accordo
**non è accordo fra esperti indipendenti** (parte A §3.4). Misura la **prossimità al confine
decisionale**, non la forza dell'evidenza. Ammissibile per il sizing una volta calibrato;
**inammissibile** come "conferma".

**(d) Prerequisito bloccante.** Se una parte della dispersione inter-repliche è artefatto
infrastrutturale (§22), allora una parte di p̂ è rumore. **Il §22 va risolto prima che
questo diventi un endpoint.**

### 21.4 — Effetto sulla decisione D-LAB-S1-CONF (parte A §5.4)

La formulazione della parte A diceva: *la confidence può entrare in un modulo separato come
feature fra le altre*. Alla luce di questo, la formulazione diventa più forte e più semplice:

> **L'oggetto designato per il sizing in Stagione 1 è `p̂_accordo`**, stimatore per
> self-consistency derivato dal tasso di accordo inter-repliche, **calibrato da un modulo
> statistico indipendente** contro gli esiti realizzati di Stagione 0.
> Il campo `confidence` verbalizzato **non entra mai nel sizing**, né direttamente né come
> feature, finché non supera l'ablazione di elicitazione del §24.3 e mostra dispersione
> sopra soglia dichiarata.

Questo soddisfa P4 per costruzione, tiene lo stadio 4 in mano al codice, e **non costa una
singola chiamata API in più**.

---

## §22 — IL METRO DEL RUMORE HA UN CONFONDENTE, E LA FINESTRA PER CHIUDERLO SI STA CHIUDENDO

### 22.1 — Il problema

Thinking Machines Lab (set. 2025, in report §Corpus 3): su Qwen3-235B, 1000 completamenti a
temperatura 0 producono **80 completamenti unici, il più comune 78 volte**; con kernel
batch-invariant tutti i run diventano **bitwise identici** (overhead ~61,5%, ridotto a
~34,35% da SGLang). La varianza a temp=0 è **artefatto infrastrutturale** — dipendenza dal
batch size dei kernel di riduzione.

Il programma gira a **temperatura > 0 per scelta** (D4), quindi il rumore di campionamento
è voluto e dominante. **Ma il rumore infrastrutturale non sparisce: si somma.** E dipende
dal batching sui server Anthropic, che dipende dal carico, che **dipende dall'ora del
giorno**.

**Conseguenza per l'Idea #13-bis**: MODE-D gira a un'ora UTC fissa, MODE-I gira a sei ore
UTC diverse. Carichi diversi → rumore infrastrutturale diverso → **il confronto di cadenza
è confuso alla radice**. Staremmo misurando in parte l'orario dei data center.

Il report lo dice come caveat generico (*"interpretare la dispersione osservata solo dopo
aver fissato o documentato l'infrastruttura di inferenza"*). Via API **non possiamo fissare
niente**. Ma possiamo **misurare il pavimento**.

### 22.2 — La soluzione: due sonde sintetiche nella suite congelata

Non serve controllare l'infrastruttura. Serve un **riferimento interno** che separi il
rumore dall'ambiguità.

| sonda | contenuto | comportamento atteso | cosa misura |
|---|---|---|---|
| **Sonda nulla** | snapshot sintetico dove la decisione è meccanicamente forzata (funding a un estremo, base a un estremo, un solo verso ammissibile) | accordo **3/3 sempre** | qualunque disaccordo qui è **rumore puro** → è il **pavimento** |
| **Sonda cieca** | snapshot sintetico a informazione nulla (funding piatto, base zero, nessun segnale) | disaccordo **massimo** | il **soffitto** della dispersione a informazione assente |

Fra pavimento e soffitto si ottiene una **scala calibrata per il metro del rumore**. La
dispersione osservata sui mondi reali si legge in percentuale di quell'intervallo, non in
assoluto.

**Nessun benchmark censito nel report ha questo controllo.** Non è un dettaglio igienico:
è la differenza fra "le repliche divergono" e "le repliche divergono più di quanto
divergerebbero su un mondo senza informazione".

### 22.3 — Perché ha una SCADENZA

La suite di regressione comportamentale congela **10–15 snapshot reali durante Stagione 0,
una volta, mai più toccati**. Se le due sonde sintetiche non entrano nella suite **adesso**,
non ci entrano più senza rompere il freeze.

**Questa è una voce con scadenza, della stessa famiglia della 1.1 di `CODA.md`.**
Va decisa prima della chiusura di S0, e la decisione va presa **prima** di vedere quanto
dispergono le repliche sui mondi reali — altrimenti la scelta è contaminata.

---

## §23 — TRE DIFETTI DI DISEGNO TROVATI INCROCIANDO IL REPORT CON I NOSTRI OTTO COMPONENTI

### 23.1 — Il confronto appaiato ha un problema di beta

**Componente 4** del design: *"Confronto appaiato giornaliero vs gamba meccanica: stesso
universo, stesso istante di decisione, differenze daily in un e-process anytime-valid."*

**Il difetto**: la gamba meccanica è **carry, delta-neutrale per costruzione** (beta ≈ 0).
Il Trader è **direzionale su BTC/ETH** (beta ≠ 0). La differenza `agente − meccanica`
**contiene il beta di BTC**.

Conseguenza: in regime toro l'agente batte la gamba carry sul P&L **per solo beta**, e
l'e-process deriva positivo. In regime orso il contrario. **Il confronto appaiato, così
com'è, è dipendente dal regime per costruzione** — e ci direbbe "l'agente vince" proprio
quando non vince.

**Il report dà la misura di quanto sia grave**: KTD-Fin (arXiv:2605.28359), 10 agenti su
548 giorni, decomposizione market/style/selection — il **miglior selection-alpha è +0,2%**,
gli altri nove da negativi fino a **−77,8%**, e **l'agente col miglior rendimento (+85% su
due anni) seleziona peggio del caso**. Il rendimento è quasi tutto beta.

**La correzione, a costo zero e senza toccare il percorso congelato:**

> Dichiarare **ORA**, prima di vedere l'esito, che al confronto appaiato si affiancano tre
> baseline calcolate **agli stessi istanti** e alla **stessa size fissa**:
> **(a) sempre-long, (b) sempre-flat, (c) coin-flip a size fissa.**
> Il numero riportato è l'**eccesso dell'agente sul migliore dei tre**, più la
> decomposizione beta / selezione.

**Perché costa zero e non viola la regola 10**: i prezzi sono già memorizzati. Le tre
baseline **non richiedono nessuna chiamata LLM** e possono essere calcolate **a stagione
chiusa** dai dati storici. Si dichiarano adesso, si calcolano dopo. Nessun codice nuovo
gira dentro la stagione.

Il report lo mette fra i controlli minimi che un revisore pretenderebbe (*"baseline
multiple: buy-and-hold, always-long, e random/coin-flip a parità di size"*). Noi ne abbiamo
due su tre mancanti.

### 23.2 — Il budget di ragionamento è un grado di libertà forse non dichiarato

Reperto dal report: la curva accuratezza↔lunghezza del ragionamento è **a U rovesciata**,
con picco intorno ai **10K token**; oltre, il ragionamento esteso fa **flippare risposte
corrette in errate**. Meccanismo proposto: **il thinking esteso aumenta la varianza della
distribuzione di output** (arXiv:2604.10739, arXiv:2506.04210). E TraderBench
(arXiv:2603.00285): il thinking esteso migliora molto il retrieval e **quasi nulla il
trading**.

Il FreezeManifest pinna modello, `prompt_sha`, `context_git_sha`, temperatura.
**Il budget di thinking è pinnato?** Non lo so, e non lo invento: `thinking.display`
compare in `CODA.md` come candidato registrato per la Stagione 1, quindi il thinking è
materia viva.

**È una verifica, non un'affermazione. Va letta dal manifest.**

Se non è pinnato, la catena di conseguenze è seria:

```
budget di thinking non dichiarato
   → varianza dell'output non controllata
      → dispersione inter-repliche contaminata (metrica #4)
         → metro del rumore non affidabile
            → p̂_accordo (§21) non affidabile
               → l'oggetto di sizing di S1 poggia su un parametro fantasma
```

Tutto ciò che sta a valle del §21 dipende da questo. **Prima verifica del piano.**

### 23.3 — La cadenza e il contesto sono confusi, e bisogna scegliere quale tenere fermo

Reperto dal report: NoLiMa (ICML 2025) — a 32K token, **10 modelli su 12 rendono metà** di
quanto rendono a contesto corto; GPT-4o scende dal 99,3% al **69,7%**. Lost-in-the-middle
(TACL 2024): calo >30%, curva a U.

**Il problema nell'Idea #13-bis**: come si costruisce lo snapshot intraday?

| scelta | conseguenza |
|---|---|
| **stesso numero di barre** (es. 30 barre daily vs 30 barre 4h) | volume di informazione costante, **ma orizzonte di lookback 6× più corto** nel braccio intraday |
| **stesso orizzonte di lookback** (es. 30 giorni: 30 barre daily vs 180 barre 4h) | orizzonte costante, **ma 6× i token** nel braccio intraday → si misura il context rot, non la cadenza |

**Non esiste una scelta neutra.** Se non si dichiara quale grandezza si tiene ferma, il
confronto di cadenza confonde due variabili e il risultato non è interpretabile.

**Raccomandazione**: tenere fermo il **volume di informazione** (stesso numero di barre,
stesso conteggio token dello snapshot), e **dichiarare esplicitamente come limitazione**
che l'orizzonte di lookback varia con la cadenza. Motivo: il context rot è un effetto
documentato e grande (fino al 50% di degrado), mentre l'orizzonte più corto è una proprietà
intrinseca del compito intraday — è parte di ciò che vogliamo misurare, non un confondente.

Questo controllo **non compare in nessuno dei protocolli intraday censiti dal report**.

---

## §24 — COME CHIUDEREI I CINQUE GAP

Il report dichiara cinque metriche senza baseline pubblicata. Per ciascuna, il modo più
economico di produrre **la prima**.

### 24.1 — Gap #3: dispersione della confidenza verbalizzata in finanza direzionale

**Come si chiude**: è già in chiusura. S0 la produce ogni giorno. Serve solo **dichiarare
prima** cosa si riporterà: istogramma completo dei valori (non media e deviazione standard —
con una distribuzione degenere sono fuorvianti), frazione in [0,50–0,60], numero di valori
distinti osservati, e frazione sui multipli di 0,05 (*One Size Fits None* riporta quote
multipli-di-5 del **96–100%**: è il confronto diretto).

**Costo: zero.** È già raccolto. **Deliverable**: la prima dispersione pubblicata di
confidenza verbalizzata in decisione direzionale crypto.

### 24.2 — Gap #4: dispersione inter-repliche a input identici in trading

**Come si chiude**: le due sonde del §22 danno pavimento e soffitto; i mondi reali danno la
distribuzione in mezzo. **Costo: due snapshot sintetici nella suite** — decine di dollari,
ma **con scadenza al freeze della suite**.

**Deliverable**: la prima misura di dispersione decisionale **normalizzata su un
riferimento interno**, invece che in assoluto. Nessuno ce l'ha.

### 24.3 — Gap #3-bis: l'ancoraggio a 0,55 è del modello o del formato?

Il report dice che è un reperto **quasi-nuovo** e che va verificato con elicitazione
alternativa prima di attribuirgli significato. Concordo, e propongo il disegno.

**Ablazione di elicitazione su snapshot congelati**, quattro formati, stesso mondo:

| formato | elicitazione | cosa distingue |
|---|---|---|
| **E1** | continuo 0–1 (attuale) | il baseline |
| **E2** | ordinale grossolano, 5 livelli | testa l'ipotesi *Rescaling Confidence* (le scale grossolane battono la 0–100) |
| **E3** | comparativo/pairwise ("questo setup è più o meno favorevole di quest'altro?") | rimuove la scala assoluta |
| **E4** | **implicito**: nessuna confidenza chiesta; p̂ = frequenza dell'azione modale su k campioni | **comportamentale, non dichiarata** — il §21 |

**Verdetto pre-dichiarato**: se l'ancoraggio sopravvive a E2 ed E3, è proprietà del modello
→ reperto pubblicabile. Se si rompe, è proprietà del formato → **abbiamo trovato gratis un
formato migliore**, e in entrambi i casi E4 è il candidato per il sizing.

**Costo**: snapshot già congelati, offline, quattro passate. Ordine **$100–200**, stima
derivata da $1,63/ciclo. Post-S0.

### 24.4 — Gap #5: coerenza feature dichiarate ↔ tool chiamati

Il report conferma: **non esiste una metrica standard con baseline trasferibile**. È
letteralmente l'Idea #6 già approvata (parte A, `CODA.md` §6.9).

**Come si chiude**: definire la metrica **prima** di calcolarla — proposta:
`coerenza = |feature dichiarate ∩ tool effettivamente chiamati| / |feature dichiarate|`,
con verifica numerica del valore citato contro lo snapshot persistito.

**Riferimento esterno da citare**: la faithfulness CoT generica (99% vs 63% su domande
logicamente equivalenti, arXiv:2503.08679) e la soglia già dichiarata in casa dall'Auditor
(**consistenza <50% ⇒ `features_used` inutilizzabile per il mining**).

**Costo: zero** — è un confronto fra due log già scritti. **Deliverable**: la prima
metrica di coerenza attribuzione-strutturata↔tool in trading.

### 24.5 — Gap #6 e #8: turnover/flip-rate e tasso di astensione in crypto perp

**Come si chiudono**: contando. Con due precisazioni non negoziabili:
- **La HOLD entra sempre nel denominatore.** È il correttivo esplicito al difetto di
  QuantAgent (parte B §14.2(3)), ed è coerente con Gate Concordia.
- Il flip-rate si riporta **condizionato sull'azione precedente**, non aggregato:
  è la previsione falsificabile #2 del report.

**Costo: zero.** **Deliverable**: le prime baseline crypto perp per entrambe.

### 24.6 — Il gap che il report NON elenca: il DSR contro una nulla di casa

Il report osserva che l'aggiustamento per test multipli è **assente quasi ovunque**
(*"nessuno dei benchmark censiti riporta un DSR con N di trial"*) e che il numero effettivo
di trial va **stimato via clustering, non contato**.

Il programma ha **33.818 strategie morte** generate sotto protocollo dichiarato: una
**distribuzione nulla empirica**, nel nostro mercato, tassata dai nostri costi.

**Nessuno può fare quello che possiamo fare noi**: riportare un DSR calibrato su una nulla
**misurata in casa** invece che su un'assunzione gaussiana. Se pubblichiamo qualcosa, quello
è il pezzo che nessun laboratorio con più soldi di noi può copiare in fretta.

---

## §25 — SCALA DI IMPLEMENTAZIONE

Ordinata per valore/costo. **Il livello Z ha scadenza.**

### Livello Z — costo zero, DECISIONE PRIMA DELLA CHIUSURA DI S0

| # | azione | perché ha scadenza |
|---|---|---|
| **Z1** | **Verificare se il budget di thinking è nel FreezeManifest.** Se assente, annotare (non riscrivere) | tutto il §21 e il §22 stanno a valle di questo parametro. Prima verifica in assoluto |
| **Z2** | **Inserire le due sonde sintetiche (§22.2) nella suite di regressione** | la suite si congela una volta sola, durante S0. Dopo non si può più |
| **Z3** | **Dichiarare le tre baseline del confronto appaiato (§23.1)**: sempre-long, sempre-flat, coin-flip | la dichiarazione deve precedere l'esito, altrimenti è contaminata. Il calcolo può avvenire a stagione chiusa |
| **Z4** | **Firmare la regola 50** (§20.1): l'ECE non si riporta mai senza dispersione accanto; sotto soglia si marca NON INTERPRETABILE | se un ECE ≈ 0,05 entra una volta in un pannello, ci convince di avere una calibrazione che non abbiamo |
| **Z5** | **Firmare D-LAB-S1-CONF nella forma del §21.4**: l'oggetto di sizing è `p̂_accordo`, non `confidence` | la scelta va fatta prima di sapere come chiude S0 |
| **Z6** | **Dichiarare il formato di riporto della dispersione della confidenza (§24.1)** | idem: prima dei dati |

### Livello L — costo quasi zero, durante S0, sola lettura

| # | azione | costo |
|---|---|---|
| **L1** | Calcolare `p̂_accordo` dai dati **già loggati** e iniziare la curva di affidabilità | zero chiamate API |
| **L2** | Calcolare la coerenza dichiarativa (Idea #6) dai due log già scritti | zero |
| **L3** | Contare turnover, flip-rate condizionato, tasso di astensione | zero |
| **L4** | Ricostruire le tre baseline dai prezzi memorizzati (dopo aver dichiarato Z3) | zero |

**Nota di igiene**: tutto il livello L è **analisi a valle su dati persistiti**, in cartella
esplorativa etichettata, fuori dai percorsi di verdetto. Regola 10 rispettata.

### Livello P — post-S0, limitato e pre-registrato

| # | azione | costo stimato | trigger |
|---|---|---|---|
| **P1** | **Ablazione di elicitazione** (§24.3, quattro formati) | ~$100–200 | chiusura S0 |
| **P2** | **Idea #13** — Pre-Screen architetture, quattro bracci (parte A §6) | ~$150–300 | chiusura S0 + suite congelata |
| **P3** | **Idea #13-bis** — Arena a due cadenze (parte B §16) | ~$340 | dopo P1 |

**Ordine motivato**: P1 prima di P3, perché se l'elicitazione E4 (accordo) si rivela
l'endpoint giusto, l'arena di cadenza va disegnata su quello e non sulla confidenza
verbalizzata — che a quel punto sarebbe una metrica secondaria.

**Totale livello P: ~$600–850**, contro i ~$1.180 di una sola stagione intraday viva.
E produce **tre reperti pubblicabili** invece di un P&L senza potenza.

---

## §26 — COSA NON FAREI

1. **Non riporterei l'ECE finché la confidenza è degenere.** Vedi §20.1. Il numero
   sembrerebbe ottimo e sarebbe privo di significato.
2. **Non userei il P&L dell'arena di cadenza come endpoint**, nemmeno come secondario non
   dichiarato. Vedi Representation Signatures: Sharpe **7,696 su 40 ore**, dichiarato dagli
   autori stessi come non-claim di profittabilità. Se lo dicono loro dei propri numeri,
   noi lo dobbiamo dire dei nostri **prima** di produrli.
3. **Non consumerei un verdetto di holdout** su nessuna delle voci di questo documento.
   Nessuna lo richiede. Holdout resta **0/2**.
4. **Non aggiungerei bracci oltre quelli dichiarati.** Ogni braccio entra nel denominatore
   del DSR. Il report è netto: nessun benchmark censito lo fa, ed è la ragione per cui la
   letteratura non è confrontabile con sé stessa.
5. **Non tratterei l'accordo inter-repliche come conferma.** Misura prossimità al confine
   decisionale, non forza dell'evidenza (PPL, parte A §3.4). Calibrabile per il sizing,
   **mai** interpretabile come "due repliche su tre confermano".
6. **Non cambierei modello, prompt o temperatura durante S0** per nessuna delle ragioni
   sopra. Tutto quanto qui descritto è compatibile con la stagione viva.

---

## §27 — COSA NON È STATO DECISO (parte C)

Nessuna decisione presa. In particolare **non** sono decise:

1. le sei voci del livello Z — sono **proposte con scadenza**, non firme;
2. la regola candidata 50 (§20.1) e il correttivo alla previsione 3 (§20.2);
3. la riformulazione di D-LAB-S1-CONF nella forma del §21.4;
4. la definizione operativa della metrica di coerenza (§24.4);
5. le soglie di tutto quanto sopra, che restano in bianco per costruzione;
6. l'ordine P1→P2→P3 e i relativi tetti di spesa.

**Restano prioritari e invariati** (da `CODA.md`, 17/08):
- verdetto costo giornata 3 di S0 — **prossimo passo dichiarato**;
- cinque firme pronte su sei;
- la domanda che blocca il PREREG_CARRY (A′ 13,72 bps vs B′ 18,74 bps);
- le tre voci con scadenza pre-fine-S0 già a registro;
- holdout **0/2**, intoccabile.

**Nota di priorità del consigliere**: le sei voci del livello Z **non spostano la fase**.
Sono dichiarazioni, non costruzioni: costano una firma ciascuna e nessuna riga di codice.
Se dovessi sceglierne una sola, sceglierei **Z1** (verifica del budget di thinking), perché
è l'unica da cui dipendono tutte le altre — e perché è una verifica di lettura, non una
decisione.

---

## §28 — PROTOCOLLO DI VERIFICA PER UNA CHAT NUOVA

Prima di procedere su questa materia, recitare:
1. **§20.1** — perché l'ECE non si riporta senza dispersione (la trappola del numero
   falsamente buono);
2. **§21.3** — le quattro riserve su `p̂_accordo`, in particolare che l'accordo non è
   probabilità finché non è calibrato e non è mai conferma;
3. **§23.1** — il problema di beta del confronto appaiato;
4. **§25**, livello Z — le sei voci con scadenza;
5. **§27** — cosa non è stato deciso.

E tenere fermo: questo documento **non modifica la fase, non apre riti, non autorizza
commit**. Tutte le proposte sono compatibili con Stagione 0 viva: nessuna tocca modello,
prompt, temperatura, snapshot o manifest.

---

*Ogni firma è dell'owner. Il consigliere propone, calcola, avverte, filtra — non firma mai.*

**Firme livello Z (§25), una per riga:**

- Z1 verifica budget thinking nel manifest: ______________________ data: __________
- Z2 due sonde sintetiche nella suite: ______________________ data: __________
- Z3 tre baseline del confronto appaiato: ______________________ data: __________
- Z4 regola 50 — ECE mai senza dispersione: ______________________ data: __________
- Z5 D-LAB-S1-CONF nella forma §21.4: ______________________ data: __________
- Z6 formato di riporto della dispersione: ______________________ data: __________

**Soglie da fissare prima di qualunque dato:**
- dispersione minima sotto cui l'ECE è NON INTERPRETABILE: ____________
- coerenza dichiarativa minima (§24.4): ____________
- tetto di spesa livello P: ____________
