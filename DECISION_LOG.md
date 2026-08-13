# DECISION_LOG — Trader Lab

Registro delle decisioni strutturali del Lab. Ogni voce è immutabile: una
decisione che cambia si supera con una voce nuova, non si riscrive.

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
Si usa la model string più specifica disponibile al momento del pin, registrata
nel Freeze manifest. **Cambio modello = nuovo track record.**
*Stato al 2026-08-13*: la string più specifica disponibile per la Sonnet
corrente è **`claude-sonnet-5`**. Gli ID dei modelli Claude correnti sono
completi così come sono: **non esiste una variante datata** e aggiungere un
suffisso data produce un 404. L'unica alternativa "datata" sarebbe scendere di
generazione (`claude-sonnet-4-5-20250929`), il che significherebbe pinnare un
modello legacy. Scelta: `claude-sonnet-5`, con la nota registrata nel manifest.
*Nota operativa*: il pin **non è ancora effettuato** — richiede l'autorizzazione
dell'owner e il timestamping OTS. `FreezeManifest.ots_pending` resta `True`.

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
