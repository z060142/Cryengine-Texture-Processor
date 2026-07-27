# Refactor Phase 11: Request Name Remap Probe

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Test whether RC rewrites CGF polygon material ids by matching request/MTL material names, or whether it preserves the raw FBX polygon material slot ids.

This matters because a converter or Blender add-on must know whether it can reorder `.mtl` sub-materials by name, or whether the `.mtl` slot order must stay aligned to the source FBX material slots.

## Fixture

The controlled Blender fixture was generated with two independent triangles:

```text
polygon 0 -> FBX material slot 0 -> Slot_0_Red
polygon 1 -> FBX material slot 1 -> Slot_1_Green
```

Each triangle has a stable center:

```text
polygon 0 center x ~= 0.0
polygon 1 center x ~= 3.0
```

The verifier can therefore map each CGF `MeshSubset` back to a source polygon by reading the subset center.

## Commands

Generate the source FBX fixture:

```powershell
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_remap" --asset-name "CE_MaterialSlotProbe_Remap" --polygon-slots "0,1"
```

Run RC with reversed request/MTL material order:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_remap\CE_MaterialSlotProbe_Remap.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_remap" --asset-name "CE_MaterialSlotProbe_Remap" --materials "Slot_1_Green,Slot_0_Red,Slot_2_Blue"
```

Verify polygon-level material ids:

```powershell
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_remap\CE_MaterialSlotProbe_Remap.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_remap\CE_MaterialSlotProbe_Remap.material_report.json" --check-polygons
```

## Evidence

The fixture manifest says:

```text
polygon 0 material_slot 0 material_name Slot_0_Red
polygon 1 material_slot 1 material_name Slot_1_Green
```

The generated request/MTL order was intentionally reversed:

```text
request order 0 name Slot_1_Green sub_index 0
request order 1 name Slot_0_Red   sub_index 1
request order 2 name Slot_2_Blue  sub_index 2
```

The generated `.mtl` used the same reversed slots:

```text
mtl slot 0 Slot_1_Green
mtl slot 1 Slot_0_Red
mtl slot 2 Slot_2_Blue
```

The CGF subsets, mapped back by center x, produced:

```text
polygon 0 -> CGF MeshSubset.nMatID 0
polygon 1 -> CGF MeshSubset.nMatID 1
```

If RC had remapped by request material name, the expected ids would have been:

```text
polygon 0 Slot_0_Red   -> request sub_index 1
polygon 1 Slot_1_Green -> request sub_index 0
```

The observed CGF ids did not follow that request-name remap.

## Rule Learned

For this controlled fixture, RC preserved raw FBX polygon material slot ids in CGF `MeshSubset.nMatID`.

```text
FBX polygon material slot 0 -> CGF nMatID 0
FBX polygon material slot 1 -> CGF nMatID 1
```

RC did not rewrite polygon material ids by request material name or `.mtl` sub-material name when the request/MTL order differed from the FBX slot order.

Therefore, our converter must keep `.mtl` sub-material slots aligned with FBX material slot ids. Reordering request/MTL materials by material name can make geometry reference the wrong material, even when request and `.mtl` agree with each other.

## Code Changes

- `tools.verify_controlled_fixture` now has `--check-polygons`.
- `verify_fixture_polygon_material_ids()` maps CGF subset centers back to fixture polygons.
- The verifier reports both:
  - `expected_raw_fbx_slot_by_polygon`
  - `request_sub_index_by_polygon_name`
- This makes request-name remap mismatches visible in the JSON output.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_verify_controlled_fixture.py
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_remap\CE_MaterialSlotProbe_Remap.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_remap\CE_MaterialSlotProbe_Remap.material_report.json" --check-polygons
```

## Remaining Work

- Done in phase 12: material assignment now prefers known FBX material slot ids over existing `.mtl` name matches.
- Add UI visibility for FBX slot ids and empty slot placeholders, so artists can see when the converter is preserving sparse slots intentionally.
- Probe deleted or disabled sub-materials with `sub_index = -1` while the FBX still contains geometry assigned to that slot.
