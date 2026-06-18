# Refactor Phase 3: Material Sub-Index Assignment

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Current Status

This phase documented the first material sub-index implementation. Phase 11 later proved that RC keeps CGF polygon material ids aligned to raw FBX material slots, even when request/MTL material names are reordered. Phase 12 supersedes the old priority rule: known FBX material slots now win over existing `.mtl` name matches.

## Goal

Make the converter stop treating material list order as the CryEngine material id. CryEngine's FBX import request needs `materials[].sub_index` to match the final `.mtl` sub-material slot. If this drifts, a converted model can point polygons at the wrong material.

This phase implements the editor-style assignment rules that were extracted from CryEngine's Mesh Importer behavior.

## What Changed

- Added `model_processing/material_index_assigner.py`.
- `output_formats/rc_request_builder.py` now uses the assignment helper for request `materials`.
- `output_formats/json_exporter.py` reads an existing sibling `.mtl` and passes its sub-material order into the request builder.
- `output_formats/mtl_exporter.py` now writes sub-materials according to assigned `sub_index`.
- `model_processing/model_loader.py` now stores `id = index + 1` and `index = index` for loaded Blender materials as a usable fallback material id.
- `model_processing/material_texture_resolver.py` preserves material metadata such as id, explicit sub-index, auto flag, deletion flag, and dummy flag when preparing MTL data.

## Assignment Rules Implemented

The assigner produces one record per unique clean material name.

Rules:

1. Skip known placeholder materials such as `Material` and `Dots Stroke`.
2. Collapse Blender duplicate suffixes such as `.001`.
3. Deleted materials receive `sub_index = -1`.
4. Explicit non-auto `sub_index` values reserve their slots.
5. Auto-assigned materials preserve FBX material id as `id - 1` when that slot is free.
6. If the FBX slot is unavailable, try to match an existing `.mtl` sub-material by name as fallback.
7. Remaining materials are sorted dummy-first, then by clean name, and placed in the first free slot.

## MTL Slot Behavior

The MTL exporter now writes material children by `sub_index`.

Example input:

```python
[
    {"name": "First", "id": 1},
    {"name": "Third", "id": 3},
]
```

Generated sub-material names:

```text
First
unassigned
Third
```

That gap is intentional. It preserves the material id relationship instead of silently compressing slots.

## JSON Behavior

When exporting `chair.fbx`, `export_json()` looks for a sibling `chair.mtl`, but known FBX slots remain authoritative.

If the MTL contains:

```text
0: collision_proxy
1: Chair
```

The generated request preserves FBX/list slot ids:

```json
[
  {"name": "Chair", "physicalize": "no_collide", "sub_index": 0},
  {"name": "collision_proxy", "physicalize": "proxy_only", "sub_index": 2}
]
```

This keeps request/MTL slots aligned to the source FBX material ids that RC writes into CGF `MeshSubset.nMatID`.

## Tests Added

- `tests/test_material_index_assigner.py`
- `tests/test_mtl_exporter.py`
- Additional MTL-alignment coverage in `tests/test_rc_request_builder.py`

Covered cases:

- parse `.mtl` sub-material names by child order
- FBX material id wins over existing MTL name matches for auto materials
- existing MTL name match remains a fallback when the FBX slot is occupied
- explicit non-auto sub-index reserves a slot
- remaining materials fill free slots deterministically
- deleted materials get `sub_index = -1`
- Blender duplicate suffixes collapse
- MTL export fills holes with `unassigned`
- JSON request preserves FBX slot order over existing MTL name order

## Verification

Passed:

```powershell
python -m pytest tests
python -m compileall model_processing output_formats tests
```

## Remaining Work

- Replace the fallback `id = index + 1` with the true FBX material id once the Blender/FBX extraction path exposes it.
- Add UI controls for explicitly deleting a material or pinning a non-auto sub-index.
- Surface assignment reasons in the UI for debugging material-slot mismatches.
- Run a generated FBX + MTL + request through real `rc.exe` and inspect the resulting CGF material table.
- Revisit physicalize consistency: CryEngine forces materials sharing the same sub-index to share the same physicalize setting.
