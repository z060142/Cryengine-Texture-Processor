# Refactor Phase 23: Fixture Semantic Material Reports

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Move the material-name semantic checks from the controlled verifier into the normal RC smoke material report.

Before this phase:

```text
tools.verify_controlled_fixture could detect swapped request/MTL names.
tools.rc_smoke_test material_report.json could only say that CGF id 0 exists in request and MTL.
```

That was not enough. The swapped-order probe is geometrically valid but semantically wrong:

```text
CGF polygon id 0 is correct as an id,
but request/MTL slot 0 points to the wrong material name.
```

## What Changed

`tools.material_mapping_report` now discovers a controlled fixture manifest beside the source FBX:

```text
<asset>.fixture_manifest.json
```

When present, the report includes:

```json
  "source_fixture_manifest": "...fixture_manifest.json",
  "fixture_material_semantic_alignment": {
    "ok": false,
    "manifest_kind": "multi-mesh-name-conflict",
    "material_checks": [],
  "polygon_checks": [],
  "duplicate_request_material_names": [],
  "duplicate_request_sub_indices": []
}
```

The new semantic report checks:

- expected fixture material table slot name vs request sub-index name
- expected fixture material table slot name vs `.mtl` sub-material name
- expected polygon CGF material id vs actual `MeshSubsets.nMatID`
- expected polygon material name vs request/MTL name at the actual CGF id
- duplicate request material names
- duplicate request sub-indices

## Swapped Request Probe

Command:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_multimesh_conflict\CE_MaterialSlotProbe_MultiMeshConflict.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_multimesh_swapped_request" --asset-name "CE_MaterialSlotProbe_MultiMeshConflict" --materials "LocalSlot0_Metal,LocalSlot0_Wood"
```

Result excerpt:

```json
{
  "fixture_material_semantic_alignment": {
    "ok": false,
    "material_checks": [
      {
        "slot": 0,
        "expected_name": "LocalSlot0_Wood",
        "request_names": ["LocalSlot0_Metal"],
        "mtl_slot_name": "LocalSlot0_Metal",
        "ok": false
      }
    ],
    "polygon_checks": [
      {
        "polygon": 0,
        "expected_cgf_material_id": 0,
        "actual_cgf_material_id": 0,
        "expected_name": "LocalSlot0_Wood",
        "request_names_for_actual_id": ["LocalSlot0_Metal"],
        "mtl_name_for_actual_id": "LocalSlot0_Metal",
        "cgf_id_ok": true,
        "ok": false
      }
    ]
  }
}
```

This confirms the report can now show the important distinction:

```text
geometry id check passed
material semantic name check failed
```

## Preserved Suffix Probe

Command:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_duplicate_requested_names\CE_MaterialSlotProbe_DuplicateRequestedNames.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_controlled_duplicate_requested_aligned" --asset-name "CE_MaterialSlotProbe_DuplicateRequestedNames" --materials "DuplicateSurface,DuplicateSurface.001"
```

Result:

```json
{
  "fixture_material_semantic_alignment": {
    "ok": true
  }
}
```

## Rule

For controlled probes, `material_report.json` is now the primary evidence artifact.

Use:

```text
cgf_material_id_alignment
```

to answer:

```text
Did every CGF material id have some request/MTL slot?
```

Use:

```text
fixture_material_semantic_alignment
```

to answer:

```text
Did that id point to the expected material name from the exported fixture?
```

## Limits

This phase does not parse arbitrary FBX material tables.

For normal user FBX files, `fixture_material_semantic_alignment` is empty unless a fixture-like manifest is available. The next durable step is to generate the same kind of material table evidence from a Blender/FBX inspector or from the future Blender plugin sidecar.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_material_mapping_report.py
```

Real RC reports regenerated and inspected:

```text
swapped request order: fixture_material_semantic_alignment.ok = false
DuplicateSurface.001 preserved: fixture_material_semantic_alignment.ok = true
```

## Remaining Work

- Add a Blender/FBX material-table inspector so non-fixture FBX files can get the same semantic report.
- Surface semantic report failures in the PySide diagnostics UI.
- Use this report structure when building the final Blender plugin export sidecar.
