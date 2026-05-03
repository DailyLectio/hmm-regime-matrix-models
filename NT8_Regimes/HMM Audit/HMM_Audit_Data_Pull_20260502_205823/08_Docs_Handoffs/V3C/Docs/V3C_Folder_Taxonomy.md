# V3C Folder Taxonomy

The HUD reads only the root V3C regime CSV files:

- `C:\Users\Valued Customer\NT8_Regimes\V3C\NQ_Regimes_V3C_Latest.csv`
- `C:\Users\Valued Customer\NT8_Regimes\V3C\ES_Regimes_V3C_Latest.csv`

Operational files are organized as:

- `Keys`: single-click batch files and task installers.
- `Scripts`: Python and PowerShell implementation files.
- `Docs`: guides, checklists, and architecture notes.
- `ModelFeed`: intermediate V3C macro/HMM feed files.
- `LiveWindow`: 100-day V3C-only export slices.
- `Reports`: daily regime reports.
- `History`: EOD archives.
- `Models`: anchored V3C HMM artifacts.

Primary manual commands:

- Startup: `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\V3C_START.bat`
- EOD: `C:\Users\Valued Customer\NT8_Regimes\V3C\Keys\V3C_EOD.bat`
