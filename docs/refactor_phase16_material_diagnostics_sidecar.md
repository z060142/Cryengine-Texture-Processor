# Refactor Phase 16: Material Diagnostics Sidecar

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Persist material-slot diagnostics next to normal export artifacts without adding non-RC fields to the RC request JSON.

Phase 14 made diagnostics available in code and smoke reports. Phase 15 surfaced them in the PySide model import UI. This phase writes a durable sidecar file during normal model export.

## What Changed

- Added `output_formats.material_diagnostics_exporter`.
- Normal MTL export now writes:

```text
<model>.material_diagnostics.json
```

- Normal FBX+JSON export also writes the same sidecar next to the generated `.fbx` and `.json`.
- Sidecar generation uses the same `assign_material_sub_indices()` logic as JSON and MTL export.
- Existing sibling `.mtl` sub-material order is passed into the sidecar writer, so fallback assignments match the actual exporter behavior.

## Sidecar Shape

Example:

```json
{
  "source_model": "asset.fbx",
  "artifact_kind": "fbx_json",
  "summary": {
    "material_count": 2,
    "diagnostic_count": 1,
    "hazard_count": 1
  },
  "materials": [
    {
      "name": "Removed",
      "original_name": "Removed",
      "source_order": 1,
      "fbx_material_id": 2,
      "fbx_slot": 1,
      "sub_index": -1,
      "assignment_reason": "deleted",
      "deleted": true,
      "diagnostics": []
    }
  ],
  "diagnostics": [
    {
      "severity": "hazard",
      "code": "deleted_known_fbx_slot_usage_unknown",
      "material": "Removed",
      "fbx_slot": 1,
      "sub_index": -1
    }
  ]
}
```

The sidecar is intentionally separate from the RC request JSON:

```text
asset.json                    -> RC input
asset.material_diagnostics.json -> converter/debug/UI/plugin evidence
```

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_diagnostics_exporter.py tests\test_material_index_assigner.py tests\test_rc_smoke_test.py
```

## Remaining Work

- Add a UI affordance to open or reveal the sidecar after export.
- Done in phase 17: add true polygon material-slot usage extraction for Blender-loaded models so diagnostics can distinguish unused deleted slots from dangerous deleted used slots.
- Use the sidecar schema as the handoff format for a future Blender add-on.
