# Preventivo vincolante del RUN2 — metodo, misure, proposta

**Data**: 2026-08-20 · **Repo**: `traderLab` · **Commit di riferimento**: `5adf0e0`
**Origine**: rito T2, passi 7-9. **Modello**: `claude-opus-5` (TL-007).

Questo documento fissa **quanto costa una giornata del rito** con la
configurazione che il RUN2 userà davvero, e da dove viene ogni cifra. I valori
qui dentro **non entrano in nessun manifest**: entrano al rito del pin, per
firma dell'owner.

## 0. Perché è un'evidenza pre-registrata

Il metodo — ricostruire la sequenza *dalla via del codice*, contare ogni
prefisso distinto con `count_tokens`, prendere i token di output dalla
distribuzione osservata dichiarandola stima, e applicare il listino letto
dalla pagina ufficiale — è stato **dichiarato nel prompt del rito prima che
esistesse un solo numero**. Nessuna misura è stata scelta dopo aver visto il
risultato, e nessuna è stata scartata. Le due sole scelte fatte a valle sono
dichiarate come tali: quale cammino di tool considerare modale (§2) e quali
due scenari di cache calcolare (§5).

---

## 1. Sha degli input

Tutto ciò che segue è misurato su questi byte esatti.

| Ingresso | sha256 |
| --- | --- |
| `agents/trader_v0/system_prompt.md` | `7ccf9dc4fcecdd72dc122d522a73a97697b4d15ad9d9d8b33a9c2bdbfb6d4177` |
| `agents/trader_v0/persona.md` | `d4680c6401daeb1f83c45ce5a1e5eefcc6d20edf526ea4439ceb6fd989ad0de3` |
| system prompt **reso** (quello che il modello riceve) | `4c90d17e3e7f1cf4aaba8047ac44f82fa7d40131972e6ee1a1fa5ab4b94d2c1d` |
| schemi dei tool (`all_tool_schemas`) | `d3accf7fe0cae5391f876f73fe99d6850f79e21c8aad7d77d56d6f18278c894f` |
| `snapshot_id` dello snapshot fresco | `7b7919358241df007b9314e2e5b3ab35d6ef23414577d4aad1375e4b975a2e70` |
| file dello snapshot su disco (852 933 byte) | `108e44ef19616a1c16568eaec478155b7a773ebf70e6249a48cc381c0affef3f` |

Lo `snapshot_id` **ricalcolato dal contenuto** coincide con il nome del file:
lo snapshot non è stato toccato dopo la costruzione.

### 1.1 Lo snapshot, in chiaro

Costruito con `scripts/build_snapshot.py` il 20/08/2026, rete verso
Hyperliquid in **sola lettura**, un solo prelievo.

| Campo | Valore |
| --- | --- |
| `asof_utc` | `2026-08-20T00:00:00+00:00` |
| universo | `BTC`, `ETH` |
| `universe_status` | `pre_screen_ufficiale` |
| barre OHLCV per asset | 120 |
| punti di funding per asset | **2 880** (120 giorni × 24 ore) |
| `depth_usd_1pct` | 250 000,0 USD, entrambi gli asset |
| `depth_source` | `costante_dichiarata`, entrambi gli asset |
| `estimator` | `hyperliquid_impact_px_v0`, entrambi gli asset |
| `spread_bps` BTC / ETH | 0,7203 / 0,4424 |

I 2 880 punti di funding sono la voce che domina tutto il costo: da soli
valgono circa 165 000 token del prefisso decisionale (§3).

Questa è **la configurazione vera**, etichetta `depth` inclusa: lo snapshot è
stato costruito dal builder corrente, quello che scrive `depth_source`, e i
tool lo servono con la chiave `depth_usd_1pct_declared` introdotta in questo
stesso rito.

---

## 2. La sequenza di una giornata, ricostruita dalla via del codice

### 2.1 Cosa dice il codice

- `arena/runner.py::run_day` — per **ogni** `replica_id` in
  `DEFAULT_REPLICA_IDS = ("r1", "r2", "r3")`, per **ogni** asset in
  `sorted(snapshot.universe)` = `("BTC", "ETH")`, una conversazione isolata:
  client nuovo, lista di messaggi nuova, nessun contesto condiviso.
  **6 conversazioni al giorno.**
