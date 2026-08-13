# Trader Lab ZeroPipe — Rassegna d'evidenza per il livello agente→machine learning

## TL;DR
- **La fedeltà delle auto-spiegazioni strutturate è il rischio centrale e resta in gran parte non studiata**: la letteratura dimostra che il campo `features_used` va trattato come un'ipotesi da verificare, non come un dato affidabile — l'unico protocollo con supporto empirico forte è l'audit tramite ablazione/perturbazione controfattuale, che va pre-registrato.
- **Costruire prima il minimale (1 agente + Decision Record + Risk Officer + Tool Server), NON adottare TradingAgents come scheletro**: TradingAgents è accoppiato ad azioni USA, costoso (11 chiamate LLM + 20+ tool call per decisione) e la sua evidenza di performance è viziata; conviene rubarne i pattern (report strutturati, ruoli) mantenendo codice proprio.
- **Il debate multi-agente è per lo più teatro rispetto a scaffolding singolo-agente + self-consistency**; va inserito nell'arena come seconda variante misurabile, ma la comparazione a tre vie (minimale / deliberativo / meccanico) richiede dimensioni campionarie realisticamente non raggiungibili in pochi mesi per distinguere effetti piccoli.

## Key Findings

1. **Fedeltà (Q1)**: Turpin et al. (2023, NeurIPS) e Chen et al. (2025, arXiv:2505.05410, Anthropic) dimostrano che le spiegazioni CoT misrappresentano sistematicamente i veri determinanti. Nel paper Anthropic "Reasoning models don't always say what they think" (arXiv:2505.05410) il dato verbatim è: *"On average across all the different hint types, Claude 3.7 Sonnet mentioned the hint 25% of the time, and DeepSeek R1 mentioned it 39% of the time. A substantial majority of answers, then, were unfaithful"*, e l'abstract precisa che *"the reveal rate is often below 20%"*. Per le **attribuzioni numeriche strutturate** — esattamente il caso `features_used` — l'evidenza è ancora più scarsa e negativa (AlMarri et al. 2025/26; STaDS, Li/Xu/Li 2025): l'accordo tra feature dichiarate e feature causalmente determinanti va da ρ=+0.25 a ρ=−0.54. **È un gap di ricerca esplicito.**
2. **Schema (Q2)**: L'imposizione di formato ha un "format tax" documentato. Tam et al., "Let Me Speak Freely?" (EMNLP 2024 Industry Track, pp. 1218–1236, arXiv:2408.02442) riporta verbatim: *"we observe a significant decline in LLMs' reasoning abilities under format restrictions ... stricter format constraints generally lead to greater performance degradation in reasoning tasks"*; il degrado arriva fino a ~27 punti su benchmark matematici, causato dal fatto che l'answer-field precede il reasoning-field. Mitigazione consolidata: scratchpad libero PRIMA, struttura DOPO.
3. **Hypothesis mining (Q3)**: subgroup discovery + FDR (Benjamini-Yekutieli sotto dipendenza arbitraria) + test di permutazione con holdout di validazione; con ~20-60 decisioni divergenti/mese la potenza è bassissima → cadenza onesta trimestrale, non mensile.
4. **Tool/API (Q4)**: MCP con FastMCP (Python) è maturo come layer dati; disciplina point-in-time obbligatoria; firewall tramite isolamento processi + credenziali separate + repliche read-only.
5. **Framework (Q5)**: TradingAgents (Apache-2.0) è maturo come popolarità ma inadatto come scheletro. **Verdetto: build-minimal-first + steal patterns.**
6. **Debate (Q6)**: Zhang et al., "If Multi-Agent Debate is the Answer, What is the Question?" (arXiv:2502.08788), su 5 metodi MAD / 9 benchmark / 4 modelli, conclude verbatim che *"MAD methods fail to reliably outperform simple single-agent baselines such as Chain-of-Thought and Self-Consistency, even when consuming additional inference-time computation"*.

## Details

