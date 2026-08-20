# Controllo mattutino del Trader Lab — wrapper per Windows Task Scheduler.
#
# Il wrapper e' volutamente sottile: non contiene logica di dominio, esattamente
# come scripts/run_daily.ps1. Verifica solo le precondizioni della MACCHINA
# (repo, uv) e cede il controllo a scripts/morning_check.py, che e' codice
# Python testato. Tutto cio' che riguarda la giornata di stanotte, l'avviso e
# l'upgrade OTS settimanale sta li', non qui.
#
# Exit code (gli stessi di scripts/morning_check.py, piu' il 2 delle precondizioni):
#   0  la giornata di stanotte e' nel ledger, rapporto scritto
#   1  la giornata di stanotte NON e' nel ledger, avviso mostrato
#   2  precondizione non soddisfatta — il controllo non e' partito
#
# Canale d'allarme (verbale RUN2 §A.6, decisione D3): su exit != 0 o su
# anomalia rilevata compare ALLARME_<data>.txt alla radice del repo, con il
# motivo dentro. Lo scrive scripts/morning_check.py; questo wrapper lo scrive
# solo nel caso in cui il controllo non parte affatto.
#
# Registrazione nel Task Scheduler: vedi docs/OPERATIONS.md. Il task NON va
# registrato da questo script.

[CmdletBinding()]
param(
    [string]$Ledger = "data/ledger/season0.jsonl",
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
$LogFile = Join-Path $LogRoot "morning-$Today.log"

function Write-CheckLine {
    param([string]$Message)
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $line = "$stamp [wrapper] $Message"
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    Write-Output $line
}

Write-CheckLine "avvio del controllo mattutino da $RepoRoot"

# -- precondizioni della macchina ------------------------------------------

# Canale d'allarme: se il controllo non parte nemmeno, il file lo scrive il
# wrapper. Altrimenti l'unico caso in cui il controllo NON puo' avvisare
# sarebbe anche l'unico in cui non lascia traccia.
$AlarmFile = Join-Path $RepoRoot "ALLARME_$Today.txt"

function Write-WrapperAlarm {
    param([string]$Reason)
    $body = @(
        "ALLARME traderLab - $Today",
        "",
        "Il controllo del mattino non e' partito:",
        "",
        "  1. $Reason",
        "",
        "Log della passata : $LogFile",
        "",
        "Questo file e' gitignorato: cancellarlo dopo averlo letto e' la",
        "chiusura prevista. Nessun automatismo lo rimuove."
    )
    Set-Content -Path $AlarmFile -Value $body -Encoding utf8
    Write-CheckLine "ALLARME scritto in $AlarmFile"
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($null -eq $uv) {
    Write-CheckLine "STOP: 'uv' non e' nel PATH del contesto in cui gira il task"
    Write-WrapperAlarm "'uv' non e' nel PATH del contesto in cui gira il task (exit 2)"
    exit 2
}

# -- il controllo vero e proprio --------------------------------------------

$arguments = @(
    "run", "python", "scripts/morning_check.py",
    "--ledger", $Ledger,
    "--ops-ledger", $OpsLedger,
    "--log-dir", $LogDir
)

Write-CheckLine ("comando: uv " + ($arguments -join " "))

& uv @arguments
$code = $LASTEXITCODE

Write-CheckLine "scripts/morning_check.py ha restituito $code"
Write-CheckLine "log del controllo: $LogFile"
# Il file d'allarme per exit != 0 e per le anomalie lo scrive lo script Python,
# che conosce i motivi. Qui si annota soltanto se e' comparso.
if (Test-Path $AlarmFile) {
    Write-CheckLine "ALLARME presente: $AlarmFile"
} else {
    Write-CheckLine "nessun ALLARME per oggi"
}
exit $code
