# APPENDICE DATATA — RICERCA SULLE ARCHITETTURE D'AGENTE — 2026-08-18

> **Tipo di documento**: appendice di ricerca + ponte tra chat.
> Integra `HANDOFF_NUOVA_CHAT_2026-08-16.md` e i quattro addendum (notte 16, giorno 16,
> sera 16, notte 17, sera 17), che restano validi per intero. **Non sostituisce nulla.**
> Ordine di lettura per una chat nuova: handoff principale → addendum notte 16 → giorno 16
> → sera 16 → notte 16/17 → sera 17 → `CODA.md` → **questo file**.
>
> **Contenuto**: verifica alla fonte primaria di un reperto già citato in casa (AMA,
> arXiv:2510.11695), un reperto nuovo non presente nel dossier di casa (*The Alpha
> Illusion*, arXiv:2605.16895, maggio 2026), l'annotazione di un errore del consigliere,
> e una proposta registrata (**Idea #13**) con trigger.
>
> **Nessun file di Stagione 0 è stato toccato. Nessuna modifica a `src/`. Nessun commit.
> Nessun rito CLI lanciato.** Tutto quanto segue è lettura e analisi.
>
> **Metrica di fase invariata: "verdetti prodotti, non idee aggiunte."**
> La storia non si riscrive, si annota.

---

## §0 — Come è nata questa istruttoria

Domanda dell'owner: costruire in parallelo a zeroPipes una *company* di agenti LLM
specializzati che cooperano — un agente analizza BTC e passa il risultato a un altro,
che usa quell'informazione più quella degli altri agenti per decidere il day trading
(apertura e chiusura, long e short).

Il consigliere ha risposto che l'idea era **già registrata** nel programma (§9 di
`2026-08-13_TRADERLAB_SINTESI_DESIGN.md`: *"seconda variante in arena: il multi-agente
deliberativo TradingAgents-style — aspettativa a priori bassa"*), e ha citato a favore
dell'istinto dell'owner un reperto della rassegna di casa.

L'owner ha posto la domanda giusta: **"architettura" di cosa? LLM o agenti?**

La verifica alla fonte primaria ha (a) risposto alla domanda, (b) scoperto un errore del
consigliere, (c) portato alla luce un paper di maggio 2026 assente dal dossier di casa.

---

## §1 — ANNOTAZIONE DI ERRORE DEL CONSIGLIERE

**Cosa è stato detto (17-18/08, in chat):** citando Agent Market Arena — *"l'architettura
dell'agente, non il backbone LLM, è il driver dominante"* — il consigliere ha scritto
all'owner *"il tuo istinto non è sbagliato"* **in una discussione sul multi-agente**,
lasciando intendere che il reperto sostenesse la company di agenti specializzati.

**Cosa dice davvero la fonte primaria:** AMA implementa **quattro agenti, tutti a cervello
singolo** — InvestorAgent (baseline singolo), TradeAgent e HedgeFundAgent (stili di
rischio diversi, cioè persona), DeepFundAgent (memoria). **Zero sistemi multi-agente nel
confronto.** Il reperto dice quindi che *persona e memoria* spostano il comportamento più
del cambio di modello. Non dice nulla su company di agenti.

**Classificazione dell'errore:** estensione indebita di una citazione oltre il suo scopo,
partendo da una parafrasi secondaria (`2026-08_AGENT_FAITHFULNESS_FRAMEWORKS_LITERATURE.md`
riportava *"variare il design strutturale"*, formula corretta ma sotto-specificata).

**È il secondo esemplare** dello stesso difetto documentato nel §8 dell'addendum sera
17/08: riempire un vuoto di conoscenza con una ricostruzione plausibile invece di
interrogare la fonte primaria. Correttivo confermato: **la fonte primaria si interroga
prima di parlare, non dopo che l'owner solleva un dubbio.**

Nessuna riscrittura del messaggio originale. Annotazione.

---

## §2 — REPERTO VERIFICATO: Agent Market Arena (arXiv:2510.11695)

**Fonte primaria consultata**: abstract arXiv (v1 13/10/2025, v2 30/10/2025),
più due sintesi indipendenti (alphaXiv, emergentmind). Autori: Lingfei Qian, Xueqing Peng
et al. (17 autori; include Alejandro Lopez-Lira e Sophia Ananiadou). Destinazione WWW 2026.

### 2.1 — Disegno sperimentale (il punto che risolve la domanda dell'owner)

| asse | livelli |
|---|---|
| **Architettura d'agente** | InvestorAgent (baseline singolo) · TradeAgent (stile di rischio A) · HedgeFundAgent (stile di rischio B) · DeepFundAgent (memoria) |
| **Backbone LLM** | GPT-4o · GPT-4.1 · Claude-3.5-haiku · Claude-sonnet-4 · Gemini-2.0-flash |
| **Asset** | TSLA, BMRN (equity) · BTC, ETH (crypto) |
| **Finestra** | init storico 2025-05-01 → 2025-07-31; trading reale dal 2025-08-01 |

I cinque backbone **sono** l'asse "modello". Il disegno serve esplicitamente a districare
l'effetto dell'architettura d'agente da quello del backbone a condizioni identiche.

**Risposta alla domanda dell'owner: architettura degli AGENTI (impalcatura, ruoli, persona,
memoria). Non architettura degli LLM.**

