# LAST_REPORT — Fase 0, Trader Lab

**Repo**: `traderLab` · **Data**: 2026-08-13 · **Natura**: costruzione componenti + collaudo

> **⚠️ Addendum del 2026-08-13 — TL-002 supera parti di questo report.**
> Due punti qui sotto sono stati superati da `DECISION_LOG.md` → TL-002:
> il **modello pinnato** non è più `claude-sonnet-5` ma **`claude-fable-5`**
> (§4, D2), e le **soglie della suite di regressione** non sono più
> `TODO-owner` (§7): l'owner ha fissato la regola
> `alarm = baseline − 0.15 (pavimento 0.70)`,
> `sunset = baseline − 0.30 (pavimento 0.50)`, confidence `+0.10` / `+0.20`.
> La constatazione su **D4 è stata ri-verificata su Fable e confermata**:
> policy identica, sampling per omissione. Tutto il resto del report resta
> valido.

> **Nessuna stagione è partita.** Il cronometro della Stagione 0 si avvia solo
> dopo il GO del Pre-Screen (che gira in `zeroPipes`) e con autorizzazione
> dell'owner. Questo repo non contiene chiavi di wallet e non esegue ordini
> reali: solo shadow.

---

## 1. Esito in una riga

Fase 0 chiusa: sei blocchi costruiti e committati, **213 test verdi + 1
skipped** (lo smoke con API reale, dietro flag), suite eseguibile **senza rete
e senza API key**, smoke end-to-end con MockLLM verificato anche fuori dalla
suite tramite gli script CLI.

---

## 2. Cosa ho letto prima di scrivere codice

`docs/research/2026-08_AGENT_FAITHFULNESS_FRAMEWORKS_LITERATURE.md` era
presente. Da lì vengono, direttamente e verificabilmente:

| Elemento del build | Origine nella rassegna |
| --- | --- |
| Razionale libero **prima** del blocco strutturato | Q2, "format tax" — Tam et al., EMNLP 2024 |
| `features_used` trattato come **ipotesi**, non come dato | Q1 — AlMarri et al. 2025/26; STaDS 2025 (ρ da +0.25 a −0.54) |
| Nessun reporter separato per l'attribuzione | Q1 — "privileged access", Transluce 2511.08579 |
| Vocabolario chiuso + ancoraggio numerico | Faithfulness Audit Protocol §2 (dichiarato: serve a verificabilità, **non** aumenta la fedeltà) |
| Dispersione tra repliche misurata ma non sufficiente | Q1 — Parcalabescu & Frank, ACL 2024 |
| Niente debate | Q6 — Zhang et al. 2502.08788; Huang et al. ICLR 2024 |
| Point-in-time strutturale, niente backtest | Q4 + Caveats sul leakage |
| Descrizioni dei tool neutre | Q4 — il wording dello schema orienta il comportamento |
| Codice proprio, non TradingAgents | Verdetto Q5: build-minimal-first |

---

## 3. I sei blocchi

| # | Blocco | Commit | Contenuto essenziale |
| --- | --- | --- | --- |
| 1 | Scaffold + contratti | `b31ad64` | 6 contratti Pydantic v2 frozen/`extra="forbid"`, `snapshot_id` = sha256 del contenuto canonico, vocabolario chiuso |
| 2 | Tool Server | `d8b097b` | SnapshotBuilder point-in-time, store con ri-validazione, 6 tool strict, log totale, firewall |
| 3 | Verbale + Risk Officer | `9695a06` | Parser che impone l'ordine, NO TRADE sui malformati, 5 regole di rischio in ordine fisso |
| 4 | Ledger + telemetria + e-process | `9a5b636` | Hash-chain con `verify()`, contatori comportamentali, betting/ONS anytime-valid, kill-criterion |
| 5 | Orchestratore | `99a4071` | 3 repliche in isolamento, client D2/D4, MockLLM deterministico |
| 6 | Regressione | `b4f9511` | Set congelabile una volta sola, metrica dichiarata ora, soglie TODO-owner che sollevano |

Struttura effettiva: `contracts/` (aggiunto rispetto alla struttura richiesta —
i contratti erano senza casa: `ledger/` è per record e analisi, non per gli
schemi), più `agents/trader_v0/`, `toolserver/`, `ledger/`, `arena/`, `tests/`,
`scripts/`.

---

## 4. Le quattro decisioni owner, in codice

### D1 — Tre repliche identiche

`arena/runner.py` crea per ogni replica un client nuovo, uno stato di
portafoglio nuovo e una lista di messaggi nuova. Il `replica_id` serve al
ledger e alla telemetria e **non entra mai nel prompt**.

