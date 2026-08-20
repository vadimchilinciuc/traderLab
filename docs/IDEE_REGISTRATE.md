# IDEE REGISTRATE — Trader Lab

Registro **append-only** delle idee che riguardano il codice, i dati e gli
artefatti di `traderLab`. Una voce non si riscrive: se un'idea cambia forma,
si aggiunge una voce nuova che la supera e lo dichiara.

**Un'idea registrata non è un cantiere aperto.** Registrarla significa fissarne
la specifica e il trigger *prima* di vedere i dati su cui girerà, così che
nessuno possa tarare il disegno dopo aver visto l'esito. Finché il trigger non
scatta — e finché l'owner non autorizza l'esecuzione — qui non si costruisce
nulla.

**Sede canonica.** L'elenco di programma delle idee con i loro trigger vive in
`zeroPipes/docs/program/CODA.md`, §6 voce 9, e **solo** lì: questo file non lo
duplica, ne trascrive la parte che riguarda il Lab (quali file si leggono,
quali guardie valgono, cosa va congelato prima). In caso di divergenza sullo
stato di una pendenza vince `CODA.md`, e la divergenza si segnala.

---

## Idea #6 — Coerenza dichiarativa (tool-call ↔ `features_used`)

- **Numero di programma**: #6.
- **Trigger**: chiusura di Stagione 0. **Scattato il 18/08/2026** (`TL-006`,
  chiusura anticipata per decisione di allocazione).
- **Stato**: registrata, **non costruita**. Esecuzione **accodata dopo il
  freeze del RUN2**, per decisione di allocazione dell'owner.
- **Natura**: rito esplorativo in **sola lettura**, fuori da ogni percorso di
  verdetto.

**Cosa misura.** Ogni decisione del Trader lascia tre tracce già registrate e
mai confrontate fra loro: cosa ha **chiesto** al Tool Server
(`data/toolcalls/*.jsonl`), cosa ha **dichiarato** di aver usato
(`features_used` del verbale), cosa ha **fatto** (`action`).

**Due livelli.**

| Livello | Domanda | Requisito |
| --- | --- | --- |
| **T1** — copertura di chiamata | per ogni feature dichiarata: quella replica, in quel ciclo, ha chiamato un tool che poteva fornire quel valore? | tabella di mappatura feature→tool **congelata e hashata prima** dell'esecuzione |
| **T2** — corrispondenza di valore | il numero dichiarato coincide con quello dello snapshot congelato, entro tolleranza dichiarata? | snapshot persistito per `snapshot_id`: la verità è recuperabile bit per bit |

T2 è il livello forte.

**Quattro esiti, dichiarati in anticipo**: `verificata` (T1 ok + T2 ok) ·
`non_ancorata` (dichiarata, tool mai chiamato) · `divergente` (tool chiamato,
numero non torna) · `non_mappabile` (nome fuori dal vocabolario congelato).
`non_mappabile` è un reperto sul **nostro** vocabolario, non sul modello: va
contato a parte o inquina la misura.

**Rischio da ispezionare come primo passo, prima di costruire.** Se
`get_asset_dossier` restituisce un superset (prezzi, funding, classifiche e
costi in un blocco solo), T1 degenera: qualunque feature risulterebbe
«coperta» da quell'unica chiamata. Se è un superset, T1 si dichiara morto
nella specifica stessa e resta T2.

**Cosa NON è.** Un **limite superiore** sulla fedeltà, non una misura di
causalità. Una feature può essere richiesta, avere il valore giusto, e non
aver deciso nulla: T2 dice «il numero è vero», non «il numero ha deciso».

**Soglie: nessuna adesso.** Non esiste un tasso base, quindi qualunque numero
sarebbe inventato. S0 produce la baseline descrittiva; le soglie si dichiarano
per la Stagione 1 in forma **relativa** a quella baseline.

**Vincoli operativi incisi**: sola lettura · nessuna scrittura in `data/` ·
etichetta esplorativa esplicita · tabella di mappatura committata e hashata
prima dell'esecuzione (toccarla dopo aver visto i risultati è taratura
mascherata) · referto gitignorato · commit solo su autorizzazione dell'owner.