### 2.2 — Reperto e sua portata reale

I framework d'agente mostrano pattern comportamentali marcatamente distinti (dal
risk-taking aggressivo alla decisione conservativa), mentre i backbone contribuiscono meno
alla variazione dell'esito. I meccanismi memory-adaptive rendono l'agente **più avverso al
rischio col passare del tempo**.

**Portata corretta**: gli assi che dominano sono **persona/stile di rischio** e **memoria**.
Non "numero di agenti".

### 2.3 — Riserve metodologiche (del consigliere, non del paper)

1. **Molteplicità.** 4 agenti × 5 backbone × 4 asset = **80 celle**. Il paper stesso rileva
   che sono specifici accoppiamenti agente-backbone a rendere bene, non una configurazione
   universalmente migliore (es. InvestorAgent + GPT-4.1 → +40,83% cumulato su TSLA). Trovare
   vincitori in una griglia da 80 celle è esattamente ciò che il DSR esiste per punire.
   **Nessun aggiustamento per molteplicità è riportato.**
2. **Finestra corta e singolo regime** (trading reale da agosto 2025).
3. **Usa news verificate da esperti** come input → superficie di contaminazione testuale
   che il nostro principio #6 (niente feed testuali) esclude per costruzione.
4. Il baseline a cervello singolo (InvestorAgent) è tra i migliori performer riportati.

### 2.4 — Conseguenza per traderLab

Gli assi che AMA indica come dominanti sono **già decisi in casa**:

| asse AMA | dove vive in traderLab | stato attuale |
|---|---|---|
| persona / stile di rischio | context files versionati in git, release via HR | congelato in S0 |
| memoria | principio #5: niente memoria/apprendimento in corsa | **disabilitato per scelta** |
| backbone | D2: Fable 5 pinnato, FreezeManifest + OTS su Bitcoin | congelato |

**Lettura**: la leva col miglior rapporto valore/costo non è aggiungere agenti — è la
**Scuola del Trader** (release di contesto tra stagioni), già registrata con trigger
"prima release post-Stagione 0" nell'addendum notte 16/08.

---

## §3 — REPERTO NUOVO: *The Alpha Illusion* (arXiv:2605.16895, 16/05/2026)

**Titolo completo**: *The Alpha Illusion: Reported Alpha from LLM Trading Agents Should Not
Be Treated as Deployment Evidence.*
**Autori**: Yuxuan Ye, Jun Han et al. — Fudan University, Shanghai Univ. of Finance and
Economics, Southwest UFE, Northeastern Univ., Imperial College London, Peng Cheng Lab.
**Corresponding**: Zenglin Xu (Fudan).
**Harness di riproduzione**: `github.com/hj1650782738/Trading`.

