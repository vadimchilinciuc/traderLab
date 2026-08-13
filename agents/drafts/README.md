# agents/drafts — proposte in revisione

Questa cartella contiene **proposte di context file**. Niente di ciò che sta
qui è in uso.

Un file diventa un context file quando sta in `agents/<nome>/`, entra in un
Freeze manifest e quindi ha un `prompt_sha`. Finché resta qui non ha `prompt_sha`,
non apre alcun segmento di track record e non viene caricato da alcun runner.

| Proposta | Stato | Note |
| -------- | ----- | ---- |
| `trader_v0_proposta` | in revisione HR | Mandato di rischio contenuto. |
| `trader_aggressive_v0_proposta` | in revisione HR, **nel cassetto fino alla Stagione 1** | Mandato di rischio esteso. In Stagione 0 la size è fissa: un mandato più ampio non avrebbe modo di manifestarsi. |

Le due proposte condividono **lo stesso `system_prompt.md`, byte per byte**.
L'unica differenza tra loro è la sezione «Il tuo mandato di rischio» di
`persona.md`. È una condizione verificata da `tests/test_drafts.py`, non una
convenzione: due varianti che differissero anche altrove non sarebbero due
mandati di rischio diversi, sarebbero due agenti diversi, e la differenza
osservata non sarebbe attribuibile al rischio.

Il cap dichiarato in una persona è un **mandato**, non un limite operativo. I
limiti che devono valere sempre stanno nel Risk Officer, che può solo ridurre
il rischio (`CLAUDE.md` §2). La bozza aggressiva dichiara cinque volte il
capitale mentre il cap applicato resta quello di configurazione: i due numeri
sono grandezze diverse e possono divergere senza che nulla cambi
nell'esecuzione.

## Cosa deve verificare la revisione

Le proposte passano già i controlli automatici di `tests/test_drafts.py`:
nessun riferimento a chi legge il verbale o a come viene usato (`CLAUDE.md` §6),
nessun guardrail nominato, mandato di processo e non di risultato, nessuna
pressione emotiva, vocabolario primitivo completo, ordine del verbale
(razionale libero prima, blocco strutturato dopo) e invalidazione ex-ante
obbligatoria.

Quello che i test **non** possono dire, e che serve a una persona:

- se il mandato descritto è quello che si intendeva dare;
- se la variante estesa differisce nel modo giusto, e non solo in un numero;
- se il tono regge senza scivolare nell'incoraggiamento o nella pressione;
- se manca qualcosa che un trader avrebbe bisogno di sapere per lavorare.

## Promuovere una proposta

Non si sposta un file e basta. Servono, nell'ordine: chiusura della revisione,
copia in `agents/<nome>/`, nuovo Freeze manifest con i nuovi sha, e la
consapevolezza che il track record precedente **non si confronta** con quello
successivo (`CLAUDE.md` §3, §10).
