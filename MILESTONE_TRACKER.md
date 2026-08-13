# MILESTONE_TRACKER — Trader Lab

> **Nessuna stagione parte da qui.** Questo repo è un cantiere. Il cronometro
> della Stagione 0 si avvia **solo** dopo il GO del Pre-Screen (che gira in
> `zeroPipes`) e con autorizzazione esplicita dell'owner.

---

## Decisioni owner congelate (D1-D4)

Non riaperte in Fase 0. Dettaglio e conseguenze in `DECISION_LOG.md` (TL-001).

| ID | Decisione | Dove vive nel codice |
| --- | --- | --- |
| **D1** | 3 repliche **identiche**: stesso modello, stesso prompt, stessa temperatura, stesso snapshot | `arena/runner.py`, `arena/config.py` |
| **D2** | Modello pinnato **Claude Sonnet** via API Anthropic; model string più specifica disponibile, registrata nel Freeze manifest. **Cambio modello = nuovo track record** | `contracts/freeze.py`, `arena/llm_client.py` |
| **D3** | Stagione 0 = **4 settimane shadow a size FISSA**; il Trader decide solo direzione e dentro/fuori; `confidence` loggata dal giorno uno per il Brier score | `arena/risk_officer.py`, `ledger/telemetry.py` |
| **D4** | Temperatura = **default operativo dell'API**, nessun override, **MAI 0**; ogni parametro di sampling dichiarato nel manifest | `contracts/freeze.py`, `arena/llm_client.py` |

**Nota D2 (stato al 2026-08-13).** Gli ID dei modelli Claude correnti sono
completi così come sono: per la Sonnet corrente **non esiste una variante
datata** e aggiungere un suffisso data produce 404. La string più specifica
disponibile è `claude-sonnet-5`. Il pin **non è ancora effettuato**.

**Nota D4 (stato al 2026-08-13).** Sui Sonnet correnti i parametri di sampling
non-default sono rifiutati dall'API con 400. Il default operativo si ottiene
**per omissione**: il client non invia `temperature`, `top_p`, `top_k`. Il
manifest lo registra come `sampling_policy="api_default_omitted"`.

---

## Fase 0 — stato per blocco

| # | Blocco | Stato | Commit |
| --- | --- | --- | --- |
| 1 | Scaffold + contratti Pydantic v2 | ✅ fatto | `feat(contracts)` |
| 2 | Tool Server con snapshot congelato | ⬜ da fare | — |
| 3 | Decision Record enforcement + Risk Officer | ⬜ da fare | — |
| 4 | Ledger + telemetria + e-process | ⬜ da fare | — |
| 5 | Orchestratore repliche | ⬜ da fare | — |
| 6 | Suite di regressione comportamentale (design + scheletro) | ⬜ da fare | — |

### Blocco 1 — Scaffold + contratti ✅

- `pyproject.toml` (uv, Python 3.13), struttura del repo, `.env.example`.
- `CLAUDE.md`: le 11 regole del Lab.
- Contratti frozen / `extra="forbid"`: `MarketSnapshot` (con `snapshot_id` =
  sha256 del contenuto canonico), `DecisionRecord` (schema v1),
  `RiskVerdict`, `ShadowFill`, `OutcomeAnnotation`, `FreezeManifest`.
- Vocabolario chiuso delle feature primitive (`contracts/vocabulary.py`).
- Test: round-trip di serializzazione, immutabilità, rifiuto dei campi extra,
  determinismo dello `snapshot_id`, disciplina point-in-time.

---

## Cosa manca per la Stagione 0

Nessuna di queste voci è risolvibile dentro `traderLab`: sono precondizioni.

| # | Manca | Chi/dove | Blocca |
| --- | --- | --- | --- |
| 1 | **Universo ufficiale dal Pre-Screen** | `zeroPipes` | L'universo attuale è `placeholder_non_ufficiale` ed è marcato tale dentro lo snapshot. Non si apre una stagione su un universo placeholder. |
| 2 | **Gamba meccanica per il confronto appaiato** | da costruire | Senza di essa l'e-process non ha un secondo braccio: gira solo su dati sintetici. Il kill-criterion non è valutabile. |
| 3 | **PREREG_LAB_S0** (documento a parte, futuro) | owner | Pre-registrazione di soglie, dimensioni campionarie e azioni conseguenti, timestampata **prima** dell'accumulo dati. |
| 4 | **Pin effettivo del modello + OTS del FreezeManifest** | owner | `ots_pending=True` finché non c'è la proof. Senza pin timestampato il track record non è difendibile. |
| 5 | **Soglie della suite di regressione fissate dall'owner** | owner | Vedi TODO-owner qui sotto. Vanno fissate **prima** della raccolta della baseline, non dopo averla vista. |

### TODO-owner — soglie della suite di regressione

Da fissare **prima** di raccogliere la baseline (Blocco 6). La metrica di
deriva è dichiarata ora; le soglie no.

| Parametro | Valore | Stato |
| --- | --- | --- |
| Metrica di deriva primaria | **action agreement rate**: quota di campioni con la stessa azione della baseline per snapshot, mediata sugli snapshot | ✅ dichiarata |
| Metrica di deriva secondaria | **distanza assoluta media sulla confidence** rispetto alla baseline | ✅ dichiarata |
| Numero di Decision Snapshot congelati | 10-15, scelti in Stagione 0, **una volta e mai più toccati** | ✅ dichiarato |
| Campioni per snapshot (k) | 5 | ✅ dichiarato |
| Cadenza di rigioco | settimanale | ✅ dichiarata |
| **Soglia di ALLARME** su agreement rate | `TODO-owner` | ⛔ da fissare |
| **Soglia di SUNSET** su agreement rate | `TODO-owner` | ⛔ da fissare |
| **Soglia di ALLARME** su distanza confidence | `TODO-owner` | ⛔ da fissare |
| **Soglia di SUNSET** su distanza confidence | `TODO-owner` | ⛔ da fissare |

**Aggancio al model sunset**: deriva oltre la soglia di sunset ⇒ il track record
si chiude **pulito** in quel punto e ne inizia uno nuovo. Non si "aggiusta" un
track record che ha attraversato una deriva.

### Kill-criterion pre-registrato

Se la **dispersione inter-repliche domina il gap agente-macchina** sulla
finestra dichiarata, il verdetto è **"no skill misurabile"**. Il criterio è
codificato in `ledger/eprocess.py` e non è negoziabile a posteriori.
