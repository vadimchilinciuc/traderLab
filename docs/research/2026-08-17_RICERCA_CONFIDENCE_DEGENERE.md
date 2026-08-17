# RICERCA — Confidence verbalizzata degenere (2026-08-17)

> Ricerca commissionata nella notte del 17/08, dopo che il Giorno 2/20 di Stagione 0 ha
> restituito **tutte e sei le decisioni a confidence esattamente 0,55** (dispersione 0,0000);
> il Giorno 1 aveva dispersione 0,0167. Il Brier è metrica pre-registrata di S0.
> **Domanda**: è un fenomeno noto degli LLM (e quindi un difetto di disegno nostro) o un
> reperto empirico su questo modello (e quindi un risultato)?
> **Risposta breve: entrambe le cose, ma con una sfumatura che conta.**
> **Niente si costruisce, S0 non si tocca.** Questo file annota reperti e registra ipotesi.

---

## A — I reperti

**A1. La confidence verbalizzata è quantizzata, non continua.**
*Rescaling Confidence* (arXiv:2603.09309, 2026): su scala 0-100 i modelli usano solo **15-28
valori distinti**; i tre più comuni coprono **oltre il 78%** delle risposte; entropia osservata
**0,95-1,88 bit** contro i 6,66 di una uniforme. Gemini 3.1 Pro risponde esattamente 100 nel
**68,4%** dei casi.

**A2. Ma l'ancoraggio documentato è verso l'ALTO (90/95/100). Il nostro è a metà scala.**
Non risulta un paper che documenti un modo a 0,50-0,55 con statistiche nominate. **Il nostro caso
è quindi parzialmente un reperto nuovo**, non solo l'istanza di un fenomeno atteso.

**A3. Il meccanismo probabile: "answer-independence".**
Seo et al. (arXiv:2510.10913, ACL 2026) formalizzano che P(C|domanda,risposta) ≈ P(C|domanda):
il numero è guidato dagli **elementi strutturali del prompt** (la parola "confidence", il range
della scala) più che dal contenuto. Caso analogo su dati clinici tabulari (arXiv:2606.19509):
confidence quasi-costante fissata dal template (0,856 zero-shot / 0,937 few-shot),
**AUROC = 0,50 esatto** — zero informazione sulla correttezza.

**A4. L'RLHF degrada la calibrazione.**
GPT-4 technical report, verbatim: il modello pre-addestrato è altamente calibrato, *"after the
post-training process, the calibration is reduced"*. Replicato su Llama-2-70B da Tian et al.
Meccanismo: l'RLHF riduce l'entropia degli output, spingendo verso pochi valori-ancora.

**A5. Su Claude l'evidenza specifica è vecchia e non entusiasmante.**
Tian et al. (EMNLP 2023): Claude-1 *"less able to verbalize well-calibrated confidences"*
rispetto alla famiglia GPT; Claude-2 recupera fino a un livello comparabile a gpt-3.5-turbo.
**Nessun follow-up 2024-2026 isola Claude.** L'estrapolazione a un modello 2026 è plausibile ma
non provata: le nostre osservazioni sono l'evidenza primaria su questo modello.

**A6. La diversità collassa sui formati vincolati.**
*The Price of Format: Diversity Collapse in LLMs* (arXiv:2505.18949): i template chat vincolati
attenuano fortemente i guadagni di diversità dalla temperatura. Il nostro compito è "scegli 1 di
3 azioni + un numero": **il collasso è atteso per costruzione**, non necessariamente segnale che
il mercato sia non ambiguo.

**A7. Il non-determinismo API aggiunge varianza, non la toglie.**
Thinking Machines Lab (11/09/2025): 1.000 richieste identiche a temperatura 0 su
Qwen3-235B producono **80 completions distinte** (la più comune 78/1.000); con kernel
batch-invariant diventano bitwise identiche. Causa dominante: batch dinamici che cambiano
l'ordine delle riduzioni floating-point. **Quindi il nostro collasso non è spiegabile con
caching o determinismo artificiale** — semmai il contrario (vedi §C2).

---

## B — La matematica che chiude la questione del Brier

