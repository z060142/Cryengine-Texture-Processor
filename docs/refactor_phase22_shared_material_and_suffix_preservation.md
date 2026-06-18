# Refactor Phase 22: Shared Material Identity and Suffix Preservation

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Close the next material-id gap after the multi-mesh probes:

```text
What happens when two meshes share the same FBX material identity?
What happens when Blender is asked to create duplicate material names?
Can the converter safely strip Blender suffixes such as .001?
```

## What Changed

- `tools.blender_material_fixture` now supports:

```text
--fixture-kind multi-mesh-shared-material
```

- The fixture creates two mesh objects that both use local slot `0` and the same Blender material datablock.
- Multi-mesh fixture manifests now record the actual Blender material name after creation, not only the requested name.
- `clean_material_name()` now preserves Blender suffixes such as `.001`.
- Material assignment no longer collapses `Stone` and `Stone.001` into one RC material.
- The controlled-fixture verifier now reports:
  - `request_name_mapping_ok`
  - `duplicate_request_material_names`
  - missing request names as semantic mapping mismatches

## Shared Material Probe

Generate the FBX:

```powershell
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_shared_material" --asset-name "CE_MaterialSlotProbe_SharedMaterial" --fixture-kind multi-mesh-shared-material
```

Run RC:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_shared_material\CE_MaterialSlotProbe_SharedMaterial.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_shared_material" --asset-name "CE_MaterialSlotProbe_SharedMaterial" --materials "SharedSlot0_Surface"
```

Verifier result:

```json
{
  "raw_fbx_slot_by_polygon": {
    "0": 0,
    "1": 0
  },
  "actual_cgf_material_id_by_polygon": {
    "0": 0,
    "1": 0
  },
  "request_name_mapping_ok": true
}
```

Rule:

```text
Two meshes using the same FBX material identity share the same CGF material id.
```

## Duplicate Requested Name Observation

Generate an FBX while requesting the same name twice:

```powershell
uv run python -m tools.blender_material_fixture --output-dir "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_duplicate_requested_names" --asset-name "CE_MaterialSlotProbe_DuplicateRequestedNames" --fixture-kind multi-mesh-name-conflict --materials "DuplicateSurface,DuplicateSurface"
```

Blender does not keep two material datablocks with exactly the same name. The manifest records:

```json
[
  {
    "name": "DuplicateSurface",
    "requested_name": "DuplicateSurface"
  },
  {
    "name": "DuplicateSurface.001",
    "requested_name": "DuplicateSurface"
  }
]
```

Before this phase, the converter stripped `.001`, skipped the second material, and produced a request/MTL with no `DuplicateSurface.001` slot.

After this phase:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_duplicate_requested_names\CE_MaterialSlotProbe_DuplicateRequestedNames.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_duplicate_requested_aligned" --asset-name "CE_MaterialSlotProbe_DuplicateRequestedNames" --materials "DuplicateSurface,DuplicateSurface.001"
```

Verifier result:

```json
{
  "actual_cgf_material_id_by_polygon": {
    "0": 0,
    "1": 1
  },
  "request_sub_index_by_polygon_name": {
    "0": 0,
    "1": 1
  },
  "request_name_mapping_ok": true
}
```

## Rule

Do not strip Blender duplicate suffixes from material names on the RC/MTL path.

```text
Stone and Stone.001 are distinct RC-visible material names.
If FBX exports both, request JSON and .mtl must preserve both.
```

## Impact

- The old "clean material name" rule was unsafe for model conversion.
- Texture grouping may still want user-facing base-name heuristics, but RC request and `.mtl` generation need exact material names.
- Blender plugins should either:
  - preserve Blender's actual unique material names, or
  - intentionally generate their own stable unique names before FBX export.
- Exact duplicate names are still ambiguous and should be rejected or uniqueified before export.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_texture_resolver.py tests\test_material_index_assigner.py tests\test_verify_controlled_fixture.py tests\test_rc_smoke_test.py
```

Real RC probes passed:

```text
shared material identity: polygon 0 -> 0, polygon 1 -> 0
Blender unique suffix preserved: DuplicateSurface -> 0, DuplicateSurface.001 -> 1
```

## Remaining Work

- Split user-facing texture base-name cleanup from RC-visible material-name identity.
- Surface missing request material names directly in smoke material reports.
- Update PySide diagnostics text to explain that `.001` may be a real material identity, not noise.
