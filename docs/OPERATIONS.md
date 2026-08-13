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

Il codice **1 resta libero di proposito**: è quello che Python usa per
un'eccezione non gestita, e non deve poter essere scambiato per un esito
previsto del rito.

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
   - *Run whether user is logged on or not*.
   - *Run with highest privileges*: **non** serve, lasciarlo spento.
3. **Triggers** → New…
   - *Daily*, ricorrenza 1 giorno.
   - Ora di avvio: **l'ora locale che corrisponde a 00:00 UTC**
     (`DEFAULT_SNAPSHOT_HOUR_UTC`). Il Task Scheduler ragiona in ora locale e
     **non** ha un'opzione UTC: con l'ora legale l'offset cambia due volte
     l'anno, quindi il trigger va ricontrollato a ogni cambio. Se l'ora locale
     non corrisponde più, il rito si ferma da solo con exit code 2 invece di
     costruire uno snapshot sbagliato.
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
