# DECISION_LOG — Trader Lab

Registro delle decisioni strutturali del Lab. Ogni voce è immutabile: una
decisione che cambia si supera con una voce nuova, non si riscrive.

| Voce | Oggetto | Stato |
| --- | --- | --- |
| TL-001 | D1-D4 e build minimale di Fase 0 | attiva, **D2 superata da TL-002** |
| TL-002 | Pin su Claude Fable 5 · soglie di regressione | attiva, **Decisione 1 (pin) superata da TL-007** |
| TL-003 | Stagione 0 autorizzata | attiva |
| TL-004 | Fix caching applicato dentro la stagione, in chiave ripristino | attiva |
| TL-005 | Lettura dichiarata del §5 (tetto token): LETTERALE | attiva |
| TL-006 | Stagione 0 chiusa anticipatamente per allocazione di budget | attiva |
| TL-007 | Pin su Claude Opus 5 · supera il pin di TL-002 | attiva |
| TL-008 | `max_tokens` = 8.000 · supera i 32.000 dichiarati in TL-002 | attiva |
| TL-009 | Ancoraggi OTS di S0 · ratifica della via (b): si annota, non si riscrive | attiva |

---

## TL-002 — D2 superata: modello pinnato = Claude Fable 5 · soglie fissate

- **Data**: 2026-08-13
- **Stato**: attiva
- **Decisa da**: l'owner (modello direttamente; soglie per delega)
- **Supera**: la **D2** di TL-001. D1, D3 e D4 restano invariate.

### Decisione 1 — Il Trader è pinnato su `claude-fable-5`

Il Lab testa "un agente LLM sa battere la macchina?": la domanda merita il
cervello più forte disponibile. Se fallisce il modello di punta, il verdetto
pesa sul concetto, non sulla scelta del modello. Il pin non era mai stato
effettuato e nessuna stagione è partita: il cambio è pulito, non c'è track
record da spezzare.

**Model string.** `claude-fable-5` è la forma **più specifica disponibile**:
come per la Sonnet, non esiste una variante datata e un suffisso data produce
404. Verificato localmente contro l'unione di ID dell'SDK installato; da
ri-verificare contro l'endpoint il giorno del pin con `scripts/verify_pin.py`.

**Conseguenze tecniche del modello, gestite in codice.** Fable non è un
Sonnet con un nome diverso: cambia il contratto di chiamata.

| Vincolo di Fable | Effetto sul Lab |
| --- | --- |
| Sampling (`temperature`, `top_p`, `top_k`) **rimosso**: inviarlo è 400 | **D4 ri-verificata e confermata**: la policy resta identica e diventa l'unica chiamata valida |
| Thinking **sempre attivo**; `disabled` e `budget_tokens` sono 400 | `thinking_policy=api_default` è l'unico valore ammesso; il client rifiuta gli altri |
| Il thinking consuma lo stesso `max_tokens` della risposta | `DEFAULT_MAX_TOKENS` alzato a 32.000: un tetto tarato su un modello senza thinking troncherebbe la risposta |
| Turni lunghi (minuti) | Il client **streamma di default**, con timeout esplicito a 900s |
| `stop_reason="refusal"` con HTTP 200 | Categoria propria (`model_refusal`), separata dai verbali malformati, e **non ritentata** |
| Richiede 30 giorni di data retention | **Precondizione da verificare**: con l'organizzazione in zero-data-retention *ogni* chiamata risponde 400 |
| Prezzo di listino più alto | Il budget guard giornaliero smette di essere una formalità |

**Fallback server-side: deliberatamente NON attivo.** La guida generale
dell'API consiglia di attivare `fallbacks` su Fable, perché un rifiuto verrebbe
servito da un altro modello nella stessa chiamata. Qui sarebbe **dannoso**:
significherebbe che parte del track record è prodotta da un modello diverso da
quello pinnato, in silenzio — esattamente ciò che D2 vieta. Un rifiuto deve
restare un rifiuto: visibile, loggato, contato.

### Decisione 2 — Soglie della suite di regressione (chiude i 4 TODO-owner)

Regola fissata dall'owner, applicata **meccanicamente** da
`arena.regression.thresholds_from_baseline`:

| Soglia | Regola |
| --- | --- |
| `agreement_alarm` | `baseline − 0.15`, pavimento `0.70` |
| `agreement_sunset` | `baseline − 0.30`, pavimento `0.50` |
| `confidence_alarm` | `+0.10` (distanza assoluta) |
| `confidence_sunset` | `+0.20` (distanza assoluta) |

I valori assoluti si scrivono in `arena/config.py` il giorno della baseline.
`ThresholdDerivation.as_config_literal()` li produce già formattati, così
l'applicazione è meccanica anche nella trascrizione.

**Due punti di interpretazione, dichiarati perché non erano nel testo.**

1. **"baseline" = auto-accordo della baseline** (`Baseline.self_agreement_rate`):
   la quota di campioni che concordano con l'azione modale del proprio
   snapshot, mediata. È l'unica quantità misurata disponibile ed è quella
   giusta — non si può pretendere dal modello più accordo di quanto ne abbia
   con se stesso a parità di input. Se l'intenzione era applicare la regola a
   1.0 (accordo perfetto per definizione), le soglie sarebbero fisse a 0.85 e
   0.70: è una riga di codice, ma è una scelta dell'owner.
2. **Il pavimento può mordere.** Con auto-accordo ≤ 0.85 il pavimento 0.70 è
   più severo di `baseline − 0.15`; con auto-accordo ≤ 0.70 la suite andrebbe
   in allarme sul comportamento **di baseline**. Non è un caso teorico con k=5.
   La derivazione lo rileva ed espone `floor_binds` / `is_degenerate` invece di
   produrre in silenzio una configurazione che suona l'allarme il primo giorno.

