# PREREG_LAB_S0_RUN2 — Pre-registrazione della stagione RUN2 del Trader Lab

> **STATO: CONTENUTI FIRMATI. NON ANCORA COMMITTATA, NON CONGELATA.**
>
> Prodotta dal rito T3 del 2026-08-20 e chiusa dal rito T3-BIS dello stesso
> giorno, che ha trascritto le dieci firme dell'owner (**F1…F10**, §14).
> Nessuna riga di questo documento autorizza un'esecuzione, e finché non è
> committata nessuna misura qui dichiarata è pre-registrata: un documento di
> pre-registrazione vale per la data in cui è stato congelato, non per quella
> in cui è stato scritto.
>
> Nel testo **non resta nessun `[DA-FIRMARE]`**. L'unico segnaposto legittimo
> è `rito_config.prereg_ref.commit` nel Freeze manifest, che solo il rito del
> pin può valorizzare (firma **F10**). Il §14 non elenca più punti aperti: è
> il **registro delle firme**.
>
> **Questo documento non riscrive `docs/PREREG_LAB_S0.md`.** Quello resta
> congelato al commit `9ef5681`, timbrato OpenTimestamps, e si **cita** —
> TL-007 lo pretende esplicitamente. Il RUN2 è una **stagione nuova con un
> modello nuovo**, non la prosecuzione della Stagione 0.

**Data della bozza**: 2026-08-20 (rito T3) · **Firme trascritte**:
2026-08-20 (rito T3-BIS) · **Repo**: `traderLab` · **Commit di
riferimento**: `a924da0`

---

## §0 — Che cos'è il RUN2, e da dove viene ogni riga di questo documento

### 0.1 Natura

Il RUN2 è **shadow**: nessun ordine reale, nessun capitale, nessuna chiave di
wallet. Misura il comportamento di tre repliche identiche di un modello pinnato
su snapshot congelati, e contabilizza l'esecuzione ai costi reali di
Hyperliquid senza eseguirla.

Il RUN2 **non misura skill**. Nessun P&L viene giudicato, nessuna promozione
del Trader può derivarne, nessun confronto con una gamba meccanica esiste
(quello è materia della Stagione 1 e della sua pre-registrazione).

### 0.2 Le fonti, in ordine di autorità

Questo documento non contiene decisioni proprie salvo dove lo dice. L'ordine di
autorità è quello del rito che l'ha prodotto:

| # | Fonte | Natura | Dove sta |
| --- | --- | --- | --- |
| 1 | **Verbale RUN2**, §A.1-A.19 | decisioni dell'owner, sessione 17-19/08/2026 | `docs/2026-08-19_VERBALE_DECISIONI_RUN2.md`, committato |
| 2 | **Ratifiche R-A…R-D** dell'owner del 20/08/2026 | decisioni dell'owner, per delega, trascritte dal prompt del rito T3 | trascritte qui, §0.4 |
| 2-bis | **Firme F1…F10** dell'owner del 20/08/2026 | decisioni dell'owner, per delega, trascritte dal prompt del rito T3-BIS | trascritte qui, §14, e incise nelle sezioni che governano |
| 3 | **Foglio delle decisioni di `zeroPipes`**, punti 12-18 | decisioni dell'owner | **`zeroPipes/docs/program/2026-08-19_VERBALE_FOGLIO_DECISIONI.md`**, righe 65-71 — trascritti al **§0.6** dalla firma **F1** |
| 4 | **Referto T1** del 20/08, §4 | classificazione delle variabili introdotte | `T1_RIPARAZIONI_REPORT.md`, **gitignorato** — trascritto per esteso al §4 |
| 5 | **Evidenza T2** del 20/08 | preventivo vincolante, listino, sonda `budget_tokens` | `docs/research/results/2026-08-20_PREREG-EVIDENCE_PREVENTIVO_RUN2.md`, committato |
| 6 | **Ricerca sull'accordo inter-replica** del 20/08 | letteratura, scelta dei test, cautele | `docs/research/2026-08-20_RICERCA_ACCORDO_REPLICHE_LITERATURE.md`, committato |
| 7 | **`scripts/run2_power.py`** | derivazioni di potenza, eseguito il 20/08 | committato con questa bozza |

Le fonti 1, 5, 6 e 7 sopravvivono a un clone pulito. La 4 **no**: i referti
sono gitignorati (`.gitignore`, regola `*_REPORT.md`). Per questo la lista
onesta del §4 è trascritta **per esteso** invece che rimandata — la convenzione
delle evidenze di `CLAUDE.md` lo impone.

Le fonti 2, 2-bis e 3 sopravvivono **solo in quanto trascritte qui**: le prime
due sono decisioni pronunciate in sessione, la terza vive in un altro repo che
questo non legge. È esattamente la ragione per cui si trascrivono per esteso
invece di rimandarle.

### 0.3 Cosa questo documento cambia rispetto al verbale

Il verbale **registra**; questo documento **dichiara prima**. Tre punti in cui
la bozza non si limita a trascrivere:

1. **§A.3 «una variabile sola» è riscritta ai fatti** (§4.4). Non è più vera
   alla lettera, e la frase va allineata invece che difesa.
2. **Il gate §7(ii) è ridefinito** sul conteggio nuovo dei malformati veri
   (§5.3), che non è confrontabile con quello di Stagione 0.
3. **Tre numeri del verbale hanno ora una derivazione** (§3.2, §9.4): il §F del
   verbale li elencava fra le affermazioni non verificate. Uno dei tre — i
   «3,0 sigma» del §A.10 — **non si riproduce nel caso peggiore** e la bozza lo
   dice.

### 0.4 Le ratifiche dell'owner del 20/08/2026 (R-A…R-D)

Trascritte dal prompt del rito T3, per delega. Sono decisioni, non proposte.

- **R-A — soglia della regola candidata 51.** L'ECE si marca **NON
  INTERPRETABILE** se `SD(confidence) < 0,05` **oppure** se i valori distinti
  di confidence sono **meno di 3**. Chiude il bianco lasciato dal §A.14.
- **R-B — collocazione del RUN2 nel budget di programma.** Il RUN2 è la
  **stagione 1 di 2** del budget di classe «agente LLM discrezionale», portata
  a verdetto. Il **tier del modello è annotato**: `claude-opus-5`, **non di
  punta**. **Clausola 18-B**: un esito negativo è **AMBIGUO DICHIARATO** —
  soffitto del modello e soffitto del concetto non sono distinguibili con
  questo disegno. Per il punto 26 del foglio: se il RUN2 è negativo, la
  stagione 2 gira sul **modello di punta**.
- **R-C — disegno del gate A.9.** Vedi §1.3 per intero: `p_accordo` è
  **categoriale a 3 livelli**, k=3 confermato, test primario di
  **permutazione** eseguito **due volte**, Fisher esatto r×c come supporto,
  **mai KS** su dati discreti, ponte k=30→k=3 per sottocampionamento esatto, e
  le **cinque cautele** della ricerca entrano nella lista onesta.
- **R-D — preventivo.** I valori dell'evidenza T2 ($89,90 · 28 giornate ·
  listino) si **citano** in questo documento; entrano nel Freeze manifest
  **solo al rito del pin**, per firma dell'owner. L'importo è stato poi firmato
  il 20/08 (**F5**, §8.3): R-D governa da qui in avanti solo il **momento** in
  cui il numero entra nel manifest, non più quale sia.

### 0.5 La lacuna dei punti 12-18 del foglio di `zeroPipes`, e la sua chiusura

Il rito T3 chiedeva di trascrivere i punti 12-18 del foglio delle decisioni del
19/08 «per trascrizione di sessione, dichiarata», e **non poté farlo**. La
ragione va detta invece che aggirata, e resta valida anche adesso che il §0.6
li contiene:

- il foglio vive in `zeroPipes/docs/program/2026-08-19_VERBALE_FOGLIO_DECISIONI.md`.
  `CLAUDE.md` stabilisce che questo repo **non duplica** i documenti di
  programma, **li punta**, e che quando serve citarli «si cita il percorso in
  `zeroPipes`, non un estratto ricopiato qui»;
- la regola **4** del programma vuole un repo e un rito alla volta, e il §C del
  verbale RUN2 registra già `zeroPipes` come **non ispezionabile** dai riti di
  questo repo;
- la chat che ha prodotto questa bozza è stata aperta con `/clear` (regola 3) e
  **non possiede il contenuto di quella sessione**. Ricostruirlo a memoria
  violerebbe la regola 46.

**L'unico punto del foglio attestato dentro `traderLab`** è il **punto 15** —
l'etichetta onesta della profondità — perché il referto T1 §4 e il referto T2
§5 lo citano e ne mostrano il codice. È trascritto alle voci **C1** e **C2**
del §4.

**Lacuna chiusa il 2026-08-20**, dalla firma **F1** dell'owner. I punti 12,
13, 14, 16, 17 e 18 sono stati forniti come **trascrizione di sessione** e sono
trascritti al **§0.6**, con la loro fonte
(`zeroPipes/docs/program/2026-08-19_VERBALE_FOGLIO_DECISIONI.md`, righe 65-71).

Resta vero tutto ciò che sta sopra: **questo repo non ha letto quel file**. La
trascrizione vale per l'attestazione dell'owner, non per un confronto di byte,
e in caso di divergenza fra le due **vale il foglio** — la divergenza si
segnala, come pretende la regola del programma. Il §15, voce 1, lo dichiara.

### 0.6 I punti 12-18 del foglio di `zeroPipes`, trascritti (firma F1)

Fonte: **`zeroPipes/docs/program/2026-08-19_VERBALE_FOGLIO_DECISIONI.md`, righe
65-71**, per **trascrizione di sessione fornita dall'owner il 2026-08-20**. Il
punto **15** non compare in questa tabella perché è l'unico già attestato dentro
`traderLab`: sta alle voci **C1** e **C2** del §4.3.

| # | Decisione del foglio | Dove vive in questo documento |
| --- | --- | --- |
| **12** | **Lista onesta delle variabili — SÌ**: il PREREG elenca ciò che cambia e ciò che resta, con la tensione **§A.3 contro §B.3** dichiarata | §4 per intero; §4.4 per la tensione |
| **13** | **Denaro pre-registrato — SÌ**: preventivo vincolante ottenuto con `count_tokens`, clausola di arresto economica, sede dei costi **`SPESE.md`** (in `zeroPipes`, creata al PASSO 5 del rito del 19/08) | §8; §8.1 per le due guardie |
| **14** | **Tetto del livello P = 850 USD, duro**, inciso in `SPESE.md`. Recepisce **D4**: 600 USD era il **fondo** della forchetta, prodotto da una macchina che ha **sottostimato tre volte su tre** | §8.7 |
| **16** | **Cap di calendario 42 giorni**, più **clausola di estensione pre-registrata** a `min(49 giorni; 2026-10-24)`. Il secondo termine recepisce **R5**: l'estensione **non attraversa il cambio d'ora** | §7; §7.1 |
| **17** | **Script di potenza committato col PREREG**: senza script eseguibile niente freeze; ingressi **marcati per provenienza**; include la **simulazione dei pavimenti 0,70 / 0,50 a k=5** | `scripts/run2_power.py`; §3.2, §9.4 |
| **18** | **B — esito ambiguo dichiarato.** Recepisce **D5**: ridefinire la domanda in «Opus-class» l'avrebbe risposta **cambiandola** | §10, clausola 18-B |

**Che cosa cambia in questo documento per effetto della trascrizione.** Niente
dei punti 12, 13, 16, 17 e 18 contraddice il testo già scritto: il §4, il §8, il
§7 e il §10 li eseguivano già, e la trascrizione li àncora a una **decisione**
invece che a una scelta di rito. Il punto **14** invece aggiunge un vincolo che
questa bozza non aveva — il **tetto di livello P** — e il §8.7 lo dichiara qui,
perché nessuna guardia di questo repo lo legge.

