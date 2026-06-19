# Phase 106 - PySide Unassigned Diagnostics

## Goal

Carry RC material report unassigned placeholder diagnostics into the PySide model import UI.

This makes `unassigned` visible as an expected CryEngine slot condition instead of leaving users to inspect the JSON report manually.

## Implementation

Updated `ui_pyside/model_import.py`:

- `run_model_material_rc_smoke()` now reads `cgf_material_id_alignment.unassigned_slot_diagnostics`
- `rc_material_smoke_summary_text()` now includes unassigned status:
  - `unassigned ok`
  - `used unassigned`
- `collect_model_material_diagnostics()` now converts RC unassigned diagnostics into rows for the Material Slot Diagnostics table
- `_run_rc_material_smoke()` refreshes diagnostics after RC smoke completes

Severity mapping:

- `gap_unassigned_placeholder` -> `info`
- `trailing_unassigned_placeholder` -> `info`
- `used_unassigned_material` -> `hazard`

## Car Report Check

Input report:

- `docs/phase105_unassigned_placeholder_diagnostics_report.json`

Smoke summary produced by the UI helper:

```text
passed / CGF ids ok / unassigned ok
```

Diagnostics produced for the car report:

```json
[
  {
    "severity": "info",
    "code": "trailing_unassigned_placeholder",
    "material": "<unassigned>",
    "fbx_slot": 16,
    "sub_index": 16,
    "request_name": "<unassigned>",
    "mtl_slot_name": "<unassigned>",
    "used_by_cgf": false,
    "max_used_material_id": 15,
    "message": "Trailing unassigned material slot is an unused RC placeholder."
  }
]
```

## Verification

```powershell
uv run python -m pytest tests\test_pyside_model_import_diagnostics.py
uv run python -m pytest tests
```

Targeted result:

- `24 passed`