**Perché non è un controllo sugli LLM.** I quattro esemplari censiti il
16/08/2026 hanno quattro autori di natura diversa — codice deterministico,
agente LLM, tool di analisi, operatore umano — e ciascuno è stato colto almeno
una volta a raccontare male sé stesso. È un controllo su **qualunque
componente che produca un resoconto di sé**, l'operatore compreso.
(`zeroPipes/docs/program/storia/ANNOTAZIONE_IDEA6_QUATTRO_ESEMPLARI_2026-08-16.md`)

### Annotazione del 2026-08-20 — il tetto di `features_used` è passato da 12 a 21

*Aggiunta in append. Il testo della voce sopra non è stato modificato.*

Le firme **F12** (principio) e **F12-bis** (forma finale) del
`docs/PREREG_LAB_S0_RUN2.md` hanno reso il tetto di `features_used` **derivato
dal vocabolario** — `len(PRIMITIVE_FEATURES)` = **21** — al posto della
costante **12** scritta a mano, di origine non documentata, che il PREREG
registra come **numero orfano**. Il tetto **applicato** dal contratto si è
quindi alzato da 12 a 21; lo schema di `submit_decision` lo **dichiara** nella
sola riga di descrizione, senza `maxItems`, perché sotto `strict: true` l'API
lo rifiuta con 400 (§2.2, le quattro sonde del 20/08).

**Conseguenza per questa idea.** I conteggi di `features_used` di **Stagione
0** e del **RUN2** **non sono confrontabili** senza dichiarare questo scarto:
sono prodotti sotto due tetti diversi, e un tetto è un vincolo che tronca la
coda della distribuzione. Qualunque tabella che li affianchi deve portare la
dichiarazione accanto al numero, non in nota.

**Cosa resta valido.** La **baseline descrittiva di S0** non è invalidata:
resta il tasso base **della sola S0**, sotto tetto 12, e va usata come tale.
Le soglie della Stagione 1, che il testo sopra dichiara in forma **relativa**
a quella baseline, ereditano la stessa avvertenza: relative a una baseline
raccolta sotto un tetto che oggi non vale più.

Nulla di questa annotazione cambia il trigger della voce, né i quattro esiti
dichiarati, né i vincoli operativi incisi.

**Fonte**: dossier
`zeroPipes/docs/research/2026-08-20_DOSSIER_RND_FRONTIERA.md`, §FASE 4.1,
cautela (i); firme F12 e F12-bis in `docs/PREREG_LAB_S0_RUN2.md` §14.

---

## Idea #12 — Ablazione naturale

- **Numero di programma**: #12.
- **Trigger**: chiusura di Stagione 0. **Scattato il 18/08/2026** (`TL-006`).
- **Stato**: registrata, **non costruita**. Esecuzione **accodata dopo il
  freeze del RUN2**, per decisione di allocazione dell'owner.
- **Natura**: rito esplorativo in **sola lettura**, a **costo zero** — nessuna
  chiamata API, nessun intervento sui dati, nessun contatto con S0.

**L'osservazione che la genera.** A temperatura maggiore di zero le repliche
del Trader divergono spontaneamente sull'insieme dei tool che chiamano: nella
giornata 2 di S0 la replica `r2` ha deciso su ETH **senza** chiamare
`get_universe`, mentre `r1` e `r3` lo hanno chiamato — stessa azione, stessa
confidence, `0,55` esatto.

**Cosa produce.** Incrociando (insieme delle prove raccolte) × (azione,
confidence) su tutte le decisioni disponibili si ottiene un segnale di
causalità dei tool senza costruire alcun esperimento: le divergenze si
accumulano da sole e sono **già** dentro `data/toolcalls/*.jsonl`.

**Limite dichiarato.** È osservazionale, non randomizzato. È il modello a
scegliere quali tool saltare, quindi «saltare» potrebbe correlare col fatto
che la decisione era facile. Non dimostra causalità: dà un **limite superiore
gratuito**.