**Cosa cambia nella pre-registrazione.** Prima le soglie assolute dovevano
precedere la baseline; ora si *derivano* da essa. L'artefatto pre-registrato
diventa quindi la **regola**, la cui impronta (`threshold_rule_fingerprint`)
viene incisa nella `Baseline` al momento della raccolta. Se la regola cambia
dopo aver visto i dati, `evaluate(report, baseline=...)` solleva
`ThresholdRuleChanged`. Senza questo, "derivare dalla baseline" sarebbe stata
una scorciatoia per scegliere le soglie a posteriori.

### Cosa questa voce NON decide

- Il pin **non è ancora effettuato**: `ots_pending` resta `True` e serve
  l'autorizzazione dell'owner più il timestamping OTS.
- La configurazione di data retention dell'organizzazione.
- L'universo, la gamba meccanica, il PREREG_LAB_S0, la data di avvio.

---

## TL-001 — Decisioni owner congelate e build minimale di Fase 0

- **Data**: 2026-08-13
- **Stato**: attiva
- **Contesto**: apertura del repo `traderLab` come cantiere separato da
  `zeroPipes`. Base di evidenza:
  `docs/research/2026-08_AGENT_FAITHFULNESS_FRAMEWORKS_LITERATURE.md`
  (verdetto Q5: **build-minimal-first + steal patterns**, non adottare
  TradingAgents come scheletro).

### Le quattro decisioni dell'owner (congelate, non riaperte)

**D1 — Tre repliche identiche.**
Tre repliche dello stesso Trader: stesso modello, stesso prompt, stessa
temperatura, stesso snapshot del mondo. Nessuna variante di prompt, nessuna
diversificazione dei ruoli.
*Motivazione*: la self-consistency tra repliche è un test **necessario ma non
sufficiente** per la fedeltà (Parcalabescu & Frank, ACL 2024). Serve a
misurare la dispersione, che è il denominatore del confronto agente-macchina.
*Implementazione*: `arena/runner.py` lancia le repliche in isolamento; il test
`test_arena.py::test_input_byte_identici_tra_repliche` verifica che ricevano
input byte-identici.

**D2 — Modello pinnato: Claude Sonnet via API Anthropic.**
⚠️ **SUPERATA da TL-002**: il modello pinnato è ora `claude-fable-5`. Il
principio resta valido e invariato — model string più specifica disponibile,
registrata nel Freeze manifest, **cambio modello = nuovo track record**.
*Testo originale, conservato per storia*: si usa la model string più specifica
disponibile al momento del pin. Al 2026-08-13 la più specifica per la Sonnet
corrente era `claude-sonnet-5`; non esiste una variante datata e un suffisso
data produce 404. Il pin non era stato effettuato, quindi TL-002 ha potuto
cambiare modello senza spezzare alcun track record.

**D3 — Stagione 0: 4 settimane shadow a size fissa.**
Il Trader decide **solo direzione e dentro/fuori**. La size è imposta dal Risk
Officer al valore fisso di config. Il campo `confidence` si logga **dal giorno
uno** per il Brier score, anche se non muove la size.
*Conseguenza sul Risk Officer*: la normalizzazione alla size fissa è l'unica
eccezione dichiarata all'invariante "il Risk Officer può solo ridurre" — la
size non è una variabile del Trader, quindi normalizzarla non è concedere
rischio discrezionale. Documentato in `contracts/risk.py`.

**D4 — Temperatura: default operativo dell'API, nessun override, MAI 0.**
Ogni parametro di sampling è dichiarato nel Freeze manifest.
*Constatazione tecnica emersa in build*: sui modelli Claude Sonnet correnti i
parametri di sampling non-default (`temperature`, `top_p`, `top_k`) sono
**rifiutati dall'API con errore 400**. Il default operativo si ottiene quindi
**per omissione**: il client non invia affatto quei campi. Il manifest lo
registra come `sampling_policy="api_default_omitted"` con i tre campi a `None`,
così che "default dell'API" non venga mai confuso con "0" o con "non
registrato". Un `temperature=0` esplicito è rifiutato dal contratto stesso.
*Ri-verifica su Fable (richiesta da TL-002)*: **confermata, policy identica**.
Su `claude-fable-5` i parametri di sampling sono rimossi allo stesso modo, e
inviarli produce 400. La verifica operativa contro l'endpoint è automatizzata
in `scripts/verify_pin.py`, da eseguire il giorno del pin.

### Cosa è stato costruito con questa voce

Fase 0, blocchi 1-6: contratti Pydantic v2, Tool Server su snapshot congelato,
enforcement del Decision Record, Risk Officer, ledger con hash-chain,
telemetria, e-process, orchestratore delle 3 repliche, scheletro della suite di
regressione comportamentale. Tutto shadow, nessun ordine reale, nessuna chiave
di wallet.

### Cosa questa voce NON decide

- L'universo definitivo (spetta al Pre-Screen in `zeroPipes`).
- Le soglie di allarme e sunset della suite di regressione (TODO-owner,
  da fissare **prima** della raccolta della baseline).
- La gamba meccanica del confronto appaiato.
- La data di avvio della Stagione 0.

---

## TL-003 — Stagione 0 autorizzata

- **Data**: 13/08/2026
- **Decisione**: l'owner autorizza l'avvio della Stagione 0 con la firma
  esplicita "Stagione 0: via" (PREREG_LAB_S0 §8, commit 9ef5681, manifest
  timbrato OTS in b1ee4d8); primo giorno atteso: 14/08/2026 00:00 UTC via
  task schedulato collaudato (exit 0x2 alla prova di cablaggio).
- **Decisa da**: l'owner.

---

## TL-004 — Fix caching applicato dentro la stagione, in chiave ripristino

