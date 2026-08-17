# RETTIFICA 01 all'ANNOTAZIONE_CONFIDENCE_S0_2026-08-17

> Annota `docs/ANNOTAZIONE_CONFIDENCE_S0_2026-08-17.md` (commit `766c18a`), che resta valido
> per tutto il resto. **Il documento originale non si riscrive.**
> Motivo: il referto `docs/DIAGNOSI_CACHING_RESIDUO_2026-08-17.md` (commit `17abe82`), prodotto
> poche ore dopo, porta evidenza diretta su tre punti dell'annotazione — uno lo **smentisce**,
> due li **chiudono**.
> Nessuna misura di S0 viene toccata. Le firme sono dell'owner.

---

## R1 — SMENTITA: l'ipotesi §B "il fix caching ha ridotto la diversità"

**Cosa diceva l'annotazione (§B, ipotesi collaterale).** Rendendo i prefissi byte-identici, il fix
`c33fd0b` *potrebbe* aver ridotto il non-determinismo dell'inferenza e con esso la diversità di
campionamento. Cronologia addotta: G1 dispersione confidence 0,0167 → fix → G2 dispersione 0,0000.
Conseguenza temuta: non poter più distinguere "mercato non ambiguo" da "calcolo reso
deterministico", con caduta dell'idea dell'entropia inter-repliche come indice di ambiguità.

**Cosa dice l'evidenza.** Il referto di diagnosi mostra che nella **stessa giornata 2** le tre
repliche hanno seguito **percorsi di raccolta dati diversi**:
- BTC: r1 richiede tutti e sei i tool in **un solo turno**; r2 e r3 spezzano la richiesta in **due
  turni**;
- ETH: r2 **omette `get_universe`**, r1 e r3 lo includono.

Prefissi totali misurati (creation + read), a conferma numerica della divergenza:
BTC r1 = 171.665 contro r2 = 171.650 (Δ 15 token);
ETH r1 = 171.454 contro r2 = 171.289 (Δ 165 token).
**Conteggi di token diversi implicano contenuto diverso**: due prefissi byte-identici non possono
produrre conteggi differenti.

**Conclusione.** Il campionamento **non** è diventato deterministico. Le repliche divergono sul
**percorso** e convergono sulla **decisione**. La dispersione nulla del G2 è quindi convergenza
autentica, non artefatto del fix.

**Conseguenze:**
1. L'ipotesi §B decade. La covariata paventata sul metro del rumore (§4.1 del PREREG) **non
   sussiste**: la misura sta osservando un fenomeno reale.
2. L'idea registrata dell'**entropia inter-repliche come indice di ambiguità del regime** — data
   per compromessa — **resta valida**.
3. La divergenza di percorso era già presente nella giornata 1 (i due tentativi di r2 su BTC hanno
   pattern di tool-call diversi tra loro): non è un effetto del fix, e il fix non l'ha creata né
   rimossa.

---

## R2 — CHIUSA: la lettura del §7(iv), ora dimostrata e non più raccomandata

**Cosa diceva l'annotazione (§B, punto aperto).** Due letture possibili di *«input byte-identici in
tutte le giornate»*: (a) contenuti (prompt, persona, dossier, config), (b) byte effettivi della
richiesta. Raccomandazione: (a).

**Cosa dice l'evidenza.** `CLAUDE.md §10` impone *«Temperatura: default operativo dell'API, nessun
override, MAI 0»*. Con sampling non deterministico obbligatorio, la conversazione generata dal
modello — e quindi la richiesta completa — **non può mai** essere byte-identica tra repliche: il
referto lo dimostra empiricamente (percorsi di tool-calling diversi a parità assoluta di input).

**Conclusione.** La lettura (b) renderebbe il pre-registration **auto-contraddittorio**: imporrebbe
il campionamento e ne esigerebbe simultaneamente l'assenza di effetti. Resta in piedi **solo la
lettura (a)**, e non come preferenza ma come unica interpretazione coerente: il gate §7(iv) si
intende soddisfatto quando sono identici i contenuti hashati nel FreezeManifest (prompt_sha,
persona, universo, config del rito, snapshot del giorno) — verificabili meccanicamente.