- `arena/runner.py::_one_conversation` — ciclo agentico fino a
  `max_tool_iterations = 10`. Ogni giro: una chiamata al modello; se la
  risposta porta `tool_use` diversi da `submit_decision`, si appende un turno
  assistente con i **soli** blocchi `tool_use` (rimedio B.3,
  `only_tool_use=True`) con id deterministici (`_deterministic_tool_id`), poi
  un turno utente con i `tool_result`. Il ciclo termina quando compare
  `submit_decision`.
- `arena/llm_client.py::complete` — payload a **cinque chiavi**: `model`,
  `max_tokens`, `system`, `messages`, `tools`. Nessun `temperature`/`top_p`/
  `top_k` (D4), nessun `thinking` (§A.7, confermato dalla sonda del §7),
  nessun `fallbacks` (CLAUDE.md §10).
- Marcatori di cache (`cache_control: {"type": "ephemeral"}`, **TTL 5 minuti**,
  il default del client): (1) il blocco `system`; (2) l'ultima definizione di
  tool; (3) l'ultimo `tool_result` dell'ultimo messaggio utente, quando
  esiste. Al primo turno il terzo marcatore non c'è: il messaggio utente sta
  **dopo** l'ultimo marcatore ed è quindi input non cacheato.

### 2.2 Il cammino di tool, dai dati

Il numero di turni non è deciso dal codice: lo decide il modello. La sola
misura disponibile su `claude-opus-5` con **questo stesso protocollo** (turno
echo normalizzato, B.3) è il rito di elicitation del 18/08: 100 chiamate, 300
turni, risposte grezze persistite.

| Reperto | Valore |
| --- | --- |
| conversazioni analizzate | 100 |
| numero di turni | **3 su 100 chiamate su 100** |
| cammino di tool | `get_universe` + `get_asset_dossier`, poi `get_ohlcv` + `get_funding`, poi `submit_decision` — **100 su 100** |
| argomenti identici (`bars=60`) | **96 su 100** (3 con `bars=70`, 1 con `bars=90`) |

Forma dei tre turni, 87 volte su 100:

| Turno | Blocchi della risposta | Tool chiamati |
| --- | --- | --- |
| 1 | `text`, `tool_use`, `tool_use` | `get_universe`, `get_asset_dossier` |
| 2 | `thinking`, `tool_use`, `tool_use` | `get_ohlcv`, `get_funding` |
| 3 | `thinking`, `text`, `tool_use` | `submit_decision` |

Le 13 varianti restanti differiscono solo per la presenza del blocco
`thinking` al turno 2 (10 casi) o per un turno 3 che non chiama
`submit_decision` (3 casi: verbale mancante).

**Scelta dichiarata**: il preventivo usa il cammino modale (`bars=60`). Le
varianti cambiano il prefisso decisionale di poche centinaia di token su
171 000 — meno dello 0,2% — e non spostano nessuna cifra di questo documento.

**Limite dichiarato**: il rito di elicitation girava su **BTC soltanto**, su
snapshot del 17 e 18/08, e con TTL di cache a **1 ora** invece dei 5 minuti
del runner. Il cammino di tool e i token di output si trasferiscono; la
struttura di cache **no**, ed è ricalcolata da zero al §5.

### 2.3 I prefissi distinti

Poiché il turno echo porta i soli `tool_use` con id deterministici, il
prefisso di una richiesta è funzione di `(asset, turno)` e **non** della
replica né della generazione: è esattamente ciò che il rimedio B.3 è servito
a ottenere. Da qui: **6 prefissi distinti al giorno**, non 18.

---

## 3. Tabella `count_tokens`

Endpoint `POST /v1/messages/count_tokens`, `model="claude-opus-5"`, payload
composto dallo stesso codice del runner (`_cached_system`, `_cached_tools`,
`_cached_messages`) sullo snapshot del §1.

