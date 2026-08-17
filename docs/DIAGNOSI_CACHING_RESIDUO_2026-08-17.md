# Diagnosi del caching residuo (giornata 2, post-fix c33fd0b)

Rito di sola lettura. Nessun file di codice, prompt, context file, config,
snapshot o ledger è stato modificato per produrre questo referto. Nessuna
chiamata API Anthropic è stata effettuata: l'analisi lavora sui log già
scritti (`data/toolcalls/`, `data/logs/`, `data/ledger/season0.jsonl`) e sul
codice sorgente già presente nel repo (`arena/runner.py`,
`arena/llm_client.py`, `toolserver/toollog.py`).

## 0. Premessa metodologica: cosa il log NON contiene

`ToolCallLog.record` (`toolserver/toollog.py:38-69`) scrive
`"response_sha256": sha256_of(response)`, e per il tool `llm_complete` il
chiamante (`arena/runner.py:333-338`) passa come `response` **solo**
`{"stop_reason": response.stop_reason}` — non il contenuto generato. Il
commento nel file spiega la scelta: "non la risposta intera, che è
ricostruibile dallo snapshot" — vero per i tool deterministici (`get_ohlcv`,
`get_asset_dossier`, ...), falso per `llm_complete`, il cui output è una
generazione del modello, non una funzione pura dello snapshot.