**Complementare all'idea #6**: quella verifica *se hai chiamato ciò che
dichiari*, questa *se chiamarlo cambia qualcosa*.

**Nota sul trigger.** Il trigger resta la chiusura di S0, scattata il 18/08. La
proposta di spostarlo al freeze del `PREREG_RUN2` è registrata come riserva e
**non** adottata (foglio delle 27 decisioni del 19/08/2026, punto 22): ciò che
è accodato è l'**esecuzione**, per allocazione, non il trigger.

### Annotazione del 2026-08-20 — il reperto B.3 può aver esaurito il campione

*Aggiunta in append. Il testo della voce sopra non è stato modificato.*

Il reperto **B.3** del verbale del RUN2
(`docs/2026-08-19_VERBALE_DECISIONI_RUN2.md`, §B.3) misura, sotto **turno echo
normalizzato**, un percorso di raccolta dati **identico in 100 chiamate su
100** — `get_universe > get_asset_dossier > get_ohlcv > get_funding` — senza
nessuna divergenza, in nessuna forma di elicitation e su nessuno dei due
snapshot. Quel protocollo normalizzato è stato portato nel runner del RUN2.

**Conseguenza per questa idea.** Le **divergenze spontanee** di tool su cui
l'ablazione naturale si regge potrebbero **non esistere più** nei dati del
RUN2: il rimedio al caching, adottato per il costo, ha come effetto
collaterale la rimozione proprio della variabilità che questa idea sfrutta.
L'idea resta eseguibile sui dati di **S0** (3 giornate, 18 slot: campione
minimo), ma non accumulerà dati nuovi.

**Verdetto rimandato alla chiusura del RUN2.** Se il RUN2 conferma **zero
divergenze** di percorso, l'idea si dichiara **«esaurita dal protocollo»**:
non falsificata e non abbandonata per stanchezza, ma **superata** da
un'ablazione *disegnata* invece che osservata — e la prima è l'idea
«**ablazione della risoluzione del funding**» (dossier §scheda 7), registrata
più sotto in questo stesso file.

Nulla di questa annotazione cambia il trigger della voce, che resta la
chiusura di S0, scattata il 18/08/2026, né lo stato di esecuzione accodata
dopo il freeze del RUN2.

**Fonte**: dossier
`zeroPipes/docs/research/2026-08-20_DOSSIER_RND_FRONTIERA.md`, §FASE 4.1 e
§4.4 punto 5.

---

## Pagella degli analisti

- **Numero di programma**: **non ancora assegnato** — l'assegnazione avviene in
  `zeroPipes/docs/program/CODA.md`, §6 voce 9, non qui.
- **Trigger**: congelamento del `PREREG_AB_LEGGING`. **Scattato il
  20/08/2026** (`zeroPipes`, commit `2c98190`).
- **Stato**: registrata, **non costruita**.
- **Natura**: pre-screen **meccanico** in **sola lettura**, di livello Max/CLI:
  nessuna spesa di API a consumo, nessun percorso di verdetto toccato.

**L'idea.** Prendere un piccolo insieme fisso di analisti pubblici, registrare
le loro affermazioni prospettiche in uno schema chiuso man mano che escono, e
misurare a posteriori se battono la moneta. Serve a stabilire se esista un
segnale utilizzabile **prima** di spendere per costruirci sopra qualunque cosa.

**Quattro clausole incise.** Nessuna delle quattro è un dettaglio
implementativo: sono le condizioni che separano una misura da un aneddoto, e
vanno rispettate tutte perché il risultato valga qualcosa.

1. **Lista chiusa.** Da tre a cinque analisti, fissati con un **addendum
   datato PRIMA della prima raccolta**. Scegliere chi entra dopo aver visto
   qualche chiamata azzeccata è selezione sul risultato, e produce un tasso di
   successo che non significa nulla.
2. **Solo prospettico.** Si raccolgono soltanto affermazioni pubblicate **dopo**
   l'inizio della raccolta. Mai chiamate passate: il campione storico è
   inseparabile da ciò che l'analista ha scelto di lasciare online.
