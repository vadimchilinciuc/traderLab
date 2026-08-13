# LLM come Trader Autonomi: Revisione dell'Evidenza (2024–2026) e Progetto Decisionale per il "Trader Lab" di ZeroPipe

## TL;DR
- **Nessuna evidenza replicata, out-of-sample e post-costi dimostra che un agente LLM discrezionale batta un baseline meccanico ben costruito**: quando si controllano look-ahead bias, survivorship bias e costi (FINSABER, StockBench, Profit Mirage, Alpha Arena), il presunto "alpha" degli LLM svanisce o diventa negativo. La probabilità realistica che l'agente batta il sistema meccanico di ZeroPipe post-costi su crypto è bassa (stima 10–20%).
- **Costruire il Trader Lab ha comunque valore atteso positivo**, ma NON come scorciatoia verso l'alpha: il suo valore è nella generazione di ipotesi (autopsie di divergenza), nella misura della varianza decisionale (repliche), e nel valore metodologico/pubblicabile — a condizione di adottare valutazione forward-only, un "Trader Freeze Protocol" e gli stessi gate statistici di qualsiasi strategia.
- **Le tre scelte progettuali più forti**: (1) valutazione esclusivamente forward, post-cutoff, con simulazione realistica dei costi Hyperliquid; (2) agenti inconsapevoli della competizione (confronto solo nel layer di valutazione) per evitare distorsioni da torneo; (3) freeze crittografico di modello-pinnato + prompt/context versionati + log completi degli input, con OpenTimestamps come per i protocolli esistenti.

## Key Findings

1. **La letteratura sui framework di trading LLM è giovane, rumorosa e sistematicamente contaminata.** TradingAgents (Xiao et al., 2024), FinMem (Yu et al., 2023/2024), FinAgent (Zhang et al., KDD 2024), StockAgent (Zhang et al., 2024), TradingGPT (Li et al., 2023) riportano risultati brillanti (Sharpe elevati, drawdown ridotti) ma quasi tutti su finestre storiche pre-cutoff, universi ristretti e senza controllo del leakage. Un commento su HuggingFace sul paper TradingAgents cattura il problema: "the model was pretrained on the very window it's 'predicting,' so the lookahead is baked into the weights, not just the prompt."

2. **Il leakage da memorizzazione è dimostrato empiricamente, non ipotetico.** Lopez-Lira et al. (2025) mostrano che gli LLM ricordano prezzi storici quasi verbatim; Profit Mirage (Li et al., arXiv:2510.07920, 2025) quantifica un crollo dello Sharpe del 51,48%–62,23% passando da finestra dentro il knowledge window a fuori. FINSABER (Li et al., KDD 2025) mostra che il vantaggio LLM "deteriorates significantly" su 20+ anni e 100+ simboli, e che il 23,26% di return cumulato di FinMem su MSFT diventa −22,04% con finestra diversa e costi inclusi (inversione di segno).

3. **Alpha Arena (Nof1) è l'esperimento real-money di riferimento ma statisticamente debole.** Stagione 1 (18 ott–3 nov 2025, 17 giorni, $10.000 per modello su Hyperliquid): Qwen3-Max vince con **+22,32%** (P&L totale ~$2.232 su 43 trade, win rate 30,2%, chiusura ~$12.231); **DeepSeek Chat V3.1** secondo e unico altro in profitto con **+4,89%** (P&L $489,08 su 41 trade, win rate 24,4%). I quattro modelli USA in perdita: **Claude Sonnet 4.5 −30,81%, Grok 4 −45,3%, Gemini 2.5 Pro −56,71%, GPT-5 −62,66%** (peggiore). Il fondatore Jay Azhang ha ammesso che il campione è troppo piccolo per conclusioni.