---

## §1 — La domanda della stagione e il gate A.9

### 1.1 La domanda

Il RUN2 fa una domanda sola, e la fa in una forma che **non richiede esiti di
mercato**:

> **La distribuzione di `p_accordo` sui mondi reali si distingue da quella
> delle sonde sintetiche?**

Se **no**, `p_accordo` è **morto come oggetto di sizing** e la stagione si
chiude con un numero invece che con un rinvio (§A.9).

La domanda che il RUN2 **non** fa è la calibrazione di `p_accordo`: richiede
**≥ 125 mondi con esito** (5 bin × 25) e non è raggiungibile in una stagione
(§A.9). È dichiarata **obiettivo pluri-stagionale**. Di conseguenza il RUN2 —
e la Stagione 1 dopo di esso — **partono a size fissa**.

> Il requisito «≥ 125 mondi (5 bin × 25)» è trascritto dal verbale §A.8-A.9.
> Il §F del verbale, punto 6, dichiara che **non ha una fonte su disco**.
> Questa bozza non lo deriva e non lo contesta: lo riporta con la sua
> provenienza.

### 1.2 `p_accordo`, definito

Per ogni **coppia giornata-asset** con tutte e tre le repliche valide,
`p_accordo` è la **categoria** in cui cadono le tre azioni:

| Categoria | Significato |
| --- | --- |
| `unanime` | le tre repliche hanno scelto la stessa azione |
| `maggioranza` | due su tre concordano |
| `tutti_diversi` | tre azioni distinte |

**È una variabile categoriale a tre livelli, non una proporzione continua**
(R-C). Con k=3 e tre azioni possibili la quota di accordo può valere solo
`{1/3, 2/3, 1}`, e la ricerca del 20/08 è netta: k=3 «è difendibile *solo* come
misura categoriale aggregata, non come stima fine di proporzione per
giornata-asset». Trattarla come continua produrrebbe intervalli di confidenza
larghissimi camuffati da numeri precisi.

### 1.3 Il disegno statistico del gate (R-C, integrale)

**k della stagione = 3 repliche. CONFERMATO**, per comparabilità con la
Stagione 0. La ricerca raccomanda di considerare k=5; la ratifica R-C sceglie
la comparabilità, e il prezzo di questa scelta è dichiarato al §12, cautela 6.

**k delle sonde = 30.** Giustificato dalla letteratura: cade nella regione di
saturazione della self-consistency (grosso del guadagno a k=5-10, plateau
attorno a k=40) e dà intervalli di Wilson stretti.

**Test primario: permutazione a due campioni.**

- **Statistica dichiarata**: **distanza in variazione totale** fra le due
  distribuzioni empiriche delle tre categorie,
  `T = ½ · Σ_i |a_i/n₁ − b_i/n₂|`.
- **Permutazioni**: **≥ 10.000**. `scripts/run2_power.py` calcola il p-value al
  suo **limite esatto** per enumerazione completa delle tabelle
  ipergeometriche multivariate — che è lo stesso test, senza errore Monte
  Carlo. Le 10.000 restano il **pavimento dichiarato** per chi ripeta il
  calcolo per campionamento.
- **α = 0,05.**
- **Eseguito DUE volte**: `reale vs sonda nulla` e `reale vs sonda cieca`.
  Entrambi si eseguono sempre; **quale dei due decide** lo dice la regola qui
  sotto.

**Regola di decisione — LETTURA DEBOLE, firmata (F2, owner, 2026-08-20)**:

> `p_accordo` **sopravvive** se la distribuzione dei mondi reali è
> **distinguibile dalla sola sonda nulla**: test di **permutazione**,
> statistica di **variazione totale**, **α = 0,05**, **n_sonda = 450** (la
> lettura conservativa dichiarata sotto), **≥ 10.000 permutazioni** oppure
> enumerazione completa al limite esatto. Un solo confronto decide la
> sopravvivenza, ed è questo.

**Il confronto con la sonda cieca resta OBBLIGATORIO** e pre-registrato — ma
come **diagnostica**, non come condizione di morte. Si esegue sempre, si
riporta sempre, e si riporta **con la potenza della cella** (tabelle del §9.5,
marginale e congiunta). Da solo non può uccidere `p_accordo`.

**Il motivo, inciso.** Nella cella più verosimile — stagione come quella
osservata in S0, sonda cieca con prior forte — la potenza **congiunta** vale
**0,44** (§9.5). Sotto la lettura forte il gate fallirebbe più di una volta su
due **anche se `p_accordo` fosse informativo**, e un non-rigetto sottopotenziato
**non è evidenza di assenza**: è il principio di futilità. Si aggiunge che il
prior della sonda cieca **è a sua volta un esito empirico** — non è noto prima
di eseguirla — e far dipendere la morte di una misura da un parametro che si
scoprirà dopo significa scrivere il gate a metà.

**Lettura forte: alternativa scartata, col suo motivo.** La lettura forte
chiedeva che **entrambi** i confronti rigettassero, e la sua giustificazione era
buona: le due sonde delimitano una banda, e un accordo indistinguibile dal
soffitto è saturo e privo di potere discriminante — il regime che Ding
(arXiv:2607.08065) documenta sul modello frontier, dove l'accordo ≥ 0,8
accompagna una risposta sbagliata il 48% delle volte. È scartata **per
potenza**, non perché dicesse una cosa falsa: questo disegno non ne ha
abbastanza per sostenerla. Ciò che la lettura forte voleva intercettare — la
saturazione — **si riporta lo stesso**, dalla diagnostica cieca e dalla cautela
7 del §12.2.

**Che potenza ha il gate così com'è firmato.** È la potenza **marginale contro
la sonda nulla** del §9.5: fra **0,918 e 1,000** in cinque scenari su sei contro
la nulla ideale, ma **0,212** nella cella «stagione quasi sempre unanime contro
sonda nulla rumorosa». Quel punto cieco la lettura debole **non lo ripara**: si
dichiara qui e si riporta accanto all'esito.

**Test di supporto**: **Fisher esatto r×c** sulla tabella
`gruppo × categoria-di-accordo` (2×3), con il **rapporto di verosimiglianza
(LRT) riportato accanto** — su campioni piccoli il LRT può essere più potente
di Fisher, e riportarne uno solo sarebbe una scelta fatta dopo aver visto il
risultato. **χ² non si usa** se qualche frequenza attesa è < 5.

**Test proibito**: **KS in forma standard**. È valido solo per distribuzioni
continue; con tre categorie e ties massicci i suoi p-value non significano
nulla. Se serve un test ordinale si usa Mann-Whitney **con correzione per
ties**, o meglio Brunner-Munzel, e **come supporto soltanto**.

**Ponte k=30 → k=3.** Dalle sonde a k=30 si deriva la distribuzione di
riferimento delle categorie a k=3 per **sottocampionamento esatto senza
reimmissione**: da 30 campioni con conteggi `(n_a, n_b, n_c)`,

```
P(unanime)       = Σ_a C(n_a, 3) / C(30, 3)
P(tutti diversi) = n_a · n_b · n_c / C(30, 3)
P(maggioranza)   = 1 − P(unanime) − P(tutti diversi)
```

`C(30,3) = 4.060` terne, enumerate: nessuna simulazione, nessuna
approssimazione. Il ponte è ciò che rende confrontabile una sonda a k=30 con
una stagione a k=3 **senza rifare la sonda a k=3**. Tabella al §9.3.

**Dimensione del gruppo sonda** — dichiarata, con la lettura conservativa
scelta: **n_sonda = 450**, cioè 15 mondi × 30 chiamate, il numero di chiamate
al modello **davvero indipendenti**. L'enumerazione delle 60.900 terne
(15 × 4.060) è disponibile ma **non si firma**: quelle terne sono sottoinsiemi
degli stessi 30 campioni, e trattarle come osservazioni indipendenti rende il
test **anticonservativo**. Lo script riporta entrambe per mostrare quanto la
scelta pesa.

---

## §2 — Setup congelato

| Voce | Valore | Fonte |
| --- | --- | --- |
| **Modello** | `claude-opus-5` | TL-007 |
| **Tier dichiarato** | **NON di punta** | R-B |
| **`max_tokens`** | **8.000** | §A.1 |
| **Sampling** | default dell'API **per omissione**: `temperature`, `top_p`, `top_k` **non inviati** | D4, `sampling_policy = api_default_omitted` |
| **Thinking** | parametro **non inviato** | §A.7 + sonda T2 §7 |
| **Fallback server-side** | **assente**, di proposito | `CLAUDE.md` §10 |
| **Repliche** | 3, identiche, input byte-identici, `replica_id` mai nel prompt | D1 |
| **Size** | **fissa** a rischio unitario, normalizzata dal Risk Officer | D3 + §A.9 |
| **Universo** | BTC, ETH — `pre_screen_ufficiale` | Pre-Screen C2, commit `3bc9a9c` |
| **Snapshot** | giornaliero, **00:00 UTC**, congelato; le decisioni leggono solo quello del giorno | firewall, `CLAUDE.md` §7 |
| **Persona** | `trader_v0`, invariata da S0 | §A.3 |
| **`freeze_id`** | **esclude** `context_git_sha`, **include** `pin_commit` | §A.2 |

### 2.1 `max_tokens = 8.000`: la divergenza si annota, non si ripara

Il registro (`DECISION_LOG.md`, TL-002 Decisione 1) dichiara
`DEFAULT_MAX_TOKENS` alzato a **32.000**; il codice
(`arena/config.py`) usa **8.000**, ed è il valore che la Stagione 0 ha
**effettivamente** usato. Il motivo inciso a commento: con 32.000 il modello
veniva scartato dallo shedding lato server nei picchi di carico.

Il RUN2 dichiara **8.000**. La divergenza è già formalizzata in `DECISION_LOG`
alla voce **TL-008**.

### 2.2 Il thinking non è una preferenza, è un vincolo dell'API

La sonda del rito T2 (evidenza §7, quattro chiamate reali, `request_id`
registrati) ha accertato che su `claude-opus-5`:

- `thinking={"type":"enabled","budget_tokens":400}` → **400**, «Input should be
  greater than or equal to 1024»;
- `thinking={"type":"enabled","budget_tokens":1024}` e `16000` → **400**,
  «`thinking.type.enabled` is not supported for this model»;
- controllo senza `thinking` → **200**.

Quindi `thinking_declared = always_on_param_omitted` nel Freeze manifest
**descrive un vincolo dell'API**, e il client verifica a ogni chiamata che il
payload non contenga il parametro, rifiutando se lo contiene.

`output_config.effort` — la leva sostitutiva che l'API indica — **non è
adottata**: sarebbe una variabile in più fra S0 e RUN2, e il RUN2 ne ha già
quattro classi (§4). Registrata come opzione per una stagione successiva.

---

## §3 — L'unità di conto e la potenza

### 3.1 L'unità è la coppia, non la giornata (§A.8)

**L'unità di conto è la coppia giornata-asset con tutte e tre le repliche
valide.**

Il reperto che lo impone: il **18/08/2026** è una giornata «riuscita» per il
registro operativo, ma **non produce nessuna coppia valida**, perché entrambi
gli asset hanno perso una replica (`no_tool_use` su r1 BTC, `model_refusal` su
r3 ETH). Contando in giornate quel giorno vale 1; contando in coppie vale 0.
Le coppie valide di tutta la Stagione 0 sono **4**.

