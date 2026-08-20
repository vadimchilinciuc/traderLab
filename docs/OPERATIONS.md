# OPERATIONS — il rito quotidiano

Manuale operativo del Trader Lab: come si esegue una giornata, come si legge
quello che è successo, e cosa si fa — e cosa **non** si fa — quando un giorno
salta.

Questo documento descrive la macchina. Le regole di ingegneria stanno in
`CLAUDE.md` e vincono su qualunque comodità operativa descritta qui.

---

## 1. Cosa fa una giornata

Una giornata è una passata di `scripts/run_daily.ps1`, che è un guscio sottile
attorno a `scripts/run_daily.py` → `arena/daily_ritual.py`. Tre passi, in
quest'ordine:

| # | Passo | Rete | Dove finisce |
| - | ----- | ---- | ------------ |
| 1 | Marcatura dei giorni mancati | no | `data/ledger/ops.jsonl` |
| 2 | Costruzione dello snapshot | **sì**, processo separato | `data/snapshots/` |
| 3 | Decisioni delle repliche | no | `data/ledger/season0.jsonl`, `data/toolcalls/` |

La rete si accende **solo** per il passo 2, in un processo suo, con
`TRADERLAB_ALLOW_NETWORK=1` iniettato per quella singola esecuzione. Il
processo che decide riceve un ambiente da cui quella variabile è stata
**rimossa**, anche se chi ha lanciato il rito ce l'aveva impostata: il firewall
del Tool Server (`CLAUDE.md` §7) non si eredita per distrazione.

Il passo 2 rifiuta di partire se non trova lo snapshot_id nel proprio output:
senza uno snapshot congelato e identificato non si decide niente. Non esiste un
ripiego su dati live.

### Ora UTC fissa

L'ora del rito è **una sola** ed è dichiarata in codice:

```
toolserver/config.py → DEFAULT_SNAPSHOT_HOUR_UTC = 0     # 00:00 UTC
```

È la stessa ora a cui `SnapshotBuilder` normalizza l'`asof_utc`. Il task
schedulato va registrato a quell'ora UTC, non a un'ora comoda: uno snapshot
costruito a un'ora diversa descrive una giornata diversa da quella che il
ledger dice di aver deciso.

Il rito schedulato gira con `--require-configured-hour` e **si ferma** (exit
code 2) se l'ora UTC di sistema non coincide con quella configurata. Le prove a
mano si lanciano con `-IgnoreConfiguredHour`.

> Cambiare l'ora significa cambiare `DEFAULT_SNAPSHOT_HOUR_UTC` **e**
> ri-registrare il task. Cambiarla solo nello scheduler produce un rito che si
> rifiuta di partire — che è il comportamento voluto.

---

## 2. Eseguire a mano

Dalla radice del repo:

```powershell
# giornata completa con MockLLM: nessuna chiamata al modello, nessun costo
.\scripts\run_daily.ps1 -IgnoreConfiguredHour

# giornata completa con il modello pinnato: consuma budget vero
$env:TRADERLAB_ALLOW_LIVE_API = "1"
.\scripts\run_daily.ps1 -Live -IgnoreConfiguredHour
```

La modalità `-Live` richiede `ANTHROPIC_API_KEY` **in ambiente**. Lo script ne
verifica la sola presenza: la chiave non viene letta, non viene stampata, non
finisce nel log. Non esiste un modo supportato di passarla da riga di comando.

Parametri: `-Ledger`, `-OpsLedger`, `-LogDir` per spostare i percorsi (utile
per una prova su cartelle usa-e-getta senza toccare il track record).

### Le quattro guardie della modalità `-Live`

Dal 20/08/2026 `scripts/run_day.py` in modalità `--live` **non parte** se una
di queste quattro non passa. Ognuna è un rifiuto pulito con exit code 2, mai
un ripiego silenzioso:

1. **Il manifest si carica, non si ricostruisce** (verbale RUN2 §A.2,
   precondizione TL-007). Il percorso è `--manifest`, di default
   `manifests/trader_v0_freeze_manifest.json`. Prima, il runner ricomponeva il
   manifest a runtime incorporando lo sha di git corrente: le tre giornate di
   Stagione 0 produssero tre `freeze_id` diversi, nessuno uguale a quello del
   manifest firmato e timbrato.
2. **Il `freeze_id` si ricalcola** dal contenuto e deve coincidere con quello
   scritto nel file. Se diverge, il manifest è stato toccato dopo la firma.
3. **`pin_commit` deve esserci.** È il commit del rito del pin, fisso per
   tutta la stagione, e ha preso il posto di `context_git_sha` dentro il
   calcolo del `freeze_id`. Assente o segnaposto = il pin non è avvenuto e non
   c'è una stagione da far girare.
4. **La spesa cumulata di stagione deve stare sotto `1,5 ×` il preventivo**
   (D5). Il preventivo è `season_budget_usd`, valorizzato al rito del pin;
   **assente è a sua volta un rifiuto**, perché trattarlo come "nessun limite"
   trasformerebbe la dimenticanza di un campo in una stagione senza tetto.
   Insieme al preventivo il runner pretende le giornate attese
   (`season_expected_days`) e le **quattro voci di listino**
   (`price_per_mtok_input`, `price_per_mtok_output`,
   `price_per_mtok_cache_write_5m`, `price_per_mtok_cache_read`): senza
   tariffe la spesa cumulata non è calcolabile, e un preventivo confrontato
   con un numero che non si sa costruire non è una guardia. Il rifiuto elenca
   **tutti** i campi mancanti in una volta.