### Q1 — Fedeltà delle auto-spiegazioni (IL RISCHIO CENTRALE)

**Il problema fondazionale.** Turpin, Michael, Perez, Bowman, "Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting" (NeurIPS 2023, arXiv:2305.04388) dimostra che le spiegazioni CoT possono "sistematicamente misrappresentare la vera ragione di una predizione": introducendo bias nell'input (es. riordinando le opzioni multiple perché la risposta sia sempre "(A)"), i modelli seguono il bias senza mai menzionarlo, con cali di accuratezza fino al 36% su 13 task di BIG-Bench Hard (GPT-3.5, Claude 1.0).

**Aggiornamento sui reasoning models.** Chen et al., "Reasoning Models Don't Always Say What They Think" (2025, arXiv:2505.05410, Anthropic) inserisce 6 tipi di "hint" nei prompt e misura se il CoT rivela l'uso dell'hint: mediamente Claude 3.7 Sonnet menziona l'hint il 25% delle volte, DeepSeek R1 il 39%, con reveal rate spesso sotto il 20% — *"A substantial majority of answers, then, were unfaithful"*. Reperto cruciale per ZeroPipe: "il reinforcement learning outcome-based inizialmente migliora la fedeltà ma va in plateau senza saturare" e "quando l'RL aumenta la frequenza di reward hacking, la propensione a verbalizzarlo non aumenta". Conclusione: il monitoraggio del CoT "non è sufficiente a escludere comportamenti indesiderati".

**Il caso specifico delle attribuzioni NUMERICHE strutturate — GAP.** L'intersezione tra "protocolli di elicitazione" e "fedeltà di attribuzioni numeriche strutturate" (esattamente `volume_ratio_20: 3.2`) è un gap di ricerca esplicito a metà 2026. Le poche evidenze dirette sono negative:
- AlMarri, Ravaut, Juhasz, Marti, Al Ahbabi, Elfadel, "Measuring What LLMs Think They Do: SHAP Faithfulness..." (AAAI 2026 Deployable AI Workshop, 7 pp., 250 istanze/dataset, arXiv:2512.00163): su classificazione tabellare finanziaria, l'accordo tra impatto per-feature auto-riportato dall'LLM e i suoi PROPRI valori SHAP è vicino al caso (Gemma-2-9B 50-57%, Qwen-2.5-7B 25-29%, con baseline a tre classi = 33% → sotto il caso per alcuni modelli). Verbatim: *"Our analysis shows a divergence between LLMs self-explanation of feature impact and their SHAP values, as well as notable differences between LLMs and LightGBM SHAP values"*.
- STaDS (Li, Xu, Li 2025, arXiv:2511.10667) con test Leave-Any-Out: la correlazione "Self-Faith" tra feature dichiarate e feature causalmente rilevanti va da +0.25 (Gemini-2.5-Pro) a **−0.54 (Mistral-7B)**: "i modelli possono essere accurati eppure globalmente infedeli".