| Grandezza | Valore |
| --- | --- |
| Obiettivo | **40 coppie** giornata-asset valide |
| Cap di calendario | **42 giorni** |
| Attesa a tasso di fallimento 0% | **20** giornate |
| Attesa al 5% | **23** giornate |
| Attesa all'11,1% (osservato in S0) | **28** giornate |

### 3.2 La derivazione, che prima non esisteva

Il §F del verbale, punti 4 e 5, dichiarava che il calcolo di potenza e la
derivazione di «40 coppie» **non esistevano su disco**. `scripts/run2_power.py`
li produce. Eseguito il 2026-08-20, seme `20260820`.

**Ipotesi** (§A.8): H₀ `q ≤ 0,10` contro `q = 0,25`, α = 0,05 unilaterale,
potenza richiesta 80%. Test **binomiale esatto**, coda destra sommata
direttamente — nessuna approssimazione normale.

| n | c critico | α effettiva | potenza a q=0,25 | ≥ 80% |
| ---: | ---: | ---: | ---: | :---: |
| 20 | 5 | 0,0432 | 0,5852 | no |
| 30 | 7 | 0,0258 | 0,6519 | no |
| 34 | 7 | 0,0481 | 0,7820 | no |
| 38 | 8 | 0,0318 | 0,7687 | no |
| **40** | **8** | **0,0419** | **0,8180** | **sì** |
| 42 | 9 | 0,0211 | 0,7571 | no |
| 45 | 9 | 0,0320 | 0,8275 | sì |
| 50 | 10 | 0,0245 | 0,8363 | sì |

**Il minimo n che raggiunge l'80% è esattamente 40.** Il numero del verbale non
è un arrotondamento comodo: è il minimo del disegno dichiarato.

**Regola di rigetto, esplicita**: con n = 40 si rigetta H₀ quando le coppie in
disaccordo sono **≥ 8 su 40** (= 20,0%). Potenza **0,8180**; dimensione
effettiva del test **0,0419**, non 0,05 — con dati discreti non esiste un test
esatto di dimensione esattamente α, e il test è quindi leggermente
**conservativo**.

**La potenza non è monotona in n.** Fra n=20 e n=60 la potenza **scende**
passando a n+1 in **6 casi** (per esempio n=34 → 35: da 0,782 a 0,678, perché
il valore critico salta da 7 a 8). Conseguenza operativa dichiarata: **41
coppie valgono meno di 40** (potenza 0,757).

**Regola delle coppie, firmata (F3, owner, 2026-08-20).** Se la stagione
raccoglie **più di 40** coppie valide, il test si esegue sulle **prime 40 in
ordine cronologico di completamento** — dove «completamento» è l'istante in cui
la **terza** replica di quella coppia ha prodotto un verbale valido — e le
eccedenti si riportano come **descrittive**. Il motivo è la non-monotonia: 41
coppie valgono meno di 40, e senza una regola scritta prima la scelta di quante
usarne si prenderebbe **dopo** aver visto i dati.

**Clausola sotto-40, firmata (F3).** Se a fine calendario — cap del §7 o sua
estensione — le coppie valide sono **meno di 40**, il test **si esegue all'n
raggiunto**: il valore critico viene dalla **stessa funzione dello script** che
ha prodotto il disegno a n=40 (`critical_value`), e la **potenza si riporta
accanto all'esito**, non in nota. La tabella è calcolata **ora**, prima della
raccolta, perché un valore critico scelto dopo aver visto quante coppie sono
arrivate non è un valore critico.

| n | c critico | soglia | α effettiva | potenza a q=0,25 | ≥ 80% |
| ---: | ---: | ---: | ---: | ---: | :---: |
| 30 | 7 | 23,3% | 0,0258 | 0,6519 | no |
| 31 | 7 | 22,6% | 0,0306 | 0,6883 | no |
| 32 | 7 | 21,9% | 0,0358 | 0,7221 | no |
| 33 | 7 | 21,2% | 0,0417 | 0,7533 | no |
| 34 | 7 | 20,6% | 0,0481 | 0,7820 | no |
| 35 | 8 | 22,9% | 0,0200 | 0,6777 | no |
| 36 | 8 | 22,2% | 0,0235 | 0,7103 | no |
| 37 | 8 | 21,6% | 0,0274 | 0,7406 | no |
| 38 | 8 | 21,1% | 0,0318 | 0,7687 | no |
| 39 | 8 | 20,5% | 0,0366 | 0,7945 | no |
| **40** | **8** | **20,0%** | **0,0419** | **0,8180** | **sì** |

Prodotta da `scripts/run2_power.py`, **Parte A.2**, con le stesse auto-verifiche
esatte del resto del file — massa di probabilità a 1, code calcolate nei due
versi, minimalità del valore critico, dimensione effettiva ≤ α — applicate a
**ogni** n della griglia: oltre `1e-9` di scarto lo script **aborta** invece di
stampare.

**Che cosa dice questa tabella, e va letto prima.** **Dieci righe su undici non
raggiungono l'80%**: la clausola sotto-40 produce quasi sempre un test
**sottopotenziato**, e nel punto peggiore della griglia (n = 30) la potenza vale
**0,6519**. La non-monotonia morde anche qui — **n = 34 vale più di n = 35**
(0,7820 contro 0,6777). Nessuna riga autorizza a fermare la raccolta prima del
cap: **l'obiettivo resta 40 coppie**, e la clausola serve a non lasciare la
stagione senza esito, non a renderla più facile.

**Le giornate attese si riproducono.** Una coppia è valida se tutte e tre le
repliche producono un verbale: a tasso di fallimento `f` per singolo esito la
probabilità è `(1−f)³`, e le giornate attese sono `40 / (2 · (1−f)³)`.

| tasso di fallimento | P(coppia valida) | giornate attese | verbale |
| ---: | ---: | ---: | ---: |
| 0,0000 | 1,0000 | 20,00 | 20 |
| 0,0500 | 0,8574 | **23,33** | 23 |
| 0,1111 (S0) | 0,7023 | **28,48** | 28 |

**Avvertenza dichiarata**: 28,48 è un'**attesa**, non un quantile. Metà delle
stagioni che seguono questo modello impiegherà **di più**. Il cap di 42 giorni
lascia un margine di 13,5 giornate **sulla media**, non sulla coda.

### 3.3 La stima puntuale di S0, dichiarata come tale

Delle 4 coppie valide di Stagione 0, **una sola** mostra disaccordo (16/08 BTC:
`flat` · `flat` · `short`); le altre tre sono unanimi. **1 su 4 = 0,25**, che è
esattamente l'alternativa a cui il disegno chiede potenza.

**È una stima su quattro osservazioni.** Fonda il calcolo, **non lo conferma**.
E viene da un'altra stagione con un **altro modello** (`claude-fable-5`).

---

## §4 — Le variabili: la lista onesta, classificata

Ogni differenza fra la Stagione 0 e il RUN2 è una variabile, e va dichiarata
**prima**. La classificazione è quella del referto T1 §4, qui trascritta per
esteso perché quel referto è gitignorato e non sopravvive a un clone.

### 4.1 Classe S — strumentazione (misura ciò che c'era, non cambia cosa fa l'agente)

| # | Variabile | Effetto sul comportamento del Trader |
| --- | --- | --- |
| S1 | `daily_dispersion` → `None` invece di `0,0` su intersezione vuota | **Nessuno.** Cambia cosa si legge a valle |
| S2 | `pairs_excluded_undefined` nel kill-criterion | **Nessuno.** Può cambiare un **verdetto** dove gli zeri finti abbassavano la dispersione media |
| S3 | `malformed_count` senza rifiuti né troncati | **Nessuno** sul comportamento. **Cambia il valore del gate §7(ii)**: i numeri di S0 non sono confrontabili senza ricontarli |
| S4 | `refusal_count` / `truncated_count` | Nessuno: contatori nuovi |
| S5 | `thinking_tokens` / `thinking_absent` nella telemetria | Nessuno |
| S6 | `last_known_day` ancorato anche al registro operativo | Nessuno sull'agente. Cambia **quanti** `skipped_day` compaiono in una stagione che parte male |
| S7 | Canale `ALLARME_<data>.txt` | Nessuno: fuori dal circuito decisionale |
| S8 | `ledger/spend.py` come sede unica del listino | Nessuno: nessun numero cambiato, solo spostato |
| **S9** | **Il listino esce da `ledger/spend.py` ed entra nel Freeze manifest** (TL-010, 20/08) | Nessuno sull'agente. **Cambia la spesa contata**: le costanti erano quelle di Fable ($10/$50) mentre il modello pinnato è Opus 5 ($5/$25), e le guardie contavano il **doppio**. Con il preventivo firmato (§8.3) la soglia dura sarebbe scattata al **giorno 21** invece che al 42 |
| **S10** | **`MANIFEST_S0.json` fra i `DEFAULT_OTS_TARGETS`** del controllo settimanale | Nessuno. Chiude un ancoraggio del record di S0 rimasto pending su tutti e quattro i calendar |

**S9 e S10 sono aggiunte di questa bozza**: il referto T1 elencava 8 voci di
strumentazione, il rito T3 ne ha prodotte altre due.

### 4.2 Classe P — protocollo di chiamata (cambia **come** si parla al modello)

| # | Variabile | Nota |
| --- | --- | --- |
| **P1** | **Il turno echo porta i soli `tool_use`, testo libero rimosso** (§B.3) | **La variabile più pesante del lotto.** Dal secondo turno in poi il modello **non rilegge più il proprio testo**. Effetto misurato: **8,8×** sul costo per chiamata (~$1,7809 → ~$0,2154) e percorso di raccolta dati **identico in 100 chiamate su 100** |
| **P2** | `freeze_id` senza `context_git_sha`, con `pin_commit` | Non cambia il payload. **Cambia l'identità del segmento**: nessun `freeze_id` del RUN2 sarà confrontabile con quelli di S0 |
| **P3** | `thinking_declared` nel manifest, verificato a ogni chiamata | Il payload non cambia. Esiste ora un invariante che può **rifiutare** una chiamata |
| **P4** | Il runner **carica** il manifest committato invece di ricostruirlo | Non cambia il payload. **Cambia cosa può girare**: pre-pin, niente |
| **P5** | Guardia dura sulla spesa di stagione (`1,5 ×` il preventivo) | Non cambia il payload. Può **interrompere** una stagione a metà: va dichiarato prima, non scoperto dopo |
| **P6** | Il runner pretende **sei** termini economici firmati, non due | Aggiunta di questa bozza (TL-010). Pre-pin il runner rifiuta anche se preventivo e giornate ci sono ma il **listino** manca |

### 4.3 Classe C — contenuto dello snapshot (cambia **cosa il Trader vede**)

| # | Variabile | Nota |
| --- | --- | --- |
| **C1** | `LiquidityEstimate.depth_source` | **Cambia lo `snapshot_id`** di ogni snapshot costruito da qui in avanti. Il valore numerico della profondità **non cambia** (250.000 USD). Gli snapshot di S0 su disco **non sono più caricabili** dal contratto nuovo: sono dati chiusi, ma è un fatto da dichiarare |
| **C2** | `get_costs` espone `depth_usd_1pct_declared` invece di `depth_usd_1pct_estimated` | **Cambia cosa il Trader legge**: il nome di una grandezza nel dossier dei costi. Il valore numerico **non cambia**. **Non tocca `tool_schemas_sha`** — verificato: da sola lascia `d3accf7f…8c894f`, perché lo schema di **input** di `get_costs` è invariato. A muoverlo è **C3**, che al pin lo porta a `ce844892…b0eb15` (§13.1). È contenuto, **non** protocollo |