> **Prima del rito del pin le guardie 3 e 4 rifiutano sempre**, ed è corretto
> così. Il manifest di Stagione 0 non ha né `pin_commit` né
> `season_budget_usd`, e sotto il contratto nuovo il suo `freeze_id`
> ricalcolato non coincide più con quello scritto nel file: il file è
> congelato e non si tocca, quindi la guardia 2 lo respinge per prima. La
> modalità mock non è toccata da nessuna delle quattro — non c'è un modello
> pinnato da rispettare quando il modello è il MockLLM.

---

## 2-bis. Smoke live di pre-stagione

**Cosa dimostra, e cosa no.** Una giornata completa contro l'API vera, con il
modello della stagione, per verificare **una cosa sola**: che il protocollo
regga: razionale in testo libero PRIMA, `submit_decision` DOPO (`CLAUDE.md`
§8). Non è una giornata di stagione, non misura edge, non produce track
record. È una precondizione al pin — il §13 passo 3 del
`docs/PREREG_LAB_S0_RUN2.md` la pretende verde prima del primo giorno, come il
§8 del `PREREG_LAB_S0` la pretendeva per la Stagione 0.

**Fonte di questa procedura**: `tests/test_live_smoke.py`, che è il codice che
la esegue, e la prassi della Stagione 0. Fino al 2026-08-20 la procedura non
era trascritta qui e viveva solo nel codice e in un referto gitignorato: chi
avesse clonato il repo non l'avrebbe trovata. Questa sezione chiude quel buco.

### Il modello viene dal pin, mai da un default di modulo

**È un principio, non la riparazione di un file** (decisione dell'owner del
2026-08-20, rito PIN-BIS). Qualunque chiamata reale all'API prende la model
string dal **Freeze manifest della stagione**, e mai da una costante di
modulo.

Il motivo è che una costante non ha modo di sapere quale modello è pinnato, e
quindi **sopravvive in silenzio a un cambio di modello**. Nel Lab è successo
due volte:

- il listino stava fra le costanti di `ledger/spend.py`, fermo a
  `claude-fable-5` ($10/$50) mentre TL-007 aveva pinnato `claude-opus-5`
  ($5/$25): le guardie economiche contavano la spesa al doppio del vero.
  Corretto da **TL-010**, che ha portato i quattro prezzi dentro il manifest;
- `tests/test_live_smoke.py` costruiva il manifest con
  `build_freeze_manifest(ASOF)`, ereditando `DEFAULT_MODEL_STRING` —
  `claude-fable-5`. Eseguita alla lettera, la procedura di S0 avrebbe fatto lo
  smoke di pre-stagione **sul modello sbagliato**: spesa su un modello non
  pinnato, e nessuna prova sul modello che la stagione avrebbe usato davvero.

Perciò il percorso del manifest si passa in `TRADERLAB_SMOKE_MANIFEST`, e da
lì escono model string, `max_tokens`, `thinking_declared` e politica di
caching. Se la variabile manca, lo smoke **fallisce** con un messaggio
esplicito: non ripiega su un default, perché un default è il difetto.

> **Pendenza dichiarata, non chiusa qui.** `DEFAULT_MODEL_STRING` in
> `arena/config.py` vale ancora `claude-fable-5` ed è tuttora il default di
> `build_freeze_manifest` e di `scripts/verify_pin.py --model`. È rimasto
> intatto di proposito: cambiarlo dentro un rito di pin ne allargherebbe il
> raggio oltre ciò che le firme coprono. La decisione è **post-pin**, e la
> candidata è **eliminare il default** e rendere il modello sempre esplicito.

### I comandi

Lo smoke richiede **due** flag di ambiente più la chiave. Il primo sblocca le
chiamate reali (`toolserver.config.live_api_allowed`), il secondo dice quale
pin provare. Senza il primo il test risulta `skipped`, ed è il comportamento
normale della suite:

```bash
# la suite normale: lo smoke e' SKIPPED, nessuna chiamata, nessun costo
uv run pytest

# lo smoke di pre-stagione: chiamate vere, costo vero
TRADERLAB_ALLOW_LIVE_API=1 \
TRADERLAB_SMOKE_MANIFEST=manifests/trader_v1_run2_freeze_manifest.json \
uv run pytest tests/test_live_smoke.py -v -s
```

`-s` non è cosmetico: senza di esso `pytest` cattura lo stdout e **i numeri
dello smoke non si vedono**. Il test stampa, e vanno trascritti nel referto:
il modello letto dal pin, `max_tokens`, `thinking_declared`, le chiamate
consumate sul `CallBudget`, e per ogni asset l'esito, l'azione, la confidenza
e le `features_used`.

`ANTHROPIC_API_KEY` si legge **solo** dall'ambiente (`CLAUDE.md` §0). Il file
`.env` del repo non viene letto dal rito notturno — vedi §4, «Ambiente del
task» — ma serve allo smoke se è la shell a caricarlo.

### La marcatura `smoke`, e perché tiene fuori dal ledger di stagione

Tre marcature, tutte con lo stesso valore letterale `smoke`, e una quarta
protezione che è strutturale:

| Dove | Valore | A cosa serve |
| --- | --- | --- |
| `ArenaConfig(replica_ids=("smoke",))` | `smoke` | una sola replica, non le tre di D1: lo smoke non è una giornata di stagione |
| `runner.run_day(..., run_id="smoke")` | `smoke` | il `run_id` che finisce in ogni riga del ledger |
| `ToolCallLog(..., run_id="smoke")` | `smoke` | il log delle tool call nasce sotto quel `run_id` |
| percorso di ledger e log | `tmp_path` di `pytest` | **la protezione vera** |

L'esclusione dal ledger di stagione **non è affidata a un'etichetta**: il test
scrive in `tmp_path`, la cartella usa-e-getta di `pytest`, quindi in
`tmp_path/ledger/smoke.jsonl` e `tmp_path/toolcalls/`. Il ledger di stagione è
`data/ledger/season0.jsonl` (`arena/daily_ritual.py`,
`DEFAULT_LEDGER_PATH`) e **non viene mai aperto**. Un'etichetta si può
dimenticare; un percorso che non esiste nel repo no. È la stessa disciplina del
§2 di `CLAUDE.md`: il vincolo sta nel codice, non nella buona volontà.