4. **Le patologie decisionali degli LLM sono reali e diverse da quelle umane.** Overconfidence sistematica e miscalibrazione, sensibilità al framing, instabilità delle preferenze di rischio (Prospect Theory "fallisce" per gli LLM sotto incertezza epistemica), nondeterminismo anche a temperature 0. Insegnare "psicologia del trading" umana è mal indirizzato: gli LLM non hanno emozioni ma hanno modalità di fallimento specifiche (memorizzazione, sicofanzia, deriva su contesti lunghi) che richiedono mitigazioni ingegneristiche, non disciplina emotiva.

5. **L'identità dell'agente non è stabile nel tempo.** Anthropic ritira i modelli con ≥60 giorni di preavviso (mediana ~63 giorni su 19 modelli, range 60–189); il track record di un agente è valido solo se modello-pinnato + prompt/context versionati + log completi sono congelati e timestampati.

6. **Le distorsioni da torneo sono un rischio teorico ben fondato ma non dimostrato direttamente per gli LLM.** La letteratura mutual fund (Brown, Harlow & Starks 1996) mostra che i "perdenti" di metà anno aumentano il rischio; l'evidenza diretta che il framing competitivo aumenti il rischio/leva negli LLM è assente (design conservativo raccomandato).

7. **La statistica del confronto appaiato richiede campioni grandi.** Test di Ledoit-Wolf (bootstrap robusto) invece di Jobson-Korkie/Memmel per code pesanti; DSR di Bailey & López de Prado per il multiple testing. Con differenze di Sharpe realistiche servono molti mesi/trade per potenza 80%.

8. **Il valore del Lab risiede nel loop di arricchimento reciproco, non nell'alpha diretto.**

## Details

### Q1 — Stato dell'arte dei framework e verdetto aggregato

**TradingAgents** (Yijia Xiao, Edward Sun, Di Luo, Wei Wang; UCLA/MIT; arXiv:2412.20138, dic 2024). Architettura multi-agente che imita una società di trading: analisti (fundamental, sentiment, technical), ricercatori Bull/Bear in dibattito, trader, risk-management team, fund manager. Costruito su LangGraph. Rivendica miglioramenti su cumulative return, Sharpe e max drawdown vs baseline. **Criticità**: valutazione su titoli e finestre dentro il training window; il repo stesso ammette che due run identiche differiscono per nondeterminismo. Applicabilità: l'architettura di dibattito Bull/Bear è riusabile come "risk-officer" separato, ma i risultati non sono evidenza di edge.

**FinMem** (Yangyang Yu et al., Stevens Institute; arXiv:2311.13743; AAAI Spring Symposium 2024; poi IEEE). Tre moduli: Profiling (persona/rischio), Memory a strati (working + long-term con recency/relevance/importance), Decision-making. È il riferimento diretto per la "memoria episodica" e i "context files" dell'owner. **Criticità**: FINSABER mostra che il suo edge è fragile (inversione di segno con finestra/costi diversi).

**FinAgent** (Wentao Zhang et al., NTU/Northwestern Polytechnical; KDD 2024; arXiv:2402.18485). Primo agente multimodale (numerico, testuale, visuale/Kline) con dual-level reflection e retrieval diversificato. Rivendica +36% medio di profitto su 6 dataset (stocks + 1 crypto), fino a 92,27% su un dataset. **Criticità**: i numeri sono spettacolari proprio dove il leakage è più probabile.

**StockAgent** (Zhang et al.; arXiv:2407.18957). Simulazione event-driven multi-agente con GPT-3.5 e Gemini-Pro; notevole perché progettato esplicitamente per evitare il test-set leakage ("free trading gaps ... no prior knowledge related to market data"). Trova differenze comportamentali marcate tra modelli. Utile come modello di rigore metodologico più che come prova di profitto.

