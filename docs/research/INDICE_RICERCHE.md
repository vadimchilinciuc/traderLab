# INDICE DELLE RICERCHE — traderLab

Registro **append-only** delle ricerche di letteratura commissionate dal Lab e
tracciate in questo repository, sotto `docs/research/`.

**A cosa serve.** Una ricerca di letteratura costa tempo e denaro, e il modo
più facile di sprecarli è rifare una domanda a cui una chat precedente ha già
risposto in un file che nessuno ricorda di avere. Questo indice esiste perché
la domanda «è già stato chiesto?» abbia una risposta in un posto solo. La
regola che ne discende sta in `CLAUDE.md`, sezione «Prima di una ricerca di
letteratura»: si legge questo indice **prima**, e se il tema è coperto o
adiacente ci si ferma e si chiede all'owner il file esistente.

**Ordine delle righe.** È l'ordine di **iscrizione**, non quello cronologico.
La prima riga è la ricerca che ha aperto il registro (20/08/2026); le righe
successive sono le ricerche già presenti in `docs/research/` al momento
dell'apertura, trascritte leggendo i file stessi. Da qui in avanti **le voci
nuove si aggiungono in fondo alla tabella** e **nessuna riga esistente si
riscrive**: una ricerca superata si segnala nella colonna
«stato / supersessioni» di entrambe le righe, non cancellando quella vecchia.

**Cosa entra qui.** Solo i documenti di ricerca sotto `docs/research/`. Gli
esiti pre-registrati stanno sotto `docs/research/results/` e non sono ricerche
di letteratura: non compaiono in questa tabella.

---

## Tabella