Precedente storico, per chi legge i file: in `data/toolcalls/` restano
`smoke-finale.jsonl` e `tl002.jsonl`, entrambi del 2026-08-13, che
**precedono** le giornate di Stagione 0 e sono smoke, non giornate. Sono
esclusi dai conteggi di stagione, e la cartella è gitignorata
(`.gitignore`, `data/toolcalls/*`).

### La verifica di retention, e quanto vale oggi

In Stagione 0 lo smoke era **anche** la prova della configurazione di data
retention dell'organizzazione, e lo era in modo forte: `claude-fable-5` non è
disponibile sotto zero-data-retention, quindi con un workspace in ZDR **ogni**
chiamata rispondeva 400 qualunque fosse il payload. Se lo smoke passava, la
retention era a posto — non c'era altro modo di passare.

**Su `claude-opus-5` la prova è più debole, e va detto.** La documentazione
ufficiale (letta il 2026-08-20,
`https://platform.claude.com/docs/en/build-with-claude/thinking-troubleshooting`)
elenca `Claude Fable 5` e `Claude Mythos 5` fra i modelli non disponibili in
zero-data-retention, e **non** vi elenca `claude-opus-5`. Quindi uno smoke
verde su Opus 5 dimostra che *quelle* chiamate sono state servite, non che il
workspace sia configurato come si crede. La verifica «di fatto» resta quella
che si può fare da qui — la chiamata passa, quindi la configurazione la
permette — e non va riportata per più di quello che è.

### Cosa si trascrive nel referto

Token e costi non escono da un contatore del test: si leggono dal log delle
tool call, che è la sede di verità (`CLAUDE.md` §9). Ogni riga
`llm_complete` porta `usage` con `input_tokens`, `output_tokens`,
`cache_creation_input_tokens`, `cache_read_input_tokens`, più
`thinking_absent` e `thinking_tokens` (§A.7):

```bash
# le righe di usage dello smoke appena eseguito
python -c "import json,sys,glob; [print(json.dumps(json.loads(r).get('usage'))) for f in glob.glob('<tmp_path>/toolcalls/*.jsonl') for r in open(f) if json.loads(r).get('tool')=='llm_complete']"
```

Il percorso di `tmp_path` lo stampa `pytest` stesso quando il test fallisce, e
si ottiene comunque con `-s` e una `print`. Il costo in dollari si calcola con
le quattro tariffe del **manifest** — mai con costanti di modulo, per la stessa
ragione del §«Il modello viene dal pin».

---

## 3. Exit code

Sono dichiarati in `arena/daily_ritual.py` (`EXIT_MEANING`) e sono quelli che
lo scheduler registra nella colonna "Last Run Result".

| Codice | Significato | Cosa fare |
| ------ | ----------- | --------- |
| 0 | Giornata completata | Niente. |
| 1 | *Non usato dal rito* | È un'eccezione Python non gestita: è un bug, apri il log e leggi la traccia. |
| 2 | Precondizione non soddisfatta — il rito non è partito | `uv` fuori dal PATH del task, ora UTC sbagliata, `-Live` senza flag o senza chiave. |
| 3 | Costruzione dello snapshot fallita | Rete, endpoint pubblico, o snapshot_id illeggibile. Vedi §5. |
| 4 | Esecuzione delle decisioni fallita | Il modello, il budget, o il ledger. Vedi §5. |
| 5 | La giornata di oggi è già nel ledger | Nessun intervento: il write-once ha fatto il suo lavoro. |
| 6 | Marcatura dei giorni mancati fallita | Il registro operativo è illeggibile o corrotto. Vedi §6. |
| 7 | Decisioni fallite con errore ritentabile per tutta la finestra di retry | Il rito è partito e l'API non ha risposto entro ~45 min (3 tentativi, 15 min di attesa ciascuno). Non è un giorno saltato: si riprova in un'altra finestra oraria. Vedi §5. |

Il codice **1 resta libero di proposito**: è quello che Python usa per
un'eccezione non gestita, e non deve poter essere scambiato per un esito
previsto del rito.

Il codice 4 può anche arrivare **dopo** fino a tre ripetizioni dell'intero
passo delle decisioni: se `scripts/run_day.py` esce con il codice dedicato di
errore ritentabile (rete/capacità transitoria), il rito attende 15 minuti e
riprova l'intero passo, fino a un totale di ~45 minuti, prima di arrendersi
con il codice 7. Il passo dello snapshot non si ripete: solo le decisioni.
Ogni attesa e il fallimento finale (se ci si arriva) sono eventi propri nel
registro operativo (`decisions_retry_wait`, `failed_decisions`).

---

## 4. Registrare il task in Windows Task Scheduler

**Lo fa l'owner, a mano.** Nessuno script del repo registra il task: registrare
un'esecuzione automatica è una decisione operativa, non un effetto collaterale
di un commit.

### Interfaccia grafica