**Non è citato in nessuno dei file di ricerca di casa** (`2026-08_LLM_TRADER_AGENTS_LITERATURE.md`,
`2026-08_AGENT_FAITHFULNESS_FRAMEWORKS_LITERATURE.md`). È un reperto nuovo, ed è
metodologicamente il più vicino al programma di qualunque cosa letta finora.

### 3.1 — Tesi

L'alpha riportato dai trading agent LLM end-to-end **non va trattato come evidenza di
deployment** finché non supera test di validità strutturale su: integrità temporale,
frizioni reali, robustezza controfattuale, calibrazione predittiva, esecuzione numerica,
e disaggregazione multi-agente.

Tre disallineamenti strutturali che restano **anche con la valutazione perfetta**:
1. la confidenza linguistica non è probabilità tradabile;
2. l'abilità narrativa non è esecuzione numerica;
3. i prior parametrici nei pesi diventano esposizioni fattoriali implicite non dichiarate.

### 3.2 — I sei protocolli P1–P6 (checklist di pre-registrazione già pubblicata)

| # | modo di fallimento | riporto minimo richiesto | se non soddisfatto |
|---|---|---|---|
| **P1** Integrità temporale | alpha da viaggio nel tempo; leakage da pretraining/retrieval; leakage semantico | versione modello, cutoff, confine di post-training, timestamp del corpus di retrieval, regole di aggiornamento memoria; almeno una finestra post-cutoff o point-in-time | al massimo evidenza da backtest storico |
| **P2** Universo dinamico | survivorship; campioni ripuliti ex-post; universi statici | universo tradabile variabile nel tempo; delisting e sospensioni; filtri di liquidità; cambi di composizione indice; vincoli di prestito e short | l'alpha può venire da universi filtrati ex-post |
| **P3** Robustezza controfattuale | *parametric prior lock-in*; insensibilità all'evidenza contraria; tilt di settore/stile impliciti | tasso di inversione della direzione, spostamento di confidenza, spostamento di size sotto evidenza contraria forte; test sector-neutral e style-neutral | le raccomandazioni possono riflettere prior, non informazione |
| **P4** Calibrazione epistemica | confidenza linguistica scambiata per probabilità di trading; confidenza auto-dichiarata non calibrata | ECE, curve di affidabilità, calibrazione condizionata al regime, calibrazione out-of-sample di qualunque punteggio usato per sizing o controllo del rischio | **la confidenza dell'LLM non deve controllare il sizing** |
| **P5** Implementazione realistica | illusione dell'alpha lordo; predizione accurata con rendimento netto negativo; costi di token e latenza che divorano il rendimento | pulizia stratificata lordo→netto: spread, slippage, commissioni, impatto di mercato, costo di prestito, ritardo di esecuzione, **costo dei token, latenza di inferenza** | i profitti non dimostrano deployabilità |
| **P6** Disaggregazione multi-agente | illusione del consenso; errori correlati tra modelli della stessa fonte; camera dell'eco | **baseline a singolo agente**, similarità dei ruoli, tasso di disaccordo, costo dei round di dibattito, latenza di coordinamento, delta di rendimento netto multi-agente | il dibattito non è aggregazione di esperti indipendenti |

**Applicabilità a scaglioni** (Tabella 2 del paper): più forte è la rivendicazione, più
protocolli servono. "Prototipo/backtest storico" richiede P1+P2+P5 e vieta il linguaggio
di deployment; "alpha deployabile" richiede P1–P5; "capacità di trading autonoma" richiede
P1–P6.

> **Avvertenza del paper stesso**: superare P1–P6 **non implica** deployabilità reale.
> Sono uno screening minimo, non una certificazione. Restano aperti rischio operativo,
> governance del modello, routing degli ordini, capacità, comportamento in coda,
> impatto di mercato avversariale.