3. **Schema forzato.** Ogni affermazione si registra come
   *(direzione, orizzonte, condizione di invalidazione)* **al momento della
   pubblicazione**. Ciò che non entra nello schema non si forza e non si
   scarta in silenzio: il **tasso di non-classificabile è esso stesso una
   metrica**, e probabilmente la più informativa sul mestiere dell'analista.
4. **Pagella pre-dichiarata.** Le metriche si fissano prima di guardare i dati:
   **hit rate contro la moneta** come misura base, **Brier** dove l'analista
   pubblica una confidence. Nessuna soglia si inventa dopo.

**Cosa questa idea NON è.** Non è un feed testuale per il Trader. Il §4 del
`CLAUDE.md` vieta news, sentiment e testo di terzi nel contesto del modello, e
questa idea non lo tocca: è una misura **su** analisti umani, condotta fuori
dal Lab, il cui esito non entra in uno snapshot.

---

## Fonte delle cinque voci del 2026-08-20 — il dossier R&D di frontiera

- **Puntatore**:
  `zeroPipes/docs/research/2026-08-20_DOSSIER_RND_FRONTIERA.md`, §FASE 3 (nove
  schede) e §FASE 4 (critica delle idee già registrate). Qui si **punta**, non
  si duplica: il dossier vive in `zeroPipes` e una copia locale invecchierebbe
  in silenzio (`CLAUDE.md`, «Le regole del programma»).

**Attenzione alla numerazione.** I riferimenti «§scheda N» che seguono sono
**numeri interni al dossier**, non numeri di programma. In particolare la
**§scheda 6** del dossier («la terza sonda») non ha nulla a che vedere con
l'**Idea #6** di programma («coerenza dichiarativa») registrata sopra, e la
**§scheda 7** non è la voce 7 di nessun altro elenco. I numeri di programma di
queste cinque voci **non sono ancora assegnati**: l'assegnazione avviene in
`zeroPipes/docs/program/CODA.md`, §6 voce 9, non qui.

**Stato comune alle cinque.** Tutte **registrate, non costruite**. Registrarle
fissa specifica e trigger *prima* di vedere i dati su cui gireranno; finché il
trigger non scatta e finché l'owner non autorizza l'esecuzione, qui non si
costruisce nulla.

---

## `k_eff` — quante repliche indipendenti sono tre repliche (dossier §scheda 3)

- **Numero di programma**: non ancora assegnato
  (`zeroPipes/docs/program/CODA.md`, §6 voce 9).
- **Trigger**: dopo che le **sonde del RUN2 sono state eseguite** (sono
  pre-stagione, fanno parte della baseline) e **prima della lettura del gate
  A.9** — come già prescrive la cautela 7 del §12.2 del
  `docs/PREREG_LAB_S0_RUN2.md`.
- **Stato**: registrata, **non costruita**.
- **Natura**: rito in **sola lettura** sui file delle sonde. **Zero chiamate**
  API aggiuntive: i dati necessari il RUN2 li produce comunque. Livello
  Max/CLI, **costo zero**.

**Domanda.** Tre repliche identiche del modello pinnato, a temperatura di
default, valgono quante repliche indipendenti — 3, 1,5, 1,1? Qual è l'ICC delle
azioni sullo stesso snapshot, e quale design effect ne deriva per ogni misura
del RUN2?

**Specifica minima.** Per ogni mondo della sonda (k = 30) si calcola la matrice
di accordo a coppie fra campioni; **kappa di Fleiss** per k rater e, in
parallelo, **ICC** su indicatori one-hot delle tre azioni;
**deff = 1 + rho(k − 1)**; **k_eff = k/deff**. Si riporta per tre insiemi:
**sonda nulla** (pavimento atteso, rho ≈ 1 e k_eff ≈ 1), **sonda cieca** (il
prior condiviso), **mondi reali** — dove k = 3 è troppo piccolo per uno
stimatore per mondo, quindi si stima **pooled** su tutte le coppie valide, con
intervallo bootstrap. Sottoprodotto: la potenza del gate A.9 **ricalcolata con
n_sonda/deff** invece di 450, cioè la tabella §9.5 resa condizionale al rho
misurato.