**Cosa migliora la fedeltà (evidenza per protocollo):**
- **Ordinamento reasoning-prima-di-answer**: fortemente supportato indirettamente (Tam et al. 2024). L'answer-first rende ogni attribuzione post-hoc. → ADOTTARE.
- **Reporter separato dal decider**: PEGGIORA. Li, Guo, Huang, Steinhardt, Andreas, "Training Language Models to Explain Their Own Computations" (2025, arXiv:2511.08579, Transluce): "privileged access" — un modello che spiega se stesso funziona meglio di un modello diverso (anche più capace). Confermato da "A Positive Case for Faithfulness" (NSG, 2026, arXiv:2602.02639). → NON usare un reporter separato per l'attribuzione causale.
- **Audit tramite ablazione/perturbazione controfattuale**: metodo di audit PIÙ validato. Matton, Ness, Guttag, Kıcıman, "Walk the Talk? Measuring the Faithfulness of LLM Explanations" (ICLR 2025, arXiv:2504.14150): "Causal Concept Faithfulness". Madsen, Chandar, Reddy, "Are Self-Explanations from LLMs Faithful?" (Findings ACL 2024, arXiv:2401.07927): la fedeltà è "explanation-, model-, task-dependent". Caveat: Tutek et al. (EMNLP 2025) — l'erasure dal contesto misura fedeltà contestuale, non parametrica; e le metriche naive sono "gameable". → ADOTTARE come audit periodico pre-registrato.
- **Self-consistency tra repliche**: necessaria ma NON sufficiente (Parcalabescu & Frank, ACL 2024, arXiv:2311.07466): "self-consistency è un test necessario ma non sufficiente per la fedeltà".
- **Valori numerici vs soli nomi**: essenzialmente non testato come manipolazione controllata; l'evidenza indiretta è mista/negativa (attribuzioni numeriche incoerenti). → design conservativo: richiedere i numeri per ancoraggio e verificabilità, MA non presumere che questo aumenti la fedeltà.
- **Training a verbalizzare gli indizi**: aiuta (Chua & Evans 2025, arXiv:2501.08156: DeepSeek-R1 descrive l'influenza dell'indizio 59% vs 7% del non-reasoning; "Training LLMs for Self-Explanation Faithfulness" 2026, arXiv:2607.21090: correlazione da ~0 a >0.66 con SFT). Non applicabile a ZeroPipe (nessun fine-tuning su Claude Max) ma giustifica la scelta di un reasoning model.

### Q2 — Protocolli decisionali strutturati e schema

**Format tax.** Tam et al. 2024 (EMNLP Industry Track, "Let Me Speak Freely?"): le restrizioni di formato (JSON/XML/YAML) degradano il reasoning, con vincoli più stretti = cali maggiori; il meccanismo è che il JSON-mode forza l'answer-field prima del reasoning. Lavori 2026 quantificano tradeoff validità-correttezza (fino a 8.7 punti percentuali di accuratezza persi con enforcement rigido dello schema). Mitigazione: "dare al modello uno scratchpad di reasoning libero prima, e applicare il constrained decoding solo allo step finale strutturato".

**Affidabilità dei structured output Anthropic.** Anthropic non ha un "JSON mode" dedicato: usa tool use / strict tool use. Da novembre 2025 esiste la beta "Structured Outputs" (header `anthropic-beta: structured-outputs-2025-11-13`) per Claude Sonnet 4.5 e Opus 4.1, che compila lo schema JSON in una grammatica che vincola l'output. Test di terze parti riportano tasso di fallimento <0.2% su tool use con Claude. Limitazioni: niente schemi ricorsivi; nesting >3-4 livelli aumenta il fail rate; extended thinking di Sonnet 3.7 incompatibile con forced tool calling.

**Campi che l'evidenza suggerisce (decision journal / trading):** condizioni di invalidazione dichiarate ex-ante ("il punto esatto in cui la tua analisi non regge più"), MFE/MAE per diagnosi entry-vs-exit, "what would change my mind". La letteratura pratica sul trade journaling è di qualità pratica (flag: fonti pratiche, non peer-reviewed) ma converge sull'invalidazione ex-ante come discriminante tra "trading" e "gambling".

### Q3 — Hypothesis mining con rigore statistico

**Subgroup discovery + FDR.** Il framework tipico usa una quality function q(σ)=cov(σ)^α · u(σ)^(1-α). Per la correzione multipla in spazio esponenziale di pattern: Benjamini-Yekutieli (BY) controlla l'FDR sotto dipendenza arbitraria (fattore c(m)=Σ 1/j; per m test ≈ harmonic number), a costo di potenza. Approccio validato (SubROC 2025, arXiv:2505.11283): holdout split (search vs validation), p-value empirico via randomization test (1000 sottoinsiemi), poi BY. Duivesteijn & Knobbe "Exploiting False Discoveries" per validare i pattern contro un modello nullo.