Conseguenza diretta: **il jsonl non permette di verificare byte a byte il
testo libero o gli argomenti dei blocchi `tool_use` del turno "ask"**. Il
campo `response_sha256` di `llm_complete` è costante (`d9c1372f...` per la
stragrande maggioranza delle righe) perché è l'hash di `{"stop_reason":
"tool_use"}`, identico per quasi ogni chiamata — **non è un hash del
contenuto**. Chi legga questo campo aspettandosi un fingerprint della
risposta ne trarrebbe una conclusione sbagliata; va segnalato esplicitamente.

Cosa **è** ricostruibile dal jsonl, in modo affidabile:
- quali tool sono stati chiamati, in che ordine, con quali argomenti, in
  quanti turni (dai record dei tool deterministici che seguono ogni
  `llm_complete` di tipo "ask");
- i token di cache (`cache_creation_input_tokens`, `cache_read_input_tokens`,
  `input_tokens`, `output_tokens`), forniti direttamente dall'API e non
  ricostruiti da questo codice.

Cosa **non è ricostruibile** da nessun file del repo: il testo libero
prodotto dal modello nel turno "ask", gli id assegnati dall'API ai blocchi
`tool_use` di quel turno (sostituiti prima di essere scritti nel messaggio
successivo, vedi §3), l'ordine esatto byte-per-byte dei blocchi. Non esiste
in `data/logs/` né altrove una cattura grezza della request/response HTTP:
`data/logs/daily-*.log` contiene solo l'output testuale del rito (riepiloghi,
non payload). Se in futuro serve questo livello di verifica, andrebbe
aggiunta una cattura esplicita (fuori scope qui: toccherebbe il codice).

Il ledger (`data/ledger/season0.jsonl`) contiene `rationale_text` per intero,
ma è il testo del turno **finale** di submit — quello che segue il blocco con
`cache_control`, quindi irrilevante per il prefisso cacheato del blocco
grande.

## 1. Le 6 decisioni della giornata 2, chiamata per chiamata

`data/logs/daily-2026-08-17.log` riporta `decisioni: 6, malformati: 0`. Ogni
decisione (replica × asset) corrisponde però a **2 o 3** chiamate
`llm_complete` reali (turno "ask" che richiede tool, a volte un secondo turno
"ask" intermedio, poi il turno di submit) — il ciclo agentico non è
un'unica chiamata. Tabella completa, dal file
`data/toolcalls/20260817T000021Z.jsonl`:

| # | riga jsonl | replica | asset | ts_utc | tipo turno | cache_creation | cache_read | input | output |
|---|---|---|---|---|---|---:|---:|---:|---:|
| 1 | 1 | r1 | BTC | 00:00:31.799 | ask (1/1) | 5.422 | 0 | 140 | 323 |
| 2 | 8 | r1 | BTC | 00:01:15.472 | **submit** | 166.243 | 5.422 | 2 | 2.973 |
| 3 | 9 | r1 | ETH | 00:01:24.372 | ask (1/1) | 0 | 5.422 | 140 | 299 |
| 4 | 16 | r1 | ETH | 00:02:01.386 | **submit** | 166.032 | 5.422 | 2 | 2.490 |
| 5 | 17 | r2 | BTC | 00:02:07.261 | ask (1/2) | 0 | 5.422 | 140 | 186 |
| 6 | 22 | r2 | BTC | 00:02:11.766 | ask (2/2) | 1.430 | 5.422 | 2 | 126 |
| 7 | 25 | r2 | BTC | 00:03:03.718 | **submit** | 164.798 | 6.852 | 2 | 3.442 |
| 8 | 26 | r2 | ETH | 00:03:10.311 | ask (1/1) | 0 | 5.422 | 140 | 275 |
| 9 | 32 | r2 | ETH | 00:03:50.426 | **submit** | 165.867 | 5.422 | 2 | 2.817 |
| 10 | 33 | r3 | BTC | 00:03:56.738 | ask (1/2) | 0 | 5.422 | 140 | 186 |
| 11 | 38 | r3 | BTC | 00:04:01.285 | ask (2/2) | 0 | 6.852 | 2 | 126 |
| 12 | 41 | r3 | BTC | 00:04:56.174 | **submit** | 0 | 171.650 | 2 | 4.305 |
| 13 | 42 | r3 | ETH | 00:05:02.732 | ask (1/1) | 0 | 5.422 | 140 | 299 |
| 14 | 49 | r3 | ETH | 00:05:35.126 | **submit** | 0 | 171.454 | 2 | 2.414 |

14 chiamate `llm_complete` reali per 6 decisioni. Somma di controllo:
`cache_creation` totale = 5.422+166.243+166.032+1.430+164.798+165.867 =
**669.792**; `cache_read` totale = 5.422×9 + 6.852×2 + 171.650 + 171.454 =
**405.606**. Entrambi coincidono esattamente con quanto riportato dal rito
(`data/logs/daily-2026-08-17.log` non lo scompone, ma il totale dei 14 record
del jsonl torna). Questo conferma che la tabella sopra è completa e che non
mancano righe.

## 2. Scritture vs riletture: blocco piccolo e blocco grande

**Blocco piccolo (system+tools, atteso ~5.422 token).** Scritto una sola
volta nell'intera giornata (riga 1, prima chiamata assoluta), riletto in
tutte le 13 chiamate successive. Comportamento ideale, nessuna anomalia:
system+tools sono byte-identici per costruzione (D1) e lo restano.

**Blocco grande (ultimo tool_result del turno di submit, atteso ~166K
token).**

| decisione | esito | dettaglio |
|---|---|---|
| r1 BTC | **SCRITTURA** | riga 8: creation 166.243, prefisso totale 171.665 |
| r1 ETH | **SCRITTURA** | riga 16: creation 166.032, prefisso totale 171.454 |
| r2 BTC | **SCRITTURA** | riga 25: creation 164.798 su un prefisso base di 6.852, totale 171.650 |
| r2 ETH | **SCRITTURA** | riga 32: creation 165.867, prefisso totale 171.289 |
| r3 BTC | **RILETTURA piena** | riga 41: creation 0, read 171.650 — hit esatto sul prefisso scritto da r2 BTC (riga 25) |
| r3 ETH | **RILETTURA piena** | riga 49: creation 0, read 171.454 — hit esatto sul prefisso scritto da r1 ETH (riga 16), **non** da r2 ETH |

Quattro scritture, due riletture piene. 669.792 / 166.000 ≈ 4,03 — il calcolo
del prompt torna: la piccola frazione oltre 4 è la scrittura isolata da 1.430
token alla riga 22 (vedi §3), non un quinto blocco grande.

C'è anche un blocco intermedio, non menzionato nel prompt ma rilevante: r2
BTC, nel suo secondo turno "ask" (riga 22), scrive 1.430 token in più sopra
al blocco piccolo — è il risultato dei primi 4 tool eseguiti prima di quel
turno, marcato con `cache_control` come "ultimo tool_result" del suo momento.
r3 BTC lo rilegge esattamente (riga 38: read 6.852 = 5.422+1.430, creation 0)
perché riproduce identico il pattern a due turni di r2. Questo blocco
intermedio non è "il" blocco grande della diagnosi ma è un'istanza dello
stesso fenomeno un livello più in basso, ed è la prova più diretta che
**quando il contenuto è identico, la cache funziona**: la rilettura è piena
sia per il blocco intermedio sia per quello grande, in entrambi i casi in cui
un replica successiva ha ripetuto esattamente il pattern di tool-call di una
precedente.

## 3. Il prefisso: cosa differisce fra repliche dello stesso asset

Il codice (`arena/llm_client.py:204-225`, `_cached_messages`) marca con
`cache_control` **l'ultimo blocco `tool_result` dell'ultimo messaggio**. Il
prefisso cacheabile del turno di submit è quindi: system (marcato) + tools
(marcato) + **l'intera conversazione precedente, turno "ask" per turno
"ask", assistant e user, fino a e incluso quel tool_result**. Perché la
cache faccia hit, tutto questo deve essere byte-identico, non solo il
blocco finale.

Non potendo leggere il testo libero né gli id del turno "ask" (§0), il
confronto si fa sull'unico segnale disponibile e affidabile: **la dimensione
totale del prefisso (creation+read accumulati) e il pattern osservabile di
tool-call** (quali tool, quanti, in che ordine, in quanti turni). Entrambi
sono conseguenza diretta e univoca del contenuto dei blocchi `tool_use` che
il modello ha effettivamente emesso — non sono un proxy debole.

**BTC.** r1 chiede tutti e 6 i tool in un solo turno (righe 2-7:
`get_universe, get_asset_dossier, get_ohlcv, get_funding, get_costs,
get_rankings`) e arriva al submit con un prefisso totale di **171.665**
token. r2 chiede solo 4 tool nel primo turno (righe 18-21: `get_universe,
get_asset_dossier, get_rankings, get_costs` — **manca `get_ohlcv` e
`get_funding`** rispetto al set di r1), poi in un secondo turno "ask" chiede
i 2 mancanti (righe 23-24: `get_ohlcv, get_funding`), e arriva al submit con
un prefisso totale di **171.650** — 15 token in meno di r1, nonostante lo
stesso insieme di 6 tool alla fine: la differenza è nel **numero di turni**
(1 vs 2) e nell'**ordine** in cui i risultati vengono raggruppati, che
cambiano la struttura dei messaggi (più blocchi `assistant`/`user`, più testo
libero intermedio) anche a parità di tool complessivi. r3 riproduce
esattamente il pattern a due turni di r2 (stesso split 4+2, stesso ordine:
righe 34-37 poi 39-40) e infatti fa hit pieno sul prefisso di r2, non su
quello di r1.

**ETH.** r1 e r3 chiedono lo stesso insieme di 6 tool in un solo turno,
nello stesso ordine (`get_universe, get_asset_dossier, get_ohlcv,
get_funding, get_costs, get_rankings`: righe 10-15 per r1, righe 43-48 per
r3) e infatti il prefisso di r3 (171.454, riga 49) fa hit esatto su quello
scritto da r1 (171.454, riga 16). r2 invece chiede **solo 5 tool** in un
turno (righe 27-31: `get_asset_dossier, get_ohlcv, get_funding, get_costs,
get_rankings` — **manca `get_universe`**), e il suo prefisso totale è
171.289, **165 token in meno** — coerente con l'assenza del risultato di
`get_universe` (una lista dell'universo di 2 simboli, dell'ordine di
grandezza giusto per quella differenza). Il prefisso di r2 ETH non viene mai
riletto da nessuno: è l'unica delle 3 repliche a produrlo, quindi resta un
"orfano" — pagato per intero come scrittura senza alcun ritorno in giornata.

**Verifica degli id deterministici (fix c33fd0b).** Il fix
(`arena/runner.py:527-538`, `_deterministic_tool_id`) sostituisce l'id
assegnato dall'API con `toolu_det_` + i primi 32 caratteri di
`sha256({"name": nome, "args": argomenti, "index": posizione})`, quindi
l'id **non dipende più da nulla di non riproducibile**: a parità di
`(nome, argomenti, posizione)` l'id è sempre lo stesso, per costruzione,
indipendentemente da quale id l'API abbia assegnato quella volta. Non è
possibile leggere l'id effettivo dal jsonl (§0), ma il fatto che r3 BTC e r3
ETH raggiungano un **hit pieno** (creation=0, non parziale) sul prefisso di
un'altra replica conferma che il meccanismo funziona come progettato: se gli
id fossero ancora divergenti anche a parità di `(nome, argomenti, posizione)`
il prefisso non potrebbe combaciare byte a byte e non ci sarebbe mai hit
pieno. Le uniche divergenze osservate residue sono a monte degli id: nel
**numero e nell'insieme dei tool richiesti** (r2 ETH salta `get_universe`)
e nel **numero di turni in cui vengono richiesti** (r2/r3 BTC spezzano la
richiesta in due).

## 4. Verdetto: (A), divergenza di prefisso residua

Per ogni coppia di repliche dello stesso asset in cui una NON ha fatto hit
sull'altra, il prefisso totale (creation+read) **differisce numericamente**:
- BTC, r2 vs r1: 171.650 vs 171.665 (Δ 15)
- ETH, r2 vs r1: 171.289 vs 171.454 (Δ 165)

Un token count diverso implica contenuto diverso: non è possibile che due
prefissi byte-identici producano conteggi di token diversi. Questo esclude
(B) per questi due casi in modo diretto — (B), "mancata scrittura
fisiologica", richiede per definizione **stesso contenuto** e nondimeno un
mancato hit; qui il contenuto non è lo stesso, quindi il mancato hit ha una
causa concreta e non un semplice fallimento probabilistico della
scrittura lato server.

Specularmente, dove il contenuto **è** risultato identico (r3 BTC che
riproduce lo split di r2, r3 ETH che riproduce il turno unico di r1), la
rilettura è avvenuta **sempre**, in modo pieno (creation=0). Nella giornata 2
non c'è un solo caso di prefisso uguale con mancata rilettura: zero evidenza
per (B) in questi dati. Non si può escludere che (B) si manifesti in
altre giornate o in altre condizioni — i dati disponibili qui non lo
testano, perché ogni coppia "stesso contenuto" osservata ha fatto hit — ma
per la giornata 2 la causa delle 2 scritture in eccesso (4 osservate contro
2 ideali) è interamente spiegata da (A).

La causa profonda di (A) non è un bug residuo del fix: è **variazione
autentica del modello nel decidere quanti tool chiamare, quali, e in quanti
turni**, permessa (anzi imposta) da CLAUDE.md §10 — "Temperatura: default
operativo dell'API, nessun override, MAI 0" — che è un vincolo esplicito di
disegno, non una svista. Con sampling non deterministico, tre repliche dello
stesso asset possono ragionevolmente scegliere strategie di tool-calling
diverse (un turno vs due, includere `get_universe` o ometterlo perché già
noto da un'altra decisione) pur avendo lo stesso prompt e lo stesso
contesto byte per byte in ingresso.

## 5. Confronto con la giornata 1 (pre-fix): cosa il fix ha eliminato, cosa resta

Dati (`data/toolcalls/20260816T000019Z.jsonl`), stessa metodologia:

| decisione | esito | prefisso totale |
|---|---|---:|
| r1 BTC | scrittura | 171.481 |
| r1 ETH | scrittura | 171.317 |
| r2 BTC, 1° tentativo | scrittura | 171.648 |
| r2 BTC, 2° tentativo (nuova conversazione) | scrittura | 171.516 |
| r2 ETH | scrittura | 171.461 |
| r3 BTC | scrittura | 171.498 |
| r3 ETH | **rilettura piena** | 171.317 (hit su r1 ETH) |

Somma controllo: cache_creation = 5.422+166.059+165.895+166.226+166.094+
166.039+166.076 = **1.001.811**; cache_read = 5.422×12 + 171.317 = **236.381**
— entrambi coincidono col totale del rito riportato per la giornata 1.

**Cosa emerge in più rispetto al prompt.** Il jsonl del giorno 1 mostra
`r2` processare **due volte per intero** il ciclo ask→tool→submit per BTC
(righe 15-22, poi di nuovo 23-29) prima di passare a ETH — coerente con un
retry applicativo (`arena/runner.py:191-209`, `_process_asset`, che rilancia
`_one_conversation` da zero fino a `malformed_retries` volte, default `1`
in `arena/config.py:158`, cioè esattamente "un solo retry" di CLAUDE.md §8).
Il log del rito riporta comunque `malformati: 0` per il giorno 1, perché
quel contatore registra solo i verdetti **rifiutati in via definitiva**: un
retry che riesce al secondo tentativo non compare lì. Il jsonl non
persiste il motivo del primo fallimento (nessun campo lo cattura per un
tentativo interno riuscito al secondo giro), quindi non è possibile
confermare da qui se fosse un verbale malformato o un'altra causa
classificata dal parser — è un'ipotesi coerente con tutta l'evidenza
disponibile (posizione del secondo ciclo, config del retry) ma va segnalata
come tale, non come certezza.

**Cosa il fix (c33fd0b) ha eliminato.** Prima del fix, su 7 tentativi di
scrittura del blocco grande, solo **1** ha trovato un prefisso identico da
rileggere (14%). Dopo il fix, su 6 tentativi, **2** fanno hit (33%). La
causa dominante pre-fix — l'id assegnato dall'API a ogni `tool_use`, diverso
a ogni generazione anche a parità di tool/argomenti (diagnosticata nel
messaggio di c33fd0b) — è stata eliminata: gli id ora sono una funzione pura
di `(nome, argomenti, posizione)`, quindi non introducono più divergenza da
soli. Lo si vede indirettamente nel fatto che gli hit pieni esistono
affatto (pre-fix ce n'era comunque uno, su ETH r3≈r1: quella coppia aveva
evidentemente lo stesso pattern di tool-call **e**, per puro caso o perché
gli id in quel caso specifico erano comunque scesi identici, un prefisso
identico — un singolo caso non è decisivo da solo, ma il salto di hit-rate
14%→33% tra giornate con lo stesso identico pattern di divergenza sui tool
(BTC quasi sempre diverso, ETH a volte uguale) è coerente con "l'id era la
causa dominante, ora è sparita, resta la causa (A) di questo referto".

**Cosa resta, immutato dal fix.** La divergenza nel numero/insieme/ordine
dei tool richiesti dal modello — la causa (A) di questo referto — era già
presente il giorno 1 (si vedano i due tentativi di r2 BTC, con pattern di
tool-call diversi fra loro: 6 tool in un turno il primo tentativo, poi un
sottoinsieme diverso il secondo) e resta oggi. Il fix non l'ha toccata
perché non era il suo bersaglio: c33fd0b agisce solo sugli id, non sul
contenuto testuale o sulla struttura dei turni che il modello sceglie di
generare.

## 6. Rimedio per (A) — descritto, non implementato

Perché la cache del blocco grande faccia hit in modo affidabile fra
repliche dello stesso asset, il prefisso — inclusi i turni "ask" generati
dal modello — deve essere byte-identico. Con sampling non deterministico
(D4, non negoziabile) questo richiede che **il modello non abbia più
margine di scelta su quanti/quali tool chiamare e in quanti turni**, oppure
che i turni "ask" scompaiano del tutto dal prefisso cacheato.

Due direzioni possibili, entrambe fuori portata di questo rito:

1. **Istruire esplicitamente il modello a richiedere tutti i tool in un
   solo turno, in un ordine fisso.** Cambierebbe il testo del prompt/persona
   (system o context file): tocca direttamente "cosa il Trader vede",
   proibito durante S0 (§5 del pre-registro) e da CLAUDE.md §2/§4. Andrebbe
   proposto come release versionata per PREREG_LAB_S1 (nuovo `prompt_sha`,
   nuovo segmento di track record).

2. **Pre-eseguire tutti i tool deterministici (dossier, ohlcv, funding,
   costs, rankings, universe) fuori dal ciclo agentico e presentarli già
   nel primo turno utente**, lasciando al modello solo la scelta finale
   (`submit_decision`). Non tocca il testo del system prompt, ma cambia
   sostanzialmente **cosa e come il Trader riceve i dati** e **quali
   decisioni di tool-uso gli restano da prendere** — un cambiamento del
   protocollo agentico, non solo un dettaglio di trasporto. Rientra
   comunque, nello spirito di CLAUDE.md §2/§4, fra le cose che alterano il
   comportamento osservabile del Trader durante una decisione: stesso
   trattamento del punto 1, da versionare e aprire in PREREG_LAB_S1, non da
   introdurre a Stagione 0 in corso.

Nessuna delle due opzioni è un fix "solo caching": il confine cacheabile
(l'ultimo `tool_result` prima del submit) è definito dal contenuto che il
modello stesso genera nei turni intermedi, quindi qualunque intervento che
lo renda riproducibile agisce, per costruzione, su cosa il Trader vede o
su come decide — non su un dettaglio di trasporto isolabile dal resto.
Per la durata di S0, il divario residuo (~2 scritture in eccesso su 6
decisioni/giorno, ordine di qualche USD/giorno) va quindi accettato come
costo strutturale del disegno attuale, non come un difetto da correggere
in corsa.