- **Data**: 2026-08-17 (applicato fra la giornata 1 e la giornata 2)
- **Stato**: attiva
- **Commit**: c33fd0b
- **Decisa da**: l'owner.

**Natura**: RIPRISTINO del §2 del PREREG_LAB_S0, non modifica. Gli id di
tool_use divergenti fra le repliche erano una fonte di divergenza di
prefisso senza contenuto semantico; il fix li ha resi deterministici,
restaurando la condizione dichiarata dal §2. Precisazione: il §2 non nomina
caching né id di tool_use; dichiara "input byte-identici". Id divergenti
rompono l'uguaglianza byte a byte anche a parità di contenuto semantico, ed
è su quella clausola che poggia la qualificazione come ripristino.

**Effetto misurato**: costo giornaliero da $13,8891 a $9,7996 (-29,44%),
contro un atteso -50/55%. Il residuo è spiegato: le scritture del blocco di
prefisso grande passano da 6 a 4, e le due che restano nascono dalla
divergenza autentica del modello sulla scelta dei tool, non riparabile
durante S0 senza cambiare cosa il Trader vede.

**Covariata annotata**: la dispersione della confidence passa da 0,0167
(G1) a 0,0000 (G2). n=2, ipotesi non tendenza. Prefissi identici potrebbero
aver ridotto il rumore da batch-invariance. Da tenere presente quando si
leggerà il metro del rumore a fine stagione.

---

## TL-005 — Lettura dichiarata del §5 del PREREG_LAB_S0 (tetto token): LETTERALE

- **Data**: 2026-08-17
- **Stato**: attiva
- **Decisa da**: l'owner.

Dichiarata PRIMA della fine della stagione, come la clausola richiede: a
fine stagione la scelta sarebbe contaminata dal sapere quante giornate sono
state raccolte.

**Contenuto**: il tetto si applica al campo `input_tokens` dell'oggetto
usage, distinto dai campi `cache_creation_input_tokens` e
`cache_read_input_tokens`. Due argomenti indipendenti: (i) il §4, punto 5,
ancora la definizione al campo usage ("Consumo: token input/output per
decisione e per giornata, dal campo usage"), dove input_tokens è un campo
distinto da cache_creation_input_tokens e cache_read_input_tokens; (ii)
l'implementazione fu costruita prima della stagione sotto la stessa
pre-registrazione.

**Conseguenza dichiarata apertamente**: con questa lettura il tetto non
morde (994 e 856 token contro un milione). La protezione di budget effettiva
è il limite di spesa Console, non il tetto token. Questo è un reperto sul
§5, registrato, non una modifica alla stagione.

---

## TL-006 — Stagione 0 chiusa anticipatamente per decisione di allocazione

- **Data**: 2026-08-18
- **Stato**: attiva
- **Decisa da**: l'owner.

**Esito: CHIUSA ANTICIPATAMENTE.** Non è **INVALIDA** nel senso del §3 del
PREREG_LAB_S0, che riserva quel termine all'inaffidabilità operativa (cap di
calendario scaduto senza raggiungere le giornate). Qui la macchina ha
funzionato: tre giornate su tre eseguite, tutte `day_completed` nell'ops
ledger, catene hash verdi, snapshot congelati e rivalidati contro il proprio
`snapshot_id`. È un caso non previsto dal §3 e viene dichiarato come tale.

**Motivazione, unica: allocazione di budget.**

| Giornata | Costo misurato |
| --- | --- |
| 2026-08-16 | $13,8891 |
| 2026-08-17 | $9,7996 |
| 2026-08-18 | $13,9027 |

Venti giornate al modello pinnato costerebbero circa $196; le stesse giornate
a tariffa Opus 5 costerebbero circa la metà. L'owner ha deciso che la
differenza non è giustificata dal ritorno atteso della stagione.

**Cosa NON è entrato in questa decisione.** Nessuna delle misure primarie del
§4 è stata letta per motivarla. Il §5 le riserva alla fine della stagione, e la
clausola è stata rispettata. Le osservazioni raccolte durante S0 su confidence,
dispersione, coerenza dichiarativa e costo sono reperti sulla macchina,
annotati altrove, e non hanno concorso alla chiusura.

**Conseguenze dichiarate**

- il gate (i) del §7 (≥ 20 giornate) non è soddisfatto: la Stagione 1 **non**
  parte da questa stagione;
- le misure primarie del §4 (dispersione inter-repliche, baseline della suite
  di regressione, telemetria) non verranno mai lette: servono venti giornate su
  un modello solo, e non esistono;
- la suite di regressione comportamentale del §6 non è mai stata congelata:
  richiedeva gli snapshot dei primi 12 giorni effettivi, e le giornate sono
  tre. Non è una pendenza persa, è una finestra che si riapre col disegno della
  stagione nuova;
- il record delle tre giornate resta valido come archivio e come unico
  esemplare comportamentale del modello pinnato in S0;
- il task pianificato è disabilitato, non cancellato: fotografia XML completa
  conservata per la ricostruzione.

---

## TL-007 — Pin su `claude-opus-5`

- **Data**: 2026-08-18
- **Stato**: attiva
- **Decisa da**: l'owner.
- **Supera**: la **Decisione 1** di TL-002 (il pin su `claude-fable-5`). La
  Decisione 2 di TL-002 (soglie della suite di regressione) resta invariata.

**Contenuto**: il modello del Trader passa da `claude-fable-5` a
`claude-opus-5`. TL-002 resta a registro e non si riscrive: viene superata da
questa voce, come TL-002 aveva superato D2 di TL-001.

**Motivazione: costo.** Tariffe da listino ufficiale Anthropic, lette il
17/08/2026: Fable 5 $10 per milione di token in input e $50 in output; Opus 5
$5 e $25. Scrittura in cache 1,25x il prezzo base dell'input, lettura da cache
0,1x. A parità di token consumati il costo si dimezza.

