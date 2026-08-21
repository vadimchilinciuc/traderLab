# Rito quotidiano del Trader Lab — wrapper per Windows Task Scheduler.
#
# Il wrapper e' volutamente sottile: non contiene logica di dominio. Decide
# soltanto se le precondizioni della MACCHINA sono soddisfatte (repo, uv,
# cartella dei log) e poi cede il controllo a scripts/run_daily.py, che e'
# codice Python testato. Tutto cio' che riguarda giorni mancati, snapshot e
# decisioni sta li', non qui: uno script di shell non e' testabile senza
# scheduler, e una regola non testata per il Lab non esiste.
#
# Exit code (gli stessi di scripts/run_daily.py, piu' il 2 delle precondizioni):
#   0  giornata completata
#   2  precondizione non soddisfatta — il rito non e' partito
#   3  costruzione dello snapshot fallita
#   4  esecuzione delle decisioni fallita
#   5  la giornata di oggi e' gia' nel ledger (write-once)
#   6  marcatura dei giorni mancati fallita
#
# Registrazione nel Task Scheduler: vedi docs/OPERATIONS.md. Il task NON va
# registrato da questo script.

[CmdletBinding()]
param(
    # Usa il modello pinnato invece del MockLLM. Richiede ANTHROPIC_API_KEY in
    # ambiente e TRADERLAB_ALLOW_LIVE_API=1.
    [switch]$Live,

    # Salta il controllo sull'ora UTC. Serve per le prove a mano: il task
    # schedulato deve girare all'ora configurata, non a un'ora qualsiasi.
    [switch]$IgnoreConfiguredHour,

    # Ledger dei verbali del SEGMENTO in corso. Il RUN2 gira su
    # 'claude-opus-5': un suo verbale in coda a season0.jsonl, che porta i 18
    # verbali di 'claude-fable-5', mescolerebbe due model string nella stessa
    # catena append-only (CLAUDE.md sez. 9 e 10).
    [string]$Ledger = "data/ledger/season0_run2.jsonl",

    # Manifest pinnato della stagione. Va passato ESPLICITAMENTE: senza questo
    # flag run_day.py cade sul default di arena/config.py, che punta ancora al
    # manifest della Stagione 0 - ed e' la ragione per cui la notte del
    # 2026-08-21 il rito e' uscito 4 senza poter raggiungere il pin del RUN2
    # (DIAGNOSI_G1, reperto A).
    [string]$Manifest = "manifests/trader_v1_run2_freeze_manifest.json",

    [string]$OpsLedger = "data/ledger/ops.jsonl",
    [string]$LogDir = "data/logs"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$LogRoot = Join-Path $RepoRoot $LogDir
if (-not (Test-Path $LogRoot)) {
    New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
}

$Today = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd")
$LogFile = Join-Path $LogRoot "daily-$Today.log"

function Write-RitualLine {
    param([string]$Message)
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $line = "$stamp [wrapper] $Message"
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    Write-Output $line
}

Write-RitualLine "avvio del rito da $RepoRoot"

# -- precondizioni della macchina ------------------------------------------

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($null -eq $uv) {
    Write-RitualLine "STOP: 'uv' non e' nel PATH del contesto in cui gira il task"
    exit 2
}

if ($Live) {
    if ($env:TRADERLAB_ALLOW_LIVE_API -ne "1") {
        Write-RitualLine "STOP: -Live richiede TRADERLAB_ALLOW_LIVE_API=1"
        exit 2
    }
    if ([string]::IsNullOrWhiteSpace($env:ANTHROPIC_API_KEY)) {
        # Si verifica la PRESENZA della chiave, mai il valore: non va letta,
        # non va stampata, non va scritta nel log.
        Write-RitualLine "STOP: ANTHROPIC_API_KEY assente dall'ambiente del task"
        exit 2
    }
    Write-RitualLine "modalita' LIVE: chiave presente in ambiente"
} else {
    Write-RitualLine "modalita' mock: nessuna chiamata al modello"
}

# -- il rito vero e proprio -------------------------------------------------

$arguments = @(
    "run", "python", "scripts/run_daily.py",
    "--ledger", $Ledger,
    "--manifest", $Manifest,
    "--ops-ledger", $OpsLedger,
    "--log-dir", $LogDir
)
if ($Live) { $arguments += "--live" }
if (-not $IgnoreConfiguredHour) { $arguments += "--require-configured-hour" }

Write-RitualLine ("comando: uv " + ($arguments -join " "))

& uv @arguments
$code = $LASTEXITCODE

Write-RitualLine "scripts/run_daily.py ha restituito $code"
Write-RitualLine "log della giornata: $LogFile"
exit $code
