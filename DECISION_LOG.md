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
