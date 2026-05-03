param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$RemoteName = 'origin',
    [string]$RemoteUrl = 'https://github.com/DailyLectio/hmm-regime-matrix-models.git',
    [string]$Branch = 'main'
)

$ErrorActionPreference = 'Stop'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}
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

function Invoke-GitQuiet {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)

    $oldErrorActionPreference = $ErrorActionPreference
    try {
        $script:ErrorActionPreference = 'Continue'
        & git @GitArgs 1>$null 2>$null
        $exitCode = $LASTEXITCODE
    }
    finally {
        $script:ErrorActionPreference = $oldErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "git $($GitArgs -join ' ') failed with exit code $exitCode"
    }
}

function Invoke-GitQuietExitCode {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)

    $oldErrorActionPreference = $ErrorActionPreference
    try {
        $script:ErrorActionPreference = 'Continue'
        & git @GitArgs 1>$null 2>$null
        return $LASTEXITCODE
    }
    finally {
        $script:ErrorActionPreference = $oldErrorActionPreference
    }
}

try {
    Write-BackupLog 'Starting backup.'
    & (Join-Path $PSScriptRoot 'sync_backup.ps1') -RepoRoot $RepoRoot

    Push-Location $RepoRoot
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.git'))) {
            Invoke-GitQuiet -GitArgs @('init')
            Invoke-GitQuiet -GitArgs @('branch', '-M', $Branch)
        }

        $existingRemote = git remote get-url $RemoteName 2>$null
        if (-not $existingRemote) {
            Invoke-GitQuiet -GitArgs @('remote', 'add', $RemoteName, $RemoteUrl)
        }

        Invoke-GitQuiet -GitArgs @('add', '--all')
        $diffExitCode = Invoke-GitQuietExitCode -GitArgs @('diff', '--cached', '--quiet')
        if ($diffExitCode -ne 0 -and $diffExitCode -ne 1) {
            throw "git diff --cached --quiet failed with exit code $diffExitCode"
        }
        $hasStagedChanges = ($diffExitCode -eq 1)

        if ($hasStagedChanges) {
            $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
            Invoke-GitQuiet -GitArgs @('commit', '-m', "Automated HMM Regime Matrix backup $stamp")
            Write-BackupLog 'Backup committed.'
        }
        else {
            Write-BackupLog 'No changes to commit.'
        }

        $hasHead = Invoke-GitQuietExitCode -GitArgs @('rev-parse', '--verify', 'HEAD')
        if ($hasHead -eq 0) {
            Invoke-GitQuiet -GitArgs @('push', '-u', $RemoteName, $Branch)
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
