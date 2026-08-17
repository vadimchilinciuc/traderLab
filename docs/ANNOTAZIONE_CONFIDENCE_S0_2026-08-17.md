# ANNOTAZIONE — Stagione 0, giornate 1-2 (2026-08-17)

> **Questo documento NON è un emendamento e non modifica nulla.**
> `PREREG_LAB_S0.md` è congelato e ancorato OTS (`PREREG_LAB_S0.md.ots`): il file originale
> non si tocca, mai. La sua intestazione stabilisce inoltre che *«dopo il primo giorno con
> verbali sono ammessi solo fix operativi che non toccano le misure dichiarate»* — il primo
> giorno con verbali è il 2026-08-16, quindi nessuna misura del §4 può essere aggiunta,
> tolta o ridefinita. Qui si annota soltanto.
> Le firme e i verdetti sono dell'owner.

---

## §A — Osservazione: confidence verbalizzata degenere

**Fatto.** Giornata 2/20 (rito UTC 2026-08-17T00:00): tutte e sei le decisioni (3 repliche ×
2 asset) hanno restituito `confidence` **esattamente 0,55**. Dispersione della confidence:
**0,0000**. Giornata 1/20: dispersione **0,0167**.

Le azioni hanno invece mostrato variabilità: G1 BTC 2/3 (r3 SHORT, due FLAT) ed ETH 3/3;
G2 BTC 3/3 SHORT ed ETH 3/3 FLAT.

Fonte: `data/ledger/season0.jsonl`, catena `verify(): ok` in entrambe le giornate.
**Nessun esito di mercato è stato consultato per produrre questa osservazione.**

**Perché non richiede alcun intervento — il pre-registration aveva già previsto tutto:**

1. **§4.3** — *«Brier: accumulazione sola, nessun giudizio in S0»*. Il Brier non produce verdetti
   in questa stagione: si accumula e basta.
2. **§4.3** — il Brier direzionale si calcola **SOLO su long/short**; per flat e close la
   confidence è loggata ma non entra. Nelle prime due giornate sono entrate **4 decisioni su 12**
   (1 short al G1, 3 short al G2).
3. **§4.3** — *«ogni eventuale scoring della confidence su flat sarà dichiarato in PREREG_LAB_S1
   prima della Stagione 1»*: la questione era già instradata al prossimo pre-registration.
4. **§4.1** — il metro del rumore è definito sull'**azione modale**, non sulla confidence:
   la misura primaria non è toccata dal collasso.
5. **§1** — S0 misura tre cose e solo tre (rumore inter-repliche, baseline comportamentale,
   affidabilità operativa). La calibrazione non è tra queste.

**Cosa resta da fare: nulla in S0.** Il materiale raccolto (ricerca del 17/08, vedi §E) è
destinato a **PREREG_LAB_S1**, dove le decisioni sullo scoring della confidence appartengono
per dichiarazione esplicita del §4.3.

---

## §B — Il fix di prompt caching è un RIPRISTINO, non una modifica in corsa

**Fatto.** Commit `c33fd0b` applicato il 2026-08-16, tra la giornata 1 e la giornata 2: gli id
`tool_use` rimandati indietro dal runner sono ora derivati dal contenuto (nome + argomenti +
posizione) invece che assegnati dall'API a ogni generazione.

**Lettura corretta.** Il §2 dichiara *«Repliche: 3, identiche, input byte-identici»*, e il §7(iv)
mette *«input byte-identici in tutte le giornate»* tra i gate di uscita.
Prima del fix, gli id assegnati dall'API **divergevano tra repliche**: era esattamente la causa
diagnosticata del mancato riuso della cache. Quindi il fix non ha alterato una proprietà
pre-registrata: **l'ha restaurata**. È un fix operativo che non tocca alcuna misura del §4,
quindi ammesso dall'intestazione del pre-registration.

**[PUNTO APERTO — OWNER]** Se la giornata 1 è girata con prefissi non byte-identici tra repliche,
va verificato se e come questo si riflette sul gate §7(iv). Due letture possibili: (a) la
proprietà si riferisce ai *contenuti* (dossier, persona, manifest), che erano identici, e gli id
di trasporto non ne fanno parte; (b) la proprietà si riferisce ai byte effettivi della richiesta.
La lettura (a) è coerente con l'intento del §2 (nessuna informazione distintiva alle repliche,
`replica_id` mai nel prompt — D1). **Da dichiarare per iscritto prima di fine stagione**, non
da decidere a posteriori sul risultato.

**Ipotesi collaterale da annotare (n=2, non è tendenza).** Rendendo i prefissi byte-identici, il
fix potrebbe aver ridotto il non-determinismo numerico dell'inferenza (batch-invariance) e con
esso la diversità di campionamento. Cronologia: G1 prefissi divergenti → dispersione confidence
0,0167; G2 prefissi identici → 0,0000. Se la dispersione resta nulla, non sarà distinguibile
"mercato non ambiguo" da "calcolo reso deterministico". **Covariata del metro del rumore
(§4.1): da tenere sotto osservazione, non da correggere.**