### 3.3 — Numeri misurati (riproduzione degli autori)

Riproduzione a **1 anno** (2025-01 → 2026-01), 5 ticker equipesati (TSLA/NVDA/KO/XOM/MSTR),
capitale iniziale $100K. Il "netto" addebita commissioni, **costo dei token**, spread e
impatto di mercato.

| sistema | Sharpe portafoglio lordo → netto | esito |
|---|---|---|
| TradingAgents | 0,43 → **0,22** | sotto il buy-and-hold |
| QuantAgent | −0,96 → **−1,15** | sotto il buy-and-hold |

- Aggregato: buy-and-hold chiude a $104,8K; TradingAgents $106,4K lordo / **$102,3K netto**;
  QuantAgent $81,4K lordo / **$77,9K netto**.
- Il buy-and-hold **netto batte entrambi gli agenti su 4 ticker su 5** (unica eccezione
  MSTR, dove il B&H stesso ha fatto −48%).
- Su TSLA: rendimento cumulato **−2,01% lordo → −10,17% netto**.
- Su 5 sistemi × 8 componenti di costo, **35 celle su 40 non sono modellate affatto**.
  Solo le commissioni sono modellate da tutti e cinque.

### 3.4 — Parametric Prior Lock-in (PPL) — il reperto centrale per noi

Definizione: prima di qualunque input in tempo reale, i pesi del modello contengono già
tilt stabili di settore, dimensione, stile o narrativa; questi tilt formano la
raccomandazione finale ma — a differenza delle esposizioni fattoriali tradizionali — non
sono dichiarati, misurati né vincolati dal rischio.

Evidenza riportata (appendice D, su Lee et al. arXiv:2507.20957, ICAIF 2025):

1. Anche di fronte a evidenza contraria esplicita, i modelli restano attaccati ai propri
   tilt: i tassi di inversione restano bassi e la confidenza auto-dichiarata **non si
   contrae in proporzione**.
2. **Modelli dello stesso ecosistema, corpus di pretraining o paradigma di allineamento
   mostrano preferenze di settore e tema fortemente convergenti** — il prior è condiviso
   tra quelli che verrebbero altrimenti trattati come agenti "indipendenti".
3. **Prompt di persona, voto multi-modello e dibattito multi-agente producono differenze
   retoriche di superficie ma non rimuovono il prior omogeneo sottostante.** L'accordo
   multi-agente è quindi un cattivo surrogato dell'accordo tra esperti indipendenti.

Ancoraggi quantitativi: al 60% di evidenza contraria, il modello con prior più forte
(Llama4-Scout) inverte la propria view in ~8% dei casi, GPT-4.1 (il meno distorto) in ~30%
— un divario di 3,8× che cresce monotonicamente col punteggio di bias settoriale del modello.

**Corrispondenza con un principio già di casa**: *"i segnali correlati non si sommano"*
(trattare comportamento correlato come conferma indipendente gonfia la forza probatoria
fino a due ordini di grandezza). PPL ne è il meccanismo, con un nome e dei numeri.

**Conseguenza diretta**: cinque ruoli costruiti tutti su Fable 5 non sono cinque teste.
Sono lo stesso prior con cinque cappelli. Una company di agenti su singolo backbone
aggrega errori correlati e li presenta come consenso.

### 3.5 — Tensione tra AMA e PPL (da tenere, non da risolvere)

AMA dice che la persona sposta **molto** il comportamento. PPL dice che la persona **non**
rimuove il prior. Possono essere vere entrambe: **divergenza di superficie alta,
indipendenza vera bassa.**

