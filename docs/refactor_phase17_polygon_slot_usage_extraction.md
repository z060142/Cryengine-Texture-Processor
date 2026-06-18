# Refactor Phase 17: Polygon Slot Usage Extraction

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Replace `usage_unknown` material hazards with real polygon material-slot usage when the Blender import path can expose it.

This phase makes deleted/remapped slot diagnostics more precise:

```text
known unused slot -> no hazard
known used slot   -> hazard
unknown usage     -> conservative hazard
```

## What Changed

- Added `model_processing.material_slot_usage`.
- `ModelLoader` now records per-polygon material slots in mesh data.
- `ModelLoader` now builds material records from mesh material slot order instead of `bpy.data.materials`.
- Material records now carry:
  - `polygon_count`
  - `used_by_polygons`
  - `mesh_names`
- `material_texture_resolver` preserves those fields into MTL/export material data.
- Material diagnostics and sidecars can now downgrade deleted-slot warnings when polygon usage proves a slot is unused.

## Bug Fixed

Using `bpy.data.materials` as the material slot source is wrong for FBX slot assignment.

During Blender verification, imported controlled FBX files produced an extra unused global material named `Material` before the real slot materials:

```text
MAT 0 Material 1 ...
MAT 1 Slot_0_Red 1 ...
MAT 2 Slot_1_Green 1 ...
MAT 3 Slot_2_Blue 0 ...
```

That shifted slot ids and would make the converter assign the wrong CryEngine material sub-index.

The fixed path uses each mesh object's material slot order:

```text
MAT 0 Slot_0_Red   1 True
MAT 1 Slot_1_Green 1 True
MAT 2 Slot_2_Blue  1 True
```

For sparse usage:

```text
MAT 0 Slot_0_Red   1 True
MAT 1 Slot_1_Green 0 False
MAT 2 Slot_2_Blue  1 True
```

## Blender Verification

Full fixture:

```powershell
blender --background --factory-startup --python-expr "<ModelLoader full fixture check>"
```

Observed:

```text
Slot_0_Red   polygon_count 1 used_by_polygons True
Slot_1_Green polygon_count 1 used_by_polygons True
Slot_2_Blue  polygon_count 1 used_by_polygons True
```

Sparse fixture:

```text
Slot_0_Red   polygon_count 1 used_by_polygons True
Slot_1_Green polygon_count 0 used_by_polygons False
Slot_2_Blue  polygon_count 1 used_by_polygons True
```

Deleted slot precision check:

```text
sparse slot 1 deleted -> hazard_count 0
full slot 1 deleted   -> hazard_count 1
```

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_model_loader_material_usage.py tests\test_material_slot_usage.py tests\test_material_texture_resolver.py tests\test_material_diagnostics_exporter.py tests\test_material_index_assigner.py
```

Blender checks passed with:

```text
C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe
```

## Remaining Work

- Surface `polygon_count` and `used_by_polygons` in the PySide diagnostics table or a material details panel.
- Persist polygon usage details in sidecar reports for all normal exports.
- Investigate multi-mesh cases where the same material slot index has different material names on different mesh objects.