**Cosa questa voce NON afferma**: che Opus 5 decida meglio. Un confronto di
qualità fra modelli richiede l'arena appaiata prevista dalla Stagione 1, e non
è stato fatto. L'unica evidenza raccolta è un giro cieco k=1 su uno snapshot
congelato, fuori stagione, su CLI e non via API pinnata: indizio, non misura.

**Vincoli che questa decisione porta con sé**

- cambio modello = **nuovo track record**. La stagione nuova è un'altra
  Stagione 0, non la Stagione 1;
- richiede una pre-registrazione nuova, che **non** riscrive
  `docs/PREREG_LAB_S0.md`: quello resta congelato e si cita;
- richiede il rito del pin del §8 con la string nuova, ri-verificata contro
  l'endpoint, e un FreezeManifest nuovo con timbro OTS.

**Precondizione al rito del pin**, dichiarata qui perché scoperta dopo il pin
precedente. Il rito Z1 del 18/08 ha accertato che `scripts/run_day.py`
ricostruisce il FreezeManifest a runtime invece di caricare quello committato:
i tre `freeze_id` delle giornate di S0 differiscono fra loro e nessuno coincide
con quello del manifest firmato e timbrato OTS. La causa è che il manifest
ricostruito incorpora il git sha corrente, che cambia a ogni commit anche
quando l'agente non è cambiato.

Conseguenza: il timbro certifica un documento che nessuna esecuzione ha usato,
e il `freeze_id` — che esiste per accorgersi se l'agente è cambiato — cambia
comunque, quindi non se ne accorgerebbe.

Nessuna violazione di S0 è avvenuta: `prompt_sha`, `model_version`,
`persona_sha` e `system_prompt_sha` sono identici in tutte e tre le giornate e
coincidono col manifest.

Il pin della stagione nuova **non è valido** finché il runner non carica il
manifest committato, ricalcola il `freeze_id` e si rifiuta di girare se
diverge. La riparazione è codice e vive fuori da questa voce.

**Stima di costo, dichiarata come stima**: circa $4,90 al giorno sui conteggi
di token della giornata 2, cioè circa $98 per venti giornate. L'85% del costo è
scrittura in cache e dipende da quanti prefissi distinti il modello genera, che
varia col modello. Incertezza dichiarata ±20%; il primo giorno reale la
corregge.

---

## TL-008 — `max_tokens` del Trader = 8.000: superamento formale dei 32.000

- **Data**: 2026-08-19
- **Stato**: attiva
- **Decisa da**: l'owner.
- **Supera**: la dichiarazione dei **32.000** contenuta nella tabella
  «Conseguenze tecniche del modello» di **TL-002** (riga sul thinking che
  consuma lo stesso `max_tokens` della risposta), registrata come divergenza
  **D5** nell'audit del 19/08. TL-002 resta intatta e non si riscrive: questa
  voce la **supera**, come TL-007 ha superato la Decisione 1 e come TL-002
  aveva superato D2 di TL-001.

**Contenuto**: il tetto di `max_tokens` del Trader è **8.000**, ed è il valore
che la Stagione 0 ha **effettivamente** usato. Non è una modifica: è la
registrazione formale di ciò che era già vero nel codice e nel manifest.

**Le prove, entrambe committate.**

| Fonte | Valore |
| --- | --- |
| `arena/config.py:50` — `DEFAULT_MAX_TOKENS` | `8_000` |
| `manifests/trader_v0_freeze_manifest.json`, campo `max_tokens` | `8000` |

**Perché il 32.000 non fu mai efficace.** Il commento di `arena/config.py`
(rito `max_tokens`, diagnosi C) lo dichiara: con `max_tokens=32_000` la
chiamata veniva **scartata dallo shedding lato server** nei picchi di carico
(`overloaded` in-stream); con un budget ridotto la chiamata passa. Il tetto fu
quindi portato a 8.000 **prima** che la stagione girasse. Le tre giornate di S0
(16, 17, 18/08) sono girate tutte a 8.000: non esiste alcuna decisione del
track record prodotta sotto un tetto di 32.000.

Il rovescio della medaglia era ed è dichiarato in codice: un turno insolitamente
lungo può troncare la risposta, e la guardia in `arena/runner.py` intercetta
`stop_reason="max_tokens"` forzando NO TRADE (`MalformedReason.TRUNCATED`), mai
un verbale parziale silenzioso.

**Alternativa scartata: portare davvero il RUN2 a 32.000.**
Scartata. Il RUN2 cambia già una variabile — il modello pinnato (TL-007). Alzare
contemporaneamente il tetto dei token ne introdurrebbe una seconda, e qualunque
differenza osservata fra i due segmenti diventerebbe non attribuibile. È
esattamente ciò che i punti **A.1** e **A.3** del verbale RUN2 vietano: una
variabile per volta.

**Cosa questa voce NON afferma**: che 8.000 sia il tetto giusto per il modello
di TL-007. È il tetto tarato su Fable e sul suo comportamento di shedding. Una
eventuale ritaratura su `claude-opus-5` è una decisione a sé, da prendere fuori
da un segmento di track record aperto e da registrare con voce propria.

**Fonti**: verbale RUN2, punto **A.1**; audit del 19/08/2026, divergenza
**D5**; foglio delle 27 decisioni del 19/08 (`zeroPipes`,
`docs/program/2026-08-19_VERBALE_FOGLIO_DECISIONI.md`), **punto 19**.

---

## TL-009 — Ancoraggi OTS della Stagione 0: ratifica della via (b)

- **Data**: 2026-08-20
- **Stato**: attiva
- **Decisa da**: l'owner (Sanji), 20/08/2026.
- **Supera**: nulla. È una voce nuova: nessuna decisione precedente si era
  pronunciata su quali byte i tre timbri della Stagione 0 certifichino.