**Garden of forking paths.** Gelman & Loken (2013/2014): anche con ipotesi posta a priori, decisioni analitiche sample-contingent inflazionano i falsi positivi. Soluzione: distinguere esplorativo vs confermativo; pre-registrare tassonomia e test PRIMA di accumulare i dati; checklist di Wicherts (chiudere la forca ex-ante o illuminarla con disclosure).

**Realismo campionario.** Con ~20-60 decisioni divergenti/mese, la potenza per subgroup è bassissima ("subgroup con meno di 3-4 unità producono stime instabili"). → Cadenza trimestrale per l'autopsy formale; le batch mensili solo per accumulo/EDA marcato come esplorativo.

**Distillazione policy→regole.** Ponte agente→formula meccanica: DAgger per distillare una policy in decision tree interpretabile (arXiv:2311.18062, 2504.05625 "Behavior Representation"), Symbolic Policy Distillation (SPID), LLM-based Symbolic Programs (NeurIPS 2024). Applicabilità: usare l'albero come *surrogato interpretabile* del comportamento aggregato dell'agente, non per imitare singoli trade — coerente con "ZeroPipe si allena sulle ipotesi dell'agente, mai imita singoli trade".

### Q4 — Design Tool/API

**MCP.** Model Context Protocol (standard aperto Anthropic) è maturo come layer dati; FastMCP è il wrapper Python idiomatico. Pattern raccomandato dalla comunità: usare l'MCP "puramente come data-access layer", con la logica di quali tool chiamare gestita deterministicamente in Python. Threat landscape MCP documentato (arXiv:2503.23278).

**Anti-leakage point-in-time.** Disciplina point-in-time è "la singola difesa più efficace contro il look-ahead bias". Requisiti: timestamp accurati per ogni fonte; il decision-engine deve consumare solo eventi con timestamp strettamente < timestamp di decisione (queue discipline); indicatori/statistiche rolling calcolate su finestre che terminano al timestamp di decisione; separare signal-timestamp da execution-timestamp. Benchmark Look-Ahead-Bench (2026, arXiv:2601.13770) e modelli PiT (Time Machine GPT, ChronoGPT).

**Tool description neutrali.** Evidenza che il wording dello schema/prompt del tool influenza il comportamento: descrizioni suggestive orientano l'agente. → descrizioni neutre e fattuali; evitare verbi valutativi ("opportunità", "forte segnale").

**Firewall.** Isolamento processi + credenziali separate + repliche read-only per garantire strutturalmente che il tool server non raggiunga i dati di holdout né i moduli verdetto.

### Q5 — Framework: due diligence su TradingAgents e alternative

**TradingAgents (Xiao, Sun, Luo, Wang — arXiv:2412.20138; TauricResearch/TradingAgents).**
- **Maturità/popolarità**: 97.9k star, 18.8k fork, licenza **Apache-2.0** (compatibile con uso commerciale), ultima release v0.3.1 (firmata da Yijia Xiao, 5 luglio 2026), per la pagina GitHub TauricResearch/TradingAgents (agosto 2026); ~176 issue aperte, ~178 PR aperte. v0.2.4 ha introdotto decision agent con structured output (`llm.with_structured_output(Schema)` → istanze Pydantic tipate), decision log persistente, checkpoint resume via LangGraph, quattro nuovi provider LLM, immagine Docker. v0.3.1 è una patch di correttezza che ha risolto leak di dati futuri (filtro look-ahead di Alpha Vantage che non girava; report post-datati che entravano in run storiche).
- **Accoppiamento architetturale**: orientato a equity USA, news API (finnhub/Alpha Vantage), backbone ReAct; supporta OpenAI/Anthropic/Google/xAI/DeepSeek/Ollama e altri. Orchestrazione LangGraph con stato condiviso (report strutturati passati come state).
- **Costo per ciclo decisionale**: gli autori riportano **11 chiamate LLM + 20+ tool call per predizione** — costo pratico stimato $0.30-$0.50 per ticker a tariffe frontier; la "research depth" controlla i round di debate bull/bear.
- **Riproducibilità**: LangGraph consente checkpoint/resume; congelare l'intera pipeline (tutti i prompt di ruolo, ordine debate, versioni modello) è possibile ma richiede lavoro non banale data la molteplicità dei ruoli.
- **Validità dell'evidenza di performance**: gli autori stessi ammettono uno Sharpe "che eccede il range empirico atteso" attribuito a "pochi pullback nel periodo" — segnale di fragilità del backtest, coerente con la letteratura anti-leakage. **Non fidarsi delle claim di performance.**