| Prefisso | token di input |
| --- | ---: |
| `system` + definizioni dei tool (misurato con un messaggio utente di 1 carattere, meno quel carattere) | **5 491** |
| BTC — turno 1 | **5 558** |
| BTC — turno 2 | **6 218** |
| BTC — turno 3 (decisionale) | **171 006** |
| ETH — turno 1 | **5 558** |
| ETH — turno 2 | **6 220** |
| ETH — turno 3 (decisionale) | **170 807** |

Da cui il messaggio utente iniziale: `5 558 − 5 491` = **67 token**, identico
per i due asset (`BTC` ed `ETH` costano lo stesso numero di token).

Il salto fra turno 2 e turno 3 — **circa 164 700 token** — è il `tool_result`
di `get_funding`: i 2 880 punti orari del §1.1.

**Il conteggio è gratuito.** La pagina ufficiale del token counting dichiara:
«Token counting is **free to use** but subject to requests per minute rate
limits based on your usage tier». Le sei righe di questa tabella non hanno
prodotto spesa.

**Il conteggio è una stima, e lo dichiara.** Stessa pagina: «The token count
is an **estimate**. In some cases, the actual number of input tokens used when
creating a message might differ by a small amount». Riscontro indipendente sui
`usage` realmente fatturati nel rito di elicitation, stesso protocollo:

| Grandezza | `count_tokens` (oggi) | fatturato (elicitation, 18/08) | scarto |
| --- | ---: | ---: | ---: |
| prefisso turno 1 | 5 558 | 5 687 (5 547 in cache + 140 input) | −2,3% sul fatturato |
| prefisso turno 2 | 6 218 | 6 262 | −0,7% |
| prefisso turno 3 | 171 006 | 171 058 | −0,03% |

Sui due prefissi che contano — quelli grandi — l'accordo è entro l'1%. Lo
scarto del turno 1 vale 129 token su una giornata da oltre un milione: è
dentro il rumore di questo preventivo e non viene corretto.

---

## 4. Listino, trascritto dalla pagina ufficiale

**Fonte**: `https://platform.claude.com/docs/en/about-claude/pricing`
(raggiunta da `https://docs.claude.com/en/docs/about-claude/pricing`, che vi
redirige con 302). **Letta il**: 2026-08-20. Riga «Claude Opus 5», valori
copiati come stampati.

| Voce | Prezzo |
| --- | --- |
| Base Input Tokens | **$5 / MTok** |
| 5m Cache Writes | **$6.25 / MTok** |
| 1h Cache Writes | **$10 / MTok** |
| Cache Hits & Refreshes | **$0.50 / MTok** |
| Output Tokens | **$25 / MTok** |

Moltiplicatori dichiarati dalla stessa pagina: scrittura in cache a 5 minuti
**1,25×** l'input, scrittura a 1 ora **2×**, lettura da cache **0,1×**. Il
client del Lab non specifica `ttl`, quindi usa il default a 5 minuti: il
prezzo di scrittura applicabile è **$6.25 / MTok**.

Voci della stessa pagina che **non** si applicano qui, dette per completezza:
Batch API (−50%, non usato: le sessioni sono interattive), fast mode
($10/$50, non usato), `inference_geo: "us"` (×1,1, non usato).

**Confronto col listino usato finora.** `ledger/spend.py` contiene ancora il
listino di **Claude Fable 5** ($10 / $50), coerente col pin di TL-002 e non
con quello di TL-007. Vedi il §8, punto 1.

---

## 5. Costo di una giornata

### 5.1 Il modello di fatturazione

Ogni richiesta si scompone in tre voci: i token **dopo** l'ultimo marcatore di
cache (input pieno), i token del prefisso **trovato** in cache (lettura), e i
token del prefisso **scritto** in cache (scrittura). Ordine di esecuzione del
runner: `r1-BTC`, `r1-ETH`, `r2-BTC`, `r2-ETH`, `r3-BTC`, `r3-ETH`.

Due scenari, entrambi calcolati.

**CALDO** — il prefisso sopravvive da una replica alla successiva. La cache
`ephemeral` dura 5 minuti e ogni lettura ne rinnova la scadenza (la colonna
del listino si chiama «Cache Hits **& Refreshes**»); fra due usi dello stesso
prefisso passano **due** conversazioni. Durata di una conversazione misurata
nell'elicitation: mediana **77 s**, P90 **92 s**, massimo 301 s. Il divario
tipico è quindi 154 s (P90: 184 s) contro un TTL di 300 s.