| **C3** | **Descrizione dello schema di `get_costs`**, corretta **al rito del pin**: la profondità è una **costante dichiarata**, non una stima (firma **F9**) | **Cambia cosa il Trader legge**: la descrizione del tool sta nel contesto di ogni chiamata. Il valore numerico **non cambia**. A differenza di C2 **muove `tool_schemas_sha`**, e quindi il `freeze_id` — che al pin viene riscritto comunque. **Questa bozza non la applica**: il testo proposto sta al §13.1 |

| **C4** | **La riga 35 di `agents/trader_v0/system_prompt.md`**, corretta **al rito del pin** con la stessa sostanza di C3 (firma **F9-bis**) | **Cambia cosa il Trader legge**: quella riga sta nell'elenco degli strumenti dentro il system prompt, quindi in **ogni** chiamata di ogni replica. Il valore numerico **non cambia**. Muove **`system_prompt_sha`**, e quindi il `freeze_id`. Nasce insieme a C3 e per la sua stessa ragione: correggere una metà della formulazione lascerebbe il modello a leggerne l'altra metà, che dice il contrario |

C1 e C2 sono autorizzate dal **punto 15** del foglio di `zeroPipes` del 19/08
(§0.6); C3 dalla firma **F9** del 20/08, C4 dalla firma **F9-bis** dello stesso
giorno.

**Cosa NON è una variabile, e perché si dichiara lo stesso.** La firma F9-bis
tocca una terza sede, `contracts/vocabulary.py` riga 44, dove la descrizione di
`depth_usd_1pct` diceva anch'essa «stimata». Quella descrizione **non raggiunge
il Trader**: di `PRIMITIVE_FEATURES` il registro dei tool usa solo le **chiavi**
(`toolserver/registry.py`, `sorted(PRIMITIVE_FEATURES)`) e `arena/verbale.py`
solo i **nomi** (`FEATURE_NAMES`). Nessuno sha del pin si muove — verificato al
rito del pin, dove `tool_schemas_sha` cambia per il solo C3 e
`system_prompt_sha` per il solo C4. È igiene, non contenuto, e sta qui perché
il rito l'ha toccata.

### 4.4 §A.3 riscritta ai fatti

Il verbale §A.3 dichiara: «fra Stagione 0 e RUN2 cambia **il modello** e
**nient'altro**».

**Non è più vero alla lettera, e questa bozza lo dichiara.** Le classi di
differenza sono **quattro**:

1. **il modello** — `claude-fable-5` → `claude-opus-5` (TL-007);
2. **il protocollo di chiamata** — P1…P6, di cui P1 (il turno echo
   normalizzato) è sostanziale;
3. **il contenuto dello snapshot** — C1, C2, C3 e C4;
4. **la strumentazione** — S1…S10, che non tocca l'agente ma **cambia i numeri
   che si leggono a valle**, in particolare il gate §7(ii).

Sono **20 voci** in quattro classi. Ognuna è autorizzata: il modello da TL-007,
P1 dal §B.3, C1 e C2 dal punto 15 del foglio, C3 dalla firma F9, C4 dalla firma
F9-bis, le altre dai riti T1 e T3. Ma
l'affermazione «una variabile sola» **non descrive più questa stagione**, e
tenerla in piedi renderebbe il RUN2 un esperimento che dichiara un disegno
diverso da quello che esegue.

**Conseguenza dichiarata sulla lettura degli esiti.** Con quattro classi di
differenza, un esito del RUN2 diverso da quello di S0 **non è attribuibile al
modello**. Questa è, indipendentemente, la stessa conclusione della clausola
18-B (§10), che vi arriva da un'altra strada.

---

## §5 — Tassonomia degli esiti

### 5.1 Le sei categorie

Ogni tentativo (replica × asset × giornata) finisce in **una sola** di queste
categorie. L'elenco è chiuso e vive in `arena/verbale.py::MalformedReason`.

| Categoria | Che cos'è | Colpa di |
| --- | --- | --- |
| **valido** | verbale conforme, decisione registrata | — |
| **malformato vero** | il protocollo ha rifiutato il verbale: `wrong_tool`, `multiple_tool_use`, `no_rationale_before_structured_block`, `rationale_too_short`, `invalid_arguments`, `asset_mismatch` | il **protocollo** |
| **`no_tool_use`** | nessun blocco strutturato nella risposta. È **una sotto-categoria del malformato vero**, elencata a parte perché è il caso che in S0 fu contato due volte | il **protocollo** |
| **rifiuto del modello** | `stop_reason = "refusal"` | il **modello**, non il protocollo |
| **troncato** | `stop_reason = "max_tokens"` | il **budget di token** |
| **infrastruttura** | la chiamata non è mai arrivata a un esito: `overloaded_error` esaurita di ritentativi, timeout, giornata non partita | la **macchina** |

### 5.2 Quale contatore, quale gate

| Categoria | Contatore | Sede unica | Entra nel gate… |
| --- | --- | --- | --- |
| valido | `decisions` | `arena/runner.py` | (i) coppie valide, e ogni misura primaria |
| malformato vero (incl. `no_tool_use`) | `malformed_count` | `arena/runner.py` + `BehavioralTelemetry` | **(ii) tasso di malformati** |
| rifiuto del modello | `refusal_count` / `refusals_total` | `arena/runner.py` + `ledger/telemetry.py` | **nessuno** — si riporta, non giudica |
| troncato | `truncated_count` / `truncated_total` | idem | **nessuno** — si riporta |
| infrastruttura | `skipped_day` / `failed_decisions` | `ledger/ops_ledger.py` | (i) indirettamente, consumando calendario |

La regola che rende la tabella non ambigua è in codice, non nel prompt:
`arena/verbale.py::is_true_malformed` esclude `MODEL_REFUSAL` e `TRUNCATED` e
**nient'altro**.

### 5.3 Il gate §7(ii), ridefinito

Il §7(ii) del `PREREG_LAB_S0` diceva «tasso malformati < 5%». Con il conteggio
di Stagione 0 quel tasso includeva i rifiuti del modello: la giornata del 18/08
stampò «malformati: 2» avendo **un** malformato vero e **un** rifiuto.

**Definizione del RUN2**:

> **(ii)** `malformed_count / tentativi < 5%`, dove `malformed_count` conta i
> **soli malformati veri** e `tentativi` è il numero di terne
> (giornata, replica, asset) per cui una chiamata al modello è stata avviata.
> Rifiuti del modello e troncamenti **non entrano** né al numeratore né al
> denominatore del gate: si riportano a parte, ciascuno col proprio contatore.

**Ricalcolo dichiarato su Stagione 0**, per mostrare quanto la ridefinizione
sposta:

| Conteggio | Numeratore | Denominatore | Tasso | Gate < 5% |
| --- | ---: | ---: | ---: | :---: |
| vecchio (malformati + rifiuti) | 2 | 18 | **11,1%** | fallito |
| **nuovo (soli malformati veri)** | **1** | **18** | **5,6%** | **fallito, di misura** |

**I numeri di S0 non sono confrontabili con quelli del RUN2 senza ricontarli**,
ed è per questo che la voce S3 sta nella lista onesta.

**Avvertenza sul denominatore, dichiarata prima**: su 18 tentativi un singolo
evento vale 5,6 punti percentuali, e il gate al 5% è quindi deciso da un evento
solo. Su una stagione da 28 giornate il denominatore atteso è **168** tentativi
(28 × 3 repliche × 2 asset) e un evento vale 0,6 punti: **il gate diventa
misurabile solo alla scala della stagione intera**. Il gate si valuta
**a fine stagione, sul denominatore pieno**, mai su una finestra parziale scelta
dopo aver visto i dati.

---

## §6 — Misure, e come si riportano

Tutte dichiarate **ora**, calcolate **a fine stagione** (§A.13-A.17). Nessuna
lettura confermativa in corsa: i pannelli operativi si guardano liberamente, le
misure di questo paragrafo si leggono e si scrivono **solo a fine RUN2**.

### 6.1 Misure primarie

1. **`p_accordo`** — la variabile categoriale del §1.2 e il suo gate (§1.3).
2. **Dispersione inter-replica** — per coppia; su intersezione vuota vale
   **`None`**, mai `0,0000`, e il log scrive **`n/d`** (§A.4). Uno zero da
   intersezione vuota è indistinguibile, a valle, da un accordo perfetto.
3. **Coerenza dichiarativa** — `features_used` prodotto dalla stessa passata
   che decide (privileged access; nessun reporter separato, `CLAUDE.md` §1).
4. **Tasso di astensione** — vedi §6.3.
5. **Telemetria comportamentale** — flip rate, turnover, i tre contatori del
   §5.2, tentativi API per chiamata.
6. **Consumo** — token input/output/cache per decisione e per giornata.

### 6.2 Le quattro baseline meccaniche (§A.13)

Dichiarate ora, calcolate a fine stagione: **sempre-long**, **sempre-short**,
**sempre-flat**, **coin-flip**.

- **Seme del coin-flip**: **`20260913`** — **firmato (F4, owner,
  2026-08-20)** e inciso qui. Il valore era **proposto** da
  `scripts/run2_power.py` (`COINFLIP_SEED_PROPOSTO`); il §A.13 chiede che il
  seme sia **dichiarato nel PREREG**, e un seme scelto dopo aver visto i
  risultati non è una baseline. Da qui in avanti il numero **vive in questo
  documento**: se lo script e il PREREG divergessero, vale il PREREG.
- **Condizioni comuni**: stessi istanti, **stessa size fissa**, **stessi
  costi** — round-trip taker **9,16 bps** su BTC e **9,53 bps** su ETH.
  **Dichiarato come costo del momento**, misurato su un book puntuale il
  17/08/2026, non come costo strutturale.
- **Copertura**: le baseline si calcolano **anche sui giorni in cui l'agente
  non decide**; il confronto si fa **sull'intersezione**, **dichiarando le
  coppie escluse**. Senza questa clausola un agente che si astiene nei giorni
  difficili batterebbe la macchina per costruzione.
- **Decomposizione beta / selezione**: regressione del P&L giornaliero sul
  rendimento BTC. Dichiarata ora, non a posteriori.

### 6.3 HOLD nel denominatore (§A.15)

**HOLD sta sempre nel denominatore.** Il **tasso di astensione** si riporta
come misura, non come nota a piè di pagina. Un metro calcolato sui soli giorni
in cui l'agente ha agito premia l'astensione selettiva senza mostrarla.

### 6.4 La dispersione si riporta come istogramma (§A.16)

**Istogramma completo dei valori distinti**, **mai** media e deviazione
standard da sole.

Il reperto che lo impone: nella Stagione 0 la confidence del 17/08 ha media
0,55 e deviazione standard **0,0000**; ma anche una distribuzione larghissima
con la stessa media si riassumerebbe in due numeri innocui. Il rito di
elicitation mostra forme con la **stessa media** (0,536) e conteggi per valore
completamente diversi: l'istogramma è l'unica cosa che le distingue.

### 6.5 ECE e Brier: raccolti, non riportati (§A.14 + R-A)

**ECE e Brier escono dal pannello primario.** Si **raccolgono**, non si
**riportano** come misure di questa stagione.

**Regola 51, soglia firmata (R-A)**:

> L'ECE **non si riporta mai senza la dispersione accanto**. Si marca **NON
> INTERPRETABILE** se `SD(confidence) < 0,05` **oppure** se i valori distinti
> di confidence sono **meno di 3**.

Se mai calcolato: **bin a massa uguale**, **correzione jackknife**.