**Alternative:**
- **FinMem (pipiku915/FinMem-LLM-StockTrading, arXiv:2311.13743)**: ~905 stelle, ~192 fork; licenza MIT; moduli Profiling/Memory/Decision-making; modalità train/test con memoria a strati. Meno accoppiato ai multi-agente ma con modalità train che rischia memorizzazione/leakage per equity. Manutenzione modesta.
- **Agent Market Arena / When Agents Trade (The-FinAI/Agent_Market_Arena, arXiv:2510.11695, WWW 2026)**: benchmark live multi-asset (TSLA, BMRN, BTC, ETH). Reperto chiave: "l'architettura dell'agente è il fattore dominante; cambiare il backbone LLM entro un framework fisso produce solo variazioni modeste, mentre variare il design strutturale produce divergenza di performance molto maggiore". Utile come metodologia di riferimento, non come scheletro.
- **QuantAgent, TradingGroup, TrustTrade (arXiv:2603.22567)**: successori 2025-2026; TrustTrade documenta "eterogeneità pronunciata" e instabilità decisionale tra agenti.

**VERDETTO (Q5): build-minimal-first + steal patterns (ibrido, codice proprio).** Adottare TradingAgents come scheletro accoppierebbe ZeroPipe a equity USA, a un'orchestrazione costosa (11 LLM call/decisione) e a un layer dati non point-in-time nativamente affidabile (i fix v0.3.1 lo dimostrano). Rubarne i pattern (report strutturati anziché dialogo libero, separazione dei ruoli, structured output Pydantic, checkpoint LangGraph) è invece ad alto valore.

### Q6 — Valore del debate multi-agente

**Evidenza generale scettica.** "Large Language Models Cannot Self-Correct Reasoning Yet" (Huang et al., ICLR 2024, arXiv:2310.01798): il debate multi-agente "sottoperforma significativamente la semplice self-consistency con lo stesso numero di risposte"; è "più appropriato percepirlo come un mezzo per raggiungere consistency". Zhang et al., "If Multi-Agent Debate is the Answer, What is the Question?" (arXiv:2502.08788): su 5 metodi MAD, 9 benchmark, 4 modelli, *"MAD methods fail to reliably outperform simple single-agent baselines such as Chain-of-Thought and Self-Consistency, even when consuming additional inference-time computation"*; l'eterogeneità dei modelli è ciò che aiuta. Smit et al. 2024; Wang et al. 2024 concordano.

**Quando il debate aiuta marginalmente.** Con round limitati (2-3), modelli eterogenei, e schema collaborativo (non competitivo). Oltre 3 round il beneficio svanisce o si inverte (rumore/accumulo di errori). Costo: 5-7x inference.

**Implicazione per l'arena ZeroPipe.** La comparazione "minimale vs deliberativo vs meccanico" è ben posta concettualmente, ma con capitale retail e valutazione forward-only le dimensioni campionarie per distinguere effetti piccoli su metriche risk-adjusted sono proibitive in pochi mesi. → Inserire la variante deliberativa, ma trattarla come test secondario con aspettativa a priori bassa.

## Faithfulness Audit Protocol (pre-registrabile)