È esattamente la distinzione su cui è costruito **Gate Concordia** (l'accordo è
non-informazione, il disaccordo è l'unico segnale azionabile). Il reperto la rafforza.

### 3.6 — Il reperto che riscatta i "ruoli" (nota su QuantAgent)

QuantAgent è l'unico sistema che sembrerebbe contraddire la tesi del paper (Sharpe
dichiarato 1,76–2,02 su strumenti HFT). Gli autori lo riclassificano come **già vicino alla
soluzione modulare**: l'architettura è per lo più modulare, con l'LLM che emette
ragionamento strutturato sui ruoli Indicatore/Pattern/Trend/Rischio, mentre **esecuzione e
stop-loss a 5 bp sono componenti fuori dall'LLM**.

**Cioè: i "ruoli" non sono agenti separati. Sono campi di un output strutturato di un
cervello solo.** Restano aperti su QuantAgent i gap P1 (dichiarazione del cutoff) e P5
(netto a frizioni piene).

### 3.7 — L'alternativa modulare raccomandata dal paper

L'LLM entra come **interfaccia informativa auditabile a monte** di moduli indipendenti di
calibrazione, rischio ed esecuzione — mai come autorità decisionale finale.

| stadio | proprietario | ruolo ragionevole dell'LLM | oggetto di audit |
|---|---|---|---|
| 1. Estrazione informazione | LLM, vincolato a schema | estrarre proposizioni strutturate da news, filing, call | span sorgente, ora di pubblicazione, ora di retrieval, etichette entità/evento |
| 2. Costruzione feature | modulo quant | fornisce input strutturati candidati, **non fissa i pesi** | tabella feature point-in-time, gestione dei mancanti, normalizzazione |
| 3. Sintesi del segnale | modello quant | **una tra molte fonti** di informazione | ablazione e contributo marginale delle feature da LLM |
| 4. Calibrazione della probabilità | modulo statistico indipendente | **non fornisce probabilità di trading auto-valutate** | ECE, curve di affidabilità, calibrazione condizionata al regime, stabilità out-of-sample |
| 5. Sizing e controllo del rischio | moduli di portafoglio e rischio | **spiega le fonti di rischio, non determina la size** | esposizioni fattoriali e settoriali, leva, drawdown, vincoli di liquidità |
| 6. Esecuzione e audit | sistema di esecuzione | osservatore o sintetizzatore | log ordini, prezzi di riempimento, slippage, latenza, ordini falliti, stop di rischio |

---

## §4 — DOVE SI COLLOCA TRADERLAB OGGI (mappatura onesta)

| stadio | traderLab in S0 | conforme? |
|---|---|---|
| 1. Estrazione | **Tool Server deterministico**, snapshot point-in-time congelato, zero testo | conforme, anzi più stretto (il paper prevede l'LLM qui; noi non abbiamo testo del tutto) |
| 2–3. Feature e sintesi | **è l'LLM a sintetizzare**: legge lo snapshot e produce la direzione | **NON conforme — ed è il punto** |
| 4. Calibrazione | nessuna. La confidence è **loggata per il Brier** e non guida nulla | conforme per omissione |
| 5. Sizing e rischio | **D3: size fissa**. Risk Officer = codice puro, può solo ridurre. Guardrail nel tool, mai nel prompt | conforme |
| 6. Esecuzione e audit | ShadowFill a costi reali Hyperliquid, ledger append-only con hash-chain, telemetria comportamentale | conforme |

**Sulla non-conformità agli stadi 2–3**: è deliberata e dichiarata. Il Lab esiste per
misurare *se* un LLM al posto del modello quant produce qualcosa. È l'imputato, non il
sistema di produzione. Il valore atteso dichiarato (10–20% di probabilità che batta la
gamba meccanica post-costi) è già scritto nella sintesi di design.

**Cosa il programma ha che nessuno dei sistemi in letteratura ha**: metro del rumore
inter-repliche, ancoraggio OTS su Bitcoin, ledger con hash-chain, kill-criteria
pre-registrati, valutazione forward-only post-cutoff per costruzione, gate meccanici
identici a quelli di ogni strategia, e **zero verdetti spesi** (holdout 0/2).

**Cosa il programma NON ha**: risultati. Tre giorni di S0. Essere metodologicamente più
puliti con n=3 non è "il meglio del meglio" — è "l'unico onesto, finora, senza niente
ancora da mostrare".

---

## §5 — PUNTO 1 DELL'OWNER: dove la Stagione 1 romperebbe il confine

### 5.1 — Il piano attuale di S1 (dalla sintesi di design, §7)

> *"Stagione 1 (90 giorni): track record vero, **sizing libero ma clampato** (qui si
> riaggancia il **meta-labeling sulla confidence calibrata**), confronto appaiato
> quotidiano, verdetti solo a fine finestra."*