**Decomposizione di Murphy (1973)**: BS = UNC + REL − RES, dove
UNC = ō(1−ō) (varianza dell'esito, fuori dal controllo del previsore),
REL = calibrazione (0 è ideale), RES = risoluzione (più alta è meglio).

**Con forecast costante c**: esiste un solo bin, quindi **RES = 0** per costruzione, e
**BS = ō(1−ō) + (c − ō)²**.

Verifica numerica sul nostro caso (c = 0,55):

| hit rate ō | Brier | lettura |
|---|---|---|
| 0,50 | 0,2525 | |
| **0,55** | **0,2475** | **calibrazione PERFETTA, risoluzione ZERO** |
| 0,60 | 0,2425 | |

**Il caso peggiore è quello che sembra migliore.** Se l'agente indovina il 55% delle volte e
dichiara sempre 0,55, il Brier è **minimizzato** e l'ECE è **perfetto** — mentre l'agente non
sta discriminando nulla. La metrica premia il comportamento degenere.

Corollario dalla letteratura: *un previsore che dice sempre 50% ha ECE perfetto e AUROC 0,5.*
**L'ECE non può essere criterio primario.**

Quadro teorico: Gneiting, Balabdaoui & Raftery (JRSS-B 2007) — il previsore ideale massimizza
la **sharpness subject to calibration**. Un forecast costante è il caso limite: calibrato ma non
sharp, cioè la *naive climatology*.

---

## C — Le due cose che la ricerca NON dice e che riguardano solo noi

**C1. L'AUROC sulla confidence non è la via d'uscita: sui nostri dati è INDEFINITO.**
La ricerca propone l'AUROC come metrica di ripiego. Ma con confidence letteralmente costante
non esiste alcun ordinamento da valutare: l'AUROC non è "basso", è **non calcolabile** (tutti
pareggi). Serve prima ripristinare varianza — cioè cambiare elicitation, che a stagione
congelata **non si può fare**.

**La via d'uscita vera ce l'abbiamo già, ed è l'accordo tra repliche.**
Giorno 1: BTC 2/3. Giorno 2: BTC 3/3, ETH 3/3. **Quel segnale varia.** La letteratura sulla
self-consistency (Wang et al., arXiv:2203.11171) dice che l'accordo tra campioni indipendenti
predice la correttezza. Quindi: **il metro del rumore, costruito per controllo qualità, è di
fatto la nostra misura di confidence non degenere** — mentre il numero dichiarato dal modello
è degenere. L'analisi di calibrazione va agganciata all'accordo, non al `confidence` field.
Cautela: con 3 repliche l'accordo assume pochi valori (3/3, 2/1, 1/1/1) — è grossolano, ma
non degenere.

**C2. Ipotesi da registrare: il fix caching potrebbe aver ridotto la diversità.**
Cronologia: Giorno 1 con prefissi divergenti → dispersione 0,0167. Fix `c33fd0b` (id
deterministici, prefissi byte-identici) applicato tra D1 e D2. Giorno 2 → dispersione **0,0000**.
Meccanismo plausibile: prefissi identici ⇒ stesso KV cache ⇒ numerica identica ⇒ meno rumore da
batch-invariance (il meccanismo di §A7 girato al contrario).
**n=2, non è nulla.** Ma se la dispersione resta 0,0000 per i giorni 3-20, non potremo
distinguere "mercato non ambiguo" da "fix ha reso il calcolo deterministico".
**Questo rende la riga TL-004 a registro più importante, non meno**: la discontinuità va
annotata perché è una covariata del metro del rumore.

---

## D — Governance: la finestra è aperta ORA e si chiude

La letteratura sulla pre-registrazione (Center for Open Science) è chiara: cambiare l'outcome
primario dopo aver visto i dati è **outcome switching**, violazione seria. Ma gli emendamenti
sono **ammessi prima che gli esiti siano noti**, se timestamped e con razionale documentato.

**Il nostro caso è difendibile per una ragione precisa**: il collasso della confidence si osserva
**dai soli output del modello**, senza guardare gli esiti di mercato. Non è una decisione
contingente sui P&L.

**E c'è una convergenza fortunata**: la **Regola 4** (sigillo sul P&L durante S0, dashboard che
non mostra giudizi) è stata adottata per altre ragioni, e oggi è **la prova che nessuno ha
guardato gli esiti**. Protegge esattamente la difendibilità di questo emendamento.

