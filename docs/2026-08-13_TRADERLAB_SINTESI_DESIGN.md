# TRADER LAB — SINTESI COMPLETA DEL DESIGN · 13/08/2026
> Tutto ciò che è stato deciso sulla struttura degli agenti trader e su come va implementata. Fonti: 9ª e 10ª revisione, HANDOFF, decisioni in chat (questa e la parallela), verdetti del filtro. Da committare in `traderLab/docs/` e caricare nel Contesto del progetto.

## 1. Cos'è (e cosa non è)
Probabilità onesta che un agente LLM batta la gamba meccanica post-costi: **10-20%** (9ª revisione). Il Lab paga comunque, perché è tre cose: **(a)** generatore di ipotesi (le divergenze agente-vs-macchina diventano candidati per il Pre-Screen), **(b)** misuratore di varianza decisionale, **(c)** asset metodologico pubblicabile. Non è la scorciatoia verso l'alpha; se poi l'agente vince davvero, tanto meglio.

## 2. Principi fondativi (incisi, non negoziabili)
1. **Un solo cervello LLM** — il Trader. Tutto il resto è codice e riti. Niente debate multi-agente (teatro a costo 5-7×, letteratura MAD).
2. **Guardrail nel tool, mai nel prompt** — il prompt si aggira, il codice no.
3. **Mandato di processo, mai di risultato** — la pressione nel prompt produce gambling (r≥0,95); l'idea "paura del broke" (decadimento del patrimonio come punizione) è RESPINTA; la sua parte buona è diventata la Telemetria.
4. **Agenti inconsapevoli** della gara e delle repliche; punteggio SOLO risk-adjusted.
5. **Niente memoria/apprendimento in corsa** — le lezioni passano per lotti da HR alle release dei context files; mai al volo.
6. **Niente feed testuali/news** — solo numeri dal Tool Server (anti-injection, anti-leakage). Eccezioni future (Idea #8) richiedono emendamento esplicito.
7. **Valutazione SOLO forward post-cutoff** — mai backtest per agenti LLM (leakage da memorizzazione dimostrato).
8. **Decisioni cieche, apprendimento condiviso** — gli agenti non vedono le posizioni altrui (conformismo respinto); la conoscenza circola solo attraverso il ledger e le autopsie.
9. **ZeroPipes è l'oracolo** ("il tool che non mente"): dati verificati, stessi numeri per agente e macchina. ZeroPipes **si allena dalle ipotesi dell'agente, mai imita singoli trade**.
10. **Vocabolario condiviso**: `features_used` nei nomi delle primitive ZeroPipes = il ponte agente↔macchina che rende ogni decisione confrontabile meccanicamente.

## 3. La company (organigramma — un solo ruolo parla)
| Ruolo | Chi è | Cosa fa |
|---|---|---|
| **Trader** | agente LLM (unico cervello) | decide E compila il verbale nella stessa passata; reasoning PRIMA, struttura DOPO |
| **Risk Officer** | codice puro | può SOLO ridurre: cap leva ~3×, size limit, un cambio/asset/giorno, anti-martingala; tentativi bloccati → loggati |
| **Analista** | ZeroPipes via Tool Server | dossier, classifiche, funding, costi — read-only |
| **Auditor** | Telemetria + audit di ablazione | mensile, 15 decisioni a campione: ridecidere SENZA la feature dichiarata; consistenza <50% ⇒ `features_used` inutilizzabile per il mining (dichiarato) |
| **HR** | owner + consigliere | release dei context files tra le versioni; mai modifiche in corsa |
| **CdA** | i gate ZeroPipes | promuovono o bocciano, meccanicamente; stessi esami di ogni strategia |

## 4. Le quattro decisioni congelate (D1-D4)
**D1**: 3 repliche IDENTICHE dello stesso Trader · **D2**: Claude Sonnet pinnato via API model string (nel FreezeManifest; cambio modello = nuovo track record) · **D3**: Stagione 0 = 4 settimane shadow a SIZE FISSA (direzione e dentro/fuori soltanto; confidence loggata dal giorno 1 per il Brier) · **D4**: temperatura = default operativo dell'API, MAI 0 (a T≈0 il metro del rumore collassa per costruzione).

**Perché le repliche**: Alpha Arena mostra dispersione, non skill. Prima di "quale agente è più bravo" si risponde a "quanto rumore produce UN agente con se stesso". Tre repliche — stesso modello, prompt, temperatura, snapshot — sono il metro del rumore. **Kill-criterion pre-registrato**: se la dispersione inter-repliche domina il gap agente-macchina, verdetto "no skill misurabile" e il Lab si declassa a puro generatore di ipotesi.

## 5. Gli otto componenti (+2 di controllo)
1. **Tool Server MCP** read-only point-in-time: lo **snapshot del giorno è costruito UNA volta** (ora UTC fissa, la stessa della gamba meccanica) e congelato; le repliche interrogano quel mondo, mai dati live (altrimenti la varianza degli input contamina il metro del rumore). Logging totale (anche COSA chiede l'agente è dato). Firewall fisico: nessun path verso holdout o moduli verdetto. Descrizioni dei tool neutre (niente verbi valutativi).
2. **Decision Record** (schema v1, 10ª revisione): rationale libero PRIMA (anti format-tax), blocco strutturato DOPO via strict tool use; `features_used` {nome primitiva, valore numerico}; confidence 0-1; invalidation conditions ex-ante; expected holding; riferimenti freeze (model_version, prompt_sha, context_git_sha, replica_id, snapshot_id). **No verbale conforme = no trade** (retry singolo dichiarato, poi rejected_malformed).
3. **Trader Ledger** append-only con hash-chain, write-once per (giorno, replica, asset).
4. **Confronto appaiato** giornaliero vs gamba meccanica: stesso universo, stesso istante di decisione, differenze daily in un **e-process anytime-valid** (ONS) — pannello leggibile ogni giorno senza peccato statistico; verdetti solo alla dichiarazione.
5. **Autopsia TRIMESTRALE** per lotti (mai mensile: potenza insufficiente; mai dal singolo trade): divergenze → tassonomia pre-registrata → subgroup discovery + FDR Benjamini-Yekutieli + holdout split → ipotesi → Pre-Screen → eventuali formule meccaniche.
6. **Trader Freeze**: modello pinnato + context files in git + temperatura/sampling dichiarati + log completi + OTS.
7. **Behavioral Telemetry**: turnover, flip rate, tentativi bloccati dal Risk Officer, verbali malformati, dispersione giornaliera tra repliche, componenti Brier, reazione ai drawdown (size dopo perdite = firma del gambling).
8. **Decision Replay** (richiesta owner): Decision Snapshot (il mondo completo al momento della scelta) + Outcome Annotation (P&L, MFE/MAE, prezzo a +1g/+7g, invalidation verificate) + pannello **Decision Review** — il "quella volta ho scelto così PER QUESTO motivo". Le lezioni entrano solo alla release successiva.

**Controlli**: **Suite di regressione comportamentale** (l'ON-check del Lab): 10-15 snapshot reali congelati in Stagione 0 (una volta, mai più toccati), rigiocati settimanalmente con k=5 campioni; metrica dichiarata ex-ante (action agreement rate + distanza media su confidence); soglie di allarme e di sunset fissate PRIMA della baseline; deriva oltre soglia ⇒ track record chiuso pulito (**model sunset**). **Faithfulness Audit** (vedi Auditor): il verbale è un'ipotesi, mai una verità — fedeltà misurata, non presunta; niente reporter separato (privileged access).

## 6. Il rito quotidiano (una catena, sempre uguale)
Chiusura barra daily UTC fissa → SnapshotBuilder congela il mondo → 3 repliche decidono in isolamento (zero contesto condiviso) → verbali validati → Risk Officer clampa → ShadowFill a costi reali Hyperliquid (maker 1,5 bps, taker 4,5) → ledger → e-process → pannello + telemetria.

## 7. Le stagioni
**Stagione 0** (4 settimane, shadow, size fissa): parte SOLO post-GO del Pre-Screen e con autorizzazione owner; misura il rumore tra repliche, accumula il Brier, congela gli snapshot della suite. **Stagione 1** (90 giorni): track record vero, sizing libero ma clampato (qui si riaggancia il meta-labeling sulla confidence calibrata), confronto appaiato quotidiano, verdetti solo a fine finestra, suite settimanale come sentinella. **Live micro** (100-200€) SOLO dopo TUTTI i gate — gli stessi di qualsiasi strategia; poi scala quarter-Kelly.

## 8. Stato attuale e dipendenze
**Fase 0 in build** (prompt lanciato: 6 blocchi — contratti → Tool Server → enforcement+Risk Officer → ledger+telemetria+e-process → orchestratore repliche con MockLLM → scheletro suite; STOP con LAST_REPORT.md; nessuna stagione parte dal build). **Mancano per la Stagione 0**: universo ufficiale dal Pre-Screen; gamba meccanica per il confronto (dalla campagna carry, se GO); PREREG_LAB_S0; pin effettivo del modello + OTS del FreezeManifest; soglie della suite fissate dall'owner. **Sinergia**: la libreria e-process è UNA — Blocco 4 del Lab ↔ holdout sequenziale della campagna carry (§8 Costituzione).

## 9. Orizzonte (in ordine di maturazione)
Seconda variante in arena: il multi-agente deliberativo TradingAgents-style (misura del valore del debate — aspettativa a priori bassa) e/o Opus come variante "quanto cervello serve" · **Folla Sintetica** (colonia di agenti naive = sensore contrarian) · **Mondi Paralleli** (mercati sintetici block-bootstrap = esame d'ammissione anti-leakage) · **Idea #8 — Redazione Sigillata** (desk che si guadagnano l'ingresso nel contesto passando i gate): PARCHEGGIATA con due vincoli — i desk non decidono mai; l'ingresso di testo nel contesto richiede emendamento esplicito alla regola no-feed-testuali con hardening anti-injection · **La Casa**: il tribunale che certifica agenti diventa il prodotto (fase monetizzazione).

## In una riga
zeroPipes è il tribunale, traderLab è l'imputato più interessante — e anche se viene condannato, ogni sua deposizione insegna qualcosa al tribunale.