Sono **due mosse insieme**:
- (a) il sizing smette di essere fisso → l'output dell'agente determina la size;
- (b) l'aggancio è il campo `confidence` → la confidenza **auto-dichiarata** dell'LLM
  diventa l'input del sizing.

La (b) è testualmente il modo di fallimento del **P4**.

### 5.2 — Perché nel nostro caso specifico è peggio

Reperto empirico di casa, giorno 1 di S0 (16/08): **sei decisioni, confidence esattamente
0,55 su tutte**, dispersione 0,0167. Confidenza degenere.

Due scenari, entrambi cattivi se si sizea sulla confidence dichiarata:
1. **La degenerazione persiste** → si sizea su una costante. È size fissa con passaggi in
   più, ma con la pretesa dichiarata di portare informazione.
2. **La degenerazione si rompe in S1** → si sizea su una variabile la cui calibrazione non
   è mai stata misurata fuori campione.

### 5.3 — La distinzione che salva il disegno

**Non è "niente sizing in S1".** Il meta-labeling nella forma corretta — quella del dossier
di casa `Meta-labeling__Probability_Calibration_and_Position_Sizing` — è un modello
**separato** che stima P(profitto) dal segnale primario più altre feature, e la size è
funzione di quella probabilità calibrata su esiti realizzati.

| forma | descrizione | confine |
|---|---|---|
| **ROMPE** | `size = f(confidence_dichiarata)` | l'LLM possiede lo stadio 4 |
| **REGGE** | `size = f(p̂)`, dove `p̂` viene da un modulo statistico indipendente e `confidence_dichiarata` è **una feature tra le altre**, ammessa solo se il suo contributo marginale è misurato per ablazione | lo stadio 4 è di proprietà del codice |

La parola che fa la differenza è **separato**. La confidence non tocca mai la size
direttamente: entra al più come feature che si è guadagnata il posto.

### 5.4 — Decisione candidata, da dichiarare PRIMA della fine di S0

**Non si può calibrare ciò che non ha dispersione.** Se S0 chiude con la confidence ancora
degenere, il meta-layer non ha nulla su cui adattarsi su quell'asse, e il disegno onesto di
S1 è size fissa (o sizing da sole feature meccaniche).

Questa regola va scritta **prima** di vedere i dati finali di S0, altrimenti la scelta è
contaminata dal sapere com'è andata — stesso identico vizio della voce 1.1 di `CODA.md`
(lettura del §5 di PREREG_LAB_S0).

**Formulazione proposta per la firma dell'owner (D-LAB-S1-CONF):**