**Fondamento empirico**: l'A/B di elicitation su `claude-opus-5` (100 chiamate,
5 forme × 2 snapshot × k=10) ha accertato che l'ancoraggio a 0,55 è **del
contenitore** — il campo `confidence` in [0,1] con un'ancora sola a 0,5 — non
del modello né della prosa. La forma A riproduce il modo 0,55 **6 volte su 10
su entrambi gli snapshot**; la forma D, stessa scala e prosa diversa, è
indistinguibile da A (distanza in variazione totale 0,10-0,20). Con la
confidence ancorata dal contenitore, un ECE calcolato su quei valori misura
**l'ancoraggio**, non la calibrazione dell'agente.

### 6.6 `n_eff` dichiarato per misura (§A.17)

`n_eff` si dichiara **per misura**, non una volta per la stagione:

| Misura | `n_eff` atteso |
| --- | --- |
| `p_accordo` (categoriale) | ~ n coppie |
| dispersione | ~ n |
| coerenza dichiarativa | ~ n |
| astensione | ~ n |
| Brier | **molto minore di n** |
| decomposizione beta | **molto minore di n** |

**Ragione**: gli **esiti** di mercato sono autocorrelati; le **decisioni** su
snapshot congelati distinti non lo sono allo stesso modo. Un `n_eff` unico per
la stagione sovrastimerebbe la precisione delle misure basate su esito.

---

## §7 — Calendario

| Voce | Valore |
| --- | --- |
| **Partenza** | **entro il 2026-09-13** |
| **Cap di calendario** | **42 giorni** dal primo giorno con verbali |
| **Estensione ammessa** | `min(49 giorni; 2026-10-24)` |
| **Giornate attese** | **28** (al tasso di fallimento di S0) |
| **Trigger** | **già ancorato a UTC** dal rito T1 |

### 7.1 Perché il 13/09 e perché il 24/10

Il cambio d'ora è il **2026-10-25**. Il trigger alle 02:00 locali coincide con
le 00:00 UTC **solo in CEST**: una stagione che attraversasse il cambio d'ora
sposterebbe l'istante dello snapshot a metà corsa, cioè **cambierebbe una
variabile senza dichiararlo** (§A.12).

Il rito T1 ha **ri-ancorato il trigger a UTC**, il che toglie il problema
tecnico. Il limite del **24/10** per l'estensione resta come margine: è il
giorno prima del cambio d'ora, e chiude la finestra **prima** che la questione
si ponga, invece di fidarsi che il ri-ancoraggio regga.

L'estensione a `min(49; 24/10)` è una **clausola dichiarata prima**, non un
rinvio concesso quando il cap scade. Oltre l'estensione, il RUN2 è **INVALIDO
per inaffidabilità operativa** e riparte da zero dopo indagine e fix — la
stessa regola del §3 del `PREREG_LAB_S0`.

### 7.2 Giorni mancati

`skipped_day` nel registro operativo, **mai recuperati**, **mai ricostruiti
retroattivamente**. `failed_decisions` (rito partito, API non ha risposto nella
finestra) è un evento distinto e conta a parte.

Soglie di allarme operativo, **non invalidanti**, da annotare: **> 4
`skipped_day` totali** oppure **> 2 consecutivi**.

**Rischio dichiarato**: la sera del 18/08 il rito di elicitation ha incontrato
**23 chiamate fallite con `overloaded_error`**, tutte transitorie e tutte
riuscite al ritentativo. Il client del rito quotidiano **già ritenta**
(`arena/llm_client.py` classifica `overloaded_error` fra i tipi ritentabili);
lo script di elicitation no, e da lì i 23 buchi. Il **denominatore** di quel
tasso **non è ricostruibile da questo repo**: si registra il conteggio assoluto
e si dichiara che la percentuale spesso citata (~57%) **non è verificata**.

---

## §8 — Denaro

### 8.1 Le due guardie

| Guardia | Soglia | Chi la legge | Cosa fa |
| --- | --- | --- | --- |
| **dura** | spesa cumulata > **1,5 ×** `season_budget_usd` | il runner, prima di girare | **la giornata non parte** |
| **d'allarme** | spesa cumulata > **1,25 ×** il pro-rata | il controllo del mattino | scrive `ALLARME_<data>.txt` |

Il pro-rata è `season_budget_usd × giornate_eseguite / season_expected_days`.
**Numeratore e denominatore vengono entrambi dal Freeze manifest** e si firmano
insieme: un preventivo tarato su 28 giornate con un pro-rata calcolato su 42
darebbe una soglia pari a `0,83 ×` la spesa attesa, cioè **sotto** di essa, e
l'allarme suonerebbe ogni giorno di una stagione perfettamente in linea.

### 8.2 I sei termini economici del pin

Il runner in `--live` pretende **tutti e sei**, e la loro assenza è un rifiuto
elencato in una volta sola (TL-010):

| Campo del manifest | Valore | Stato |
| --- | --- | --- |
| `season_budget_usd` | **$89,90** | **FIRMATO** (F5, 20/08) |
| `season_expected_days` | **28** | calcolato, T2 §6 |
| `price_per_mtok_input` | **5,00** | letto il 20/08 |
| `price_per_mtok_output` | **25,00** | letto il 20/08 |
| `price_per_mtok_cache_write_5m` | **6,25** | letto il 20/08 |
| `price_per_mtok_cache_read` | **0,50** | letto il 20/08 |

Prezzi in USD per milione di token, riga «Claude Opus 5» della pagina di
listino ufficiale, letta il **2026-08-20** (evidenza T2 §4). La scrittura in
cache è quella a **5 minuti** perché il client non specifica `ttl` e il default
è 5 minuti; quella a 1 ora ($10) **non si applica**.

**R-D**: questi valori si **citano** qui, ed entrano nel manifest **al rito
del pin**. Con la firma **F5** del 20/08 il `season_budget_usd` non è più una
proposta — è deciso a **$89,90** — ma resta `null` nel manifest fino al pin,
perché è lì che il `freeze_id` viene ricalcolato e timbrato.

### 8.3 Il preventivo firmato, e l'avvertenza che lo accompagna

| | Valore |
| --- | --- |
| costo giornaliero, scenario **CALDO** | **$3,2107** |
| costo giornaliero, scenario **FREDDO** | **$7,1731** |
| `season_budget_usd` = giornaliero caldo × 28 | **$89,90** |
| soglia dura (1,5 ×) | **$134,85** |

**Perché 1,5 × 28 = 42 è il punto giusto**: con questi due numeri la soglia
dura si tocca esattamente al **giorno 42** se la stagione spende come previsto,
cioè nello stesso istante in cui scade il cap di calendario. Stop economico e
stop di calendario si incontrano invece di contraddirsi.

**L'avvertenza**: se il RUN2 girasse in regime **freddo**, la soglia dura
verrebbe toccata al **giorno 18,8** e la stagione si fermerebbe da sola a metà.
Non è un difetto della guardia: è la guardia che funziona. Ma va saputo
**prima**, non scoperto al giorno 19. L'incertezza che conta **non** è la banda
P10-P90 dei token di output (±2,4%): è **quale scenario di cache si verifica**,
e vale **2,2×**.

**La firma (F5, owner, 2026-08-20): `season_budget_usd` = $89,90.** È il
preventivo dello scenario **caldo** dell'evidenza T2; la soglia dura resta
**$134,85** e continua a incontrare il cap di calendario al giorno 42.

**L'alternativa scartata, col suo motivo.** Il preventivo sulla media dei due
scenari — $5,1919/giorno → `season_budget_usd` = **$145,37**, soglia dura
$218,06 — reggerebbe in regime freddo fino al giorno 30,4. È **scartato**, e il
motivo è che descrive male che cosa il regime freddo **è**: un **guasto
diagnosticabile**, non un costo più alto da assorbire. Se al giorno ~19 la
guardia dura ferma la stagione, la cosa giusta è **guardare
`cache_creation_input_tokens`** (§8.4) e capire perché la cache non tiene — non
avere un budget abbastanza largo da non accorgersene. Un preventivo che assorbe
il guasto **compra silenzio**, e la guardia serve esattamente a impedirlo.

### 8.4 Il numero che il primo giorno misura

Il regime di cache **non è deciso, è ipotizzato**. Il primo giorno reale dice
quale dei due scenari vale, guardando `cache_creation_input_tokens` nel log
delle tool call: **vicino a 336.000 significa caldo, vicino a 1.025.000
significa freddo**. È la misura che sostituisce l'ipotesi, ed è dichiarata
prima di essere raccolta.

### 8.5 Cosa il preventivo NON copre

- **Giornate fallite**: un errore transitorio con ritentativi paga i turni già
  consumati e non produce verbale.
- **Rifiuti del modello**: `stop_reason="refusal"` prima di qualunque output
  non è fatturato, ma i turni precedenti della stessa conversazione sì.
- **Riti di manutenzione** (sonde, diagnosi, prove): stanno sulla riga di spesa
  del rito, non su quella della stagione.

### 8.6 Limite di Console

Limite mensile **500 USD**, notifica a **300 USD**, ricaricamento automatico
**SPENTO** (§A.18).

**STATO: chiuso (F6, owner, 2026-08-20).** La chiusura è registrata in
`zeroPipes/docs/program/CODA.md`, **voce 1.3**: i tre valori sopra sono stati
**eseguiti e verificati dall'owner il 19/08/2026** in Console. La ratifica del
**20/08** attesta che **da allora nulla è cambiato**. Il reperto che questa voce
chiude è la sera del 18/08, quando il ricaricamento automatico risultava ancora
attivo.

Resta vero che **la Console non lascia traccia in questo repo**: la chiusura
vale per l'attestazione dell'owner e per la voce di `CODA.md`, non per un
controllo che `traderLab` possa rifare. Il §15, voce 5, lo dichiara.

### 8.7 Il tetto di livello P, che sta fuori da questo repo

Il **punto 14** del foglio (§0.6) fissa un **tetto duro di 850 USD** al livello
P, inciso in `zeroPipes/docs/program/SPESE.md`. Recepisce **D4**: la cifra di
600 USD era il **fondo** di una forchetta, prodotta da una macchina che aveva
**sottostimato tre volte su tre**.

Va detto con precisione **che cosa non è**: non è il budget di questa stagione.
Il `season_budget_usd` del §8.3 vale **$89,90** e la sua soglia dura **$134,85**
(§8.1). Il tetto di livello P sta a un piano più alto e conta la spesa del
**programma**, riti di manutenzione compresi — cioè proprio la voce che il §8.5
dichiara **fuori** dalla contabilità di stagione.

**Nessuna guardia di `traderLab` legge quel tetto**, e non deve: il §7 di
`CLAUDE.md` vieta a questo repo ogni percorso verso `zeroPipes`. Il controllo è
dell'owner, sul registro `SPESE.md`. Qui il numero si trascrive perché un
vincolo economico che può fermare la stagione senza comparire nella sua
pre-registrazione sarebbe un vincolo **scoperto dopo**.

---

## §9 — Sonde e suite di regressione

### 9.1 La suite

**15 snapshot × k = 5**, cadenza settimanale dalla raccolta della baseline in
poi (§A.10). Soglie derivate meccanicamente dalla regola TL-002, **non
superata** da TL-007:

```
agreement_alarm  = max(baseline − 0,15 ; 0,70)
agreement_sunset = max(baseline − 0,30 ; 0,50)
```

dove `baseline` è l'**auto-accordo** della baseline: per ogni snapshot la quota
di campioni che coincidono con l'azione modale, mediata sugli snapshot.

### 9.2 Le due sonde (§A.11)

Stanno **dentro** la suite, per disegno, non accanto ad essa:

| Sonda | Costruzione | Cosa delimita |
| --- | --- | --- |
| **nulla** | decisione meccanicamente forzata | il **pavimento del rumore** — accordo massimo per costruzione |
| **cieca** | informazione nulla | il **soffitto** — l'accordo che resta senza alcun segnale |