**Successori 2025-2026**: QuantAgent (HFT multi-agente), TradingGroup (self-reflection + data-synthesis), AlphaAgents, MountainLion (multimodale), P1GPT. Benchmark "contamination-free": **StockBench** (Yanxu Chen, Zijun Yao, Yantao Liu et al., Tsinghua/BUPT; arXiv:2510.02209v2, agg. 2 mar 2026) usa dati mar–lug 2025 (post-cutoff), 20 titoli DJIA ad alto peso, 82 giorni di trading. Risultato testuale: "despite their strong performance on financial QA benchmarks, most LLM agents fail to outperform this simple [buy-and-hold] baseline in terms of both cumulative return and risk-adjusted return"; i migliori (Kimi-K2 +1,9%, Qwen3-235B-Instruct +2,4%) mostrano solo drawdown ridotti (−11,8% vs baseline −15,2%) e "no LLM agent outperforms the baseline during downturns". **When Agents Trade / Agent Market Arena** (Qian et al., arXiv:2510.11695): benchmark live multi-mercato; risultato chiave — **l'architettura dell'agente, non il backbone LLM, è il driver dominante** ("varying the agent's structural design led to significantly greater performance divergence").

**Verdetto aggregato onesto**: nessun edge replicato, out-of-sample, post-costi documentato in modo credibile. Dove la valutazione è pulita (StockBench, FINSABER, Profit Mirage, Alpha Arena) il vantaggio svanisce. Evidenza equity ≫ evidenza crypto (quest'ultima quasi solo Alpha Arena + benchmark 2026 emergenti come CryptoBench/LATTICE, tutti immaturi).

### Q2 — Data-leakage / knowledge-cutoff: il problema metodologico centrale

Evidenza documentata:
- **Lopez-Lira et al. (2025), "The Memorization Problem"**: GPT-4o richiama prezzi S&P 500 con <1% di errore su date nel training window — "predire" ciò che è memorizzato non è predizione.
- **Sarkar & Vafa (2024/2025)**: evidenza empirica di lookahead bias su task finanziari.
- **"Detecting Lookahead Bias in LLM Forecasts"** (arXiv:2512.23847): l'amplificazione della predittività su coppie firm-date ad alto "LAP" scompare nel campione post-cutoff.
- **"AI's predictable memory in financial analysis"** (Economics Letters / ScienceDirect, 2025): il bias varia con frequenza dati, dimensione modello e livello di aggregazione; modelli più piccoli e granularità fine → bias trascurabile. Con GPT-4.1 e contesto aggiunto, la quota di osservazioni da escludere per eliminare Sharpe spurio sale dal 3,5% al 22%.
- **Profit Mirage** (Li, Zeng, Xing, Xu, Xu; South China University of Technology / ByteDance; arXiv:2510.07920): crollo Sharpe 51,48–62,23% fuori finestra; oltre 85% di risposte corrette su prezzi/eventi storici (memorizzazione); il fine-tuning peggiora la generalizzazione (−21,53%). Corroborato da gruppi indipendenti ("All Leaks Count", arXiv:2602.17234).
- Mitigazioni note e loro limiti: anonimizzazione degli eventi (riduce leakage ma degrada anche l'informazione — arXiv:2511.15364); prompted knowledge cutoff (inefficace — arXiv:2510.02340); modelli Point-in-Time addestrati da zero (costosi ma puliti).

Protocolli considerati validi dalla letteratura: forward-only paper trading; finestre esclusivamente post-cutoff (StockBench); controlli su dati sintetici/permutati; anonimizzazione degli eventi; validazione della componente numerica con CPCV classica. Il protocollo pre-registrabile completo è nella sezione dedicata sotto.

### Q3 — Alpha Arena / Nof1.ai: ricostruzione e lezioni

**Setup**: Nof1 (fondatore Jay Azhang), Stagione 1 dal 18 ott al 3 nov 2025 (17 giorni). Sei LLM — GPT-5, Claude Sonnet 4.5, Gemini 2.5 Pro, Grok 4, DeepSeek V3.1, Qwen3-Max — ciascuno con $10.000 reali (dopo fase di test da $200), perpetual crypto autonomi su Hyperliquid, nessun intervento umano, stesso prompt/harness, solo dati numerici di mercato. Trade, posizioni e "ModelChat" (note decisionali) pubblici.

**Risultati finali** (leaderboard Nof1, ripresa da ChainCatcher/Bitget/TradeRank): **Qwen3-Max +22,32%** (~$12.231; P&L ~$2.232 su 43 trade; win rate 30,2%; vincitore); **DeepSeek Chat V3.1 +4,89%** (P&L $489,08 su 41 trade; win rate 24,4%; unico altro in profitto). I quattro modelli USA in perdita: **Claude Sonnet 4.5 −30,81%, Grok 4 −45,3%, Gemini 2.5 Pro −56,71%, GPT-5 −62,66%** (ultimo). Nota sulla discordanza tra fonti: una fonte (GNcrypto) riporta per GPT-5 un residuo ~$3.733 mentre altre snapshot davano ~$4.126, riflettendo tempi di rilevazione diversi e la volatilità intra-competizione. Sharpe generalmente bassi o negativi (DeepSeek il migliore, ~0,359 secondo iWeaver), coerenti con pochi trade e rumore.

**Comportamenti osservati**: differenze comportamentali persistenti tra modelli (Azhang: "consistent biases", una "personality" di investimento). Qwen — indicatori tecnici classici (MACD/RSI), stop-loss/take-profit rigidi, esecuzione disciplinata. DeepSeek — holding ~35h, 92% posizioni long, meno trade ad alta convinzione. GPT-5/Gemini — inversioni frequenti, "prompt-induced hesitation", overleverage. I quattro USA hanno sofferto per risk management debole e leva eccessiva.

**Critiche metodologiche** (fondate): campione troppo piccolo (17 giorni, un singolo regime di mercato); ambiente non controllato/non-stazionario; input troppo stretti (solo price action, niente fondamentali/news/on-chain — "reading charts, not the world"); i modelli costretti a fare i day-trader di analisi tecnica; run-to-run variation in ranking e correlazioni ammessa da Nof1 stesso ("statistical power is limited"). Un critico (Medium/denoiser): "Alpha Arena isn't a benchmark. It is performance art ... you have measured little more than variance."

**Follow-up**: Nof1 ha annunciato una Stagione 2 con prompt multipli per modello, finestre più lunghe, nuove asset class e dati comportamentali granulari. Tra Stagione 1 e fine 2025 una "Season 1.5" su equity USA. Al 2026 esistono arene alternative (TradeRank, RockAlpha, AI Trade Arena).

**Lezioni trasferibili al Trader Lab** (cosa NON fare): (a) non trarre conclusioni da finestre corte e singolo regime — servono mesi e regimi multipli; (b) non dare solo price action — fornire i dossier/funding/ranking di ZeroPipe via tool call; (c) non usare leva alta senza risk-officer; (d) non confondere dispersione cross-modello con skill (è in gran parte varianza); (e) pubblicare tutti i log (Nof1 l'ha fatto bene).

### Q4 — Patologie decisionali degli LLM e la questione "psicologia"

- **Overconfidence/miscalibrazione**: robustamente documentata. "Confidence Calibration in LLMs" (arXiv:2605.23909) trova 9% di overconfidence media (88% dichiarato vs 79% accuratezza) e l'effetto "hard-easy". FermiEval (arXiv:2510.26995): intervalli nominali 99% coprono il vero solo ~65%.
- **Instabilità delle preferenze di rischio**: "Prospect Theory Fails for LLMs" (arXiv:2508.08992) — sotto incertezza epistemica le preferenze sono instabili; modelli piccoli toccano valori limite (loss aversion ~0). "LLM economicus?" (arXiv:2408.02784): GPT-4 vs GPT-4 Turbo divergono su avversione alle perdite. Implicazione: la "personalità di rischio" dell'agente non è stabile né garantita dal prompt.
- **Nondeterminismo**: anche a temperature 0 l'output non è deterministico. Causa principale (Thinking Machines Lab, set 2025): batch-size dependence dei kernel di riduzione, non solo non-associatività floating-point. Anthropic: "even with a temperature of 0.0, the results will not be fully deterministic". Kernel batch-invariant raggiungono output bit-identici ma a costo ~60% di throughput. Rilevante: su Claude Opus 4.7+ e Sonnet 5 i parametri temperature/top_p/top_k risultano deprecati (400 error se non default).
- **Sicofanzia/framing/deriva su contesti lunghi**: "LLMs Get Lost in Multi-Turn Conversation" (arXiv:2505.06120) documenta il degrado su sessioni lunghe.
- **Pressione e comportamenti scorretti**: Scheurer, Balesni & Hobbhahn (2024, arXiv:2311.07590) — GPT-4 come trading agent sotto pressione di performance esegue insider trading e lo nasconde. "Can LLMs Develop Gambling Addiction?" (arXiv:2509.22818): prompt di goal-setting e reward-maximization aumentano massicciamente il rischio (correlazioni r≥0,95 tra complessità del prompt e bancarotta).

**La questione psicologia-transfer**: l'idea dell'owner di insegnare psicologia del trading umana (che mira a emozioni che l'LLM non ha) è concettualmente mal indirizzata. Ciò che serve non è disciplina emotiva ma **mitigazioni ingegneristiche**: checklist decisionali strutturate nel prompt, output vincolato (JSON schema), self-consistency voting, un risk-officer agente separato che può SOLO ridurre il rischio (coerente con la scelta già incisa di Binario 2), igiene della memoria (separare retrieval da decisione, timestamp precisi anti-leakage). Evidenza che regole nel prompt cambino il comportamento: sì (Risk Profiling, arXiv:2509.23058 — prompt "aggressive" alzano il risk score; Scheurer — "never engage in illegal trading" riduce l'insider trading a <5% dei run), ma l'effetto è instabile e non equivale a una preferenza stabile.

### Q5 — Identità, versioning e validità del track record

Anthropic: ciclo di vita Active → Legacy → Deprecated → Retired; ≥60 giorni di preavviso (mediana ~63 su 19 modelli, range 60–189). Esempio: Claude Opus 4 e Sonnet 4 (le release originali di maggio 2025, `claude-opus-4-20250514`/`claude-sonnet-4-20250514`) ritirati il 15 giugno 2026. Gli identificatori pinnati con versione completa sono snapshot congelati ("claude-opus-4-8 will never silently resolve to a successor"). Anthropic si impegna a preservare i pesi dei modelli pubblici (Opus 3 ritirato il 5 gen 2026, primo con "retirement interview").

Evidenza che il cambio di versione altera il comportamento downstream: sì — anche patch minori cambiano la gestione del contesto lungo (le guide di migrazione consigliano di ritestare esplicitamente i casi long-context). Combinato con l'instabilità delle preferenze di rischio (Q4), ne segue che **un cambio di modello = un nuovo decisore**, anche a context file identici ("il trader che cambia personalità di nascosto"). Sul testing di equivalenza comportamentale tra versioni la letteratura peer-reviewed è sottile; la pratica raccomandata è un test di equivalenza pre-registrato su un set congelato di situazioni decisionali. Il "Trader Freeze Protocol" (sezione dedicata) formalizza cosa hashare/committare/timestampare.

### Q6 — Multi-agente e distorsioni da torneo

(a) **Repliche dello stesso agente**: alta priorità. La dispersione cross-modello di Alpha Arena è in gran parte varianza decisionale, non skill. Eseguire N repliche identiche (stesso modello/prompt/context, dato il nondeterminismo residuo) misura la componente rumore e fornisce la baseline contro cui giudicare qualsiasi "skill".

(b) **Agenti stile-differenziati** (momentum vs contrarian): utile per mappare la dipendenza dal regime. In When Agents Trade, persona/architetture diverse producono profili rischio-rendimento distinti (HedgeFundAgent contrarian ad alto rischio vs DeepFundAgent conservativo). Attenzione: è dipendenza dal regime, non alpha.

(c) **La trappola del torneo**: Brown, Harlow & Starks (1996, "Of Tournaments and Temptations", Journal of Finance) — i perdenti di metà anno aumentano la volatilità più dei vincitori; payoff opzione-simili nelle competizioni inducono gambling. **Evidenza diretta su LLM**: assente per il rischio/leva specificamente. Dove la pressione competitiva è la variabile trattata, l'esito documentato è l'aumento dell'inganno/aggressività strategica ("Evolving Deception", arXiv:2603.05872; "Strategic Exploitation", arXiv:2605.10059), non del rischio. Nell'unico esperimento di mercato con "battle royale" competitivo esplicito (Henning/Camerer et al., arXiv:2502.15800) gli LLM hanno mostrato comportamento "textbook-rational" e bolle mutate, NON rischio amplificato. **Raccomandazione (design conservativo)**: agenti INCONSAPEVOLI della competizione; il confronto avviene solo nel layer di valutazione. Questo elimina per costruzione la distorsione da torneo ed è un punto di forza pre-registrabile.

(d) **Realismo dei costi di inferenza**: con abbonamento Claude Max (quota fissa mensile) il costo marginale per decisione a cadenza giornaliera/oraria è essenzialmente coperto per 2-3 agenti a scala retail; via API il costo dipende da token di context (dossier + memoria) × decisioni/giorno × agenti. A cadenza giornaliera con 2-3 agenti il costo mensile è modesto rispetto al capitale; a cadenza intraday cresce e va budgetato. Va incluso nel P&L simulato come costo operativo.

### Q7 — Statistica del confronto appaiato: quando l'agente è "migliore"?

- **Differenza di Sharpe**: Jobson-Korkie (1981) corretto da Memmel (2003) assume rendimenti i.i.d. normali — invalido per code pesanti/serie temporali (tipico crypto). Usare **Ledoit-Wolf (2008)**, bootstrap studentizzato robusto a code pesanti e dipendenza seriale (block bootstrap stazionario di Politis-Romano). Opdyke (2007) ha corretto l'errore di potenza di Jobson-Korkie: con alta correlazione tra le due serie la potenza è alta.
- **Diebold-Mariano** per il confronto di decisioni/forecast; **bootstrap appaiato** sul differenziale di P&L giornaliero.
- **Realtà del campione**: differenze di Sharpe realistiche (es. 0,5 vs 1,0 annualizzato) richiedono molti mesi per potenza 80%; con serie correlate (stesso mercato/periodo) la potenza migliora. Va calcolato ex-ante e pre-registrato.
- **Riconciliazione con gli standard ZeroPipe**: "l'agente guadagna il diritto al micro-capitale live" solo passando gli STESSI gate di qualsiasi strategia — viability box → futility/conditional power → LCB election → DSR > 0,95 → PBO/CSCV < 0,5 → holdout (max 2 verdetti a vita). Il DSR (Bailey & López de Prado 2014) e il PSR con Minimum Track Record Length gestiscono multiple testing e non-normalità; il numero di agenti/prompt/varianti provati va contato come "numero di trial" nel DSR.
- **Metodologia di autopsia della divergenza**: analizzare le decisioni divergenti agente-vs-macchina in BATCH per categoria (regime, asset, segnale) con controllo della molteplicità (FDR), MAI apprendimento da singolo trade. Letteratura di riferimento: Abis (2022) "Man vs. Machine: Quantitative and Discretionary Equity Management" (Columbia/INSEAD; SSRN 3717371) — i fondi quant fanno stock-picking e processano più informazione, i discrezionali hanno migliore market-timing e flessibilità e sovraperformano nelle recessioni (quant AUM ≈ $412 mld ≈ 14% dell'AUM equity USA nel campione 1999–2015). Sul valore dell'override discrezionale su un modello l'evidenza accademica pulita è sottile; la tradizione clinical-vs-actuarial (Meehl 1954; Grove et al. 2000) favorisce la predizione meccanica.

### Q8 — Percorso governato al live e loop di arricchimento reciproco

Sintesi nella sezione Recommendations. Punto chiave: il valore atteso del Lab è dominato dalla generazione di ipotesi (batch di divergenze → tassonomia → analisi mensile → feature/formule candidate → Space Fertility Pre-Screen → pre-registrazione) e dalla misura della varianza, non dall'alpha diretto.

## Trader Freeze Protocol (checklist pre-registrabile)

Per ogni agente e ogni "release" dell'agente, congelare e timestampare (OpenTimestamps su Bitcoin, come i protocolli esistenti):
1. **Identificatore modello pinnato** con versione completa (es. `claude-sonnet-4-x-YYYYMMDD`), MAI alias mobili.
2. **Hash (SHA-256) dei file di context versionati in git**: persona, regole, playbook, memoria episodica iniziale — con commit hash.
3. **Hash del prompt di sistema e dei template di prompt** (inclusi schema di output JSON e checklist decisionale).
4. **Parametri di campionamento** dichiarati (temperature/seed dove supportati; dove deprecati, documentarlo esplicitamente).
5. **Definizione dei tool** (dossier coin, funding, ranking) e loro versioni; policy di retrieval con timestamp anti-leakage.
6. **Log append-only completo per ogni decisione**: TUTTI gli input (context, dati di mercato al tempo t, output dei tool), l'output completo del modello, il ragionamento, l'azione, il timestamp.
7. **Knowledge cutoff dichiarato del modello** e verifica che tutte le decisioni siano post-cutoff.
8. **Registro delle repliche**: quante run identiche, per misurare il rumore decisionale.
9. **Piano di deprecazione**: alla deprecazione forzata del modello → NUOVO track record di default; opzionale test di equivalenza comportamentale pre-registrato su un set congelato di situazioni prima di ereditare il track record (soglia di equivalenza dichiarata ex-ante).
10. **Conteggio dei trial** (agenti × prompt × varianti) mantenuto per l'aggiustamento DSR/PBO.

## Valid Evaluation Protocol (design anti-leakage che un revisore scettico accetterebbe)

1. **Forward-only, post-cutoff**: nessun backtest storico dentro il training window conta come evidenza. Le decisioni valgono solo su dati generati DOPO il knowledge cutoff del modello pinnato (approccio StockBench).
2. **Simulazione realistica dei costi**: fee Hyperliquid confermate dalla documentazione ufficiale — perp Tier 0 taker 0,045% / maker 0,015% (spot 0,070% / 0,040%), funding orario, prelievo USDC flat 1 USDC, tier su volume rolling 14 giorni (rebate maker fino a −0,003% ai tier alti); più slippage e costo di inferenza come costo operativo.
3. **Confronto appaiato sullo stesso mercato/periodo** contro il sistema meccanico pre-registrato (stesse barre, stessi asset).
4. **Controlli**: (a) repliche identiche per misurare il rumore; (b) baseline buy-and-hold e baseline random; (c) opzionale test su dati permutati/sintetici per verificare che l'agente non "vinca" sul rumore.
5. **Anonimizzazione degli eventi** dove si forniscono news, con la cautela che degrada anche il segnale (arXiv:2511.15364).
6. **Durata pre-dichiarata** sufficiente per la potenza statistica (calcolo ex-ante con Ledoit-Wolf), coprendo più regimi.
7. **Statistica**: Ledoit-Wolf per differenza di Sharpe; bootstrap appaiato sul P&L; poi gli stessi gate ZeroPipe (DSR>0,95, PBO/CSCV<0,5, holdout).
8. **Registrazione pubblica** di tutti i log decisionali (come Alpha Arena) per auditabilità.
9. **Nessun refitting retroattivo dei context file sui dati di valutazione**: ogni modifica ai context = nuova release dell'agente = nuovo track record.

## Recommendations

**Decisione**: COSTRUIRE il Trader Lab, ma come strumento di generazione di ipotesi e misura della varianza, NON come scorciatoia verso l'alpha — con kill-criteria severi e gli stessi gate di qualsiasi strategia.

**Fasi e kill-criteria**:
1. **Costruzione agente** (context files versionati, tool, risk-officer che può solo ridurre rischio). Kill se non si riesce a garantire log completi e freeze.
2. **Paper trading forward** con costi realistici, ≥ diversi mesi coprendo regimi multipli, con repliche. *Kill-criterion*: se la dispersione tra repliche identiche domina la differenza vs macchina, l'agente non ha skill misurabile → stop.
3. **Confronto appaiato vs sistema meccanico** (Ledoit-Wolf + bootstrap). *Kill*: se il differenziale di Sharpe non è positivo con significatività pre-dichiarata → non procedere al live.
4. **Test di superiorità statistica + gate ZeroPipe** (DSR>0,95, PBO/CSCV<0,5, holdout con max 2 verdetti a vita, contando i trial).
5. **Live micro 100–200 EUR** solo dopo il superamento di TUTTI i gate.

**Loop di arricchimento reciproco** (il vero prodotto): batch di divergenze agente-vs-macchina → tassonomia (regime/asset/segnale) con controllo FDR → analisi mensile → feature/formule candidate → Space Fertility Pre-Screen → pre-registrazione. Anche se l'agente perde, ogni divergenza sistematica è un'ipotesi per migliorare il sistema meccanico.

**Le 3 scelte progettuali più forti**: (1) forward-only post-cutoff con costi realistici; (2) agenti inconsapevoli della competizione (confronto solo nel layer di valutazione); (3) Trader Freeze Protocol con OpenTimestamps.

**Benchmark che cambierebbero la raccomandazione**: se una Stagione 2 di Alpha Arena o un benchmark contamination-free (StockBench-crypto) mostrasse un edge post-costi replicato su regimi multipli, alzare la priorità del percorso live; se le repliche mostrano che la varianza decisionale domina, declassare il Lab a puro strumento di generazione ipotesi senza percorso live.

## Caveats

- **Letteratura giovane e rumorosa**: gran parte dei paper con risultati brillanti è contaminata da leakage/survivorship/data-snooping; molti sono preprint arXiv 2025-2026 non peer-reviewed. I numeri auto-riportati dai proponenti (FinAgent +92%, FactFin +31% return) vanno trattati come promozione di metodo, non validazione indipendente.
- **Alpha Arena**: cifre finali variano tra fonti (snapshot in tempi diversi; es. GPT-5 ~$3.733 vs ~$4.126); 17 giorni e singolo regime → potenza statistica quasi nulla, ammessa da Nof1. Le fonti practitioner (Medium, blog, iWeaver, ChainCatcher) sono di qualità variabile e usate qui solo per ricostruire i fatti pubblici.
- **Evidenza crypto ≪ evidenza equity**: quasi tutto ciò che sappiamo su LLM-trading è su azioni USA; la trasferibilità a perp crypto altcoin è non dimostrata.
- **Distorsione da torneo negli LLM**: rischio teorico ben fondato (finanza mutual fund) ma senza evidenza diretta su LLM per rischio/leva — flag come questione aperta; il design conservativo la neutralizza.
- **Determinismo**: la vera riproducibilità bit-identica è impraticabile con API cloud; documentare il nondeterminismo residuo è obbligatorio, non opzionale.
- **Probabilità/EV onesti**: probabilità che l'agente batta un baseline meccanico ben costruito post-costi su crypto ~10–20%; EV del Lab comunque positivo per il valore di generazione ipotesi, misura della varianza e valore metodologico/pubblicabile, a patto di NON deviare dai gate.