**FREDDO** — nessun prefisso sopravvive e ogni conversazione riscrive tutto.
È il caso peggiore realistico: giornata lenta, errori transitori con backoff
lungo, esecuzione non consecutiva.

### 5.2 Token per giornata

| Voce | CALDO | FREDDO |
| --- | ---: | ---: |
| input pieno | 402 | 402 |
| output | 29 079 | 29 079 |
| letture da cache | **759 377** | 70 260 |
| scritture in cache | **336 322** | **1 025 439** |

### 5.3 Token di output — **STIMA DICHIARATA**

Questa è l'unica voce che non è misurata sulla configurazione di oggi, ed è
marcata stima per questo.

**Fonte**: `usage.output_tokens` delle 100 conversazioni del rito di
elicitation su `claude-opus-5`, 18/08/2026 (referto
`ELICITATION_OPUS_REPORT.md`, dati grezzi in
`scratchpad/elicitation/call_*.json`, gitignorati).

| Percentile | token di output per conversazione |
| --- | ---: |
| minimo | 2 903 |
| **P10** | **4 361** |
| P25 | 4 650 |
| **mediana** | **4 846** |
| media | 4 851 |
| P75 | 5 132 |
| **P90** | **5 397** |
| massimo | 6 025 |

Ripartizione per turno (mediane): turno 1 **102**, turno 2 **200**, turno 3
**4 540**. Il verbale è quasi tutto il costo di generazione.

**Perché tutte e 100 e non le sole forme A e D.** Le forme B, C ed E del rito
di elicitation cambiavano lo schema del campo di confidence, quindi non sono
il verbale del RUN2. Sulle sole A+D (n=40) la mediana è **4 920** invece di
4 846, cioè +1,5%: la differenza sposta il costo giornaliero di meno di $0,02.
Ho usato tutte e 100 per avere un campione più largo, e dichiaro qui il valore
alternativo.

Il punto usa la **mediana**; la banda usa **P10** e **P90**.

### 5.4 Costo

| Scenario | punto (mediana output) | banda P10 – P90 |
| --- | ---: | --- |
| **CALDO** | **$3,2107 / giorno** | $3,1378 – $3,2932 |
| **FREDDO** | **$7,1731 / giorno** | $7,1002 – $7,2557 |

Per conversazione: **$0,5351** (caldo), **$1,1955** (freddo).

**La banda P10-P90 non è l'incertezza principale, e sarebbe disonesto
presentarla come tale.** Vale ±2,4%, perché l'output è solo il 23% del costo
nello scenario caldo. L'incertezza che conta è **quale scenario di cache si
verifica**, e vale **2,2×**.

### 5.5 Verifica del modello contro spesa reale

Il modello non è una congettura: riproduce spese misurate.

| Caso misurato | Misurato | Modello | Scarto |
| --- | ---: | ---: | ---: |
| conversazione a cache calda, TTL 1h (elicitation, test 2 e 3) | $0,2154 e $0,2028 | $0,2129 | entro il 6% |
| conversazione a cache fredda, TTL 1h (elicitation, test 1) | $1,7809 | $1,8370 | +3,1% |

Le stesse formule, con il prezzo di scrittura a 5 minuti al posto di quello a
1 ora, danno i numeri del §5.4.

### 5.6 Confronto con la Stagione 0

Spesa **reale** delle tre giornate di S0, ricalcolata dai log delle tool call
(`data/toolcalls/*.jsonl`, gitignorati; i numeri sono trascritti qui perché
sopravvivano al clone). S0 girava su `claude-fable-5` **e** con il runner
precedente al rimedio B.3.

| Giornata | input | output | letture | scritture | costo al listino Fable | gli stessi token al listino Opus |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 16/08 | 994 | 22 402 | 236 381 | 1 001 811 | **$13,89** | $6,94 |
| 17/08 | 856 | 20 261 | 405 606 | 669 792 | **$9,80** | $4,90 |
| 18/08 | 1 004 | 23 010 | 271 268 | 997 670 | **$13,90** | $6,95 |

Due letture di questa tabella.

