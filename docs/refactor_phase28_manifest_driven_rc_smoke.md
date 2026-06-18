# Refactor Phase 28: Manifest-Driven RC Smoke

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Close the full proof loop:

```text
FBX -> Blender material inspector sidecar -> request JSON / .mtl -> RC -> material_report semantic alignment
```

Before this phase, the smoke harness still needed manual `--materials` input even when a `.fbx_material_manifest.json` sidecar existed.

## What Changed

`tools.rc_smoke_test` now supports:

```powershell
--materials-from-manifest
```

When enabled, it discovers:

```text
<asset>.fixture_manifest.json
<asset>.fbx_material_manifest.json
```

and uses that table to build material specs:

```json
[
  {
    "name": "DuplicateSurface",
    "id": 1,
    "sub_index": 0,
    "auto_assigned": false
  },
  {
    "name": "DuplicateSurface.001",
    "id": 2,
    "sub_index": 1,
    "auto_assigned": false
  }
]
```

The smoke bundle also copies the material sidecar next to the copied FBX in the work directory.

## Real RC Probe

Command:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_inspector_duplicate_names\CE_MaterialSlotProbe_DuplicateRequestedNames.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_manifest_driven_duplicate_names" --asset-name "CE_MaterialSlotProbe_DuplicateRequestedNames" --materials-from-manifest
```

Result:

```json
{
  "request_materials": [
    {
      "name": "DuplicateSurface",
      "sub_index": 0
    },
    {
      "name": "DuplicateSurface.001",
      "sub_index": 1
    }
  ],
  "mtl_slots": [
    {
      "slot": 0,
      "name": "DuplicateSurface"
    },
    {
      "slot": 1,
      "name": "DuplicateSurface.001"
    }
  ],
  "fixture_material_semantic_alignment": {
    "manifest_kind": "blender-fbx-material-inspection",
    "ok": true
  }
}
```

## Rule

For RC smoke testing an FBX with a material manifest sidecar, prefer:

```powershell
--materials-from-manifest
```

This prevents the test command from becoming a second, manually maintained material table.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_rc_smoke_test.py tests\test_material_manifest.py tests\test_material_mapping_report.py
```

Real RC probe passed:

```text
DuplicateSurface -> request/MTL/CGF semantic slot 0
DuplicateSurface.001 -> request/MTL/CGF semantic slot 1
fixture_material_semantic_alignment.ok = true
```

## Remaining Work

- Add a UI action or export option that runs the manifest-driven RC smoke path for the selected model.
- Show semantic alignment success/failure in the PySide Model Import tab after RC runs.
- Run the same workflow on larger real assets instead of only controlled probes.