**La finestra si stringe ogni giorno.** Con 18 giornate davanti, l'emendamento va fatto adesso.

---

## E — Azioni proposte (verdetto owner)

**E1. Emendamento timestamped al pre-registration di S0** — PRIMA di guardare qualunque esito:
- documenta il collasso come osservazione (con i numeri: 0,0167 → 0,0000);
- mantiene il Brier come pianificato ma lo riporta **decomposto** (UNC/REL/RES), così che
  RES ≈ 0 sia esplicito e non nascosto sotto un punteggio che sembra buono;
- aggiunge come co-primarie: **hit rate delle azioni vs base rate** e **accordo tra repliche**
  come segnale discriminante (l'unico che varia);
- dichiara che l'ECE non è criterio, con la ragione (il previsore al 50% ha ECE perfetto).
  Non tocca prompt, modello, snapshot, manifest: **nessuna violazione del freeze**.

**E2. Riga TL-004 a registro** (già in coda dal 16/08, ora motivata due volte): fix caching
applicato tra D1 e D2, con l'ipotesi C2 annotata come covariata possibile del metro del rumore.

**E3. Test di determinismo API** — FUORI da S0, su snapshot congelato, non tocca la stagione:
inviare N volte la stessa singola chiamata e guardare la distribuzione degli output. Se in
isolamento c'è varianza ma le repliche giornaliere collassano, il collasso è nella distribuzione
sottostante. Costo: qualche dollaro. Trigger: quando c'è budget e voglia.

**E4. A/B di elicitation** — REGISTRATO, si costruisce **dopo S0**: baseline attuale vs top-k con
probabilità vs quote/odds vs CoT "evidenze pro e contro poi decidi" vs distribuzione verbalizzata.
Su snapshot congelati identici. Metrica di successo: **dispersione + AUROC**, non ECE.
Trigger: prima release post-S0, insieme ai reason codes e alla Scuola del Trader.

**E5. Separare il sizing dalla confidence dell'LLM** — registrato, non urgente.
La letteratura trading (arXiv:2607.03015; KTD-FIN arXiv:2605.28359; Foresight Arena
arXiv:2605.00420) converge: buoni punteggi probabilistici non si traducono in trade profittevoli;
il position sizing va deterministico e fuori dal prompt. Coerente con quanto già deciso in casa
(niente pressione nel prompt, guardrail nel tool).

---

## F — Cosa NON si fa

- **Non si tocca il prompt, il modello, lo snapshot o il manifest a stagione in corso.**
- **Non si fa l'A/B di elicitation dentro S0**: contaminerebbe la stagione.
- **Non si conclude "l'agente non ha segnale"**: con confidence degenere quella conclusione non è
  supportata. Le tre ipotesi (nessun segnale / metrica sbagliata / elicitation sbagliata) si
  distinguono solo con i test di E3-E4.
- **Non si dichiara vittoria se il Brier esce buono**: con RES=0 un Brier basso è l'artefatto
  descritto in §B, non una prova di calibrazione.

---

## G — Il reperto che vale come risultato

Se Fable 5 emette 0,55 costante su un compito a output vincolato, con **snapshot congelati,
catena hash, ancoraggio OTS, tre repliche identiche e pre-registrazione**, quello è un risultato
empirico riportabile su un modello di frontiera 2026 — e con una provenienza migliore di quella
di molti paper del settore. Il modo mid-range non è documentato in letteratura (§A2).

È il primo deliverable concreto dell'idea registrata la notte del 16/08 — *il laboratorio come
strumento di misura del giudizio delle AI* — e non richiede che l'agente sappia tradare.

---

## H — Limiti dichiarati

- Molti paper citati sono **preprint 2026 non peer-reviewed**: usarli come corroborazione,
  verificare i numeri sulla camera-ready.
- **"Claude Fable 5" non compare in letteratura**: le conclusioni poggiano su proprietà generali
  dei modelli RLHF e sulla famiglia Claude storica (Claude-1/2, ora deprecati).
- **Numerosità**: 6 decisioni × 20 giorni = 120 osservazioni, ma clusterate per giornata e per
  asset. Gli intervalli di confidenza su qualunque AUROC saranno ampi. Dichiararli sempre.
- n=2 giornate: **tutto quanto sopra è ipotesi**, non tendenza. Il Giorno 3 aggiunge un punto.