1. **La stima di TL-007 («circa $4,90 al giorno») veniva dal giorno più
   economico dei tre.** Sugli altri due lo stesso calcolo dà $6,94 e $6,95. La
   voce dichiarava un'incertezza del ±20%: lo scarto reale fra le tre giornate
   è del ±17%, dentro quella dichiarazione, ma il valore centrale era il
   minimo e non la mediana.
2. **Lo scenario FREDDO del RUN2 ($7,17) è quasi identico ai giorni di S0
   ricalcolati al listino Opus.** Ha senso: un RUN2 in regime freddo riscrive
   la cache tanto quanto la riscriveva S0 senza il rimedio B.3. Il guadagno
   del rimedio è **tutto** nel regime caldo, dove il costo scende di **2,2×**
   rispetto al giorno peggiore di S0.

---

## 6. Proposta

Il preventivo si scrive su **28 giornate**, non su 42: 42 è il **cap di
calendario** del verbale RUN2 §A.8, cioè un limite, non una previsione.

| | Valore |
| --- | --- |
| `season_expected_days` | **28** |
| giornaliero, punto (scenario caldo) | **$3,2107** |
| **`season_budget_usd` = giornaliero × 28** | **$89,90** |
| soglia dura (`HARD_STOP_MULTIPLIER` = 1,5×) | **$134,85** |

**Perché 1,5 × 28 = 42 è il punto giusto.** Con questi due numeri la soglia
dura si tocca esattamente al **giorno 42** se la stagione spende come
previsto — cioè nello stesso istante in cui scade il cap di calendario. Stop
economico e stop di calendario si incontrano invece di contraddirsi: nessuno
dei due può interrompere la stagione prima dell'altro senza che qualcosa sia
andato diversamente dal previsto.

### 6.1 L'avvertenza che va letta prima di firmare

Se il RUN2 girasse in regime **freddo**, la soglia dura verrebbe toccata al
**giorno 18,8** e la stagione si fermerebbe da sola a metà. Non è un difetto
della guardia: è la guardia che funziona. Ma va saputo **prima**, non
scoperto al giorno 19.

Alternativa prudenziale, offerta all'owner e **non** raccomandata al posto
della proposta: preventivo sulla media dei due scenari, $5,1919/giorno →
`season_budget_usd` = **$145,37**, soglia dura $218,06, che in regime freddo
regge fino al giorno 30,4. Il prezzo di questa scelta è una guardia più lenta
ad accorgersi di uno sfondamento vero.

**La scelta è dell'owner e si firma al rito del pin.** Nessuno di questi
numeri è stato scritto in un manifest da questo rito.

### 6.2 Cosa il preventivo NON copre

- Le giornate **fallite**: un errore transitorio con ritentativi paga i turni
  già consumati e non produce verbale. Il modello conta solo giornate
  riuscite.
- I **rifiuti del modello**: `stop_reason="refusal"` prima di qualunque output
  non è fatturato, ma i turni precedenti della stessa conversazione sì.
- I riti di **manutenzione** (sonde, diagnosi, prove): stanno sulla riga di
  spesa del rito, non su quella della stagione.

---

## 7. Sonda `budget_tokens` — chiude CODA voce 16

**Domanda**: `thinking.budget_tokens` è accettato su `claude-opus-5`, e con
quale minimo?

**Protocollo**: quattro chiamate reali, `max_tokens` minimo sensato, prompt di
quattro parole. Una chiamata rifiutata con 400 non viene fatturata.

| # | Payload | Esito | Messaggio **verbatim** |
| --- | --- | --- | --- |
| 1 | `thinking={"type":"enabled","budget_tokens":400}`, `max_tokens=2000` | **400** | `thinking.enabled.budget_tokens: Input should be greater than or equal to 1024` |
| 2 | `thinking={"type":"enabled","budget_tokens":1024}`, `max_tokens=2000` | **400** | `"thinking.type.enabled" is not supported for this model. Use "thinking.type.adaptive" and "output_config.effort" to control thinking behavior.` |
| 3 | `thinking={"type":"enabled","budget_tokens":16000}`, `max_tokens=32000` | **400** | identico al #2 |
| 4 | **controllo**: nessun `thinking`, `max_tokens=64` | **200** | — (20 token di input, 4 di output, `stop_reason="end_turn"`) |

