# CLAUDE.md — Regole del Trader Lab

Questo file è il contratto di ingegneria del repo `traderLab`. Vale per ogni
agente (umano o LLM) che tocchi questo codice. Le regole non sono consigli:
violarle invalida il track record.

## 0. Natura del repo

- `traderLab` è un **cantiere**, non una stagione. Il cronometro della
  Stagione 0 si avvia **solo** dopo il GO del Pre-Screen (che gira in
  `zeroPipes`) e con autorizzazione esplicita dell'owner.
- Questo repo **non contiene chiavi di wallet** e **non esegue ordini reali**.
  Solo esecuzione shadow, contabilizzata con i costi reali di Hyperliquid.
- L'unica credenziale ammessa è `ANTHROPIC_API_KEY`, letta **solo** da
  ambiente. Mai in codice, mai in un file committato, mai in uno snapshot.

## 1. Un solo cervello

- **Il Trader è l'unico componente LLM.** Tutto il resto — snapshot, tool,
  risk officer, ledger, telemetria, e-process, orchestratore — è codice
  deterministico, testabile, senza chiamate a modelli.
- Nessun secondo agente "critico", "reporter" o "supervisore" che usi un LLM.
  In particolare **nessun reporter separato** per l'attribuzione causale:
  la stessa passata che decide produce `features_used` (privileged access —
  vedi §Q1 della rassegna di fedeltà).

## 2. Guardrail nel tool, mai nel prompt

- Ogni vincolo che deve **valere sempre** è implementato in codice: nel Tool
  Server (cosa è visibile) o nel Risk Officer (cosa è eseguibile).
- Il prompt non è un meccanismo di sicurezza. Se una regola sta solo nel
  prompt, per il Lab **non esiste**.
- Il Risk Officer **può solo ridurre il rischio**. Non può aprire posizioni,
  non può aumentare la size, non può cambiare direzione.

## 3. Niente memoria, niente apprendimento in corsa

- Il Trader è **stateless tra le decisioni**. Nessuna memoria persistente,
  nessun riassunto della sessione precedente, nessun fine-tuning, nessun
  esempio few-shot che cambi nel tempo.
- Le lezioni entrano **solo** tramite una release esplicita e versionata dei
  context file (prompt/persona), che cambia `prompt_sha` e
  `context_git_sha` — e quindi apre un nuovo segmento di track record.

## 4. Niente feed testuali

- Il Trader vede **solo numeri** provenienti dal Tool Server: OHLCV, funding,
  ranking cross-sezionali, spread/depth stimati, costi.
- **Nessuna news, nessun sentiment, nessun testo di terzi**, nessun campo
  libero proveniente dall'esterno. Questo elimina una superficie di leakage e
  di prompt injection.

## 5. Niente debate, niente backtest

- **Niente debate multi-agente.** L'evidenza (Zhang et al. 2502.08788; Huang
  et al. ICLR 2024) non lo giustifica al costo che ha.
- **Niente backtest** come prova di edge. La valutazione è **solo forward**.
  Il codice non contiene e non deve contenere un motore di backtest.
- La disciplina point-in-time è strutturale: il Trader consuma uno **snapshot
  congelato** e non può vedere nulla di successivo al suo `asof_utc`.

## 6. Agenti inconsapevoli

- Le repliche **non sanno** di essere repliche.
- Il prompt **non menziona** gara, arena, confronto, gamba meccanica,
  valutazione, punteggio, altri agenti o il fatto stesso di essere valutati.
- Le descrizioni dei tool sono **neutre e fattuali**: niente verbi valutativi
  ("opportunità", "segnale forte", "conviene"), niente aggettivi che
  suggeriscano una direzione.

## 7. Firewall del Tool Server

- Durante una decisione il Tool Server legge **solo** lo store degli snapshot
  su disco. Nessun accesso di rete live. Nessun path verso `zeroPipes`.
- La rete pubblica si tocca **solo** in fase di costruzione dello snapshot,
  in un processo separato, dietro il flag `TRADERLAB_ALLOW_NETWORK=1`.
- Una richiesta fuori dallo snapshot congelato è un **errore pulito**, mai un
  fallback silenzioso su dati live.

## 8. Verbale o niente

- Il Trader produce il razionale **in testo libero PRIMA**, poi il blocco
  strutturato via strict tool use (mitigazione del "format tax", Tam et al.
  EMNLP 2024).
- Verbale non conforme = **NO TRADE**, registrato come `rejected_malformed`.
  È ammesso **un solo retry**, dichiarato e loggato.
- Mai prefill dell'assistant: sui modelli correnti restituisce 400 e comunque
  renderebbe post-hoc ogni attribuzione.

## 9. Tutto è loggato

- Ogni tool call (replica, tool, argomenti, hash della risposta, timestamp) va
  in JSONL append-only. **Cosa il Trader chiede è un dato**, alla pari di cosa
  decide.
- Il ledger è append-only con hash-chain (`prev_hash`) e write-once per
  (giorno, replica, asset). Non si riscrive la storia.

## 10. Modello pinnato

- Model string, parametri di sampling, sha di prompt/context/tool-schema e
  data del pin vivono nel **Freeze manifest**.
- **Cambio modello = nuovo track record.** Non si confrontano segmenti con
  model string diverse.
- Temperatura: **default operativo dell'API, nessun override, MAI 0** (D4).
  Sui modelli Sonnet correnti i parametri di sampling non-default vengono
  rifiutati con 400: il codice quindi **non invia** `temperature`, `top_p`,
  `top_k`. Questo è registrato nel manifest come scelta esplicita.

## 11. Cosa NON fare, in breve

| Mai | Perché |
| --- | --- |
| Aggiungere un secondo LLM | §1 |
| Mettere un vincolo solo nel prompt | §2 |
| Passare stato tra decisioni | §3 |
| Iniettare testo/news nel contesto | §4 |
| Scrivere un backtester | §5 |
| Dire alla replica che è in gara | §6 |
| Chiamare la rete durante una decisione | §7 |
| Accettare un verbale malformato | §8 |
| Riscrivere una riga di ledger | §9 |
| Cambiare modello senza nuovo track record | §10 |

## Convenzione dei context file

Nei file di `agents/trader_v0/` le righe che iniziano con `>` (blockquote) sono
**note per chi mantiene il Lab** e vengono rimosse prima di comporre il prompt
effettivo (`arena.config.strip_editorial`). Senza questo filtro la nota che
dice "questo testo non parla di repliche" sarebbe essa stessa un riferimento
alle repliche dentro il contesto del modello.

Gli sha del Freeze manifest si calcolano sul **file come sta su disco**, non
sul testo ripulito: è il file che viene congelato.

## Convenzioni di codice

- Python 3.13, `uv` per l'ambiente, Pydantic v2 per **tutti** i contratti.
- Ogni contratto è `frozen=True` e `extra="forbid"`. I dati non mutano dopo
  la creazione e un campo inatteso è un errore, non un'aggiunta silenziosa.
- Timestamp sempre UTC, timezone-aware, ISO-8601.
- Hash: SHA-256 su JSON canonico (chiavi ordinate, separatori compatti,
  UTF-8), tramite `contracts.hashing`.
- Test: `uv run pytest`. La suite deve girare **senza rete e senza API key**.
