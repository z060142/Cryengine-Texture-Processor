# Refactor Phase 20: Multi-Mesh Material Name Probe

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Prove how RC maps material ids when different mesh objects each use local FBX material slot `0`, but those local slot entries have different material names.

This is the missing case after the single-mesh probes:

```text
Object A polygon material_index = 0, material name = LocalSlot0_Wood
Object B polygon material_index = 0, material name = LocalSlot0_Metal
```

## What Changed

- `tools.blender_material_fixture` now supports:

```text
--fixture-kind multi-mesh-name-conflict
```

- The new fixture creates two mesh objects, each with one triangle and one local material slot.
- The manifest records:
  - object name
  - raw local FBX material slot
  - material name
  - expected CGF material id
  - triangle center used for subset-to-polygon matching
- `tools.verify_controlled_fixture` now distinguishes:
  - `raw_fbx_slot_by_polygon`
  - `expected_cgf_material_id_by_polygon`
  - `actual_cgf_material_id_by_polygon`
- The verifier uses manifest `center_x` hints when available, so multi-mesh chunk order does not decide the result.

## Probe Commands

Generate the controlled FBX:

```powershell
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_multimesh_conflict" --asset-name "CE_MaterialSlotProbe_MultiMeshConflict" --fixture-kind multi-mesh-name-conflict
```

Run RC:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_multimesh_conflict\CE_MaterialSlotProbe_MultiMeshConflict.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_multimesh_conflict" --asset-name "CE_MaterialSlotProbe_MultiMeshConflict" --materials "LocalSlot0_Wood,LocalSlot0_Metal"
```

Verify polygon material ids:

```powershell
uv run python -m tools.verify_controlled_fixture --manifest "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_multimesh_conflict\CE_MaterialSlotProbe_MultiMeshConflict.fixture_manifest.json" --report "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_multimesh_conflict\CE_MaterialSlotProbe_MultiMeshConflict.material_report.json" --check-polygons
```

## Result

The manifest intentionally uses raw local FBX slot `0` for both polygons:

```json
{
  "raw_fbx_slot_by_polygon": {
    "0": 0,
    "1": 0
  }
}
```

The generated CGF uses material ids `0` and `1`:

```json
{
  "actual_cgf_material_id_by_polygon": {
    "0": 0,
    "1": 1
  }
}
```

The request and MTL slots were:

```json
[
  { "name": "LocalSlot0_Wood", "sub_index": 0 },
  { "name": "LocalSlot0_Metal", "sub_index": 1 }
]
```

## Rule

For multi-mesh FBX files, raw per-object local material slot ids are not enough to predict CGF `MeshSubsets.nMatID`.

In this probe, both polygons used local slot `0`, but RC mapped the second mesh to CGF material id `1`.

This proved that per-object local material slots are not the final CGF ids for multi-mesh FBX files. Phase 21 refines the cause: RC did not remap by request/MTL material name when request order was swapped. The observed ids are best explained as FBX material table indices that the request/MTL files must mirror.

Practical rule:

```text
The converter must preserve a stable FBX material table order and emit request/MTL sub-materials in that same order.
Do not treat local mesh material slot index alone as the final CGF material id for multi-mesh models.
```

## Impact

- Blender plugin/export tooling should build a global material table from the actual FBX material identities in exported order.
- Request JSON `materials[].name`, request `sub_index`, and `.mtl` sub-material slot names must mirror that table order.
- A per-mesh local slot can still be useful for diagnostics, but it is not the complete identity.
- Phase 19 diagnostics should stay, but their wording should not claim that slot id is always authoritative in multi-mesh exports.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_blender_material_fixture.py tests\test_verify_controlled_fixture.py
```

Real RC probe passed:

```text
raw local slots: polygon 0 -> 0, polygon 1 -> 0
FBX/export material order: LocalSlot0_Wood -> 0, LocalSlot0_Metal -> 1
CGF ids: polygon 0 -> 0, polygon 1 -> 1
```

## Remaining Work

- Update material conflict diagnostics so the UI explains the difference between local slot ids and global material identities.
- Keep Phase 21's swapped request-order probe in mind when implementing automatic MTL generation.
- Keep Phase 22's suffix-preservation probe in mind when implementing Blender material-name handling.
