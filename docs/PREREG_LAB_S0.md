# PREREG_LAB_S0 — Pre-registrazione della Stagione 0 del Trader Lab
> Congelata il 13/08/2026, PRIMA della raccolta di qualunque baseline e prima
> del pin. Emendamenti: solo additivi e datati; dopo il primo giorno con
> verbali sono ammessi solo fix operativi che non toccano le misure dichiarate.
> Le firme sono dell'owner (dirette o per delega esplicita al consigliere,
> registrate in chat il 13/08/2026).

## §1 — Natura e scopo
La Stagione 0 è shadow: nessun ordine reale, nessun capitale. Misura tre cose
e SOLO tre: (a) il rumore decisionale inter-repliche, (b) la baseline
comportamentale del Trader per la suite di regressione, (c) l'affidabilità
operativa del rito quotidiano. La Stagione 0 NON misura skill: nessun P&L
viene giudicato, nessun confronto con la gamba meccanica esiste (Stagione 1),
nessuna promozione o bocciatura del Trader può derivarne.

## §2 — Setup congelato
- Modello: Claude Fable 5 (`claude-fable-5`), pinnato al rito del pin con
  string ri-verificata contro l'endpoint, sampling per omissione (D4),
  thinking a default API, nessun fallback server-side, refusal categoria
  propria. TL-001/TL-002 del DECISION_LOG.
- Repliche: 3, identiche, input byte-identici, replica_id mai nel prompt (D1).
- Size: fissa a rischio unitario, normalizzata dal Risk Officer (D3). Il
  Trader decide direzione e dentro/fuori.
- Universo: BTC, ETH — ufficiale dal Pre-Screen C2 (commit 3bc9a9c).
- Snapshot: giornaliero, 00:00 UTC, costruito dal rito; le decisioni leggono
  solo lo snapshot del giorno (firewall).
- Persona: `trader_v0` promossa dalla bozza `trader_v0_proposta` approvata
  dalla revisione HR del 13/08/2026; hash dei context files nel
  FreezeManifest al pin. Variante primaria e UNICA in S0: Normal. La variante
  Aggressive resta non eseguibile in S0 (size fissa) e comunque esplorativa.

## §3 — Durata e calendario
- Obiettivo: 20 giornate effettive di verbali (= finestra pre-registrata del
  kill-criterion) per tutte e 3 le repliche.
- Cap di calendario: 42 giorni dal primo giorno con verbali. Se il cap scade
  prima delle 20 giornate effettive: S0 è INVALIDA per inaffidabilità
  operativa; indagine, fix, e S0 riparte da zero con baseline azzerata.
- Giorni mancati: policy implementata — skipped_day nell'ops ledger, mai
  recuperati, mai ricostruiti retroattivamente. failed_decisions (rito
  partito, API non ha risposto nella finestra di 45 minuti) è evento
  distinto e conta separatamente.
- Soglie di allarme operativo (non invalidanti, da annotare): >4 skipped_day
  totali oppure >2 consecutivi.

## §4 — Misure primarie (dichiarate ora, lette a fine S0)
1. Dispersione inter-repliche: per (giornata, asset), accordo con l'azione
   modale delle 3 repliche; media su S0. È il metro del rumore per la
   Stagione 1.
2. Baseline della suite di regressione: raccolta a fine S0 (cfr. §6);
   cancello di ammissibilità: self_agreement_rate ≥ 0,75. Sotto: la
   Stagione 1 NON parte con questo setup; decisione owner.
3. Brier: accumulazione sola, nessun giudizio in S0. Semantica congelata:
   il Brier direzionale si calcola SOLO sulle decisioni long/short (esito =
   segno del rendimento sull'orizzonte dichiarato); per flat e close la
   confidence viene loggata ma NON entra nel Brier direzionale in S0; ogni
   eventuale scoring della confidence su flat sarà dichiarato in
   PREREG_LAB_S1 prima della Stagione 1.
4. Telemetria comportamentale: flip rate, turnover, tasso di verbali
   malformati, tentativi API per chiamata (telemetria 67acd77).
5. Consumo: token input/output per decisione e per giornata, dal campo usage.

## §5 — Vincoli operativi
- Tasso di malformati < 5% su S0 (i malformati restano NO TRADE sempre).
- Budget: spend limit sul workspace API (Console) + tetto dichiarato di
  1.000.000 token input e 200.000 token output per giornata complessiva
  (3 repliche); superamento → evento budget_stop nell'ops ledger e giornata
  chiusa come failed_decisions per budget.
- Nessuna lettura confermativa in corsa: i pannelli si guardano liberamente,
  le MISURE di §4 si leggono e si scrivono solo a fine S0.
- Nessuna modifica ai context files, alla config del modello o al Risk
  Officer durante S0. Un cambio forzato (es. deprecazione modello) chiude S0
  come INVALIDA e si riparte.

## §6 — Suite di regressione comportamentale
- Snapshot congelati: gli snapshot dei primi 12 giorni effettivi di S0,
  scelti da questa regola meccanica e congelati UNA volta sola.
- k = 5 campioni per snapshot; cadenza settimanale dalla raccolta baseline
  in poi.
- Soglie: derivate meccanicamente dalla regola di TL-002
  (alarm = baseline − 0,15, pavimento 0,70; sunset = baseline − 0,30,
  pavimento 0,50; confidence +0,10 / +0,20) e scritte in config il giorno
  della baseline. is_degenerate deve risultare falso; se vero, vale il
  cancello di §4.2.

## §7 — Gate di uscita S0 → Stagione 1 (tutti AND)
(i) ≥ 20 giornate effettive per tutte e 3 le repliche entro il cap;
(ii) tasso malformati < 5%;
(iii) baseline raccolta e ammissibile (§4.2), soglie scritte in config;
(iv) integrità: ledger verify() verde su tutta S0, input byte-identici in
     tutte le giornate, zero violazioni del firewall;
(v) decisione dell'owner di avviare la Stagione 1, che richiede la propria
    PREREG_LAB_S1 (gamba meccanica dalla campagna carry, e-process appaiato,
    kill-criterion, eventuale sizing libero) congelata prima del via.

## §8 — Il rito del pin (precondizione al primo giorno)
Checklist, nell'ordine: smoke live VERDE (retention verificata di fatto);
scripts/verify_pin.py verde (string esatta accettata; sampling esplicito
rifiutato; thinking: disabled rifiutato); promozione della persona approvata
in agents/trader_v0/ con hash nel FreezeManifest; FreezeManifest completo
(model string, sampling_policy, prompt_sha, universo, config rito);
ots_pending → False con timbro OTS del manifest; commit dedicato. SOLO dopo
questo rito il primo giorno di S0 può essere eseguito, su autorizzazione
esplicita dell'owner.