| # | data | file | domande coperte | stato / supersessioni |
| --- | --- | --- | --- | --- |
| 1 | 2026-08-20 | `2026-08-20_RICERCA_ACCORDO_REPLICHE_LITERATURE.md` | **Q1-Q6**, numerate nel file. Q1 self-consistency e accordo campionario come predittore di correttezza; Q2 leggi di scala di *k*; Q3 test statistici per il gate (permutazione, Fisher esatto r×c, invalidità del KS su dati discreti); Q4 controlli sintetici floor/ceiling nella valutazione; Q5 errori correlati fra repliche; Q6 novità post-gennaio 2026. | **In vigore.** Nessuna supersessione. Fonda il gate del `PREREG_LAB_S0_RUN2` sull'accordo inter-replica come oggetto di probabilità per il sizing. La sezione «Cosa non ho trovato» dichiara quattro vuoti di letteratura, fra cui il fatto che nessuno studio misura la correlazione fra repliche identiche di un modello pinnato. |
| 2 | 2026-08 | `2026-08_LLM_TRADER_AGENTS_LITERATURE.md` | **Q1-Q8**, numerate nel file. Q1 stato dell'arte dei framework; Q2 data-leakage e knowledge-cutoff; Q3 ricostruzione di Alpha Arena / Nof1.ai; Q4 patologie decisionali degli LLM; Q5 identità, versioning e validità del track record; Q6 multi-agente e distorsioni da torneo; Q7 statistica del confronto appaiato; Q8 percorso governato al live. | **In vigore.** Ricerca fondativa del Lab: da qui vengono la valutazione forward-only, il Trader Freeze Protocol e le repliche inconsapevoli (`CLAUDE.md` §5, §6, §10). Non superata. |
| 3 | 2026-08 | `2026-08_AGENT_FAITHFULNESS_FRAMEWORKS_LITERATURE.md` | **Q1-Q6**, numerate nel file. Q1 fedeltà delle auto-spiegazioni strutturate (il campo `features_used`); Q2 protocolli decisionali strutturati e schema; Q3 hypothesis mining con rigore statistico; Q4 design di Tool/API; Q5 due diligence su TradingAgents e alternative; Q6 valore del debate multi-agente. | **In vigore.** Il suo Q1 è citato da `CLAUDE.md` §1 come fonte del *privileged access* (la stessa passata che decide produce `features_used`, nessun reporter separato); il suo Q6 fonda il divieto di debate multi-agente di `CLAUDE.md` §5. Non superata. |
| 4 | 2026-08-17 | `2026-08-17_RICERCA_CONFIDENCE_LETTERATURA.md` | Non numerate a Q: **sei aree**. Area 1 anchoring e clustering della confidence verbalizzata; Area 2 effetto di RLHF e instruction tuning; Area 3 diversità di campionamento fra prompt identici; Area 4 metriche quando la probabilità è degenere (decomposizione di Murphy, degenerazione del Brier); Area 5 metodi di elicitation che allargano la distribuzione; Area 6 governance e disegno sperimentale. | **In vigore.** **Duplicato dichiarato**: contenuto identico, a meno dei fine-riga, a quello della riga 6. Questa è la copia del 17/08, con fine-riga CRLF ed eccezione dichiarata in `.gitattributes` §4. |
| 5 | 2026-08-17 | `2026-08-17_RICERCA_CONFIDENCE_DEGENERE.md` | Non numerate a Q: **sezioni A-H**. A i reperti sulla quantizzazione della confidence; B la matematica che chiude la questione del Brier; C ciò che la letteratura non dice e riguarda solo il Lab; D governance e finestra temporale; E azioni proposte; F cosa non si fa; G il reperto che vale come risultato; H limiti dichiarati. | **In vigore.** Sintesi operativa in italiano della riga 4, scritta la notte del 17/08 dopo che il Giorno 2 di Stagione 0 aveva restituito tutte e sei le confidence a 0,55. Le due si leggono insieme: questa decide, la riga 4 documenta. |
| 6 | 2026-08-19 | `Degenerate_Verbalized_Confidence_in_LLM_Trading_Agents__Diagnosis__Metrics__and_Elicitation_Remedies.md` | Le stesse della riga 4 (sei aree), essendone il medesimo testo. | **In vigore, ma ridondante.** Fonte inglese estesa, recuperata dal Knowledge della chat di progetto e committata il 19/08 (commit `8cfe894`, audit del 19/08, famiglia N8). Contenuto **identico** a quello della riga 4 a meno dei fine-riga: questo file ha LF, la riga 4 ha CRLF. Non supera la riga 4 e non ne è superato: sono la stessa ricerca in due sedi, e citarne una vale come citare l'altra. |
| 7 | 2026-08-18 | `2026-08-18_RICERCA_ARCHITETTURE_AGENTE.md` | Non numerate a Q: **parte A**, §0-§8. Verifica di Agent Market Arena (arXiv:2510.11695); *The Alpha Illusion* (arXiv:2605.16895) con i protocolli P1-P6 e il Parametric Prior Lock-in; mappatura di traderLab sui sei stadi modulari; dove la Stagione 1 romperebbe il confine; idea #13, registrata e non costruita; la superficie di overfitting nuova. | **In vigore.** Parte A di una trilogia: si legge prima della riga 8 (parte B) e della riga 9 (parte C). Contiene un'annotazione di errore del consigliere (§1), che resta a registro. |
| 8 | 2026-08-18 | `2026-08-18_RICERCA_CADENZA_SISTEMI_INTRADAY.md` | Non numerate a Q: **parte B**, §11-§19. Tre reperti nuovi sulla cadenza decisionale (firme cognitive misurabili, turnover come collo di bottiglia, incomparabilità del campo con sé stesso); analisi forense di QuantAgent (arXiv:2509.09995) con otto rilievi sul protocollo di valutazione; tassonomia dei sistemi; idea #13-bis, arena a due cadenze, registrata e non costruita. | **In vigore.** Parte B. **Presuppone** la riga 7. Contiene la seconda annotazione di errore del consigliere (§11). |
| 9 | 2026-08-18 | `2026-08-18_ANALISI_RICERCA_PIANO_IMPLEMENTAZIONE.md` | Non numerate a Q: **parte C**, §20-§25. Due correzioni al report di ricerca (l'ECE non interpretabile con confidence degenere; un non-sequitur nella previsione falsificabile #3); il reperto principale sull'oggetto probabilità; il confondente del metro del rumore e le due sonde sintetiche nella suite congelata; tre difetti di disegno; come chiudere i cinque gap; scala di implementazione. | **In vigore.** Parte C, analisi critica e piano operativo. **Presuppone** le righe 7, 8 e 10. Da qui vengono le due sonde sintetiche del verbale RUN2 §A.11 e la regola candidata sull'ECE del §A.14. |
| 10 | 2026-08-18 | `2026-08-18_RICERCA_CADENZA_BASELINE_CENSIMENTO.md` | Non numerate a Q: **censimento**, sezioni A-E. Tabella-censimento delle otto metriche cognitive del Lab con le baseline pubblicate esistenti; se esista uno studio che confronti la stessa architettura su ≥2 cadenze misurando qualcosa di diverso dal P&L (risposta: no); patologie decisionali che peggiorano con la cadenza; valutazione critica dei protocolli intraday; caveat espliciti. | **In vigore.** Report di ricerca estesa che le righe 8 e 9 presuppongono. Dichiara aperto il gap centrale del programma: nessuno studio fra il 2023 e l'agosto 2026 confronta la stessa architettura su due o più cadenze misurando qualcosa di diverso dal P&L. |

---

## Come si aggiunge una voce

1. La ricerca nasce come file sotto `docs/research/`, con il nome nella forma
   `<AAAA-MM-GG>_RICERCA_<SLUG>.md` oppure `<AAAA-MM>_<SLUG>_LITERATURE.md`.
2. Si **aggiunge una riga in fondo** alla tabella, con il numero progressivo
   successivo. Le colonne «domande coperte» e «stato / supersessioni» si
   compilano **leggendo il file**, non a memoria.
3. Se la ricerca nuova supera una vecchia, la supersessione si scrive **in
   entrambe** le righe. La riga vecchia resta dov'è: un registro append-only
   non cancella, dichiara.