Tutti e tre i rifiuti con `type: "invalid_request_error"`. `request_id`:
`req_011CeD8SxtVPUd5GwwFutTkS`, `req_011CeD8SyxESK4yeZcEkB4ri`,
`req_011CeD8T16CG8rpq3cC512Wm`.

### Risposta, e perché la sequenza andava fatta in quest'ordine

**Non esiste un `budget_tokens` minimo accettato su `claude-opus-5`: non
esiste un `budget_tokens` accettato, punto.**

La chiamata #1 da sola avrebbe indotto in errore: il messaggio parla di un
minimo di 1024 e sembra dire «alza il valore». È una validazione di **schema**,
che scatta prima del controllo di supporto del modello. Le chiamate #2 e #3 lo
smentiscono: a 1024 e a 16000 il rifiuto cambia messaggio e dice che è la
**forma** `thinking.type: "enabled"` a non essere supportata, non il valore. Se
il rito si fosse fermato al #1, la voce si sarebbe chiusa con la risposta
sbagliata.

La #4 chiude il ragionamento dal lato opposto: lo stesso payload, tolto il
solo parametro sotto esame, passa. Il rifiuto è del parametro, non della
chiamata.

**Conseguenze.**

1. La scelta del client — **non inviare** `thinking` — è confermata come
   l'**unica** forma valida, e la dichiarazione
   `thinking_declared = always_on_param_omitted` del Freeze manifest descrive
   un vincolo dell'API, non una preferenza.
2. `thinking_tokens` resta `None` nella telemetria: l'API non espone un
   contatore separato del ragionamento, e i token di ragionamento restano
   indistinguibili da quelli del verbale dentro `output_tokens`. Il campo è
   già pronto ad accoglierne il valore se un giorno esisterà.
3. L'API indica `output_config.effort` come leva sostitutiva. **Non
   adottata**: sarebbe una variabile in più fra S0 e RUN2, e il RUN2 ne ha già
   tre (modello, protocollo di chiamata, etichetta `depth`). Va registrata
   come opzione per una stagione successiva, non presa qui.

**Spesa della sonda**: **$0,000200** — una sola chiamata fatturata su quattro.

---

## 8. Cosa questo documento lascia aperto

1. **`ledger/spend.py` porta ancora il listino di Fable** ($10/$50), non
   quello di Opus 5 ($5/$25) del §4. Le due guardie economiche calcolano
   quindi una spesa **doppia** di quella vera: la soglia dura scatterebbe alla
   metà del preventivo firmato. È un errore nella direzione prudente, non in
   quella pericolosa, ma è un errore: va corretto **prima** del rito del pin,
   perché un preventivo di $89,90 confrontato con una spesa contata al doppio
   si comporta come un preventivo di $44,95. Non l'ho corretto in questo rito:
   il rito non lo elencava fra i passi, e cambiare i prezzi cambia il
   comportamento di entrambe le guardie.
2. **Il terzo ancoraggio OTS non è nel controllo settimanale.**
   `scripts/morning_check.py::DEFAULT_OTS_TARGETS` contiene due dei tre file
   timbrati; `MANIFEST_S0.json` manca. Conseguenza misurata in questo rito: il
   suo `.ots` era rimasto **pending su tutti e quattro i calendar** mentre gli
   altri due erano già confermati su Bitcoin.
3. **La stima dell'output è di un altro giorno e di un altro asset.** Viene da
   BTC sugli snapshot del 17-18/08. Il primo giorno reale del RUN2 la
   sostituisce con una misura.
4. **Il regime di cache non è deciso, è ipotizzato.** Il primo giorno reale
   dice quale dei due scenari del §5 vale, guardando
   `cache_creation_input_tokens` nel log delle tool call: vicino a 336 000
   significa caldo, vicino a 1 025 000 significa freddo.
5. **I 2 880 punti di funding sono il 96% del prefisso decisionale.** Ridurli
   sarebbe la leva di costo più grande disponibile, e cambierebbe **cosa il
   Trader vede**: è una decisione di disegno, non di budget, e non si prende
   dentro un rito di preventivo.