Insieme delimitano la banda entro cui un accordo osservato è informativo.
**k = 30** per entrambe.

### 9.3 Il ponte k=30 → k=3, tabellato

Prodotto da `scripts/run2_power.py`, enumerazione esatta su `C(30,3) = 4.060`
terne:

| sonda a k=30 (a/b/c) | `unanime` | `maggioranza` | `tutti_diversi` |
| --- | ---: | ---: | ---: |
| 30 / 0 / 0 | 1,0000 | 0,0000 | 0,0000 |
| 29 / 1 / 0 | 0,9000 | 0,1000 | 0,0000 |
| 27 / 2 / 1 | 0,7204 | 0,2663 | 0,0133 |
| 24 / 5 / 1 | 0,5010 | 0,4695 | 0,0296 |
| 20 / 8 / 2 | 0,2946 | 0,6266 | 0,0788 |
| 18 / 9 / 3 | 0,2219 | 0,6584 | 0,1197 |
| 15 / 10 / 5 | 0,1441 | 0,6712 | 0,1847 |
| 12 / 10 / 8 | 0,0975 | 0,6660 | 0,2365 |
| 10 / 10 / 10 | 0,0887 | 0,6650 | 0,2463 |

**Un reperto che vale la pena leggere**: anche una sonda perfettamente casuale
(10/10/10) produce `unanime` l'**8,9%** delle volte e `maggioranza` il
**66,5%**. La categoria `maggioranza` è quasi sempre la modale **per pura
combinatoria**, indipendentemente da qualunque segnale. Un `p_accordo` che
cadesse su «maggioranza il 67% delle volte» non direbbe nulla.

### 9.4 Il pavimento morde — quanto, misurato

L'avvertenza del §A.10 dice che il pavimento **può** mordere. La simulazione
dice **quanto**. Per ogni valore dell'auto-accordo **vero** si raccoglie una
baseline (15 × 5), se ne derivano le soglie, e si fa girare una passata di
controllo (15 × 5) **sullo stesso identico modello**: un allarme lì dentro è un
**falso allarme per costruzione**. 20.000 ripetizioni per punto, seme
`20260820`.

| auto-accordo vero | baseline media misurata | allarme medio | pavimento morde | **P(falso allarme)** | P(falso sunset) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0,50 | 0,5920 | 0,7000 | 100,0% | **1,0000** | 0,8579 |
| 0,60 | 0,6455 | 0,7000 | 100,0% | **0,9939** | 0,2626 |
| 0,65 | 0,6797 | 0,7000 | 100,0% | **0,9335** | 0,0616 |
| 0,70 | 0,7182 | 0,7000 | 99,8% | **0,7020** | 0,0069 |
| 0,75 | 0,7600 | 0,7003 | 97,5% | **0,3123** | 0,0003 |
| 0,80 | 0,8053 | 0,7032 | 82,8% | **0,0604** | 0,0000 |
| 0,85 | 0,8516 | 0,7167 | 43,6% | **0,0094** | 0,0000 |
| 0,90 | 0,9007 | 0,7520 | 6,4% | **0,0012** | 0,0000 |
| 0,95 | 0,9502 | 0,8002 | 0,0% | 0,0000 | 0,0000 |

**Tre letture, tutte dichiarate prima della raccolta.**

1. **La suite è utilizzabile solo se l'auto-accordo vero è ≥ 0,85.** Sotto
   0,80 il falso allarme è frequente; a 0,70 la suite allarma su un modello
   che non è cambiato **7 volte su 10**. Non è un difetto della regola TL-002:
   è ciò che significa un pavimento assoluto applicato a un modello rumoroso.
2. **La baseline misurata sovrastima sempre l'auto-accordo vero.** Con k=5 e
   tre azioni la quota modale non può scendere sotto 2/5: a un auto-accordo
   vero di 0,50 la baseline misurata vale 0,59. Chi legge la baseline non sta
   leggendo il parametro.
3. **Cancello di ammissibilità della suite: 0,85. Firmato (F7, owner,
   2026-08-20).** Il §4.2 del `PREREG_LAB_S0` aveva un cancello a
   `self_agreement_rate ≥ 0,75`: per il RUN2 è **superato** dalla simulazione
   di questa tabella, che a 0,75 dà una probabilità di falso allarme **sul
   comportamento di baseline** fra **0,31 e 0,70** (righe 0,75 e 0,70).
   **Conseguenza incisa**: se la baseline misurata cade **sotto 0,85**, la
   suite **non è ammissibile come strumento d'allarme** per questa stagione —
   la raccolta prosegue ed è **descrittiva**, ma **nessuna soglia viene scritta
   in config e la suite non ha alcuna autorità di kill**.

**Effetto sul gate (iii) del §11, dichiarato prima.** Quel gate chiede la
baseline «raccolta e **ammissibile**». Con il cancello firmato a 0,85, una
baseline misurata sotto quel valore lascia il gate (iii) **non soddisfatto**, e
i gate del §11 sono in **AND**: la stagione non si ferma per questo — la
raccolta descrittiva continua — ma il RUN2 **non potrà dichiarare superati tutti
i gate di uscita**, e l'esito si riporta dicendolo. Va scritto ora: a esito noto
questa distinzione sarebbe una scusa.

**Il numero del verbale che non si riproduce.** Il §A.10 dichiara un errore
standard di **0,050** e un calo di 0,15 come evento a **3,0 sigma**. La
simulazione dà una deviazione standard della passata di controllo che vale
**0,0496 in media** sulla griglia — il verbale ha ragione in media — ma
**0,0663 nel caso più rumoroso** (auto-accordo vero 0,60), dove un calo di 0,15
vale **2,3 sigma**, non 3,0. Il verbale §F, punto 7, dichiarava già che quel
calcolo non era stato verificato.

**La correzione, firmata (F8, owner, 2026-08-20), è per annotazione.** Il
verbale del 19/08 è committato e **non si riscrive**; la riga che vale, e che si
cita da qui in avanti, è questa:

> «errore standard 0,050 e calo di 0,15 = **3,0 sigma al valore centrale**
> (SD media 0,0496); nel caso peggiore della griglia (SD 0,0663 a p_vero 0,60)
> lo stesso calo vale **2,3 sigma**».

Fonte: la **Parte B** di `scripts/run2_power.py` — cioè esattamente ciò che il
§F, punto 7, del verbale attendeva.

### 9.5 La potenza del gate

Test di permutazione, statistica di variazione totale, α = 0,05,
n_reale = 40 coppie, **n_sonda = 450** (lettura conservativa), 4.000 stagioni
simulate per cella, seme `20260820`. Nessuna sonda è ancora stata eseguita:
**questi sono scenari, non misure**, e la tabella si legge «se la sonda cadesse
qui, la potenza sarebbe questa».

Le distribuzioni sono scritte come `(unanime, maggioranza, tutti_diversi)`.

**Potenza marginale** — un solo confronto:

| scenario reale | vs nulla ideale (1,00/0/0) | vs nulla con rumore (0,95/0,05/0) | vs cieca prior forte (0,60/0,35/0,05) | vs cieca prior debole (0,40/0,45/0,15) |
| --- | ---: | ---: | ---: | ---: |
| **S0 osservata** (0,75/0,25/0) | 1,000 | 0,952 | 0,451 | 0,990 |
| quasi sempre unanime (0,90/0,10/0) | 0,918 | **0,212** | 0,994 | 1,000 |
| unanime 4 su 5 (0,80/0,20/0) | 0,999 | 0,839 | 0,735 | 1,000 |
| un po' di disaccordo (0,70/0,25/0,05) | 1,000 | 0,991 | 0,189 | 0,935 |
| disaccordo frequente (0,60/0,35/0,05) | 1,000 | 1,000 | **0,027** | 0,567 |
| disaccordo dominante (0,50/0,40/0,10) | 1,000 | 1,000 | 0,154 | 0,144 |

**Controllo di dimensione** (reale = sonda, deve dare circa α): 0,000 / 0,013 /
0,029 / 0,024. Il test è **conservativo**, come atteso da un esatto discreto: la
dimensione effettiva sta sotto α, mai sopra.

**Potenza CONGIUNTA** — la potenza che avrebbe avuto la lettura **forte**,
quella che chiedeva che **entrambi** i confronti rigettassero sulla stessa
stagione. La firma **F2** l'ha scartata; la tabella resta perché è il **motivo
inciso** dello scarto, e perché la diagnostica contro la sonda cieca (§1.3) si
riporta con la potenza della sua cella:

| scenario reale | nulla ideale + cieca forte | nulla ideale + cieca debole | nulla rumorosa + cieca forte | nulla rumorosa + cieca debole |
| --- | ---: | ---: | ---: | ---: |
| **S0 osservata** (0,75/0,25/0) | **0,441** | 0,988 | 0,393 | 0,949 |
| quasi sempre unanime (0,90/0,10/0) | 0,908 | 0,925 | **0,198** | 0,219 |
| unanime 4 su 5 (0,80/0,20/0) | 0,741 | 0,998 | 0,568 | 0,838 |
| un po' di disaccordo (0,70/0,25/0,05) | 0,200 | 0,941 | 0,188 | 0,924 |
| disaccordo frequente (0,60/0,35/0,05) | 0,029 | 0,560 | 0,029 | 0,568 |
| disaccordo dominante (0,50/0,40/0,10) | 0,139 | 0,143 | 0,152 | 0,144 |

**Quattro cose che questa tabella dice, e che vanno lette prima di firmare.**

1. **La potenza del gate dipende da dove cadono le sonde più che da dove cade
   la stagione.** Sotto lo scenario osservato in S0, la potenza congiunta va da
   **0,39 a 0,99** a seconda di quanto la sonda cieca è distante. Le sonde non
   sono un contorno: sono metà del disegno.
2. **Nella cella più verosimile — stagione come S0, sonda cieca con prior
   forte — la potenza congiunta è 0,44.** Sotto la lettura forte il gate
   fallirebbe più di una volta su due **anche se `p_accordo` fosse
   informativo**: è il numero che ha deciso la firma **F2** in favore della
   lettura debole. Un «non distinguibile» in quella cella non è evidenza che
   `p_accordo` sia morto.
3. **Se la stagione fosse quasi sempre unanime e la sonda nulla avesse un po'
   di rumore, la potenza crolla a 0,20.** È la saturazione che la letteratura
   descrive: quando l'accordo è al soffitto perde potere discriminante.
4. **La riga «disaccordo frequente vs cieca prior forte» dà 0,029, sotto α.**
   Non è un difetto: quelle due distribuzioni sono quasi identiche, e un test
   che non le distingue si sta comportando correttamente. È la definizione
   operativa di «`p_accordo` indistinguibile dal soffitto».

**Conseguenza dichiarata**: l'esito «gate non superato» va riportato
**insieme alla potenza che il gate aveva in quella configurazione di sonde**.
Un gate fallito a potenza 0,44 e uno fallito a potenza 0,99 sono due
affermazioni diverse, e riportarli allo stesso modo sarebbe disonesto. Sotto la
lettura **debole** firmata (F2) la potenza da riportare accanto al **verdetto**
è quella **marginale contro la sonda nulla** — la prima tabella di questo
paragrafo; la potenza **congiunta** accompagna la **diagnostica** cieca.

---

## §10 — Clausola 18-B: un esito negativo è AMBIGUO DICHIARATO

Ratifica **R-B** dell'owner, 20/08/2026.

Il RUN2 è la **stagione 1 di 2** del budget di classe «agente LLM
discrezionale», portata a **verdetto**. Il modello pinnato è `claude-opus-5`,
di tier **dichiaratamente non di punta**.

