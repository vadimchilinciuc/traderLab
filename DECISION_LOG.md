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
