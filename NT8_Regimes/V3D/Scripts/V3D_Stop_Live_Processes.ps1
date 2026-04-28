$ErrorActionPreference = "SilentlyContinue"

$patterns = @(
    "MacroRegimeBuilder_V3D.py",
    "HMMWatchdog_V3D.py",
    "RegimeSupervisor_V3D.py",
    "Start_V3D_StageA_Macro.bat",
    "Start_V3D_StageB_HMM.bat",
    "Start_V3D_StageC_Supervisor.bat"
)

$matches = Get-CimInstance Win32_Process | Where-Object {
    $cmd = $_.CommandLine
    if (-not $cmd) { return $false }
    foreach ($pattern in $patterns) {
        if ($cmd -like "*$pattern*") { return $true }
    }
    return $false
}

if (-not $matches) {
    Write-Host "No V3D live pipeline processes found."
    exit 0
}

foreach ($proc in $matches) {
    Write-Host ("Stopping PID {0}: {1}" -f $proc.ProcessId, $proc.Name)
    Stop-Process -Id $proc.ProcessId -Force
}

Write-Host "V3D live pipeline stop request complete."
