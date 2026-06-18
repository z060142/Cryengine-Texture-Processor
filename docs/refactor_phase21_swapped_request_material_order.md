# Refactor Phase 21: Swapped Request Material Order Probe

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Check whether RC remaps CGF `MeshSubsets.nMatID` by request/MTL material name when request material order differs from the FBX material order.

Phase 20 proved that two mesh objects can both use local material slot `0` while RC writes CGF ids `0` and `1`. This phase tests the next question:

```text
If request/MTL says Metal = 0 and Wood = 1,
will RC rewrite the Wood polygon to id 1?
```

## Probe

The FBX fixture is the same as Phase 20:

```text
Object 0: local material slot 0 -> LocalSlot0_Wood
Object 1: local material slot 0 -> LocalSlot0_Metal
```

The request/MTL order is deliberately swapped:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_multimesh_conflict\CE_MaterialSlotProbe_MultiMeshConflict.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_multimesh_swapped_request" --asset-name "CE_MaterialSlotProbe_MultiMeshConflict" --materials "LocalSlot0_Metal,LocalSlot0_Wood"
```

Verification:

```powershell
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_multimesh_conflict\CE_MaterialSlotProbe_MultiMeshConflict.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_multimesh_swapped_request\CE_MaterialSlotProbe_MultiMeshConflict.material_report.json" --check-polygons
```

## Result

The verifier result:

```json
{
  "ok": true,
  "raw_fbx_slot_by_polygon": {
    "0": 0,
    "1": 0
  },
  "actual_cgf_material_id_by_polygon": {
    "0": 0,
    "1": 1
  },
  "request_sub_index_by_polygon_name": {
    "0": 1,
    "1": 0
  },
  "request_name_mapping_ok": false
}
```

RC did not rewrite the Wood polygon to request sub-index `1`, and did not rewrite the Metal polygon to request sub-index `0`.

## Rule

RC's generated CGF material ids are not remapped by request/MTL material name.

The strongest current rule is:

```text
CGF material ids follow the FBX/export material table order.
The request JSON and .mtl must be emitted in that same order.
Names are validation anchors, not a reliable remapping mechanism.
```

## Impact

- A converter or Blender plugin must not freely sort material names alphabetically.
- Do not let UI display order become request/MTL slot order unless it matches the exported FBX material table.
- A valid report needs two checks:
  - geometry id check: do CGF ids match the expected FBX table ids?
  - semantic name check: do those ids point to the same names in request/MTL?
- `tools.verify_controlled_fixture` now exposes `request_name_mapping_ok` for that second check.

## Verification

Passed:

```powershell
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_multimesh_conflict\CE_MaterialSlotProbe_MultiMeshConflict.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_multimesh_swapped_request\CE_MaterialSlotProbe_MultiMeshConflict.material_report.json" --check-polygons
```

The command exits successfully because the geometry ids match the FBX material table expectation. It also reports:

```text
request_name_mapping_ok: false
```

That false value is the important semantic hazard.

## Remaining Work

- Make smoke reports surface this semantic mismatch without requiring the controlled-fixture verifier.
- Add a duplicate-name probe to learn how RC behaves when two FBX materials share the same display name.
- Update the PySide diagnostics wording so users understand that request/MTL slot order must mirror exported FBX material order.
