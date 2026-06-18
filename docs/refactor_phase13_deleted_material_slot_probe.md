# Refactor Phase 13: Deleted Material Slot Probe

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Test what RC does when the request marks a material as deleted with `sub_index = -1`, while the source FBX geometry still uses that material slot.

This matters for the converter and Blender add-on UI. If deleted request materials remapped or removed geometry slots, the tool could safely hide or delete material slots. If RC keeps the geometry slot id, deletion is only safe when the source geometry no longer references that slot.

## Code Changes

`tools.rc_smoke_test` now accepts material specs in the `--materials` argument:

```text
Name
Name:deleted
Name:-1
Name:4
```

Examples:

```powershell
--materials "Slot_0_Red,Slot_1_Green:deleted,Slot_2_Blue"
```

The old comma-separated name list still works:

```powershell
--materials "Bark,Leaves"
```

## Fixture

The controlled Blender fixture was generated with two triangles:

```text
polygon 0 -> FBX material slot 0 -> Slot_0_Red
polygon 1 -> FBX material slot 1 -> Slot_1_Green
```

## Commands

Generate the controlled FBX:

```powershell
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_deleted" --asset-name "CE_MaterialSlotProbe_Deleted" --polygon-slots "0,1"
```

Run RC with slot 1 marked deleted in the request:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_deleted\CE_MaterialSlotProbe_Deleted.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_deleted" --asset-name "CE_MaterialSlotProbe_Deleted" --materials "Slot_0_Red,Slot_1_Green:deleted,Slot_2_Blue"
```

Verify polygon-level material ids:

```powershell
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_deleted\CE_MaterialSlotProbe_Deleted.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_deleted\CE_MaterialSlotProbe_Deleted.material_report.json" --check-polygons
```

## Evidence

The generated request contains:

```text
Slot_0_Red   sub_index 0
Slot_1_Green sub_index -1
Slot_2_Blue  sub_index 2
```

The generated `.mtl` contains:

```text
slot 0 Slot_0_Red
slot 1 unassigned
slot 2 Slot_2_Blue
```

The CGF subset ids, mapped back to source polygons by center x, are:

```text
polygon 0 -> CGF MeshSubset.nMatID 0
polygon 1 -> CGF MeshSubset.nMatID 1
```

The material report correctly flags that CGF material id `1` is not present as a non-negative request sub-index:

```text
material_id 1 -> in_request false, in_mtl true, mtl_slot_name unassigned
```

## Rule Learned

`sub_index = -1` does not remove or remap a geometry material slot that is still used by the FBX.

```text
FBX polygon material slot 1
request material Slot_1_Green sub_index -1
MTL slot 1 unassigned
CGF MeshSubset.nMatID 1
```

Therefore, deleted request materials are only safe when the source geometry does not reference that FBX material slot. For conversion tooling, a deleted/disabled material slot should be treated as a hazard unless polygon usage is known.

The safer default for the converter is:

```text
Preserve the FBX slot and write an explicit placeholder material instead of deleting the slot.
```

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_rc_smoke_test.py
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_deleted" --asset-name "CE_MaterialSlotProbe_Deleted" --polygon-slots "0,1"
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_deleted\CE_MaterialSlotProbe_Deleted.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_deleted" --asset-name "CE_MaterialSlotProbe_Deleted" --materials "Slot_0_Red,Slot_1_Green:deleted,Slot_2_Blue"
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_deleted\CE_MaterialSlotProbe_Deleted.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_deleted\CE_MaterialSlotProbe_Deleted.material_report.json" --check-polygons
```

## Remaining Work

- Add a converter-side diagnostic when a deleted material has a known FBX slot id and polygon usage is unknown.
- Add UI visibility for slot hazards: deleted, placeholder, missing request slot, and missing `.mtl` slot.
- Extract true polygon-to-material-slot usage from Blender/FBX so deleted slots can be allowed only when truly unused.