Verificato da `test_input_byte_identici_tra_repliche`: il runner registra
l'impronta sha256 di `(system, tools, messages)` per ogni (replica, asset) e il
test assicura che le tre impronte coincidano.

### D2 — Modello pinnato Claude Sonnet — **con una constatazione da portare all'owner**

Il mandato era "la model string più specifica/**datata** disponibile". Ho
verificato contro la documentazione corrente dell'API:

- Gli ID dei modelli Claude correnti **sono completi così come sono**. Per la
  Sonnet corrente **non esiste una variante datata**, e aggiungere un suffisso
  data produce un **404**.
- L'unica string genuinamente "datata" sarebbe `claude-sonnet-4-5-20250929`,
  cioè **scendere di generazione** e pinnare un modello legacy.

**Scelta implementata**: `claude-sonnet-5`, con la constatazione registrata nel
campo `model_string_note` del manifest, in `DECISION_LOG.md` e nel tracker.
Se l'owner preferisce la riproducibilità di uno snapshot datato al costo di un
modello legacy, è una riga di config in `arena/config.py` — ma è una decisione
sua, non mia.

**Il pin non è stato effettuato.** `FreezeManifest.ots_pending` resta `True`.

### D3 — Stagione 0: size fissa, confidence dal giorno uno

`RiskOfficer` normalizza la size al valore di config con un clamp. Il campo
`confidence` è obbligatorio nel `DecisionRecord`, viene loggato sempre, e
`BrierAccumulator` esiste già con la decomposizione di Murphy — resta vuoto in
Fase 0 perché gli esiti arrivano solo in Stagione 0.

**Un punto che ho dovuto dichiarare esplicitamente**: normalizzare alla size
fissa può *alzare* una size richiesta più bassa, il che sembra violare "il Risk
Officer può solo ridurre". Non lo è: in Stagione 0 la size non è una variabile
del Trader (D3 dice che decide solo direzione e dentro/fuori), quindi
normalizzarla rimuove un grado di libertà che il protocollo non concede. È
l'unica eccezione, ed è documentata in `contracts/risk.py`. Tutte le altre
regole possono solo ridurre.

### D4 — Temperatura: default operativo dell'API, mai 0 — **seconda constatazione**

Sui modelli Claude Sonnet correnti i parametri di sampling non-default
(`temperature`, `top_p`, `top_k`) sono **rifiutati dall'API con errore 400**.

Il "default operativo dell'API" si ottiene quindi **per omissione**: il client
non invia affatto quei campi. Questo rende D4 non solo una scelta di policy ma
**l'unica forma di chiamata valida** — il che è un rafforzamento, non un
problema.

Codificato su tre livelli:
1. `FreezeManifest` registra `sampling_policy="api_default_omitted"` con i tre
   campi a `None`, così "default dell'API" non si confonde mai con "0" o con
   "non registrato";
2. il contratto **rifiuta** `temperature=0.0` esplicita;
3. `AnthropicTraderClient` si rifiuta di partire con un manifest che dichiari
   sampling esplicito, e `test_d4_il_client_non_invia_parametri_di_sampling`
   ispeziona il payload effettivo.

---

## 5. Le tre cose che il collaudo ha trovato

Le riporto perché sono esattamente il tipo di errore che un build "verde al
primo colpo" avrebbe nascosto.

**1. La nota editoriale finiva nel prompt.** `system_prompt.md` si apriva con
un blockquote che diceva *"questo testo non contiene alcun riferimento a
repliche, confronti, valutazione"*. Quella nota **era essa stessa** un
riferimento alle repliche dentro il contesto del modello, e violava CLAUDE.md
§6. Trovato dal test `test_il_prompt_non_menziona_gara_repliche_o_valutazione`.
Risolto con `strip_editorial()`: i blockquote sono note per chi mantiene il
Lab e vengono rimossi prima di comporre il prompt. Gli sha del manifest restano
quelli del file su disco, perché è il file che viene congelato.

**2. L'e-process era bilaterale.** L'ipotesi nulla dichiarata è
`E[agente − macchina] ≤ 0`, ma con λ libero di andare negativo il processo
accumulava capitale anche su un agente **sistematicamente peggiore** della
macchina — cioè produceva "evidenza" per la direzione sbagliata. Corretto
vincolando λ ≥ 0 (test unilaterale), con `one_sided=False` disponibile per il
caso bilaterale e un test che documenta la differenza.

**3. `tool_choice` forzato avrebbe rotto il protocollo.** Forzare
`tool_choice` su `submit_decision` sopprime il testo che lo precede — cioè
esattamente il campo che l'ordine reasoning-prima esiste per proteggere. Il
runner usa quindi `tool_choice` automatico e l'ordine è imposto **nel parser**,
che rifiuta i verbali in cui il blocco strutturato non è preceduto da testo.
Documentato in `arena/verbale.py` perché è controintuitivo.