**Cosa si congela prima.** Lo **stimatore** (Fleiss kappa + ICC one-hot), il
**bootstrap** (numero di repliche B e seme), e la **soglia dichiarativa**:
`k_eff < 1,5` sui mondi reali ⇒ «le tre repliche sono, ai fini statistici, un
agente e mezzo», e ogni n_eff del §6.6 si divide per deff.

**Clausola incisa, scritta ora e prima dei dati.** Questa idea **NON modifica
il gate A.9**, firmato **F2**. Non è un secondo gate, non entra in un percorso
di verdetto e non cambia la regola di lettura dell'esito: **corregge soltanto
la potenza riportata accanto all'esito**. Se l'esecuzione producesse un numero
che invita a rileggere il gate, la risposta corretta è annotare, non rileggere.

**Guardia (regola 49).** Caso degenere = tutte le sonde unanimi ⇒ rho
indefinito, o formalmente 1: la guardia deve restituire **`n/d`**, mai `1,0`.
Il rumore infrastrutturale entra in rho come *minore* accordo, cioè in
direzione conservativa per l'idea, e va detto.

**Cosa la falsificherebbe.** `k_eff ≈ 3` sui mondi reali (rho ≈ 0): le repliche
sarebbero quasi indipendenti e il programma avrebbe sovrastimato il problema —
esito buono e perfettamente scrivibile. Oppure: rho della **sonda cieca ≈ rho
dei mondi reali**, cioè l'accordo reale è tutto prior, e `p_accordo` muore per
un'altra strada — coerente con la cautela 7.

**Fonte**: dossier
`zeroPipes/docs/research/2026-08-20_DOSSIER_RND_FRONTIERA.md`, **§scheda 3**.

---

## La terza sonda — invarianza sotto perturbazioni semanticamente nulle (dossier §scheda 6)

- **Numero di programma**: non ancora assegnato
  (`zeroPipes/docs/program/CODA.md`, §6 voce 9). **Da non confondere con
  l'Idea #6 di programma**, registrata sopra: qui il «6» è il numero della
  scheda del dossier.
- **Trigger**: **dopo la chiusura del RUN2** — è una modifica di disegno della
  suite di sonde e non entra in una stagione congelata — e prima del PREREG
  della stagione successiva (RUN3/S1), dove la sonda diventerebbe la terza
  della suite se informativa. L'esecuzione richiede un **preventivo vincolante
  con `count_tokens`** prima di spendere (regola 50).
- **Stato**: registrata, **non costruita**.
- **Natura**: misura su **API pinnata**, **livello P** (tetto 850 USD,
  apertura alla chiusura del RUN2 — `zeroPipes/docs/program/SPESE.md`).
  **Costo stimato**: decine di USD — 300 chiamate a $0,21–0,56 secondo il
  regime di cache, cioè **$65–170** — ma il numero che vale è quello del
  preventivo, non questa stima.

**Domanda.** Quanta parte dell'accordo inter-replica sopravvive a perturbazioni
dello snapshot che **non cambiano l'informazione** — ordine dei campi,
arrotondamento all'ultima cifra, sinonimia di etichetta, ordine dei tool nel
registro? Se la distribuzione delle azioni si sposta (TV > 0,20) sotto rumore
**nullo**, allora `p_accordo` misurava la superficie.

**Perché completa le due sonde esistenti.** Le due sonde del RUN2 delimitano
**pavimento** (sonda nulla) e **soffitto** (sonda cieca); nessuna misura la
**fragilità**, che è il terzo lato della banda. È anche la versione onesta
della
sensibilità di formato già trovata in casa — forme A e D indistinguibili, B/C/E
disperse (`docs/2026-08-19_VERBALE_DECISIONI_RUN2.md` §B.1): là il contenitore
muoveva il *numero*, qui si chiede se muove l'**azione**.