1. `Task Scheduler` → **Create Task…** (non "Basic Task": serve il controllo
   sull'account e sulle condizioni).
2. **General**
   - Nome: `traderLab — rito quotidiano`.
   - ~~*Run whether user is logged on or not*~~ → **corretto**: usare invece
     ***Run only when user is logged on***. Le variabili d'ambiente
     **utente** richieste da `-Live` (vedi sotto) vivono nel profilo
     dell'utente e servono una sessione attiva per essere lette in modo
     affidabile — bastano Win+L (sessione bloccata, non chiusa), non basta il
     logoff. Verificato sul task registrato: `LogonType=Interactive` (non
     `S4U`), coerente con questo vincolo.
   - *Run with highest privileges*: **non** serve, lasciarlo spento.
3. **Triggers** → New…
   - *Daily*, ricorrenza 1 giorno.
   - Ora di avvio: **l'ora locale che corrisponde a 00:00 UTC**
     (`DEFAULT_SNAPSHOT_HOUR_UTC`). L'interfaccia grafica ragiona in ora
     locale, quindi da qui l'ancoraggio a UTC **non si ottiene**: si ottiene
     dalla riga di comando, vedi «Ancorare il trigger a UTC» sotto. Se l'ora
     locale non corrisponde più, il rito si ferma da solo con exit code 2
     invece di costruire uno snapshot sbagliato.
   - *Synchronize across time zones*: spuntato, se disponibile.
4. **Actions** → New… → *Start a program*
   - Program/script: `powershell.exe`
   - Argomenti:
     `-NoProfile -ExecutionPolicy Bypass -File "C:\percorso\traderLab\scripts\run_daily.ps1"`
   - Aggiungere ` -Live` agli argomenti **solo** quando la stagione è
     autorizzata e il pin è stato effettuato.
   - Start in: `C:\percorso\traderLab`
5. **Conditions**
   - Togliere *Start the task only if the computer is on AC power*.
   - Lasciare *Wake the computer to run this task* a discrezione: una macchina
     spenta produce un giorno saltato, che è un esito legittimo e registrato.
6. **Settings**
   - *If the task fails, restart every*: **non impostare**. Un ritentativo
     automatico su un rito che ha già scritto nel ledger si scontra con il
     write-once e produce solo rumore (exit code 5).
   - *Stop the task if it runs longer than*: 4 ore.
   - *If the task is already running*: **Do not start a new instance**.

### Riga di comando equivalente

Da eseguire una volta sola, dall'owner, con il percorso reale del repo:

```powershell
$repo = "C:\percorso\traderLab"
$azione = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\run_daily.ps1`"" `
    -WorkingDirectory $repo
# 00:00 UTC espresso in ora LOCALE della macchina.
$oraLocale = [System.TimeZoneInfo]::ConvertTimeFromUtc(
    (Get-Date).ToUniversalTime().Date, [System.TimeZoneInfo]::Local)
$trigger = New-ScheduledTaskTrigger -Daily -At $oraLocale
$impostazioni = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -MultipleInstances IgnoreNew -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "traderLab — rito quotidiano" `
    -Action $azione -Trigger $trigger -Settings $impostazioni
```

### Ancorare il trigger a UTC

**Eseguito il 20/08/2026** sul task `traderLab — rito quotidiano` (verbale
RUN2 §A.6 e §A.12). Il trigger era `2026-08-15T02:00:00+02:00`: le 02:00
locali valgono le 00:00 UTC **solo finché vige CEST**, e il 25/10/2026 il
cambio d'ora avrebbe spostato l'istante dello snapshot di un'ora a metà
stagione — cioè cambiato una variabile senza dichiararlo.

Il rimedio è scrivere la `StartBoundary` con il **suffisso `Z`**. Il Task
Scheduler la conserva così: il trigger segue UTC e il cambio d'ora non lo
tocca. Comando realmente eseguito, da PowerShell:

```powershell
$t = Get-ScheduledTask | Where-Object { $_.TaskName -like "*rito quotidiano*" }
$nome = $t.TaskName
$xml = Export-ScheduledTask -TaskName $nome
$nuovo = $xml -replace '<StartBoundary>2026-08-15T02:00:00\+02:00</StartBoundary>', `
                       '<StartBoundary>2026-08-15T00:00:00Z</StartBoundary>'
Register-ScheduledTask -TaskName $nome -Xml $nuovo -Force
```

> **Attenzione a come si verifica.** `Get-ScheduledTask`,
> `Export-ScheduledTask` e `schtasks /query` **rendono la boundary in ora
> locale**: dopo il comando qui sopra continuano a mostrare
> `2026-08-15T02:00:00+02:00`, e sembra che non sia successo niente. Non è
> così. La definizione conservata sta in
> `C:\Windows\System32\Tasks\traderLab — rito quotidiano` e va letta lì:
>
> ```powershell
> Get-Content -LiteralPath "C:\Windows\System32\Tasks\traderLab — rito quotidiano" `
>     -Encoding Unicode | Select-String "StartBoundary"
> ```
>
> Verificato il 20/08/2026: il file conserva `2026-08-15T00:00:00Z`, mentre
> `schtasks /query` mostrava `2026-08-15T02:00:00+02:00`. **Il file ha
> ragione.** Chi verifica solo con `schtasks` conclude, sbagliando, che
> l'ancoraggio non è stato applicato.

Nota su `Set-ScheduledTask -Trigger`: assegnare `StartBoundary` sull'oggetto
restituito da `Get-ScheduledTask` e ripassarlo a `Set-ScheduledTask` **non
funziona** — provato il 20/08, la boundary resta quella locale. La via che
funziona è quella dell'XML qui sopra.

### Ambiente del task

Il task **non** eredita la sessione interattiva. Due conseguenze pratiche:

- `uv` deve stare nel PATH dell'account con cui gira il task, altrimenti il
  wrapper si ferma con exit code 2 alla prima riga utile.
- `ANTHROPIC_API_KEY` in modalità `-Live` va impostata come variabile
  d'ambiente **utente o di macchina**, non nel profilo della shell. Il file
  `.env` del repo **non viene letto** dal rito: serve solo allo smoke test
  manuale.

Dopo la registrazione, provare una volta con **Run** dal menù contestuale e
leggere il log della giornata prima di considerare il task attivo.

**Stato operativo (verificato il 14/08/2026).**

- Variabili d'ambiente **utente** richieste: `ANTHROPIC_API_KEY` e
  `TRADERLAB_ALLOW_LIVE_API=1` — il task **non legge `.env`** (vale anche fuori
  da `-Live`, vedi sopra).
- Vincolo "Esegui solo se l'utente è connesso" = **sessione attiva richiesta**:
  Win+L (blocco schermo) va bene, il **logoff no** — il task è registrato con
  `LogonType=Interactive` e non gira senza una sessione utente aperta.

---

## 5. Leggere i log

Un file per giornata, sotto `data/logs/`, con la data **UTC** nel nome:

```
data/logs/daily-2026-08-13.log
```

Ogni riga inizia con un timestamp UTC. Le righe scritte dal guscio PowerShell
portano il marcatore `[wrapper]`; tutte le altre vengono dall'orchestratore
Python. Lo stdout e lo stderr dei due processi figli sono riportati integralmente
in blocchi indentati (`--- build_snapshot stdout ---`, `--- run_day stderr ---`).

Due passate nello stesso giorno **si accodano allo stesso file**: il log
racconta la giornata, non l'esecuzione.

Cosa cercare, in ordine:

| Riga | Significato |
| ---- | ----------- |
| `STOP: …` | Il motivo per cui il rito si è fermato. C'è sempre, se si è fermato. |
| `snapshot congelato: <sha256>` | Lo snapshot su cui si è deciso. |
| `giorni mancati marcati come skipped_day: …` | Ci sono buchi. Vedi §6. |
| `giornata completata` | Ultima riga di una giornata riuscita. |

Il log **non** è il track record. La contabilità sta nei due ledger:

```powershell
# integrità della catena dei verbali
uv run python -c "from ledger.trader_ledger import TraderLedger; print(TraderLedger('data/ledger/season0.jsonl').verify())"

# giorni saltati registrati
uv run python -c "from ledger.ops_ledger import OpsLedger; print(OpsLedger('data/ledger/ops.jsonl').skipped_days())"
```

Il log dei tool (`data/toolcalls/<run_id>.jsonl`) dice **cosa il Trader ha
chiesto**, che è un dato alla pari di cosa ha deciso (`CLAUDE.md` §9).

---

## 6. Se un giorno salta

Un giorno salta quando il rito non gira o non arriva a scrivere: macchina
spenta, rete assente, task disabilitato, errore al passo 2 o 3.

### Cosa fa il Lab, da solo

Alla passata successiva, il rito confronta l'ultimo giorno presente nel ledger
dei verbali con la data odierna e scrive uno `skipped_day` nel registro
operativo per **ogni giorno in mezzo**. Il giorno corrente non è mai un giorno
saltato: sta per essere eseguito. La marcatura è idempotente — finché il buco
esiste, ogni rito lo ri-rileva e non lo riscrive.

### Cosa NON si fa, mai

**Non si recuperano le decisioni di un giorno saltato.** Non c'è un flag, non
c'è uno script, e non va aggiunto.

Il motivo non è pigrizia operativa: uno snapshot ricostruito oggi per l'altro
ieri conterrebbe dati che quel giorno non erano ancora noti, e il Trader
deciderebbe guardando il futuro. Un verbale del genere non è una decisione, è
un backtest travestito — e i backtest non sono ammessi come prova di edge
(`CLAUDE.md` §5). Un buco onesto vale più di una riga inventata: il buco si
conta, la riga falsa contamina il track record.

Lo stesso vale per il write-once: se il ledger contiene già la giornata di
oggi, il rito esce con 5 e non tocca nulla. Non è un errore da aggirare.

### Cosa fa l'owner

1. Aprire il log del giorno in cui il rito si è fermato e trovare la riga
   `STOP:`.
2. Rimuovere la causa (rete, PATH, chiave, ora del trigger).
3. Lanciare a mano la giornata **odierna** — mai una passata:
   `.\scripts\run_daily.ps1 -IgnoreConfiguredHour`.
4. Verificare che i giorni saltati siano marcati (`skipped_days()`) e che la
   catena del ledger verifichi ancora.
5. Se i giorni saltati sono molti o consecutivi, annotarlo: una finestra di
   valutazione con buchi ha meno osservazioni appaiate di quante ne dichiara, e
   la finestra pre-registrata del kill-criterion (`ledger/eprocess.py`) conta
   **osservazioni**, non giorni di calendario.

---

## 7. Cosa questo rito non fa

- **Non effettua il pin.** `ots_pending` resta `True` finché l'owner non esegue
  la procedura di pin (`scripts/verify_pin.py` e il Freeze manifest).
- **Non avvia una stagione.** Far girare il rito in mock non apre alcun track
  record; la Stagione 0 parte solo con l'autorizzazione esplicita dell'owner.
- **Non registra sé stesso** nello scheduler.
- **Non legge `.env`.** L'unica credenziale ammessa arriva dall'ambiente.
- **Non recupera il passato**, in nessuna circostanza.

---

## 8. Controllo mattutino

Un secondo task, indipendente dal rito quotidiano: gira ogni mattina alle
**07:00 ora locale** e risponde a tre domande — *il rito di stanotte ha
prodotto verbali?*, *il rito di STANOTTE (quella che deve ancora partire)
troverà le sue precondizioni soddisfatte?* e *la stagione sta spendendo più in
fretta del preventivo?* — più, il lunedì, un tentativo silenzioso di far
avanzare il timbro OTS dei file congelati. Non tocca il ledger, non decide
nulla: è uno strumento di lettura e di controllo, non un secondo rito.

**Registrato il 20/08/2026** (verbale RUN2 §A.6). Fino ad allora lo script
esisteva sul disco e non lo lanciava nessuno.

### Cosa fa

`scripts/morning_check.ps1` → `scripts/morning_check.py`
(`arena`-style: il wrapper PowerShell è sottile, la logica sta nello script
Python, per lo stesso motivo di `run_daily.ps1`). Tre passi indipendenti:

1. **Verifica la giornata di stanotte** (quella appena passata), **ma solo se
   una stagione è attiva**. Cerca nel ledger dei verbali
   (`data/ledger/season0.jsonl`) la giornata corrispondente a 00:00 UTC di
   oggi.
   - **Se c'è**: genera il rapporto del mattino (`scripts/morning_report.py`,
     vedi sotto) e lo appende a `data/logs/morning-<data>.log`. Exit 0.
   - **Se non c'è e una stagione è attiva**: mostra un avviso **visibile**
     sullo schermo (`msg.exe`, con fallback a un popup PowerShell se
     `msg.exe` non è disponibile) con il testo `traderLab: il rito di
     stanotte NON ha prodotto verbali - controlla
     data/logs/daily-<data>.log`, e scrive lo stesso allarme nel log del
     controllo. Exit 1. Un avviso che non riesce a comparire (es. nessuna
     sessione interattiva) è annotato nel log ma **non** fa fallire il
     controllo per quello: l'exit code racconta la giornata, non il popup.
   - **Se non c'è e nessuna stagione è attiva**: nessun avviso, nessun
     allarme, exit 0, con il motivo scritto nel log. Fuori da una stagione il
     rito notturno è spento per costruzione e i verbali che non produce non
     sono un'anomalia: sono la normalità. Un allarme che suona ogni mattina
     di un cantiere fermo insegna a non guardarlo, cioè si disattiva da solo
     senza che nessuno l'abbia spento. **Ogni altra anomalia continua ad
     allarmare** anche fuori stagione: il preflight che dice NO e il ritmo di
     spesa oltre soglia restano motivi validi.

   **Quando una stagione è «attiva»**: il Freeze manifest di default
   (`manifests/trader_v0_freeze_manifest.json`, o quello passato con
   `--manifest`) esiste, si carica, il suo `freeze_id` ricalcolato coincide, e
   porta un `pin_commit` vero. Manifest assente, illeggibile, con `freeze_id`
   divergente o non ancora pinnato valgono tutti **nessuna stagione**; quale
   dei quattro sia lo dice il log.
2. **Esegue il preflight della PROSSIMA passata** (`scripts/preflight.py`,
   vedi sotto), sempre, indipendentemente dall'esito del passo 1 — sono due
   notti diverse, ieri notte e stanotte. La tabella finisce nel log del
   mattino (blocco `--- preflight per stanotte ---`). Se il preflight dice
   NO, mostra un **secondo** avviso visibile, distinto da quello del passo 1:
   `traderLab: stanotte NON partira' - <prima causa>`. Non tocca l'exit code
   del controllo, che resta determinato solo dal passo 1.
3. **Solo il lunedì**, tenta l'upgrade OpenTimestamps dei file elencati in
   `DEFAULT_OTS_TARGETS`, che sono i **tre** file timbrati del record di
   Stagione 0: `manifests/trader_v0_freeze_manifest.json`,
   `docs/PREREG_LAB_S0.md` e `MANIFEST_S0.json`. Il terzo è stato aggiunto il
   20/08/2026: mancava, e la conseguenza si è misurata — il suo `.ots` era
   rimasto pending su tutti e quattro i calendar mentre gli altri due erano
   già confermati su Bitcoin (§8 punto 2 di
   `docs/research/results/2026-08-20_PREREG-EVIDENCE_PREVENTIVO_RUN2.md`). Via
   `scripts/ots_stamp.py upgrade`, con `TRADERLAB_ALLOW_NETWORK=1` iniettato
   **solo** in quel sottoprocesso — stessa disciplina di rete del passo dello
   snapshot nel rito quotidiano (`CLAUDE.md` §7). Non è mai bloccante: se i
   calendar non rispondono o l'attestazione resta pending, l'esito finisce
   nel log e il controllo prosegue comunque. Fuori dal lunedì questo passo
   non parte.
4. **Verifica il ritmo di spesa della stagione** (D5). Legge la spesa
   cumulata — le giornate e i `run_id` dal ledger dei verbali, i token dal log
   delle tool call — e la confronta con `1,25 ×` il pro-rata del preventivo
   (`season_budget_usd` del Freeze manifest × giornate eseguite ÷
   `season_expected_days` **dello stesso manifest**). Oltre soglia è
   un'anomalia. Non tocca l'exit code: la soglia che **ferma** le cose è
   quella dura, `1,5 ×` il preventivo, e vive nel runner (§2). I termini sono
   **sei** — `season_budget_usd`, `season_expected_days` e le quattro voci di
   listino `price_per_mtok_*` — e si firmano insieme al rito del pin: finché
   ne manca anche uno solo il passo si **salta** con il motivo scritto nel
   log, e non produce allarmi — un allarme che scatta ogni giorno per una
   condizione normale insegna a ignorare il canale.

   Le giornate attese stavano in una costante di `ledger/spend.py`
   (`SEASON_EXPECTED_DAYS = 42`) e ora sono un campo del manifest. Il motivo è
   aritmetico: con un preventivo tarato su 28 giornate e un pro-rata calcolato
   su 42, la soglia varrebbe `0,83 ×` la spesa attesa, cioè **sotto** di essa,
   e l'allarme suonerebbe ogni giorno di una stagione perfettamente in linea
   col proprio preventivo.

   Il **listino** ha fatto la stessa strada, il 20/08/2026, per un motivo
   speculare: erano quattro costanti dello stesso modulo, ferme ai prezzi di
   Claude Fable 5 ($10 input / $50 output) mentre il modello pinnato era
   diventato `claude-opus-5` ($5 / $25). Entrambe le guardie contavano quindi
   la spesa al **doppio** del vero, e con il preventivo proposto di $89,90 la
   soglia dura sarebbe scattata al giorno 21 invece che al 42. Una costante di
   modulo non può accorgersi che il modello è cambiato; un campo del pin,
   assente finché non lo si firma, sì. I prezzi in vigore sono trascritti nel
   §4 di
   `docs/research/results/2026-08-20_PREREG-EVIDENCE_PREVENTIVO_RUN2.md`:
   input $5 / MTok, output $25 / MTok, scrittura in cache a 5 minuti
   $6,25 / MTok, lettura da cache $0,50 / MTok.

### Il canale d'allarme: `ALLARME_<data>.txt`

Verbale RUN2 §A.6, decisione D3. Su **exit ≠ 0** o su **anomalia rilevata** il
controllo scrive `ALLARME_<data>.txt` alla radice del repo, **con dentro
l'elenco numerato dei motivi**. Il file è gitignorato (`.gitignore`,
`ALLARME_*.txt`): è un segnale per l'owner che apre il laptop, non un
artefatto del track record.