---

## 6. Verifiche che valgono la pena di essere citate

- **Due repliche, stesso `snapshot_id` → byte identici** su tutti e sei i tool.
- **Richiesta fuori snapshot → errore pulito e tipizzato**, mai un fallback su
  dati live.
- **Firewall strutturale**: un test ispeziona il sorgente di `registry.py` e
  `store.py` e verifica che non contengano `httpx` né `hyperliquid`; qualunque
  path contenente `zeropipes` viene rifiutato in costruzione.
- **Manomissione del ledger**: alterare un campo o rimuovere una riga rompe la
  catena, e `verify()` dice **a quale indice**.
- **E-process sotto il nullo**: su 200 ripetizioni indipendenti i falsi
  positivi restano ≤ α = 0.05.
- **Brier**: la decomposizione di Murphy verifica
  `BS = reliability − resolution + uncertainty` a 1e-9 su 2000 campioni.
- **Smoke CLI reale** (non solo test): 6 decisioni, 0 malformati, dispersione
  0.0000, catena ledger `ok`.

---

## 7. Cosa manca per la Stagione 0

Nessuna di queste voci è risolvibile dentro `traderLab`.

| # | Manca | Chi | Perché blocca |
| --- | --- | --- | --- |
| 1 | **Universo ufficiale dal Pre-Screen** | `zeroPipes` | L'universo attuale è `placeholder_non_ufficiale` e lo stato viaggia **dentro** lo snapshot. Non si apre una stagione su un placeholder. |
| 2 | **Gamba meccanica** | da costruire | Senza secondo braccio l'e-process gira solo su dati sintetici e il kill-criterion non è valutabile. |
| 3 | **PREREG_LAB_S0** (documento a parte) | owner | Soglie, dimensioni campionarie e azioni conseguenti, timestampate prima dell'accumulo. |
| 4 | **Pin effettivo + OTS del manifest** | owner | `ots_pending=True`. Senza pin timestampato il track record non è difendibile. Include la decisione su D2 (vedi §4). |
| 5 | **Soglie della suite di regressione** | owner | 4 valori `TODO-owner`. Il codice **solleva** invece di usare default. |

### I quattro numeri che servono dall'owner

Da fissare **prima** della raccolta della baseline, non dopo averla vista:

| Parametro | Valore |
| --- | --- |
| `agreement_alarm` | `TODO-owner` |
| `agreement_sunset` | `TODO-owner` |
| `confidence_alarm` | `TODO-owner` |
| `confidence_sunset` | `TODO-owner` |

Metrica, numero di snapshot (10-15), campioni per snapshot (k=5) e cadenza
(settimanale) sono invece **già dichiarati**, in codice e nel tracker.

---

## 8. Limiti dichiarati di questo build

Onestà su cosa questo repo **non** dimostra:

- **Non c'è alcuna evidenza di edge.** Non è stato misurato nulla: non ci sono
  decisioni reali, non c'è PnL, non c'è confronto. C'è un'infrastruttura.
- **Il MockLLM non è una strategia.** È una soglia deterministica sul dossier
  che serve a far girare la pipeline senza rete.
- **L'universo è un placeholder** e i test usano dati sintetici: il
  `SnapshotBuilder` è stato collaudato contro una sorgente finta, non contro
  Hyperliquid vero. Il primo `build_snapshot.py` con rete vera è un passo
  ancora da fare.
- **`features_used` resta un'ipotesi non verificata.** Il Faithfulness Audit
  Protocol (ablazione, self-consistency, controfattuali di bias) è progettato
  nella rassegna ma **non implementato** in Fase 0: serve la Stagione 0 per
  avere decisioni su cui girare.
- **Le stime di spread e depth sono stime**, dichiarate tali nel record
  (`estimator`), e nel fallback sono costanti di configurazione.

---

## 9. Stato del repo

- Branch `main`, 7 commit (1 preesistente di docs + 6 di blocco).
- Suite: `uv run pytest` → 213 passed, 1 skipped, ~2s.
- Nessun `.env` committato; `.gitignore` esclude `data/` (snapshot, ledger,
  log dei tool) tranne i `.gitkeep`.
- Push su `origin/main` effettuato.

### Comandi utili

```bash
uv run pytest                                    # suite completa, senza rete
uv run python scripts/run_day.py --snapshot-id <sha>   # giornata con MockLLM

TRADERLAB_ALLOW_NETWORK=1 uv run python scripts/build_snapshot.py
TRADERLAB_ALLOW_LIVE_API=1 uv run pytest tests/test_live_smoke.py -v
```