**Specifica minima.** 2 snapshot congelati — gli stessi del rito di
elicitation, **17 e 18/08**, già usati, così nulla di nuovo viene «visto» dal
modello; **4 trasformazioni nulle** congelate in una tabella hashata; k = 30
per
cella ⇒ 2 × 5 (originale + 4) × 30 = **300 chiamate**. Metrica: **TV** fra
distribuzione delle azioni originale e perturbata, per snapshot, con intervallo
per permutazione (lo stesso test del gate A.9, riusato). Si riporta anche
l'effetto sul **percorso dei tool**: era identico 100/100 sotto turno echo
normalizzato (§B.3), e una sua rottura sarebbe un reperto a sé.

**Cosa si congela prima.** Le **4 trasformazioni**, una per classe (ordine dei
campi · arrotondamento · sinonimia di etichetta · ordine dei tool), gli
**snapshot**, **k**, e la **soglia TV = 0,20** — che non è inventata: è la
distanza osservata fra le forme A e D, cioè il «rumore di forma» già misurato
in casa. Sopra quella soglia, la perturbazione nulla muove più della prosa. Il
**protocollo di chiamata** è identico al RUN2 (P1, turno echo normalizzato),
sul modello pinnato.

**Classificazione dichiarata.** La trasformazione «ordine dei tool» tocca il
**registro**, non lo snapshot: si classifica come variabile **P** (protocollo),
non C.

**Guardia (regola 49).** L'invarianza può essere **alta per rigidità**: un
agente che risponde sempre `flat` è perfettamente invariante. Se la
distribuzione originale ha un solo valore, la cella si marca **`n/d`**, non
TV = 0. Due snapshot sono pochi: è un **pre-screen**, e si dichiara come tale.

**Cosa la falsificherebbe.** TV ≈ 0 su tutte e quattro le trasformazioni, con
distribuzioni originali **non degeneri**: l'agente è invariante alla
superficie,
l'accordo è informativo almeno in questo senso, e la terza sonda non serve.
Esito pulito, a costo limitato.

**Fonte**: dossier
`zeroPipes/docs/research/2026-08-20_DOSSIER_RND_FRONTIERA.md`, **§scheda 6**.

---

## Ablazione della risoluzione del funding — il 96% del prefisso (dossier §scheda 7)

- **Numero di programma**: non ancora assegnato
  (`zeroPipes/docs/program/CODA.md`, §6 voce 9).
- **Trigger**: **dopo la chiusura del RUN2** — è una variabile di **classe
  C**, cambia cosa il Trader vede — come **input al disegno del RUN3**.
  Preventivo `count_tokens` prima di spendere (regola 50).
- **Stato**: registrata, **non costruita**.
- **Natura**: misura su **API pinnata**, **livello P**. **Costo stimato**:
  decine di USD (**$40–150**).

**Domanda.** Le azioni del Trader cambiano se i **2.880 punti orari** di
funding
— il **96% del prefisso** — vengono sostituiti da **360 punti a 8 h**, o da **6
statistiche riassuntive** (media 24 h / 72 h / 168 h, segno, percentile 90 g)?
Se non cambiano, il costo per chiamata scende di un ordine di grandezza senza
toccare il comportamento.

**Perché è anche una misura di fedeltà.** La cautela 13 del PREREG RUN2 chiama
questa scelta «decisione di disegno, non di budget, da non prendere dentro una
pre-registrazione»: un rito separato e pre-registrato è esattamente il luogo
dove si può prendere. Ed è l'unica misura di **fedeltà causale** a costo basso
su una feature specifica: se la risoluzione non cambia nulla, il Trader **non
legge** il funding fine, qualunque cosa dichiari in `features_used`. È il
complemento causale dell'**Idea #6** di programma registrata sopra, ed è
l'ablazione *disegnata* che l'annotazione all'**Idea #12** indica come
sostituto se l'ablazione naturale risulta esaurita dal protocollo.

**Specifica minima.** 2–3 snapshot congelati, **già visti** dal modello in riti
precedenti per non consumare giornate nuove; **3 risoluzioni**; k = 30 ⇒
**180–270 chiamate**. Metriche: **TV** fra distribuzioni di azioni (test di
permutazione), **tasso di `flat`**, **token del prefisso e costo per chiamata**
per risoluzione, **percorso dei tool**. Le tre risoluzioni si costruiscono
dallo
**stesso grezzo**, in modo deterministico e con digest.

