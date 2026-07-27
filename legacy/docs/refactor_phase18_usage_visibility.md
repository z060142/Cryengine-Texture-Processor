# Refactor Phase 18: Usage Visibility

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Make polygon material-slot usage visible in both diagnostics sidecars and the PySide UI.

Phase 17 started extracting true polygon usage from Blender-loaded models. This phase exposes the extracted usage so hazards explain themselves.

## What Changed

- `<model>.material_diagnostics.json` material rows now include:
  - `polygon_count`
  - `used_by_polygons`
  - `mesh_names`
- Flattened sidecar diagnostics now include the same usage fields.
- PySide model import diagnostics now carry the same usage metadata.
- The PySide diagnostics table now has a `Usage` column.

Example UI usage text:

```text
2 polygons (used)
0 polygons (unused)
unknown
```

## Why This Matters

The old hazard message could say a deleted material slot was risky, but the user still had to infer whether geometry was actually using that slot. Now the UI and sidecar can show the exact polygon count when known.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py
```

Offscreen PySide check passed:

```text
probe.fbx [hazard]
Removed
2 polygons (used)
```

## Remaining Work

- Add material rows to the UI even when there are no hazards, so users can inspect all slots.
- Add a sidecar/open-location affordance after model export.
- Started in phase 19: add diagnostics for multi-mesh cases where the same slot index has different material names on different mesh objects.
