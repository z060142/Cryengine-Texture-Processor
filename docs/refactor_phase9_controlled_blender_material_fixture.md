# Refactor Phase 9: Controlled Blender Material Fixture

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Prove the material-id rule with a controlled FBX instead of relying on a GameSDK sample whose polygon material assignments are unknown.

## What Changed

- Added `tools/blender_material_fixture.py`.
- Added `tools/verify_controlled_fixture.py`.
- Added tests for both tools.

The Blender fixture generator:

1. runs Blender in background mode,
2. creates one mesh object named `CE_MaterialSlotProbe`,
3. creates three material slots:
   - `Slot_0_Red`
   - `Slot_1_Green`
   - `Slot_2_Blue`
4. assigns two polygons to material slots `0` and `1`,
5. exports an FBX,
6. writes a `*.fixture_manifest.json` with the expected CGF material ids.

## Commands

Generate the fixture:

```powershell
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture" --asset-name "CE_MaterialSlotProbe"
```

Run RC through the existing smoke harness:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture\CE_MaterialSlotProbe.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled" --asset-name "CE_MaterialSlotProbe" --materials "Slot_0_Red,Slot_1_Green,Slot_2_Blue"
```

Verify expected material ids against the generated material report:

```powershell
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture\CE_MaterialSlotProbe.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled\CE_MaterialSlotProbe.material_report.json"
```

## Fixture Manifest

The generated manifest recorded:

```json
{
  "materials": [
    {"slot": 0, "name": "Slot_0_Red"},
    {"slot": 1, "name": "Slot_1_Green"},
    {"slot": 2, "name": "Slot_2_Blue"}
  ],
  "polygons": [
    {"polygon": 0, "material_slot": 0, "material_name": "Slot_0_Red"},
    {"polygon": 1, "material_slot": 1, "material_name": "Slot_1_Green"}
  ],
  "expect_cgf_material_ids": [0, 1]
}
```

## RC/CGF Result

The generated RC request contained:

```json
[
  {"name": "Slot_0_Red", "physicalize": "no_collide", "sub_index": 0},
  {"name": "Slot_1_Green", "physicalize": "no_collide", "sub_index": 1},
  {"name": "Slot_2_Blue", "physicalize": "no_collide", "sub_index": 2}
]
```

The generated `.mtl` contained the same names in slots `0`, `1`, and `2`.

The CGF reader found:

```json
{
  "material_ids": [0, 1],
  "meshes": [
    {
      "subset_count": 2,
      "subsets": [
        {"subset": 0, "num_indices": 3, "material_id": 1},
        {"subset": 1, "num_indices": 3, "material_id": 0}
      ]
    }
  ]
}
```

The verifier returned:

```json
{
  "ok": true,
  "expected": [0, 1],
  "actual": [0, 1]
}
```

## Rule Learned

For this controlled Blender FBX:

```text
Blender polygon material_index -> FBX material slot -> RC request sub_index -> CGF MeshSubsets.nMatID
```

Used material slots `0` and `1` survived RC conversion as CGF material ids `0` and `1`.

RC may reorder mesh subsets by geometry or internal batching. In the observed CGF, subset `0` had `material_id = 1` and subset `1` had `material_id = 0`. The subset order is not the material id rule; `MeshSubset.nMatID` is the authoritative material slot id.

Unused material slot `2` stayed present in request/MTL but did not appear in CGF `material_ids`, because no polygon used it.

## Verification

Passed:

```powershell
uv run python -m pytest tests
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture" --asset-name "CE_MaterialSlotProbe"
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture\CE_MaterialSlotProbe.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled" --asset-name "CE_MaterialSlotProbe" --materials "Slot_0_Red,Slot_1_Green,Slot_2_Blue"
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture\CE_MaterialSlotProbe.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled\CE_MaterialSlotProbe.material_report.json"
```

## Remaining Work

- Extend the fixture to use slot `2` on an actual polygon.
- Add a fixture with a gap, for example slots `0` and `2`, to prove whether RC preserves sparse material ids.
- Add a fixture with renamed or reordered MTL slots to test how request `sub_index` behaves when it differs from FBX material order.
- Feed these results back into the converter's material assignment UI and future Blender plugin path.