Esiste perché l'avviso a schermo non basta: `msg.exe` e il popup PowerShell
richiedono una sessione interattiva, e se non c'è l'avviso non compare e nel
log resta una riga che nessuno apre. Il file invece resta lì finché qualcuno
non lo guarda. **Cancellarlo dopo averlo letto è la chiusura prevista**:
nessun automatismo lo rimuove, e nessun automatismo lo sovrascrive se non una
seconda passata dello stesso giorno.

I motivi che lo fanno comparire, nell'ordine in cui vengono elencati:

| Motivo | Origine |
| ------ | ------- |
| `prova forzata …` | `--force-alarm`, vedi sotto |
| `exit N — …` | stagione attiva e giornata di stanotte assente dal ledger (passo 1) |
| `preflight NO per stanotte: …` | il preflight dice NO (passo 2) |
| `ritmo di spesa oltre soglia (D5): …` | la cumulata sfonda il pro-rata (passo 4) |

Un caso lo scrive il wrapper PowerShell e non lo script Python: quando `uv`
non è nel PATH del task, il controllo non parte affatto (exit 2) e senza
quella riga in `morning_check.ps1` l'unico caso in cui il controllo non può
avvisare sarebbe anche l'unico in cui non lascia traccia.

**Provare il canale senza rompere niente.** Un allarme che non si è mai visto
scattare non si distingue da un allarme che non scatta:

```powershell
# in modo-allarme forzato: il file compare, con il motivo dentro
uv run python scripts/morning_check.py --force-alarm
# in modo normale, con la giornata di stanotte a posto: non compare
uv run python scripts/morning_check.py
```

Verificato il 20/08/2026 su un ledger sintetico contenente la giornata
corrente: in modo forzato `ALLARME_2026-08-20.txt` è comparso con il motivo
`prova forzata del canale d'allarme`; in modo normale non è comparso, ed exit
è stato 0. Il file di prova è stato rimosso a fine verifica.

### `scripts/preflight.py`

Verifica **di giorno** le otto precondizioni della passata di **stanotte**,
nato da due notti di Stagione 0 perse per precondizioni scoperte solo a
mezzanotte. Stampa una tabella PASS/FAIL/PROMEMORIA e la riga finale `PRONTO
PER STANOTTE: SI` o `NO — <prima causa>`. Invocabile anche da solo:

```powershell
uv run python scripts/preflight.py
```

Punto rilevante: **il rito non legge mai `.env`** (§4, §7 sopra). Il
preflight legge `.env` solo in via diagnostica, per segnalare un
disallineamento con l'ambiente di processo — mai come fonte reale della
risoluzione di `-Live`, che replica esattamente quella di `run_daily.ps1`
(Arguments del task registrato, poi ambiente di processo). Il passo (c),
rete verso Hyperliquid, gira in un sottoprocesso separato con
`TRADERLAB_ALLOW_NETWORK=1` iniettato solo lì, mai nel processo del
preflight — stessa disciplina di `CLAUDE.md` §7. Exit code: `0` se pronto,
`1` altrimenti.