**Cosa si congela prima.** Le **tre risoluzioni esatte** e il **codice che le
produce** (hash), gli **snapshot**, **k**, e la **regola di lettura**:
`TV < 0,10` su tutti gli snapshot per la risoluzione a 8 h ⇒ «la risoluzione
oraria è costo senza effetto misurabile», e il RUN3 può dichiarare 8 h come
default; `TV > 0,20` ⇒ il funding fine muove l'azione, si tiene e si dichiara.
Gli snapshot vanno scelti su **regimi diversi** (funding piatto e funding in
movimento) **prima** del rito, **per data e non per esito**.

**Guardia (regola 49).** Come per la terza sonda: una TV bassa può nascere
dalla
**rigidità** dell'agente e non dall'irrilevanza della feature. Il controllo è
la
dispersione originale non degenere; con distribuzione originale a un solo
valore
la cella è `n/d`. Pochi snapshot ⇒ **pre-screen, non verdetto**.

**Cosa la falsificherebbe.** Azioni che cambiano **già** passando da 1 h a 8 h:
il Trader usa la granularità, e il costo del prefisso è un prezzo da pagare,
non
uno spreco.

**Fonte**: dossier
`zeroPipes/docs/research/2026-08-20_DOSSIER_RND_FRONTIERA.md`, **§scheda 7**.

---

## Replica pre-registrata del reperto «la forma C sposta l'azione» (dossier §scheda 8)

- **Numero di programma**: non ancora assegnato
  (`zeroPipes/docs/program/CODA.md`, §6 voce 9).
- **Trigger**: **dopo la chiusura del RUN2 e prima del PREREG della Stagione
  1** — il RUN2 non cambia elicitation (variabile A.3), quindi la replica non
  può toccarlo. Preventivo `count_tokens` prima di spendere (regola 50).
- **Stato**: registrata, **non costruita**.
- **Natura**: misura su **API pinnata**, **livello P**. **Costo stimato**:
  decine di USD (**$50–200**).

**Domanda.** Il reperto «**forma C ⇒ `flat` 8 su 9** dove le repliche reali
davano `short` 3 su 3» — un solo snapshot, n = 9 — si replica su snapshot
diversi e regimi diversi? L'elicitation «in quote» rende l'agente
**sistematicamente più prudente**, e di quanto?

**Perché ora.** Il verbale del RUN2 lo classifica come «reperto, non ipotesi
del
disegno, da tenere per la Stagione 1». La Stagione 1 dovrà **scegliere una
forma
di elicitation** (candidata: B, distribuzione sulle tre azioni); sceglierla
senza sapere che C muove l'azione significherebbe cambiare la **misura
primaria** per un effetto collaterale. È inoltre una **replica**, che il
programma non ha mai eseguito su un proprio reperto comportamentale.

**Specifica minima.** **4 snapshot** — due già visti, due nuovi **scelti per
data prima del rito**; forme **A** e **C** (B come terzo braccio se il budget
lo
consente); k = 30 ⇒ **240–360 chiamate**. Metriche: **tasso di `flat` per
forma**, **TV A-vs-C per snapshot**, **direzione dell'effetto**, con test di
permutazione. Brier e istogramma della confidence si riportano **solo come
raccolta**, mai come metrica al limite degenere (regola 51).

**Cosa si congela prima.** Le due (o tre) **forme**, con lo **sha dello
schema**
come in §B.1, gli **snapshot**, **k**, e l'**ipotesi direzionale**: «C aumenta
`flat` di **≥ 20 punti** su **≥ 3 snapshot su 4**» — replicata sì / no, senza
gradazioni inventate dopo.

**Clausola incisa, scritta ora e prima dei dati.** Un esito **positivo NON
promuove la forma C**. Non la rende la forma della Stagione 1 e non la rende
preferibile: dice soltanto che **la forma di elicitation è una variabile di
disegno della misura primaria** e va trattata come tale nel PREREG S1, cioè
scelta e congelata con una motivazione, non ereditata per abitudine.

