param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$RemoteName = 'origin',
    [string]$RemoteUrl = 'https://github.com/DailyLectio/hmm-regime-matrix-models.git',
    [string]$Branch = 'main'
)

$ErrorActionPreference = 'Stop'
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'Never'

$logDir = Join-Path $env:LOCALAPPDATA 'hmm-regime-matrix-backup'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir 'backup.log'

function Write-BackupLog {
    param([string]$Message)
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -LiteralPath $logFile -Value $line
}

try {
    Write-BackupLog 'Starting backup.'
    & (Join-Path $PSScriptRoot 'sync_backup.ps1') -RepoRoot $RepoRoot

    Push-Location $RepoRoot
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.git'))) {
            git init | Out-Null
            git branch -M $Branch | Out-Null
        }

        $existingRemote = git remote get-url $RemoteName 2>$null
        if (-not $existingRemote) {
            git remote add $RemoteName $RemoteUrl
        }

        git add --all
        git diff --cached --quiet
        $hasStagedChanges = ($LASTEXITCODE -ne 0)

        if ($hasStagedChanges) {
            $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
            git commit -m "Automated HMM Regime Matrix backup $stamp" | Out-Null
            Write-BackupLog 'Backup committed.'
        }
        else {
            Write-BackupLog 'No changes to commit.'
        }

        git rev-parse --verify HEAD | Out-Null
        if ($LASTEXITCODE -eq 0) {
            git push -u $RemoteName $Branch | Out-Null
            Write-BackupLog 'Backup pushed.'
        }
    }
    finally {
        Pop-Location
    }
}
catch {
    Write-BackupLog ("ERROR: " + $_.Exception.Message)
    throw
}
