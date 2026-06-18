# Refactor Phase 19: Slot Name Conflict Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Detect when multiple meshes use the same material slot index with different material names.

RC material ids are slot ids, not names. A name conflict does not necessarily break geometry conversion, but it means the material name cannot be trusted as the slot identity.

## What Changed

- `model_processing.material_slot_usage` now tracks `material_names` per slot.
- Slot usage summaries now include:
  - `material_names`
  - `slot_name_conflict`
- `ModelLoader` carries those fields into material records.
- `material_texture_resolver` preserves those fields into export material data.
- `material_index_assigner` emits a warning diagnostic:

```text
material_slot_name_conflict
```

- Sidecar material rows and flattened diagnostics now include `material_names` and `slot_name_conflict`.
- PySide diagnostics collection carries the same conflict metadata.

## Rule

When a slot has multiple names:

```text
this is a warning that local slot identity and material-name identity may diverge
do not assume material name alone or local mesh slot alone is sufficient
use the later RC probe results before deciding the final mapping
```

The diagnostic is a warning rather than a hazard because the CGF geometry can still be correct if the FBX material names, request sub-indices, and `.mtl` slots remain aligned.

Phase 20 supersedes the earlier conservative assumption that the local slot id is always authoritative. A real multi-mesh RC probe showed that two objects can both use local FBX slot `0`, while RC writes CGF material ids `0` and `1` by matching the FBX material names to request/MTL sub-materials.

## Example

Two meshes:

```text
MeshA slot 0 -> Wood
MeshB slot 0 -> Metal
```

Usage summary:

```json
{
  "polygon_count": 2,
  "mesh_names": ["MeshA", "MeshB"],
  "material_names": ["Metal", "Wood"],
  "slot_name_conflict": true,
  "used_by_polygons": true
}
```

Diagnostic:

```json
{
  "severity": "warning",
  "code": "material_slot_name_conflict",
  "fbx_slot": 0,
  "material_names": ["Metal", "Wood"]
}
```

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_slot_usage.py tests\test_model_loader_material_usage.py tests\test_material_index_assigner.py tests\test_material_texture_resolver.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py
```

## Remaining Work

- Decide how the UI should help resolve name conflicts, for example by choosing the canonical `.mtl` slot name.
- Update the UI wording to explain local slot ids versus global material identities.
- Add swapped-order and duplicate-name probes to stress the Phase 20 material-name mapping rule.
