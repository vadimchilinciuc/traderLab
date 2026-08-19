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