> Il campo `confidence` del Decision Record non determina in alcun caso la dimensione
> della posizione. Può entrare in un modulo di calibrazione **separato** come feature fra
> le altre, e solo se il suo contributo marginale è misurato per ablazione. Precondizione
> per qualunque uso in sizing: **ECE out-of-sample e curve di affidabilità misurate sui
> dati di S0**, con soglia dichiarata prima di guardarli. Se a fine S0 la dispersione della
> confidence resta sotto [soglia da fissare dall'owner], la Stagione 1 parte a **size
> fissa** e il meta-labeling sulla confidence è rinviato.

**Nota**: S0 sta già raccogliendo il materiale per decidere. Il Brier è loggato dal giorno 1;
l'ECE è una decomposizione degli stessi dati. Non serve raccogliere nulla di nuovo.

---

## §6 — IDEA #13 (REGISTRATA, NON COSTRUITA)

**Nome**: Pre-Screen di Fertilità per architetture d'agente.
**Trigger**: chiusura di Stagione 0 **e** suite di 10–15 snapshot congelata.
**Stato**: registrata. Nessun codice, nessun repo, nessun prompt CLI.

**Principio**: si applica alle architetture lo stesso attrezzo già inventato in casa per le
strategie (Space Fertility Pre-Screen). Rigioco offline su snapshot già congelati e
persistiti — stesso mondo, stesso istante, stessi numeri — quindi **confronto appaiato a
input identici**, la forma con più potenza disponibile.

**Bracci proposti** (numero dichiarato prima, piccolo, ognuno conta come trial nel DSR):

| braccio | cosa varia | costo inferenza |
|---|---|---|
| **A** — liscio | baseline attuale, 1 passata | 1× |
| **B** — self-consistency | nulla, solo k=5 campioni + voto | ~5× |
| **C** — ruoli come campi del verbale | struttura dell'output (pattern QuantAgent, §3.6) | ~1× |
| **D** — persona alternativa | context file (asse dominante secondo AMA) | ~1× |

**Il multi-agente vero (5 chiamate) resta fuori**, perché il P6 chiede di misurare *prima*
similarità dei ruoli e tasso di disaccordo, e il PPL predice che su un solo backbone quei
numeri saranno pessimi. Se lo si volesse davvero, servirebbero backbone eterogenei → rompe
il FreezeManifest e il modello di costo.

**Metrica: NON il P&L.** Con n≈15 snapshot il P&L non ha potenza. La metrica è **divergenza
decisionale a mondo identico**: l'architettura cambia l'azione, e di quanto rispetto alla
dispersione inter-repliche già misurata?

**Kill gate dichiarato prima**: se la divergenza dei bracci B/C/D non supera la dispersione
inter-repliche, la domanda si chiude gratis. Non "il multi-agente è peggio" — bensì *"la
variazione architetturale non produce una decisione distinguibile dal rumore di un singolo
cervello"*. Risultato negativo, pubblicabile.

**Cautela su C**: aggiungere struttura è format tax documentata (Tam et al., EMNLP 2024
Industry Track — fino a ~27 punti di degrado sotto vincolo di formato), mitigabile con
scratchpad libero prima e struttura dopo, che è già lo schema del Decision Record v1.

**Vincoli di igiene**: sola lettura su snapshot già persistiti; cartella esplorativa
etichettata; repo separato o percorso fuori dai path di verdetto; regola 10 rispettata
(niente codice nuovo nei percorsi di verdetto post-freeze).

---

## §7 — LA SUPERFICIE DI OVERFITTING NUOVA (avvertenza)

Se l'architettura è il driver dominante, l'architettura è anche la **nuova superficie di
overfitting**. Il paper elenca i gradi di libertà che gli LLM aggiungono al quant
tradizionale: versioni del modello, temperatura, system prompt, esempi few-shot, corpus
RAG, lunghezza della memoria, persona degli agenti, round di dibattito, regole di parsing
dell'output, strategie di tool-call. E cita Novy-Marx & Velikov (NBER WP 33363) sull'HARKing
industrializzato a partire da oltre 30.000 segnali candidati.

Il programma conosce quel film: **33.818 strategie morte**. Ma quel cimitero è un *asset*
perché è nato sotto protocollo dichiarato — è una distribuzione nulla empirica. Una ricerca
di architetture non dichiarata produrrebbe venti cadaveri: **troppo pochi per essere una
nulla, troppi per essere un test pulito.** Il peggio dei due mondi.

Da cui: numero di bracci dichiarato prima, piccolo, e conteggio dei trial nel DSR.

---

## §8 — COSA NON È STATO DECISO

Nessuna decisione è stata presa in questa sessione. In particolare **non** sono stati decisi:

1. se costruire una company di agenti (Idea #13 è **registrata**, non approvata);
2. la formulazione D-LAB-S1-CONF del §5.4 (è una **proposta**, con una soglia lasciata in
   bianco per l'owner);
3. se e quando caricare *The Alpha Illusion* fra i reperti di casa;
4. qualunque modifica a S0, al prompt, ai context file, al FreezeManifest.

**Restano prioritari e invariati** (da `CODA.md`, 17/08):
- verdetto costo giornata 3 di S0 (prossimo passo dichiarato);
- cinque firme pronte su sei (§1.4, §3.1, §3.2, §3.4, §6 dell'addendum sera 17/08);
- la domanda che blocca il PREREG_CARRY: **la finestra di legging è un costo strutturale
  ricorrente, sì o no?** (A′ 13,72 bps vs B′ 18,74 bps);
- le tre voci con scadenza pre-fine-S0 (lettura del §5, riga TL-004, limite di spesa Console);
- holdout **0/2**, intoccabile.

---

## §9 — RIFERIMENTI (per la chat ricevente)

| id | titolo | nota |
|---|---|---|
| arXiv:2510.11695 | *When Agents Trade: Live Multi-Market Trading Benchmark for LLM Agents* (Qian et al., WWW 2026) | **verificato alla fonte**. AMA. 4 agenti tutti a cervello singolo × 5 backbone |
| arXiv:2605.16895 | *The Alpha Illusion* (Ye, Han et al., 16/05/2026) | **reperto nuovo**, non nei file di casa. P1–P6, riproduzione a 1 anno, PPL |
| arXiv:2507.20957 | Lee et al., *Your AI, Not Your View* (ICAIF 2025) | base empirica del PPL |
| arXiv:2502.08788 | Zhang et al., *Stop Overvaluing Multi-Agent Debate* | dibattito vince <20% su 36 configurazioni; aggiungere round o agenti non migliora |
| arXiv:2510.02209 | StockBench (Chen et al.) | già nei file di casa |
| arXiv:2510.07920 | Profit Mirage (Li et al.) | già nei file di casa |
| arXiv:2408.02442 | Tam et al., *Let Me Speak Freely?* (EMNLP 2024) | format tax, già nei file di casa |
| NBER WP 33363 | Novy-Marx & Velikov, *AI-Powered (Finance) Scholarship* | HARKing industrializzato |

**Verifica esterna 18/08**: nof1.ai mostra ancora la Season 1.5 (equity, chiusa il
03/12/2025). **Nessuna Season 2** pubblicata. nof1 ha in roadmap sistemi multi-agente che
collaborano o competono su portafogli condivisi — cioè **non l'hanno ancora fatto**,
nonostante $15M raccolti a maggio 2026. Il buco sperimentale è reale.

---

## §10 — PROTOCOLLO DI VERIFICA PER UNA CHAT NUOVA

Prima di procedere su questa materia, recitare:
1. **§1** (annotazione di errore del consigliere) — perché spiega *come* si è arrivati qui;
2. **§4** (mappatura onesta: dove traderLab è conforme e dove no, e perché la
   non-conformità agli stadi 2–3 è deliberata);
3. **§8** (cosa NON è stato deciso).

E tenere fermo: questo documento **non modifica la fase, non apre riti, non autorizza
commit**. Idea #13 è registrata con trigger, non costruita. La proposta D-LAB-S1-CONF
attende la firma dell'owner e una soglia numerica che solo lui può fissare.

---

*Ogni firma è dell'owner. Il consigliere propone, calcola, avverte, filtra — non firma mai.*

**Firma owner (D-LAB-S1-CONF, §5.4)**: ______________________  data: ____________

**Firma owner (registrazione Idea #13, §6)**: ______________________  data: ____________
