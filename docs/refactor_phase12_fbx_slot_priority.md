# Refactor Phase 12: FBX Slot Priority

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Apply the phase 11 RC finding to the converter's real material assignment logic.

Phase 11 showed that RC does not rewrite polygon material ids by matching request or `.mtl` material names. CGF `MeshSubset.nMatID` follows the raw FBX polygon material slot id. Therefore, the converter must not let an existing `.mtl` name match reorder materials away from known FBX slots.

## What Changed

- `model_processing.material_index_assigner.assign_material_sub_indices()` now preserves FBX material ids before trying existing `.mtl` name matches.
- Explicit non-auto `sub_index` values still reserve their slots first.
- Existing `.mtl` sub-material names remain available as a fallback when the preferred FBX slot is already occupied.
- JSON request generation and `.mtl` export now share the same corrected priority.

## Current Assignment Priority

The assigner now uses this order:

1. Deleted materials receive `sub_index = -1`.
2. Explicit non-auto `sub_index` values reserve their slots.
3. Auto materials preserve FBX material id as `id - 1` when that slot is free.
4. Auto materials reuse matching existing `.mtl` sub-material names only as fallback.
5. Remaining materials are sorted dummy-first, then by clean name, and fill the first free slots.

## Why This Changed

The old phase 3 rule preferred existing `.mtl` name matches before FBX ids. That made request and `.mtl` agree with each other, but phase 11 proved this is not enough: geometry in the CGF still points at the raw FBX material slot id.

Example:

```text
FBX polygon slot 0 -> Slot_0_Red
FBX polygon slot 1 -> Slot_1_Green

request/MTL reversed by name:
slot 0 -> Slot_1_Green
slot 1 -> Slot_0_Red

observed CGF:
polygon 0 -> nMatID 0
polygon 1 -> nMatID 1
```

If the converter had kept the reversed `.mtl` order, polygon 0 would render with the material in slot 0, which would now be the wrong material.

## Tests Updated

- `tests/test_material_index_assigner.py`
  - FBX material id wins over existing `.mtl` name order for auto materials.
  - Existing `.mtl` name matching is still a fallback when the FBX slot is occupied.
- `tests/test_rc_request_builder.py`
  - Exported JSON preserves FBX slot order even if an existing sibling `.mtl` has names in a different order.
- `tests/test_mtl_exporter.py`
  - Exported `.mtl` preserves FBX slot order over existing sub-material name order.

## Verification

Passed:

```powershell
uv run python -m pytest tests
```

## Remaining Work

- Replace fallback material list order with true source FBX material slot extraction wherever the loader can expose it.
- Add UI/debug visibility for:
  - source FBX material slot
  - assigned `sub_index`
  - assignment reason
  - placeholder `unassigned` slots
- Probe deleted or disabled sub-materials with `sub_index = -1` while the FBX still contains geometry assigned to that slot.