`scripts/morning_report.py` (invocabile anche da solo, `uv run python
scripts/morning_report.py`) stampa un rapporto sintetico dell'ultima
giornata toccata dal rito: data, esito (`completata` / `skipped_day` /
`failed_decisions` / `nessuna`), per ogni asset le decisioni delle tre
repliche con confidence e l'accordo tra loro (`3/3`, `2/3`, `1/3`), i token
del giorno (input, output, letti e scritti in cache) con il costo stimato in
USD **al listino firmato nel Freeze manifest** (`--manifest`, per default
quello di `arena.config.DEFAULT_MANIFEST_PATH`), l'esito di `verify()` sulla
catena del ledger, e il conteggio delle giornate
registrate sulla finestra del kill-criterion pre-registrato
(`ledger/eprocess.py`, `window=20`). Gestisce con grazia il caso in cui non
esista ancora nessuna giornata.

Quando il manifest non porta il listino — la condizione normale finché il rito
del pin non è avvenuto — la riga del costo dice `non calcolabile — listino
assente dal Freeze manifest` invece di stampare una cifra. I token restano
stampati: è da quelli che si ricava il costo il giorno in cui il listino c'è.
Il rapporto **non** inventa una tariffa per riempire la riga, ed è esattamente
il modo in cui il listino di Claude Fable 5 è sopravvissuto per due settimane
al cambio del modello pinnato.

### Come leggerlo

Un file per giornata di controllo, sotto `data/logs/`, con la data **UTC**
nel nome:

```
data/logs/morning-2026-08-17.log
```

Stesse convenzioni del log del rito quotidiano (§5): timestamp UTC su ogni
riga, marcatore `[wrapper]` per le righe del guscio PowerShell, il rapporto
del mattino in un blocco indentato (`--- rapporto del mattino ---`). Cosa
cercare, in ordine:

| Riga | Significato |
| ---- | ----------- |
| `STOP: …` | La giornata di stanotte manca; segue il testo dell'avviso mostrato. |
| `--- rapporto del mattino ---` | La giornata c'è: il rapporto sintetico segue, indentato. |
| `ritmo di spesa: …` | Passo 4 (D5): la cumulata contro il pro-rata, oppure il motivo per cui il passo è stato saltato. |
| `upgrade OTS …` | Solo il lunedì: esito del tentativo di upgrade per ciascuno dei tre file. |
| `ALLARME scritto in …` | Il canale d'allarme è scattato; le righe `motivo:` che seguono sono le stesse che finiscono nel file. |
| `nessun allarme: …` | Nessun motivo rilevato: `ALLARME_<data>.txt` **non** viene creato. |

Exit code: `0` giornata presente, rapporto scritto; `1` giornata assente,
avviso mostrato; `2` precondizione della macchina non soddisfatta (`uv`
fuori dal PATH del task) — lo stesso significato dell'exit code 2 del rito
quotidiano, non del passo 1.

### Registrare il task in Windows Task Scheduler

**Eseguito il 20/08/2026.** Il task si chiama `traderLab — controllo
mattutino` ed è registrato con il comando qui sotto, che è quello realmente
lanciato (non una ricetta descritta e mai eseguita):

```powershell
$repo = "C:\Users\vadim.chilinciuc\git\traderLab"
$nome = "traderLab — controllo mattutino"
$azione = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\morning_check.ps1`"" `
    -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At "07:00"
$impostazioni = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
$principale = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive
Register-ScheduledTask -TaskName $nome -Action $azione -Trigger $trigger `
    -Settings $impostazioni -Principal $principale -Force
```

Stato verificato subito dopo, con `schtasks /query /tn "traderLab — controllo
mattutino" /v /fo LIST`:

| Voce | Valore |
| ---- | ------ |
| Stato | **Pronta / Abilitata** |
| Tipo di pianificazione | Ogni giorno, ogni 1 giorni |
| Ora di avvio | **07:00:00** (ora locale) |
| Data di avvio | 20/08/2026 |
| Avvio in | `C:\Users\vadim.chilinciuc\git\traderLab` |
| Logon | `Interactive` |

Note che valgono quanto per il rito quotidiano (§4):

- *Run only when user is logged on* — l'avviso visibile (`msg.exe` o il
  popup PowerShell) richiede una sessione interattiva per poter comparire; e
  `uv` deve stare nel PATH dell'account con cui gira il task. Il file
  `ALLARME_<data>.txt` invece compare comunque: è il canale che non dipende
  dalla sessione.
- L'ora del trigger è **ora locale**, non UTC, e qui è voluto: a differenza
  del rito quotidiano, il controllo delle 07:00 non ha un vincolo strutturale
  sull'ora — è un promemoria per l'owner, non una decisione point-in-time.
  Non c'è quindi una guardia che lo ferma se l'orario slitta con il cambio
  d'ora, e non serve ancorarlo a UTC: "le 07:00" deve restare un orario
  sensato per aprire il laptop, non un istante di mercato.

> **Stato operativo al 20/08/2026, aggiornato dal rito T2.**
> Il task del controllo mattutino è **abilitato** — `Enable-ScheduledTask`
> eseguito il 20/08 su autorizzazione dell'owner, prossima esecuzione
> 20/08/2026 07:00 locali. Quello del rito quotidiano resta **disabilitato**
> dalla chiusura anticipata di Stagione 0 (`DECISION_LOG.md`, TL-006).
>
> Questa coppia **non produce più un allarme al giorno**. Prima del T2 il
> controllo trovava ogni mattina che «il rito di stanotte NON ha prodotto
> verbali» — che è vero — e usciva 1 scrivendo un `ALLARME_<data>.txt`. Ora
> guarda prima se una stagione è attiva: il manifest di default non è
> pinnato, quindi i verbali notturni **non sono attesi** e la loro assenza non
> è più un motivo d'allarme (passo 1). Il canale resta acceso per tutto il
> resto.
>
> Il controllo può quindi restare acceso da qui al rito del pin, che è la
> ragione per cui è stato riacceso: dev'essere già in funzione — e già
> osservato — quando la prima notte del RUN2 gira davvero. Le due chiusure
> che il T1 aveva lasciato aperte restano disponibili ma non sono più
> necessarie:
>
> ```powershell
> # (a) sospendere il controllo fino al rito del pin
> Disable-ScheduledTask -TaskName "traderLab — controllo mattutino"
> # (b) riabilitare il rito notturno: i due task tornano coerenti
> Enable-ScheduledTask  -TaskName "traderLab — rito quotidiano"
> ```
>
> I due task si accendono insieme: un controllo che verifica un rito spento
> non misura niente, e un rito acceso senza controllo non ha chi lo guardi.

### Cosa non fa

- **Non decide nulla e non scrive nel ledger.** Legge soltanto.
- **Non recupera una giornata saltata.** Se il rito di stanotte non è
  partito, il controllo lo segnala; il recupero non esiste, per lo stesso
  motivo del §6.
- **Non effettua il pin OTS.** L'upgrade del lunedì fa avanzare un timbro
  già esistente da pending a confermato — non crea un nuovo timbro e non
  tocca il pin del modello.
- **Non ferma il rito per motivi di spesa.** Il passo 4 allerta e basta. La
  soglia che ferma è quella dura, `1,5 ×` il preventivo, e sta nel runner
  (§2): le due soglie hanno funzioni diverse e non vanno confuse.
- **Non cancella l'allarme che ha scritto.** `ALLARME_<data>.txt` resta
  finché l'owner non lo rimuove. Un allarme che sparisce da solo è un allarme
  che si può non vedere mai.