---

## §C — Tetto token del §5: due letture, e i numeri non sono neutri

Il §5 dichiara *«tetto dichiarato di 1.000.000 token input e 200.000 token output per giornata
complessiva (3 repliche); superamento → evento `budget_stop` nell'ops ledger e giornata chiusa
come `failed_decisions` per budget»*.

| | `input_tokens` | `cache_read` | `cache_creation` | **totale lato input** | output |
|---|---|---|---|---|---|
| Giornata 1 | 994 | 236.381 | 1.001.811 | **1.239.186** | 22.402 |
| Giornata 2 | 856 | 405.606 | 669.792 | **1.076.254** | 20.261 |

- **Lettura letterale** (`usage.input_tokens`): 994 e 856 — largamente sotto il tetto.
- **Lettura economica** (tutto ciò che si paga come input): **entrambe le giornate sopra il
  milione**. Con questa lettura entrambe avrebbero dovuto chiudere come `budget_stop` /
  `failed_decisions`, con effetti sul §3 (giornate mancate) e sul §7(i) (≥ 20 giornate effettive).

L'implementazione non ha fatto scattare alcun `budget_stop`: legge quindi letteralmente. Essendo
stata costruita **prima** dell'inizio della stagione e sotto lo stesso pre-registration, quella è
con ogni probabilità l'interpretazione pre-registrata.

**[PUNTO APERTO — OWNER, da chiudere prima di fine S0]** Dichiarare per iscritto quale delle due
letture vale, con la ragione. Non è un emendamento (non cambia il tetto né la misura): è la
disambiguazione di un termine già scritto. Va fatta **adesso e non a fine stagione**, perché a
fine stagione la scelta sarebbe contaminata dal sapere quante giornate sono state raccolte.

L'output è tranquillo sotto entrambe le letture (22K e 20K contro 200K).

---

## §D — Reperto strutturale: il cancello di ammissibilità è a senso unico

**Osservazione, non azione.** Il §4.2 fissa il cancello a `self_agreement_rate ≥ 0,75`, misurato
dal §6 rilanciando lo stesso snapshot congelato k=5 volte.

Un agente **perfettamente rigido** — che risponde sempre in modo identico — ottiene
`self_agreement_rate = 1,00` e passa il cancello col massimo. Il cancello è costruito per
intercettare un agente **troppo rumoroso**; non può intercettarne uno **troppo deterministico**.

Il §6 conferma l'asimmetria: `floor_binds` e `is_degenerate` (in `arena/regression.py`,
`ThresholdDerivation`) proteggono dal collasso delle soglie quando la baseline è **bassa**
(alarm = baseline − 0,15, pavimento 0,70). Con baseline 1,00 nessun pavimento morde e la
derivazione risulta regolare.

**È la stessa forma della degenerazione del Brier, un piano più sopra**: il Brier è minimizzato
da una confidence costante, il cancello è massimizzato da un agente che non varia. Due metriche
indipendenti nello stesso pre-registration, entrambe ottimizzate dal comportamento degenere.

**Nota tecnica**: esistono **due** `is_degenerate` distinti nel repo —
`arena/regression.py` (`ThresholdDerivation`, quello citato dal §6) e `ledger/telemetry.py`
(su `daily_dispersion`). Il cancello del §6 riguarda le soglie, **non** la confidence.

**Destinazione: PREREG_LAB_S1.** Il cancello va reso **a due lati** — né troppo rumoroso, né
degenere — con la soglia inferiore di variabilità dichiarata prima di avere i dati.
**Niente si costruisce ora, S0 non si tocca.**

---

## §E — Provenienza

- Repo `traderLab`, branch `main`.
- Documenti di supporto: `docs/research/2026-08-17_RICERCA_CONFIDENCE_DEGENERE.md` e
  `docs/research/2026-08-17_RICERCA_CONFIDENCE_LETTERATURA.md` (commit `72329b8`).
- Fix caching: commit `c33fd0b`.
- Giornate registrate alla redazione: **2/20**. Catena `season0.jsonl`: `verify(): ok`.
- Nessun esito di mercato consultato. La **Regola 4** del cruscotto (sigillo sul P&L durante S0)
  è in vigore dal contratto dashboard e precede questa osservazione.

---

## §F — Cosa NON cambia

Prompt · modello (`claude-fable-5`, TL-002) · temperatura · snapshot e loro congelamento ·
manifest · schema del Decision Record · misure del §4 · gate del §7 · cancello del §4.2 ·
cap di calendario · Regola 4 · qualunque soglia numerica preesistente.

**Nessuna misura è stata aggiunta, tolta o ridefinita.** Questo documento osserva e registra.