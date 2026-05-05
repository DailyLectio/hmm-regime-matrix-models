# V3D Folder Taxonomy

The V3D folder now mirrors the V3C operating layout.

## Root V3D Folder

Live model output stays in the root because the V3D pipeline and HUD expect these files:

- `NQ_RegimeMatrix_Latest.csv`
- `ES_RegimeMatrix_Latest.csv`
- `NQ_Macro_Regimes_V3D.csv`
- `ES_Macro_Regimes_V3D.csv`
- `NQ_HMM_Regimes_V3D.csv`
- `ES_HMM_Regimes_V3D.csv`
- `HMMWatchdog_V3D_state.json`

## Keys

`C:\Users\Valued Customer\NT8_Regimes\V3D\Keys`

Manual command files live here.

- `V3D_START.bat`: one-click morning startup.
- `V3D_EOD.bat`: one-click end-of-day shutdown and report.
- `V3D_PreMarket_Master.bat`: full morning orchestrator.
- `V3D_EndOfDay_Shutdown.bat`: full evening closeout.
- `Start_V3D_StageA_Macro.bat`: starts Macro only.
- `Start_V3D_StageB_HMM.bat`: starts HMM only.
- `Start_V3D_StageC_Supervisor.bat`: starts Supervisor only.

## Scripts

`C:\Users\Valued Customer\NT8_Regimes\V3D\Scripts`

Python and PowerShell implementation files live here.

## Docs

`C:\Users\Valued Customer\NT8_Regimes\V3D\Docs`

Operator guides, checklists, and workflow notes live here.

## Reports

`C:\Users\Valued Customer\NT8_Regimes\V3D\Reports`

Daily V3D reports are written here.

## History

`C:\Users\Valued Customer\NT8_Regimes\V3D\History`

Continuous V3D history stays here. End-of-day snapshots go to `History\Archives`.