**Rischi dichiarati.** Effetto dipendente dal regime; il prior condiviso fra
repliche (diversità correlata) gonfia l'apparenza di un effetto sistematico;
quattro snapshot restano pochi. La forma C chiede «quote» e può interagire col
Risk Officer a size fissa: **fuori perimetro, si annota**.

**Cosa la falsificherebbe.** Nessuna differenza sistematica A-vs-C sugli
snapshot nuovi: il reperto era **rumore su n = 9** e si chiude come tale.

**Fonte**: dossier
`zeroPipes/docs/research/2026-08-20_DOSSIER_RND_FRONTIERA.md`, **§scheda 8**.

---

## Baseline «segno del funding» — l'agente direzionale è un trader di carry rumoroso? (dossier §scheda 9)

- **Numero di programma**: non ancora assegnato
  (`zeroPipes/docs/program/CODA.md`, §6 voce 9).
- **Trigger**: **la stesura del PREREG della Stagione 1**. Le **quattro
  baseline del RUN2 sono firmate e non si toccano**: la quinta baseline si
  dichiara nel documento della stagione successiva, non si aggiunge a una
  stagione congelata. Il **calcolo** avviene a fine stagione.
- **Stato**: registrata, **non costruita**.
- **Natura**: **zero chiamate** API, livello Max/CLI, **costo zero**.
  Descrittiva: **nessun potere di verdetto**, come tutte le baseline.

**Domanda.** Se alle quattro baseline meccaniche se ne aggiunge una **quinta**
—
`short` quando il funding medio 24 h > 0, `long` quando < 0, **stessi istanti,
stessa size, stessi costi** — quanta parte del P&L shadow dell'agente è
spiegata
da questa baseline nella decomposizione beta/selezione già dichiarata (§6.2)?

**Perché ora.** Il confronto appaiato è dichiarato «contaminato da beta».
Questa
è l'unico **ponte misurabile** fra i due filoni del programma: il Lab come
generatore di ipotesi e la campagna carry. Se il Trader, vedendo il funding,
sceglie sistematicamente il lato che lo **incassa**, la sua «discrezionalità» è
una versione rumorosa di una regola che il programma **già valuta
meccanicamente** — e lo si saprebbe con una regressione, non con
un'impressione.

**Specifica minima.** Baseline calcolata a fine stagione, **sugli stessi
giorni** e con la **stessa clausola di copertura** delle altre quattro
(calcolata anche nei giorni in cui l'agente non decide; confronto
sull'**intersezione**, con le coppie escluse **dichiarate** — §6.2).
Regressione
del **P&L giornaliero dell'agente** su {rendimento BTC, P&L della baseline
funding-sign}; si riportano **R² parziale** e **coefficiente**; **HOLD nel
denominatore** (§6.3); **n_eff molto minore di n**, come già dichiarato per le
misure basate su esito (§6.6).

**Cosa si congela prima.** La **regola esatta** della baseline (finestra 24 h,
soglia 0, costi **9,16 / 9,53 bps** come le altre quattro), il **modello di
regressione**, e la **lettura**: R² parziale **> 0,5** ⇒ «l'agente è un carry
trader rumoroso», e il suo valore aggiunto va misurato **al netto** della
baseline; R² parziale ≈ 0 ⇒ l'agente fa altro.

**Rischi dichiarati.** Potenza bassissima su una sola stagione (n_eff piccolo,
dichiarato). Il **beta di BTC** e il **segno del funding** sono correlati — il
funding è positivo nei rally — quindi la **collinearità va riportata**, non
nascosta dietro un R² parziale.

**Cosa la falsificherebbe.** Coefficiente **nullo o negativo** con intervalli
stretti: l'agente non segue il funding, e la baseline si archivia come
**controllo negativo utile**.

**Fonte**: dossier
`zeroPipes/docs/research/2026-08-20_DOSSIER_RND_FRONTIERA.md`, **§scheda 9**.