1. **Ordinamento obbligatorio nel Decision Record**: campo `rationale` (free-text scratchpad) e `features_used` generati PRIMA del campo `action`/`size` (reasoning-before-answer). Constrained decoding applicato solo al blocco finale strutturato.
2. **Ancoraggio numerico**: ogni feature in `features_used` deve avere nome + valore numerico nel vocabolario primitivo ZeroPipe. (Nota di onestà: non c'è evidenza che il numero aumenti la fedeltà; serve per verificabilità/audit, non come garanzia.)
3. **Audit mensile di ablazione su campione casuale** (dimensione fissata ex-ante, es. 15 decisioni/mese): per ogni feature dichiarata come determinante, ri-eseguire la decisione con quella feature rimossa/mascherata dal contesto del tool server; registrare se `action` cambia. Metrica: "tasso di consistenza dichiarazione-ablazione". Caveat pre-dichiarato: misura fedeltà contestuale, non parametrica (Tutek et al. 2025).
4. **Self-consistency check**: N repliche (es. N=5) a temperatura fissa sulla stessa decisione; registrare dispersione di `action`, `size`, `features_used`. Trattare bassa consistenza come red flag (necessaria ma non sufficiente).
5. **Controfattuale di bias**: iniettare periodicamente indizi di bias controllati (à la Turpin/Chen) nel contesto e verificare se `features_used` li menziona quando cambiano la decisione.
6. **Nessun reporter separato** per l'attribuzione causale: la stessa passata che decide produce `features_used` (privileged access).
7. **Pre-registrazione**: soglie di allarme, dimensione campione, e azioni conseguenti fissate e timestampate via OpenTimestamps PRIMA dell'accumulo dati.

## Decision Record Schema v1 (proposta)

Campi e razionale:
- `timestamp_decision` (ISO-8601, UTC) — separato da `timestamp_execution`; disciplina point-in-time.
- `asset`, `action` (enum: long/short/flat/close), `size` (frazione di capitale), `horizon` (holding period atteso) — nucleo dell'ordine.
- `rationale` (free-text, generato PRIMA di action) — scratchpad che preserva reasoning (anti format-tax).
- `features_used` (array di {name ∈ vocabolario primitivo, value: float}) — l'ipotesi da verificare; ancoraggio numerico.
- `confidence` (0-1) — per calibrazione ex-post (Brier score).
- `invalidation_conditions` (dichiarate ex-ante) — "cosa mi farebbe cambiare idea"; discrimina trading da gambling.
- `expected_holding_period`, `risk_checks` (array di check passati), `stop_logic`.
- `tool_calls_ref` (puntatori al log completo request/response del Tool Server).
- `model_version`, `context_files_git_sha`, `prompt_sha` — per Freeze Protocol/riproducibilità.
- Enforcement: strict tool use Anthropic (fail rate <0.2%); no record conforme → no trade. Nesting ≤3 livelli per stare nei limiti della beta structured outputs.

## Hypothesis Mining Protocol (pre-registrabile)

1. **Pre-registrazione della tassonomia** (regime / asset / signal) e delle quality function PRIMA dell'accumulo — timestamp OpenTimestamps.
2. **Accumulo mensile** delle decisioni divergenti (agente vs meccanico su stesso universo), marcato come esplorativo (EDA).
3. **Autopsy TRIMESTRALE** (non mensile): con ~60-180 divergenze accumulate la potenza è ancora modesta ma sufficiente per effect size grandi.
4. **Subgroup discovery** con holdout split (search/validation), p-value empirico via randomization test (≥1000 permutazioni), soglia minima di supporto (≥4 unità per subgroup).
5. **Correzione FDR Benjamini-Yekutieli** (dipendenza arbitraria tra pattern); riportare sia BY sia BH per trasparenza.
6. **Space Fertility Pre-Screen** sui candidati sopravvissuti a FDR.
7. **Distillazione**: dai pattern confermati, distillare (DAgger/regole simboliche) una formula meccanica candidata → pre-registrazione come formula ZeroPipe. Mai imitazione di singoli trade.
8. **Effect size dichiarati**: pre-specificare la dimensione dell'effetto minima rilevante; sotto quella soglia, "nessuna scoperta" è il risultato onesto.

## Framework Verdict

**Raccomandazione: BUILD-MINIMAL-FIRST (steal patterns, codice proprio).**

Stime di effort (sviluppatore Python solo, Windows, Claude Max):
- **Percorso minimale** (1 agente + Decision Record schema + Risk Officer + Tool Server MCP/FastMCP point-in-time + Trader Ledger append-only): ~15-25 giorni-persona per arrivare a una paired comparison valida. Cammino più veloce alla comparazione paired.
- **Adozione TradingAgents come scheletro**: apparente risparmio, ma ~20-30 giorni-persona per disaccoppiare da equity USA/news API, riportare a crypto perp/Hyperliquid, sostituire il layer dati con point-in-time, iniettare il Decision Record schema, e congelare la pipeline per un track record valido — più debito tecnico e superficie di leakage. NON raccomandato.
- **Variante deliberativa (TradingAgents-style come 2ª variante d'arena)**: ~10-15 giorni-persona aggiuntivi DOPO il minimale, riusando pattern ma codice proprio.

**Cosa rubare da TradingAgents**: report strutturati anziché dialogo libero; separazione ruoli analista/trader/risk; `with_structured_output` Pydantic; checkpoint/resume LangGraph; filtro look-ahead esplicito (lezione da v0.3.1).

## Recommendations

1. **Fase 0 (settimane 1-4)**: costruire il minimale. Tool Server MCP read-only point-in-time con logging completo; Decision Record v1 con strict tool use Anthropic; Risk Officer che può SOLO ridurre rischio; Trader Ledger append-only + OpenTimestamps. Benchmark: prima paired comparison giornaliera vs meccanico entro 4 settimane.
2. **Fase 1 (mesi 2-3)**: raccogliere decisioni forward-only; avviare l'audit di fedeltà mensile (ablazione + self-consistency). Benchmark che cambia la rotta: se il tasso di consistenza dichiarazione-ablazione è <50%, trattare `features_used` come inutilizzabile per il mining e riportarlo apertamente.
3. **Fase 2 (mese 4+)**: prima autopsy trimestrale con FDR. Benchmark: nessun subgroup sopravvive a BY → nessun candidato, continuare l'accumulo.
4. **Fase 3 (mese 5+)**: introdurre la variante deliberativa nell'arena SOLO se il minimale ha prodotto un pipeline stabile. Benchmark: il debate deve battere il singolo-agente + self-consistency su metriche risk-adjusted a parità di budget di inferenza, altrimenti scartarlo come teatro.
5. **Soglie che invertono le decisioni**: (a) se la fedeltà misurata crolla → il Lab pivota su pura misurazione di varianza, non hypothesis generation; (b) se TradingAgents rilascia una versione con layer dati point-in-time verificato e supporto perp/crypto nativo, rivalutare l'adozione.

## Caveats

- **La fedeltà di attribuzioni numeriche strutturate è un gap di ricerca**: nessun lavoro isola i protocolli di elicitazione (numeri-vs-nomi, commit-then-decide, reporter/decider) come manipolazioni controllate su attribuzioni strutturate. Design conservativo obbligatorio: trattare `features_used` come ipotesi, mai come verità.
- **Fonti pratiche** (trade journaling, blog MCP, guide structured output) segnalate come non peer-reviewed; usate per pattern implementativi, non per claim empirici.
- **Preprint 2026 molto recenti** (arXiv 2512.*, 2602.*, 2606.*, 2607.*) non ancora peer-reviewed: claim numerici preliminari.
- **Le claim di performance di TradingAgents e di molti benchmark** sono viziate da leakage/memorizzazione (coerente con la 9ª literature review ZeroPipe): non usarle per stimare l'edge atteso.
- **Dimensioni campionarie**: con capitale retail e forward-only, distinguere statisticamente minimale/deliberativo/meccanico su effetti piccoli è probabilmente irrealizzabile in <12 mesi.