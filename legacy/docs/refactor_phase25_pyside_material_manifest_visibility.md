# Refactor Phase 25: PySide Material Manifest Visibility

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Expose FBX material-table evidence in the PySide model import flow.

Phase 24 added a Blender inspector that writes:

```text
<asset>.fbx_material_manifest.json
```

This phase makes the app read that sidecar when importing a model, so users can see the RC-relevant material table instead of only the Blender-loaded material list.

## What Changed

Added shared helpers:

```text
model_processing.material_manifest
```

They handle:

- discovering `.fixture_manifest.json`
- discovering `.fbx_material_manifest.json`
- loading a manifest
- summarizing material/polygon counts
- converting manifest materials into UI table rows

`tools.material_mapping_report` now uses the shared discovery helper instead of its own copy.

`ui_pyside.model_import` now records a `material_manifest` entry per imported model:

```json
{
  "path": "asset.fbx_material_manifest.json",
  "summary": {
    "kind": "blender-fbx-material-inspection",
    "material_count": 2,
    "polygon_count": 2
  },
  "materials": [
    {
      "slot": 0,
      "name": "DuplicateSurface",
      "source": "CE_MultiMeshSlotProbe_0",
      "local_slot": 0
    }
  ]
}
```

The PySide Model Import tab now shows:

```text
Material Table: 2 slots / 2 polygons (blender-fbx-material-inspection)
```

and adds an `RC Material Table` table with:

```text
Slot | Material | Source | Local Slot
```

## Rule

When a sidecar exists, the UI should show the RC-facing material identity table.

That table is different from a user-facing material list:

```text
Stone and Stone.001 are separate RC material identities.
Two mesh-local slot 0 entries may map to different global material table slots.
```

## Limits

- The UI reads existing sidecars but does not yet run the Blender inspector automatically.
- A missing sidecar shows `not found`; this is not an error yet.
- The table is visibility-only in this phase. It does not block export or rewrite request/MTL ordering by itself.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_manifest.py tests\test_material_mapping_report.py tests\test_pyside_model_import_diagnostics.py
uv run python -m compileall ui_pyside model_processing tools tests
```

## Remaining Work

- Build on Phase 26's PySide action by using generated manifests in request JSON and `.mtl` generation.
- Surface material semantic alignment failures directly in the Model Import tab.
- Use the manifest table as the source of truth when building request JSON and `.mtl` from imported FBX models.