**Contenuto**: dei tre ancoraggi OpenTimestamps del record di Stagione 0, due
— `manifests/trader_v0_freeze_manifest.json` e `MANIFEST_S0.json` — furono
timbrati sui byte del **working tree convertito** (CRLF), non sui byte del
blob (LF). Il terzo, `docs/PREREG_LAB_S0.md`, fu timbrato sul blob e vi
coincide. L'owner ratifica la **via (b)**: si annota, non si riscrive.

**Le due vie, e perché è stata scelta questa.**

| Via | Cosa avrebbe fatto | Esito |
| --- | --- | --- |
| (a) | ricommittare i due JSON con i fine-riga CRLF che furono timbrati | **scartata**: cambia il blob sha di un percorso di verdetto (`manifests/trader_v0_freeze_manifest.json`) e del manifesto degli hash del record (`MANIFEST_S0.json`), cioè grandezze che altri documenti già citano |
| (b) | dichiarare quali byte sono timbrati e scrivere la ricetta che li ricostruisce da qualunque macchina | **ratificata** |

**I tre digest timbrati**, trascritti qui per esteso perché il documento di
evidenza è tracciato ma questa voce deve reggere da sola (convenzione delle
evidenze di `CLAUDE.md`):

| Target | digest timbrato (sha256) | si verifica su |
| --- | --- | --- |
| `docs/PREREG_LAB_S0.md` | `f0a22924a24fdd27f251d8da645664cc8fcf0e75607e2ca18388c4e1e41628d4` | i byte del **blob** |
| `manifests/trader_v0_freeze_manifest.json` | `429186db0eabc30e5fbb55b5b402a59995d7756fb5eea33a251aa28a0f1b98e8` | `crlf(blob)` |
| `MANIFEST_S0.json` | `ced493a7b3ea36168d6b3c7a4fe7aa81bfada0bd318928dd2a6d552cb8c27275` | `crlf(blob)` |

Le due condizioni si escludono a vicenda: nessuna configurazione di checkout
riproduce tutti e tre i timbri, e prima di questa ratifica l'unico posto al
mondo in cui tornavano tutti e tre era il working tree dell'owner.

**Dove sta l'evidenza.** Metodo, misure e ricetta di verifica per target
stanno in `docs/research/results/2026-08-20_PREREG-EVIDENCE_ANCORAGGI_OTS_S0.md`,
committato con **`6410880`** («docs(ots): ancoraggi S0 — evidenza, ricetta di
verifica, .gitattributes»). Il §5 di quel documento è la ricetta: si lavora
sui byte letti con `git cat-file blob`, e per i due JSON si applica la
trasformazione LF→CRLF prima del confronto. Il confronto `sha256` è offline;
`ots verify` richiede rete e si esegue fuori dai riti a rete vietata.

**Cosa la ratifica porta con sé, in `.gitattributes`** (stesso commit
`6410880`):

- le sedi ancorate `docs/**` e `manifests/**` sono coperte da `-text`: ogni
  file che vi nascerà si materializza in ogni clone con i byte del blob;
- i due artefatti congelati e già timbrati restano l'**eccezione dichiarata**
  (`text=auto`), perché sotto `-text` comparirebbero modificati in eterno e
  nessuna `git add` sarebbe lecita su file congelati;
- **sei eccezioni di eredità**, anch'esse `text=auto`: documenti `docs/**`
  pre-esistenti, **non ancorati**, committati con blob LF e presenti nel
  working tree con CRLF. Nessun timbro è in gioco per loro; sotto `-text`
  comparirebbero come modificati senza che nulla sia cambiato, e il rumore
  nasconderebbe le modifiche vere. Quando uno di essi verrà riscritto con
  fine-riga LF, la sua riga di eccezione va rimossa e il file torna sotto
  `-text`.

**Cosa questa voce NON afferma**: che i timbri siano deboli. Certificano
esattamente gli stessi byte di contenuto dei file committati — la differenza è
soltanto un `CR` per riga, e la §3.1 dell'evidenza lo dimostra per entrambi i
JSON nei due versi. Afferma soltanto che la verifica passa per una ricetta e
non per un confronto diretto.

**Regola per il futuro**, incisa in `CLAUDE.md`: ogni timbro OTS si appone sui
byte del **blob** (`git cat-file`), mai su una copia del working tree; ogni
file da ancorare nasce coperto da `.gitattributes` **prima** dello stamp, e
nasce in `docs/` o in `manifests/`, mai nella radice del repo — la radice non
è coperta da `-text`, ed è esattamente lì che stava `MANIFEST_S0.json` quando
il caso si è prodotto.

---

## TL-010 — Il listino esce dalle costanti ed entra nel pin

- **Data**: 2026-08-20
- **Stato**: attiva
- **Decisa da**: l'owner (Sanji), 20/08/2026, nel prompt del rito T3, passo 0.
- **Supera**: nulla di dichiarato. Corregge un difetto di attuazione di **D5**
  (guardie economiche di stagione): la decisione D5 non aveva mai detto da
  dove i prezzi dovessero venire, e l'implementazione li aveva messi fra le
  costanti di `ledger/spend.py`.

**Contenuto**: i quattro prezzi con cui la spesa di stagione viene contata —
input, output, scrittura in cache a 5 minuti, lettura da cache — non sono più
costanti di modulo. Sono **campi del Freeze manifest**
(`price_per_mtok_input`, `price_per_mtok_output`,
`price_per_mtok_cache_write_5m`, `price_per_mtok_cache_read`), con default
`None`, che entrano nel calcolo del `freeze_id` ed è il **rito del pin** a
valorizzare. Il runner in `--live` rifiuta di girare se ne manca anche uno
solo, elencando in una volta tutti i campi mancanti, esattamente come già
faceva per `season_budget_usd` e `season_expected_days`.