**Correzione di formulazione all'annotazione §B.** «Il fix ha restaurato la proprietà *input
byte-identici*» è impreciso. Formulazione corretta: **il fix ha rimosso una fonte di divergenza del
prefisso (gli id assegnati dall'API) che non aveva alcun contenuto semantico**; la divergenza
residua è generata dal modello stesso ed è consentita per disegno. La proprietà del §2/§7(iv)
riguarda gli **input**, che erano e restano identici.

Resta **aperto** l'altro punto dell'annotazione: la lettura del tetto token del §5.

---

## R3 — CHIUSA: l'anomalia r2 doppio-BTC della giornata 1

**Cosa era in coda dal 16/08.** Il log della giornata 1 mostrava 7 cicli decisionali ma 6 verbali
in catena: r2 aveva deciso BTC due volte e un verbale risultava scartato o sovrascritto in
silenzio. Costo del doppione ~$2,2.

**Cosa dice l'evidenza.** `arena/runner.py` (`_process_asset`) rilancia `_one_conversation` da zero
fino a `malformed_retries` volte (default **1** in `arena/config.py`, cioè "un solo retry" come da
`CLAUDE.md §8`). Il contatore «malformati» del log registra **solo i verdetti rifiutati in via
definitiva**: un retry riuscito al secondo tentativo non vi compare, da cui il `malformati: 0` del
giorno 1 pur in presenza di un ciclo ripetuto.

**Riserva dichiarata dal referto, che si accoglie.** Il motivo del **primo** fallimento non è
persistito da alcun campo (nessun record cattura la causa di un tentativo interno poi riuscito):
l'ipotesi «verbale malformato al primo giro» è coerente con tutta l'evidenza disponibile —
posizione del secondo ciclo, configurazione del retry — ma **non è una certezza**.

**Conseguenza.** Voce chiusa come comportamento **atteso e documentato**, non come anomalia.
Resta un'osservazione: **il retry non è visibile in telemetria**. Registrarlo esplicitamente
sarebbe materia di codice, quindi **fuori da S0**; annotato per PREREG_LAB_S1.

---

## R4 — Undicesimo esemplare dell'idea #6

Il campo `response_sha256` scritto da `ToolCallLog.record` per il tool `llm_complete` **non è
l'hash della risposta**: il chiamante passa come `response` soltanto
`{"stop_reason": response.stop_reason}`, quindi il valore è **costante** su quasi tutte le righe.
Un componente il cui nome descrive qualcosa che non fa. Chi lo leggesse come fingerprint del
contenuto ne trarrebbe conclusioni sbagliate.

Il referto di diagnosi l'ha **segnalato invece di usarlo** — che è il comportamento corretto, e la
ragione per cui la sua conclusione regge.

**Conseguenza operativa (fuori da S0, per PREREG_LAB_S1):** non esiste oggi in nessun file del
repo una cattura del testo libero e degli id emessi dal modello nei turni "ask". Se un giorno
servirà verificare byte a byte il prefisso, andrà aggiunta una cattura esplicita — è codice, quindi
non ora.

---

## R5 — Cosa NON cambia

Nessuna misura del §4 del pre-registration è toccata. Prompt · modello · temperatura · snapshot ·
manifest · schema del Decision Record · gate del §7 · cancello del §4.2 · Regola 4 · soglie:
tutto invariato. Il divario di caching residuo (~2 scritture in eccesso su 6 decisioni, ordine di
qualche USD al giorno) è **accettato come costo strutturale del disegno attuale** per la durata di
S0: entrambi i rimedi possibili cambiano cosa il Trader vede o come decide, e sono quindi vietati
dal §5 a stagione in corso.

**Nota di metodo.** Questo non è uno scarto: è una conclusione con evidenza. La regola di programma
stabilita il 17/08 — *nessuna scelta si scarta senza evidenza; ciò che non si può validare ora si
rinvia con un trigger dichiarato; lo scarto definitivo richiede un numero o un testo che lo
sostenga* — è soddisfatta dal referto `17abe82`.