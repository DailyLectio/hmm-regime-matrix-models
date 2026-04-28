param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'

$modelSource = 'C:\Users\Valued Customer\NT8_Regimes'
$nt8Source = 'C:\Users\Valued Customer\Documents\NinjaTrader 8'
$keywords = '(V3B|V3C|V3D|Regime|HMM|TradeLog|Matrix|LiveDataExporter|ValueAreaExporter)'

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Parent,
        [Parameter(Mandatory = $true)][string]$Child
    )

    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\') + '\'
    $childFull = [System.IO.Path]::GetFullPath($Child).TrimEnd('\') + '\'
    if (-not $childFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify path outside repo: $Child"
    }
}

function Reset-MirrorDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-ChildPath -Parent $RepoRoot -Child $Path
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Invoke-RoboCopy {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [string[]]$ExcludedDirs = @(),
        [string[]]$ExcludedFiles = @()
    )

    Assert-ChildPath -Parent $RepoRoot -Child $Destination
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    $args = @(
        $Source,
        $Destination,
        '/MIR',
        '/R:1',
        '/W:1',
        '/NFL',
        '/NDL',
        '/NJH',
        '/NJS',
        '/NP'
    )

    if ($ExcludedDirs.Count -gt 0) {
        $args += '/XD'
        $args += $ExcludedDirs
    }

    if ($ExcludedFiles.Count -gt 0) {
        $args += '/XF'
        $args += $ExcludedFiles
    }

    & robocopy @args | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "Robocopy failed from $Source to $Destination with exit code $LASTEXITCODE"
    }
}

function Copy-MatchingFiles {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$DestinationRoot,
        [Parameter(Mandatory = $true)][string[]]$Extensions
    )

    Reset-MirrorDirectory -Path $DestinationRoot
    if (-not (Test-Path -LiteralPath $SourceRoot)) {
        return
    }

    $sourceFull = [System.IO.Path]::GetFullPath($SourceRoot).TrimEnd('\') + '\'
    Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -Force |
        Where-Object {
            $Extensions -contains $_.Extension.ToLowerInvariant() -and
            ($_.Name -match $keywords -or $_.DirectoryName -match $keywords)
        } |
        ForEach-Object {
            $relative = $_.FullName.Substring($sourceFull.Length)
            $dest = Join-Path $DestinationRoot $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
        }
}

if (-not (Test-Path -LiteralPath $modelSource)) {
    throw "Missing model source folder: $modelSource"
}

if (-not (Test-Path -LiteralPath $nt8Source)) {
    throw "Missing NinjaTrader source folder: $nt8Source"
}

$modelDestination = Join-Path $RepoRoot 'NT8_Regimes'
Reset-MirrorDirectory -Path $modelDestination

$excludedDirs = @(
    '.git',
    '.venv',
    'venv',
    'env',
    '__pycache__',
    '.pytest_cache',
    'Exports',
    'Incoming',
    'Active',
    'Backtest',
    'Strategy Analyzer',
    'Archive',
    'Archives',
    'Logs',
    'LiveWindow',
    'Reports',
    '*_files',
    (Join-Path $modelSource 'MacroRegime\data\raw')
)

$excludedFiles = @(
    '*.pyc',
    '*.pyo',
    '*.log',
    '*.tmp',
    '*.temp',
    '*.bak',
    '*.backup',
    '*.zip',
    '*.lnk',
    '*.html',
    '.env',
    '.env.*',
    '*.key',
    '*.pem',
    '*.pfx',
    '*.crt',
    'secrets.*',
    'credentials.*',
    'token.*',
    '*.Last.txt',
    '*_1min_export.txt',
    '*_Continuous_*_Last.txt',
    '*_Continuous_*.Last.txt',
    '*_Stitched_*.txt',
    '*_Macro_Regimes*.csv',
    '*_Regimes_HMM*.csv',
    '*_Regimes_V3C.csv',
    '*_HMM_Regimes*.csv',
    '*_RegimeMatrix_History*.csv',
    '*_RegimeMatrix_Full*.csv',
    'Macro_Regimes.csv',
    'Footprint_Export.csv',
    'V3C_V3D_*Comparison.csv',
    '*.parquet',
    '*.feather',
    '*.h5',
    '*.sqlite',
    '*.db',
    'HUD_Override_Log.csv',
    'V3D_TradeLog.csv',
    '*Trade_Log*.csv'
)

Invoke-RoboCopy -Source $modelSource -Destination $modelDestination -ExcludedDirs $excludedDirs -ExcludedFiles $excludedFiles

Copy-MatchingFiles `
    -SourceRoot (Join-Path $nt8Source 'bin\Custom\Indicators') `
    -DestinationRoot (Join-Path $RepoRoot 'NinjaTrader8\bin\Custom\Indicators') `
    -Extensions @('.cs')

Copy-MatchingFiles `
    -SourceRoot (Join-Path $nt8Source 'bin\Custom\Strategies') `
    -DestinationRoot (Join-Path $RepoRoot 'NinjaTrader8\bin\Custom\Strategies') `
    -Extensions @('.cs')

Copy-MatchingFiles `
    -SourceRoot (Join-Path $nt8Source 'templates\Strategy') `
    -DestinationRoot (Join-Path $RepoRoot 'NinjaTrader8\templates\Strategy') `
    -Extensions @('.xml')

Write-Host "Backup mirror refreshed at $RepoRoot"