**Il difetto che l'ha resa necessaria, con i numeri.** Le costanti portavano
il listino di **Claude Fable 5** — $10 / MTok in input, $50 in output — fissato
al pin TL-002 del 14/08. Il pin **TL-007** del 18/08 ha cambiato modello a
`claude-opus-5`, che costa **$5 e $25**: metà. Le costanti non se ne sono
accorte, perché una costante di modulo non ha modo di sapere quale modello è
pinnato. Entrambe le guardie economiche contavano quindi la spesa al **doppio**
del vero. Con il preventivo di stagione proposto per il RUN2 — $89,90 su 28
giornate, soglia dura `1,5 ×` = $134,85 — la soglia sarebbe scattata al
**giorno 21** invece che al giorno **42**: la stagione si sarebbe fermata a
metà credendo di aver speso il doppio di quanto aveva speso. Il difetto era
nella direzione prudente, ma un preventivo di $89,90 che si comporta come uno
di $44,95 non è un preventivo prudente: è un preventivo diverso da quello
firmato.

**I prezzi in vigore**, trascritti qui per esteso perché questa voce deve
reggere da sola. Riga «Claude Opus 5» della pagina di listino ufficiale
(`https://platform.claude.com/docs/en/about-claude/pricing`), letta il
**2026-08-20**:

| Voce | Prezzo (USD / MTok) | Campo del manifest |
| --- | ---: | --- |
| Base Input Tokens | **5,00** | `price_per_mtok_input` |
| Output Tokens | **25,00** | `price_per_mtok_output` |
| 5m Cache Writes | **6,25** | `price_per_mtok_cache_write_5m` |
| Cache Hits & Refreshes | **0,50** | `price_per_mtok_cache_read` |

La scrittura in cache è quella a **5 minuti** e non quella a 1 ora ($10 /
MTok) perché il client (`arena/llm_client.py`) non specifica `ttl` e il default
è 5 minuti. Un client che passasse a 1 ora userebbe un'altra riga di listino,
e sarebbe un altro pin. Metodo e misure stanno nel §4 di
`docs/research/results/2026-08-20_PREREG-EVIDENCE_PREVENTIVO_RUN2.md`; il
difetto era già dichiarato nel §8 punto 1 dello stesso documento.

**La conseguenza dichiarata.** I prezzi entrano nel `freeze_id`, come già vi
entrava il preventivo. Un ritocco di listino da parte del fornitore **non** si
insegue quindi a stagione aperta — il manifest è firmato e timbrato — e le
guardie continuano a contare con le tariffe con cui il preventivo fu
calcolato. È la scelta coerente: le due cifre confrontate restano omogenee, e
una guardia che cambia unità di misura a metà stagione non misura più niente.