> **Clausola 18-B.** Un esito **negativo** del RUN2 è **AMBIGUO DICHIARATO**:
> soffitto del **modello** e soffitto del **concetto** non sono distinguibili
> con questo disegno. Il RUN2 non può rispondere alla domanda «l'idea di un
> agente LLM discrezionale non funziona» perché non ha un braccio che la separi
> dalla domanda «questo modello non basta».

**Per il punto 26 del foglio di `zeroPipes`**: se il RUN2 è negativo, la
**stagione 2 gira sul modello di punta**. Quello è il braccio che scioglie
l'ambiguità, e va eseguito prima che la classe possa essere chiusa.

**Un esito positivo non è ambiguo allo stesso modo**: se un modello non di
punta mostra `p_accordo` informativo, la domanda «serve il modello di punta?»
resta aperta ma non blocca nulla.

**Questa clausola non è un'assicurazione contro il fallimento.** Non rende un
esito negativo meno negativo: dice soltanto **a che cosa non può essere
attribuito**. La stessa conclusione arriva, per un'altra strada, dal §4.4: con
quattro classi di differenza fra S0 e RUN2, nessun confronto fra le due
stagioni isola il modello.

---

## §11 — Gate di uscita del RUN2 (tutti in AND)

| # | Gate | Come si misura |
| --- | --- | --- |
| **(i)** | **≥ 40 coppie** giornata-asset valide entro il cap (o l'estensione del §7) | conteggio sul ledger dei verbali |
| **(ii)** | **tasso di malformati veri < 5%** sul denominatore pieno della stagione | §5.3 |
| **(iii)** | **baseline della suite raccolta e ammissibile** — auto-accordo misurato **≥ 0,85** (F7) — con le soglie scritte in config prima della prima passata di controllo | §9.4 |
| **(iv)** | **integrità**: `verify()` verde su tutto il ledger, input byte-identici in tutte le giornate, zero violazioni del firewall, `freeze_id` identico e uguale a quello timbrato in **tutte** le giornate | §A.2 |
| **(v)** | **verdetto sul gate A.9** in **lettura debole** (F2), riportato **con la potenza** che aveva e con la **diagnostica** contro la sonda cieca accanto | §1.3, §9.5 |
| **(vi)** | **decisione dell'owner** sul passo successivo | — |

**(iv) è il gate che la Stagione 0 avrebbe fallito.** I tre `freeze_id` di S0
differivano fra loro e nessuno coincideva con quello del manifest firmato e
timbrato. La riparazione è in codice dal rito T1 (`load_pinned_manifest`), e
questo gate esiste perché quel fallimento non passi due volte in silenzio.

**Il gate (v) non è un gate di successo.** «`p_accordo` è morto come oggetto di
sizing» è un esito **valido** del RUN2, e chiude una questione aperta invece di
rinviarla. Ciò che il RUN2 non può fare è **non rispondere**.

---

## §12 — La lista onesta

Quello che questa stagione **non** può dire, dichiarato prima di raccoglierla.

### 12.1 Le cinque cautele su `p_accordo` (R-C, dalla ricerca del 20/08)

1. **L'accordo fra repliche NON è evidenza indipendente.** Gli errori correlati
   sono documentati sia fra modelli — Kim et al., ICML 2025: su HELM, coppie di
   modelli concordano circa il **60% delle volte quando sbagliano entrambi** —
   sia **dentro** lo stesso modello (arXiv:2607.02808: guadagni da majority
   voting «below half of the theoretical gains under independence»).
2. **L'accordo unanime può essere errore comune ad alta confidenza.** È la
   «consensus hallucination»: CHOKE (arXiv:2502.12964) documenta allucinazioni
   ad alta certezza robuste fra contesti; Ding (arXiv:2607.08065) misura che
   sul modello frontier una risposta con accordo ≥ 0,8 è **sbagliata il 48%
   delle volte** (CI 95% [0,40; 0,56]).
3. **Il mode collapse da RLHF gonfia `p_accordo`.** L'ottimizzazione
   RLHF/DPO concentra la massa di probabilità sulle risposte tipiche
   (arXiv:2510.01171) e i template di chat strutturati sopprimono la diversità
   attenuando l'effetto della temperatura (arXiv:2505.18949). **A T > 0 le
   repliche di uno stesso modello pinnato sono meno indipendenti di quanto la
   temperatura suggerisca.**
4. **Il disaccordo è più informativo dell'accordo.** Il disaccordo identifica i
   casi difficili in modo affidabile; l'accordo può riflettere bias condiviso,
   euristica memorizzata o prior di posizione. Conseguenza per il sizing: se
   `p_accordo` sopravvivrà al gate, la leva naturale è **il disaccordo come
   segnale di astensione o riduzione**, non l'accordo come segnale di
   amplificazione.
5. **La relazione accordo → correttezza non è monotona nella capacità del
   modello.** Ding misura la correlazione **più bassa** proprio sul modello
   frontier (ρ = 0,20 su GPQA) nonostante l'accordo medio più alto. Per un
   modello molto capace `p_accordo` può essere ancorato al soffitto e privo di
   potere discriminante — e questo interagisce con la clausola 18-B: **la
   stagione 2 sul modello di punta potrebbe avere `p_accordo` meno
   informativo, non più.**

**Nota sulla qualità delle fonti**, trascritta dalla ricerca: i fondamenti
(Wang et al. ICLR 2023; Farquhar et al. *Nature* 2024; Kadavath et al.; Kim et
al. ICML 2025) sono peer-reviewed; le evidenze **più direttamente pertinenti a
`p_accordo`** (Ding 2607.08065; Del et al. 2603.19118; Cacioli 2604.24070) e
tutti i lavori sui trading agent sono **preprint arXiv non ancora
peer-reviewed**. Il 48% di Ding è un **risultato singolo non replicato**, e i
suoi dati vengono da un esercizio di corso con 53 runner studenti non garantiti
indipendenti.

### 12.2 Le cautele di disegno

6. **k = 3 è statisticamente debole**, e la scelta è consapevole. La ricerca lo
   dice: k=3 «è difendibile *solo* come misura categoriale aggregata». R-C
   conferma k=3 **per comparabilità con S0**, e il prezzo è che nessuna stima
   fine di proporzione per coppia è possibile. Le sonde a k=30 esistono
   **proprio** per ancorare l'interpretazione delle categorie grossolane.
7. **Se le sonde a k=30 mostrassero pavimento e soffitto già indistinguibili
   fra loro**, la banda informativa sarebbe nulla e aumentare k non aiuterebbe:
   `p_accordo` andrebbe abbandonato a prescindere dall'esito della stagione.
   **Questa verifica va fatta sulle sonde prima di leggere il gate**, ed è
   dichiarata qui.
8. **Il RUN2 cambia quattro classi di variabili, non una** (§4.4).
9. **La potenza del gate dipende dalle sonde più che dalla stagione** (§9.5), e
   un gate fallito va riportato con la sua potenza. La lettura debole firmata
   (F2) alza quella potenza ma non la rende alta ovunque: contro una sonda
   nulla rumorosa, su una stagione quasi sempre unanime, vale **0,212**.
10. **La suite di regressione è uno strumento solo sopra un auto-accordo vero
    di 0,85**, cancello firmato da F7 (§9.4). Sotto quel valore la raccolta
    resta descrittiva e la suite non ha autorità di kill.
11. **La stima dei token di output del preventivo viene da un altro giorno e da
    un altro asset**: BTC sugli snapshot del 17-18/08, con TTL di cache a 1 ora
    invece dei 5 minuti del runner. Il primo giorno reale la sostituisce con
    una misura.
12. **Il regime di cache non è deciso, è ipotizzato** (§8.4).
13. **I 2.880 punti di funding sono il 96% del prefisso decisionale.** Ridurli
    sarebbe la leva di costo più grande disponibile e cambierebbe **cosa il
    Trader vede**: è una decisione di disegno, non di budget, e non si prende
    dentro una pre-registrazione.
14. **Le riparazioni allo snapshot già individuate — artefatto del weekend,
    giorno-della-settimana — NON entrano nel RUN2** (§A.3): sono rimandate al
    RUN3. La diagnosi che le fonda non è stata verificata da questo documento.
15. **Il tasso di `overloaded_error` non è ricostruibile** (§7.2).
16. **`p_accordo` non è mai stato misurato su decisioni di trading.** La
    ricerca è esplicita: non esiste alcuno studio che quantifichi la
    calibrazione di `p_accordo` inter-replica su decisioni long/short/flat su
    cripto. Le curve accordo → correttezza esistono solo per QA e ragionamento.
    Il RUN2 **è** l'esperimento, non la conferma di un risultato noto.

---

## §13 — Cosa manca al rito del pin

Checklist, nell'ordine. Il pin è **precondizione al primo giorno**, come il §8
del `PREREG_LAB_S0` lo era per la Stagione 0.

| # | Passo | Stato al 2026-08-20, dopo il rito T3-BIS |
| --- | --- | --- |
| 1 | **Questo documento committato.** I contenuti sono **firmati** (F1…F10, §14) e nel testo non resta nessun `[DA-FIRMARE]` | **manca il commit** |
| 2 | `scripts/verify_pin.py` verde sulla string `claude-opus-5` contro l'endpoint | **manca** (richiede rete e API) |
| 3 | Smoke live verde, retention verificata di fatto | **manca** |
| 4 | **La parola «stimata» sulla profondità, corretta in tutte le sue sedi** — variabili di contenuto **C3** (descrizione dello schema di `get_costs`, muove `tool_schemas_sha`) e **C4** (riga 35 di `agents/trader_v0/system_prompt.md`, muove `system_prompt_sha`), più `contracts/vocabulary.py` riga 44 che non muove nulla. I testi sono al **§13.1** | **DECISO (F9 per C3, F9-bis per C4 e per l'igiene): si applica QUI, al pin.** Non applicata dalla bozza |
| 5 | `pin_commit` valorizzato con lo sha del commit del pin, e `rito_config.prereg_ref.commit` col commit che congela **questo** documento | segnaposto `PLACEHOLDER` e `[DA-FIRMARE: …]` — **F10**: sono gli unici segnaposto legittimi residui |
| 6 | `season_budget_usd` = **$89,90**, firmato (F5, §8.3) | **firmato**, da **valorizzare** nel manifest |
| 7 | Le **quattro voci di listino** valorizzate (5,00 / 25,00 / 6,25 / 0,50) | segnaposto `null` |
| 8 | `freeze_id` ricalcolato **dopo** aver valorizzato 4-7, e scritto nel file | il `freeze_id` della bozza è `1c429d6f…86cdfc` e **cambierà** |
| 9 | Commit dedicato del manifest, con pathspec esplicito | — |
| 10 | Timbro **OpenTimestamps** sui byte del **blob** (`git cat-file`), mai su una copia del working tree; `ots_pending → False` e `ots_proof_path` valorizzato | — |
| 11 | `MANIFEST_S0.json`, `docs/PREREG_LAB_S0.md`, i due manifest e **questo documento** nei `DEFAULT_OTS_TARGETS` del controllo settimanale | i primi tre ci sono; i due nuovi **mancano** |
| 12 | Autorizzazione esplicita dell'owner al primo giorno | — |

La bozza del manifest è in
**`manifests/trader_v1_run2_freeze_manifest.json`**, con tutti i campi del
contratto enumerati e i segnaposto dichiarati nel blocco `_bozza`.

### 13.1 La profondità non è una stima: i testi, e le tre sedi (F9 + F9-bis)

La descrizione dello schema di `get_costs` dice oggi:

> «Restituisce le commissioni maker e taker in basis point e **le stime di
> spread e profondità** per un simbolo, con il nome dello stimatore usato.»

È la formulazione che il punto 15 del foglio (§0.6) contesta: lo **spread** è
davvero stimato dal book, la **profondità** no — è la costante dichiarata di
`snapshot_builder.DECLARED_DEPTH_USD`, e `LiquidityEstimate.depth_source` lo
registra. Il testo proposto per il rito del pin:

> «Restituisce, per un simbolo, le commissioni maker e taker in basis point, la
> **stima dello spread** dal book — con il nome dello stimatore usato — e la
> **profondità dichiarata** entro l'1% dal mid, che è una costante del
> costruttore dello snapshot, non una misura.»

**Questa bozza non lo applica**, e la ragione è che applicarlo qui sposterebbe
`tool_schemas_sha` e `freeze_id` due volte: una adesso e una al pin, dove il
manifest viene riscritto comunque per il `pin_commit`, il preventivo e il
listino. Si applica **una volta sola**, al pin, e il `freeze_id` che verrà
timbrato è quello che già la comprende.

La formulazione resta **neutra e fattuale**, come il §6 di `CLAUDE.md` pretende:
dice che cosa il numero è, non se sia molto o poco.

**La seconda sede: la riga 35 del system prompt (F9-bis).** La stessa parola
compare in `agents/trader_v0/system_prompt.md`, nell'elenco degli strumenti:

> «`get_costs` — commissioni, spread stimato, **profondità stimata**.»

Il §15 punto 9 di questa bozza la rilevava e dichiarava di non averla decisa. La
firma **F9-bis** dell'owner (20/08/2026, per delega, in estensione di F9) la
decide: si corregge **al pin**, insieme a C3, con la stessa sostanza. Il testo:

> «`get_costs` — commissioni, spread stimato, **profondità dichiarata** (una
> costante del costruttore dello snapshot, non una misura).»

Il motivo è inciso nella firma stessa: correggere metà formulazione lascerebbe
il modello a leggere una contraddizione — la descrizione del tool direbbe
«dichiarata» e l'elenco degli strumenti, nella stessa finestra di contesto,
direbbe «stimata». Questa sede sta **nel contesto del modello**: muove
`system_prompt_sha`, ed è la variabile di contenuto **C4** (§4.3).

**La terza sede: `contracts/vocabulary.py` riga 44 (F9-bis, igiene).** Anche la
descrizione di `depth_usd_1pct` in `PRIMITIVE_FEATURES` diceva «Profondità
stimata in USD entro l'1% dal mid». Diventa:

> «Profondità dichiarata in USD entro l'1% dal mid: una costante del costruttore
> dello snapshot, non una misura.»

Questa **non raggiunge il Trader** — di `PRIMITIVE_FEATURES` il codice usa solo
chiavi e nomi — e infatti non muove nessuno degli sha del pin. Non è una
variabile: è igiene, dichiarata perché il rito l'ha toccata (§4.3).

**Cosa il rito del pin ha effettivamente misurato**, con gli sha per esteso, in
modo che il conto sia verificabile da chiunque cloni il repo:

| sha del pin | prima di F9/F9-bis | dopo |
| --- | --- | --- |
| `tool_schemas_sha` | `d3accf7fe0cae5391f876f73fe99d6850f79e21c8aad7d77d56d6f18278c894f` | `ce8448924028390830645f4c6203fab2339a226dc6779b4d602090b9e2b0eb15` |
| `system_prompt_sha` | `7ccf9dc4fcecdd72dc122d522a73a97697b4d15ad9d9d8b33a9c2bdbfb6d4177` | `555d7fa52d1dffc0c0e6ee9f72d75c9ffbe0182675cfe4ded62e1e2f56145cef` |
| `persona_sha` | `d4680c6401daeb1f83c45ce5a1e5eefcc6d20edf526ea4439ceb6fd989ad0de3` | invariato |

---

## §14 — Il registro delle firme (F1…F10 + F9-bis, owner, 2026-08-20)

Questa sezione **non elenca più punti aperti**: elenca le dieci decisioni con
cui l'owner ha chiuso i nove `[DA-FIRMARE]` del rito T3, più il segnaposto che
resta legittimamente al rito del pin. Le firme sono state pronunciate **per
delega esplicita alla proposta del consigliere** e trascritte dal prompt del
rito T3-BIS.

| Sigla | Decisione firmata | Dove è incisa | Chiude |
| --- | --- | --- | --- |
| **F1** | I punti **12, 13, 14, 16, 17, 18** del foglio di `zeroPipes` sono trascritti; il §0.5 dichiara la lacuna **chiusa**, con data e fonte | §0.5, §0.6, §8.7 | il n. 1 |
| **F2** | Gate A.9 in **lettura DEBOLE**: sopravvivenza = distinguibilità dalla **sola sonda nulla**. Il confronto con la cieca resta **obbligatorio come diagnostica**, mai come condizione di morte. Lettura forte annotata come **scartata**, col motivo (potenza congiunta 0,44) | §1.3, §9.5, §11 (v) | il n. 2 |
| **F3** | **Prime 40 coppie** in ordine cronologico di completamento per il test, le eccedenti descrittive; **clausola sotto-40** con tabella dei valori critici per n = 30…40 | §3.2; `run2_power.py`, Parte A.2 | il n. 3 |
| **F4** | Seme della baseline coin-flip = **`20260913`**, inciso | §6.2 | il n. 4 |
| **F5** | `season_budget_usd` = **$89,90**; l'alternativa $145,37 è **scartata**, col motivo (il regime freddo è un guasto da diagnosticare, non da assorbire) | §8.2, §8.3 | il n. 5 |
| **F6** | **Limite di Console chiuso**: 500 USD/mese, notifica a 300, ricarica automatica spenta — eseguito e verificato dall'owner il 19/08; la ratifica del 20/08 attesta che nulla è cambiato | §8.6 | il n. 6 |
| **F7** | Cancello di ammissibilità della suite = **0,85**; sotto quel valore la suite **non ha autorità di kill** e la raccolta è descrittiva | §9.4, §11 (iii) | il n. 7 |
| **F8** | Correzione del §A.10 **per annotazione**: 3,0 sigma al valore centrale, 2,3 nel caso peggiore della griglia | §9.4 | il n. 8 |
| **F9** | **`get_costs`**: la descrizione si corregge **al rito del pin**; è la variabile di contenuto **C3**; il testo proposto è al §13.1 e **non è applicato ora** | §4.3, §13, §13.1 | il n. 9 |
| **F9-bis** | **La stessa correzione in TUTTE e tre le sedi**: descrizione dello schema di `get_costs` (C3), riga 35 di `agents/trader_v0/system_prompt.md` (**C4**, nuova), `contracts/vocabulary.py` riga 44 (igiene, non raggiunge il modello). Motivo inciso: correggere metà formulazione lascerebbe il modello a leggere una contraddizione | §4.3, §4.4, §13 passo 4, §13.1, §15 punto 9 | il n. 9 **per intero** |
| **F10** | `rito_config.prereg_ref.commit` **resta un segnaposto** fino al rito del pin: è l'unico residuo legittimo | manifest; §13, passo 5 | — |

**L'unico segnaposto residuo, per esteso.** Nel Freeze manifest,
`rito_config.prereg_ref.commit` vale `[DA-FIRMARE: il commit che congela il
PREREG del RUN2]`, e non può valere altro: quel commit **non esiste ancora**
mentre questo documento viene scritto. È la sola circolarità legittima del
disegno, e si risolve al pin.

---

## §15 — Cosa non ho potuto verificare

Sezione mai vuota per compiacenza.

1. **I punti 12-18 del foglio di `zeroPipes`** (§0.6). Ora **trascritti**, per
   attestazione dell'owner del 20/08 — ma «trascritti» non è «verificati»:
   questo repo non legge `zeroPipes` (firewall del §7 di `CLAUDE.md`, e regola
   4 del programma), e **nessun byte del file sorgente è stato confrontato**.
   Se la trascrizione e il foglio divergessero, vale il foglio, e la divergenza
   si segnala.
2. **Il requisito «≥ 125 mondi con esito (5 bin × 25)»** (§1.1). Trascritto dal
   verbale, che a sua volta dichiara di non averne una fonte su disco.
3. **Il costo di round-trip taker di 9,16 / 9,53 bps** (§6.2). Viene da un
   referto gitignorato e da un book puntuale del 17/08. Trascritto per esteso
   qui perché sopravviva al clone, ma **non ri-misurato** da questo rito.
4. **La stima dei token di output** del preventivo (§8.3): 100 conversazioni su
   BTC del 18/08, dati grezzi in `scratchpad/`, gitignorati.
5. **Lo stato del limite di Console** (§8.6). La voce è **chiusa** dalla firma
   F6 e dalla voce 1.3 di `zeroPipes/docs/program/CODA.md`, ma la chiusura è
   un'**attestazione**: la Console non lascia traccia nel repo, e nessun rito di
   `traderLab` può rifare quel controllo.
6. **Le distribuzioni delle sonde** (§9.5). Nessuna sonda è stata eseguita:
   tutta la tabella di potenza è su scenari dichiarati.
7. **Il modello di rumore della simulazione della suite** (§9.4): «azione
   preferita con probabilità p, le altre due in parti uguali» è la scelta più
   semplice che produce l'auto-accordo voluto. Una distribuzione a due modi
   darebbe pavimenti **più severi**. È una scelta di questo rito, dichiarata.
8. **La diagnosi delle riparazioni allo snapshot rimandate al RUN3** (§12.2,
   14): registrata come rimandata, non giudicata.
9. **La stessa parola «stimata» fuori da `get_costs`.** La firma F9 corregge la
   descrizione dello schema di `get_costs` (§13.1). La medesima formulazione
   compare però anche in `agents/trader_v0/system_prompt.md`, riga 35
   («`get_costs` — commissioni, spread stimato, **profondità stimata**»), e in
   `contracts/vocabulary.py`, riga 44. La prima **sta nel contesto del
   modello**, e correggerla muoverebbe `system_prompt_sha` e quindi il
   `freeze_id`; la seconda **non raggiunge il Trader**, perché di
   `PRIMITIVE_FEATURES` il registro dei tool usa solo le chiavi. **Il rito
   T3-BIS non ha deciso e non ha toccato nulla di tutto ciò**: lo rileva,
   perché F9 riguarda il solo schema di `get_costs`, e correggere metà di una
   formulazione lascerebbe l'altra metà a dire il contrario.

   **Chiusa dalla firma F9-bis** (owner, 20/08/2026, per delega, in estensione
   di F9) e applicata dal **rito del pin** dello stesso giorno: tutte e tre le
   sedi sono corrette. La riga 35 del system prompt è la variabile di contenuto
   **C4** (§4.3) e muove `system_prompt_sha`; `contracts/vocabulary.py` è
   igiene e non muove nulla. I testi e gli sha, prima e dopo, stanno al §13.1.
   Questa voce resta scritta perché il §15 registra ciò che un rito **non** ha
   potuto fare, e cancellarla riscriverebbe la storia del T3-BIS.

**Nota di metodo.** Tutte le derivazioni di questo documento sono state fatte
**senza rete e senza API**: `scripts/run2_power.py` usa solo la libreria
standard, e ogni sua tabella è riproducibile con
`uv run python scripts/run2_power.py` a partire dal seme dichiarato. Le sue
auto-verifiche abortiscono l'esecuzione se un'identità esatta non vale entro
`1e-9`. La **Parte A.2** — la tabella della clausola sotto-40 del §3.2 — è stata
aggiunta dal rito T3-BIS per la firma F3, con le stesse auto-verifiche estese a
ogni n della griglia.
