# Refactor Phase 10: Sparse Material Slot Verification

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Extend the controlled Blender fixture so it can test more than the simple `0,1` material slot case. The important question was whether RC preserves sparse FBX material ids such as `0,2`, or compresses them to `0,1` in the generated CGF.

## What Changed

- `tools/blender_material_fixture.py` now accepts `--polygon-slots`.
- The fixture mesh now creates one independent triangle per requested polygon slot.
- The fixture manifest now records:
  - `polygon_material_slots`
  - per-polygon material slot/name
  - `expect_cgf_material_ids`
- Added tests for polygon slot argument parsing.

## Commands

Full contiguous case:

```powershell
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_full" --asset-name "CE_MaterialSlotProbe_Full" --polygon-slots "0,1,2"
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_full\CE_MaterialSlotProbe_Full.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_full" --asset-name "CE_MaterialSlotProbe_Full" --materials "Slot_0_Red,Slot_1_Green,Slot_2_Blue"
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_full\CE_MaterialSlotProbe_Full.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_full\CE_MaterialSlotProbe_Full.material_report.json"
```

Sparse case:

```powershell
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_sparse" --asset-name "CE_MaterialSlotProbe_Sparse" --polygon-slots "0,2"
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_sparse\CE_MaterialSlotProbe_Sparse.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_sparse" --asset-name "CE_MaterialSlotProbe_Sparse" --materials "Slot_0_Red,Slot_1_Green,Slot_2_Blue"
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_sparse\CE_MaterialSlotProbe_Sparse.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_sparse\CE_MaterialSlotProbe_Sparse.material_report.json"
```

## Results

Full contiguous case:

```text
polygon_slots: [0, 1, 2]
expected:      [0, 1, 2]
actual:        [0, 1, 2]
subsets:       [(0, 2, 3), (1, 1, 3), (2, 0, 3)]
```

Sparse case:

```text
polygon_slots: [0, 2]
expected:      [0, 2]
actual:        [0, 2]
subsets:       [(0, 2, 3), (1, 0, 3)]
```

Subset tuple format:

```text
(subset_index, MeshSubset.nMatID, num_indices)
```

## Rule Learned

RC preserves used material slot ids in `MeshSubsets.nMatID`, including sparse ids.

```text
Used Blender material slots 0 and 2 -> CGF material ids 0 and 2
```

RC does not compress sparse used material ids into contiguous values. This means our converter must preserve empty/unassigned `.mtl` slots when material ids have gaps. The phase 3 decision to fill holes with an `unassigned` placeholder is aligned with the observed RC behavior.

Subset order is not stable enough to use as the material id. In both the full and sparse cases, RC reordered subsets, but each subset's `nMatID` kept the source material slot id.

## Verification

Passed:

```powershell
uv run python -m pytest tests
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_full" --asset-name "CE_MaterialSlotProbe_Full" --polygon-slots "0,1,2"
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_sparse" --asset-name "CE_MaterialSlotProbe_Sparse" --polygon-slots "0,2"
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_full\CE_MaterialSlotProbe_Full.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_full" --asset-name "CE_MaterialSlotProbe_Full" --materials "Slot_0_Red,Slot_1_Green,Slot_2_Blue"
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_sparse\CE_MaterialSlotProbe_Sparse.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_sparse" --asset-name "CE_MaterialSlotProbe_Sparse" --materials "Slot_0_Red,Slot_1_Green,Slot_2_Blue"
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_full\CE_MaterialSlotProbe_Full.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_full\CE_MaterialSlotProbe_Full.material_report.json"
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_sparse\CE_MaterialSlotProbe_Sparse.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_sparse\CE_MaterialSlotProbe_Sparse.material_report.json"
```

## Remaining Work

- Test request/MTL remapping where request `sub_index` differs from raw FBX material slot order.
- Verify how deleted materials with `sub_index = -1` are represented when the FBX still contains a material slot.
- Feed the sparse-slot rule into the PySide material assignment UI so gaps are visible and intentional.
