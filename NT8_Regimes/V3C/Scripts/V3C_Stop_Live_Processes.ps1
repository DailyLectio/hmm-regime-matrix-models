$ErrorActionPreference = "SilentlyContinue"

$patterns = @(
    "V3C_ModelFeed_Watchdog.py",
    "RegimeMatrixSupervisor.py",
    "Start_V3C_ModelFeed_Watchdog.bat",
    "Start_RegimeMatrixSupervisor.bat"
)

$all = Get-CimInstance Win32_Process
$targets = @{}

foreach ($pattern in $patterns) {
    $all |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$pattern*" } |
        ForEach-Object { $targets[$_.ProcessId] = $_ }
}

$changed = $true
while ($changed) {
    $changed = $false
    foreach ($proc in $all) {
        if ($targets.ContainsKey($proc.ParentProcessId) -and -not $targets.ContainsKey($proc.ProcessId)) {
            $targets[$proc.ProcessId] = $proc
            $changed = $true
        }
    }
}

$targets.Values |
    Sort-Object ProcessId -Descending |
    ForEach-Object {
        Write-Host ("Stopping V3C PID {0}: {1}" -f $_.ProcessId, $_.CommandLine)
        Stop-Process -Id $_.ProcessId -Force
    }

if ($targets.Count -eq 0) {
    Write-Host "No V3C live Python/batch processes found."
}