**Cosa questa voce NON afferma**: che la spesa storicamente registrata fosse
sbagliata. I token consumati sono quelli, e sono nel log delle tool call; era
sbagliata la loro **conversione in dollari**. Le tre giornate di Stagione 0
girarono davvero su `claude-fable-5` e il loro costo al listino Fable è
corretto: $13,89, $9,80 e $13,90 (trascritti dal §5.6 dell'evidenza citata).

**Effetto collaterale visibile.** Il rapporto del mattino
(`scripts/morning_report.py`) non stampa più un costo quando il manifest non
porta il listino: scrive `non calcolabile — listino assente dal Freeze
manifest` e lascia i token. Finché il rito del pin del RUN2 non è avvenuto,
questa è la riga che si vedrà, ed è corretta — la riga precedente era una
cifra calcolata al listino di un modello diverso da quello pinnato.


---

## TL-011 — Autorizzazione al primo giorno del RUN2 (PREREG §13 passo 12)

- **Data**: 2026-08-21
- **Stato**: attiva
- **Decisa da**: l'owner (Sanji), 21/08/2026, per delega esplicita nel prompt
  del rito di riparazione del cablaggio RUN2 (`FIX_G1`).
- **Supera**: nulla. **Chiude** il passo **12** del §13 di
  `docs/PREREG_LAB_S0_RUN2.md`, l'ultimo rimasto aperto della checklist del
  rito del pin.

**Dove va incisa, e perché qui.** Il §13 passo 12 pretende «autorizzazione
esplicita dell'owner al primo giorno» e **non prescrive né la forma né la
sede**: la colonna «Stato» di quella riga porta un trattino. Le firme del RUN2
(F1…F14, F9-bis, F12-bis) vivono nel §14 del PREREG, ma quel documento è
**congelato e timbrato** — `docs/PREREG_LAB_S0_RUN2.md.ots`, e il manifest lo
riferisce con `rito_config.prereg_ref.commit = afc40d95…` — quindi non lo si
tocca. In assenza di sede prescritta, la sede è questo registro, in append.

**Il testo autorizzato, per esteso:**

> AUTORIZZAZIONE AL PRIMO GIORNO (Sanji, 21/08/2026): il RUN2 inizia con la
> giornata il cui snapshot è delle 00:00 UTC del 22/08/2026. Il tentativo
> delle 00:00 UTC del 21/08 NON è una giornata della stagione: guardia del
> freeze scattata su manifest sbagliato per difetto di cablaggio
> (DIAGNOSI_G1), zero chiamate, $0,00; lo snapshot e6404c11… resta archiviato
> come artefatto pre-stagione e non entra in alcun conteggio. I contatori del
> §7.2 decorrono dal primo giorno di stagione.

**I numeri che l'autorizzazione presuppone**, trascritti per esteso perché
questa voce deve reggere da sola quando il referto che li ha prodotti non
esisterà più (i referti dei riti sono gitignorati):

| Grandezza | Valore, al 2026-08-21 |
| --- | --- |
| Chiamate all'API del modello nella notte del 21/08 | **zero** |
| Dollari spesi nella notte del 21/08 | **$0,00** |
| Snapshot pre-stagione archiviato | `e6404c11c046f7e942fcee569cd33a136c6050b2edbdcc5ccd577fcf021367bd`, `asof_utc = 2026-08-21T00:00:00+00:00`, 852.894 byte |
| Verbali nel ledger del RUN2 | **0** — il file `data/ledger/season0_run2.jsonl` non esiste ancora |
| Spesa cumulata del RUN2 | **$0,00**, `days_executed = 0` su **28** giornate attese |
| `freeze_id` pinnato, dichiarato e ricalcolato | `2136b199210dd9f231ba8faef3bd764161585167256640373c4ddc1e23d03f02` |
| Modello pinnato | `claude-opus-5` |

**Il vincolo di calendario che questa autorizzazione consuma.** Il §7 del
PREREG fissa la partenza «entro il **2026-09-13**»; con il primo giorno al
22/08 restano **22 giorni** di margine. Il cap di calendario di 42 giorni
decorre dal **primo giorno con verbali**, non da questa firma: al 21/08 non è
in pericolo, perché verbali non ce ne sono.

**Cosa questa voce NON autorizza.** Non autorizza un recupero della giornata
del 21/08 né di alcuna giornata precedente: una decisione presa oggi su uno
snapshot di ieri vedrebbe un futuro che il Trader di allora non aveva
(`CLAUDE.md` §5). Lo snapshot `e6404c11…` resta sul disco come artefatto, e il
suo essere completo e integro — verificato dalla DIAGNOSI_G1 — **non** è una
ragione per consumarlo. Non autorizza nemmeno un rilancio manuale: il primo
giorno è quello schedulato, alle 00:00 UTC del 22/08.

---

## TL-012 — I record del 19-21/08 sono PRE-STAGIONE e non contano per il §7.2

- **Data**: 2026-08-21
- **Stato**: attiva
- **Decisa da**: l'owner (Sanji), 21/08/2026, per delega esplicita nel prompt
  del rito `FIX_G1`.
- **Supera**: nulla. È un'**annotazione di lettura** su tre righe del registro
  operativo, non una loro modifica.

**I fatti.** Il registro operativo `data/ledger/ops.jsonl` porta tre righe
scritte tutte alle `2026-08-21T00:00:03Z`, `seq` 3, 4 e 5:

| `seq` | Chiave | Dettaglio |
| ---: | --- | --- |
| 3 | `{"day": "2026-08-19", "event": "skipped_day"}` | «nessuna decisione registrata; ultimo giorno con una traccia: 2026-08-18» |
| 4 | `{"day": "2026-08-20", "event": "skipped_day"}` | idem |
| 5 | `{"day": "2026-08-21", "event": "run_failed"}` | «run_day.py ha restituito 2» |

**La lettura, e perché è necessaria.** La Stagione 0 è **chiusa al
18/08/2026** (voce TL-006); il RUN2 **non era iniziato** — la sua
autorizzazione al primo giorno è la voce TL-011, del 21/08, e fissa il primo
giorno al 22/08. Il 19, il 20 e il 21 agosto **non appartengono a nessuna
stagione**: sono giorni di cantiere. I due `skipped_day` marcano quindi
l'assenza di verbali di una stagione che non stava correndo, e il `run_failed`
registra un rito che si è fermato alla guardia del freeze — correttamente, e su
un manifest che non era il suo (DIAGNOSI_G1, verdetto e reperto A).

**La conseguenza dichiarata.** Le soglie di allarme operativo del **§7.2** del
PREREG del RUN2 — «> 4 `skipped_day` totali» oppure «> 2 consecutivi» — si
contano **dal primo giorno di stagione**, cioè dal 2026-08-22. Le tre righe qui
sopra **non entrano in quel conteggio**. Al 21/08 il conteggio della stagione è
quindi **zero su entrambe le soglie**, e non due su due come una lettura
ingenua del registro suggerirebbe.

**Perché l'annotazione sta qui e non nel registro operativo.** Il registro è
append-only con hash-chain e write-once per (giorno, evento): riscrivere una
riga romperebbe la catena da quel punto in poi, e aggiungere un campo
`pre_stagione` a righe già scritte e già incatenate è la stessa cosa. Il
registro conserva **cosa è successo**; questo log conserva **come va letto**.
Sono due mestieri diversi, e la separazione è deliberata (`CLAUDE.md` §9).

Se in futuro lo schema del registro operativo prevedesse una marcatura
append-only dei record fuori stagione — una riga nuova che qualifica una riga
vecchia, mai una modifica — quella marcatura potrà essere aggiunta e dovrà
citare questa voce. Non esiste oggi, e inventarla in questo rito avrebbe
significato cambiare uno schema di ledger per un problema di lettura.

---

## TL-013 — Il `freeze_id` di `trader_v0` non è più riproducibile, e non si corregge

- **Data**: 2026-08-21
- **Stato**: attiva
- **Decisa da**: l'owner (Sanji), 21/08/2026, per delega esplicita nel prompt
  del rito `FIX_G1`.
- **Supera**: nulla. Registra un **reperto** accertato dalla DIAGNOSI_G1 e
  decide, esplicitamente, di **non** ripararlo.

**Il fatto.** `manifests/trader_v0_freeze_manifest.json` — il pin della
Stagione 0 — dichiara `freeze_id =
f37b8c2c98351ed93f1a841d6b6e58faba2d1023e5883b3c8ff6da3ba37535e1`, e sotto il
contratto `FreezeManifest` corrente il ricalcolo sul contenuto dà un valore
**diverso**. Diverso, per giunta, in momenti diversi: `5ec416a7…` il 20/08 alle
01:33Z, `753f3cbd…` lo stesso giorno alle 05:00Z, `46c11951…` la notte del
21/08. Il valore **dichiarato** non si è mai mosso.

**La causa, accertata e non congetturata.** Non è una manomissione: il file è
**identico al blob committato** (`git diff HEAD --` sul suo percorso è vuoto) e
il suo timbro `.ots`, che certifica quei byte, non è in discussione. La causa è
che `freeze_id` si calcola su `canonical_payload()`, cioè su **tutti** i campi
del contratto corrente, e **otto campi** aggiunti al contratto dai riti del
19-20/08 (commit `4196958`, `a924da0`, `474a1b5`) non esistono in quel file e
vi entrano con i loro **default**: `pin_commit`, `season_budget_usd`,
`season_expected_days`, `thinking_declared`, `price_per_mtok_input`,
`price_per_mtok_output`, `price_per_mtok_cache_write_5m`,
`price_per_mtok_cache_read`. Ogni commit che tocca il contratto sposta quindi
il ricalcolo di un manifest vecchio — ed è esattamente il motivo per cui il
valore si è mosso tre volte in due giorni.

**La decisione: nessuna correzione.** Il file non si tocca, il `freeze_id`
dichiarato non si riscrive, il timbro non si rifà. Le ragioni, in ordine:

1. **la validità storica è intatta.** Il timbro OTS certifica i byte, i byte
   non sono cambiati, e i 18 verbali della Stagione 0 girarono sotto il
   contratto di allora, per il quale quel `freeze_id` era riproducibile;
2. **riscrivere il valore sarebbe la manomissione** che il messaggio d'errore
   teme: allineerebbe il file al contratto di oggi e romperebbe la
   corrispondenza con il timbro;
3. la Stagione 0 è **chiusa** (TL-006) e nessun rito futuro deve caricare quel
   manifest per girare.

**Cosa questo reperto insegna, e che vale per il RUN2.** Il `freeze_id` di un
manifest è riproducibile **solo sotto il contratto con cui fu scritto**. Il pin
del RUN2 vive quindi sotto la stessa spada: finché la stagione corre, il
contratto `FreezeManifest` **non si tocca**, perché un campo aggiunto — anche
con un default innocuo, anche senza modificare un byte del manifest — sposta il
ricalcolo, e la guardia del freeze rifiuta di far girare la giornata. Il test
`tests/test_dry_run_notturno.py::test_il_manifest_pinnato_del_run2_e_raggiungibile_e_verde`
esiste per rendere quel rosso visibile **in suite** invece che a mezzanotte.

---

## TL-014 — Un preflight che non percorre la strada del rito, mente

- **Data**: 2026-08-21
- **Stato**: attiva
- **Decisa da**: l'owner (Sanji), 21/08/2026, per delega esplicita nel prompt
  del rito `FIX_G1`.
- **Supera**: la lettura implicita per cui un controllo non eseguito potesse
  essere riportato come un controllo superato.

**La dottrina, in una riga**: *un preflight che non percorre la strada del
rito, mente*. Il **PASS finto è vietato**: un controllo che non si può eseguire
è **FAIL** o **AVVISO**, mai PASS, e un controllo che verifica qualcosa di
adiacente a ciò che il rito farà non è quel controllo.

**Il difetto misurato che la impone.** Il 2026-08-20, due volte nella stessa
giornata, il controllo del mattino ha concluso **exit 0** e il suo preflight ha
risposto **PRONTO PER STANOTTE: SI** con otto righe verdi, mentre il manifest
che la notte avrebbe caricato era **già irricevibile** — la stessa divergenza
del `freeze_id` di TL-013, già scritta nel suo stesso log alle 01:33Z e alle
05:00Z. La notte seguente il rito è uscito **4** su quella identica causa. Le
due forme del difetto:

- la precondizione «FreezeManifest presente coi due `.ots`» verificava che i
  file **esistessero**, non che il manifest **si caricasse**. Un file che c'è e
  non si carica passava;
- fuori stagione «nessuna stagione attiva» era uno stato **normale**, e un
  manifest che non si carica veniva letto come «nessuna stagione» invece che
  come un guasto: il sistema **sapeva** e taceva.

**Cosa la dottrina impone al codice** (attuato dal rito `FIX_G1` del 21/08):

1. il preflight **compone ed esegue il comando notturno effettivo** —
   `scripts/run_day.py --dry-run --live` con **lo stesso** manifest e **lo
   stesso** ledger della notte — e lo percorre fino al punto immediatamente
   precedente l'istanziazione del client. Le cinque guardie attraversate sono
   quelle vere, non una loro imitazione;
2. un controllo che **solleva** o che non parte vale **NO**, mai silenzio: il
   ramo d'eccezione del preflight nel controllo del mattino non lascia più
   l'esito indeterminato;
3. un manifest designato per il rito e **non caricabile** (assente, illeggibile
   o con `freeze_id` divergente) è sempre un **allarme**. Resta muto — e deve
   restare muto — il manifest **sano ma non ancora pinnato**: quello è il
   cantiere fermo, non un guasto, e un allarme che suona ogni mattina è il modo
   più efficace di disattivare un allarme senza spegnerlo;
4. l'esito ≠ 0 del rito notturno è un **allarme**, letto dal **registro
   operativo** del Lab — append-only, con hash-chain — e non dal
   `LastTaskResult` del Task Scheduler, che è un solo numero che la passata
   successiva sovrascrive.

**Il principio generale, oltre il preflight.** Un controllo esiste per
anticipare un rifiuto, non per riprodurlo. «Tanto il runner lo rifiuta da sé» è
vero e irrilevante: il rifiuto del runner arriva a mezzanotte, quando non c'è
più tempo per ripararlo, e il controllo del mattino esiste per anticiparlo di
diciassette ore. **Un guasto che il sistema conosce e non dice è peggio di un
guasto che non conosce**, perché insegna a fidarsi di una tabella verde.
