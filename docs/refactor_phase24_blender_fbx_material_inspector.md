# Refactor Phase 24: Blender FBX Material Inspector

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Generalize the fixture manifest idea toward real FBX files.

Phase 23 made `material_report.json` able to perform semantic checks when a manifest is available. This phase adds a Blender-backed inspector that can create a manifest-like sidecar directly from an FBX:

```text
<asset>.fbx_material_manifest.json
```

## What Changed

Added:

```text
tools.blender_material_inspector
```

Command:

```powershell
uv run python -m tools.blender_material_inspector --fbx "path\to\asset.fbx"
```

The inspector writes:

```json
{
  "manifest_kind": "blender-fbx-material-inspection",
  "materials": [
    {
      "slot": 0,
      "name": "MaterialName",
      "first_object": "MeshObject",
      "first_local_slot": 0
    }
  ],
  "polygons": [
    {
      "polygon": 0,
      "object": "MeshObject",
      "object_polygon": 0,
      "material_slot": 0,
      "material_table_slot": 0,
      "material_name": "MaterialName",
      "expected_cgf_material_id": 0,
      "center_x": 0.0
    }
  ]
}
```

`tools.material_mapping_report` now discovers both sidecar shapes:

```text
<asset>.fixture_manifest.json
<asset>.fbx_material_manifest.json
```

## Probe

Inspector command:

```powershell
uv run python -m tools.blender_material_inspector --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_fixture_duplicate_requested_names\CE_MaterialSlotProbe_DuplicateRequestedNames.fbx"
```

Observed material table:

```json
[
  {
    "slot": 0,
    "name": "DuplicateSurface"
  },
  {
    "slot": 1,
    "name": "DuplicateSurface.001"
  }
]
```

Then the FBX and sidecar were copied to a directory without the original fixture manifest and passed through RC smoke:

```powershell
uv run python -m tools.rc_smoke_test --fbx "S:\Crytek\crytek\Stripped to the bone\controlled_fbx_inspector_duplicate_names\CE_MaterialSlotProbe_DuplicateRequestedNames.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\rc_smoke_work_inspector_duplicate_names" --asset-name "CE_MaterialSlotProbe_DuplicateRequestedNames" --materials "DuplicateSurface,DuplicateSurface.001"
```

The generated material report discovered:

```text
CE_MaterialSlotProbe_DuplicateRequestedNames.fbx_material_manifest.json
```

and produced:

```json
{
  "fixture_material_semantic_alignment": {
    "ok": true
  }
}
```

## Rule

For non-fixture FBX files, generate a Blender material inspection sidecar before RC smoke testing if material semantic evidence matters.

The current practical workflow is:

```text
1. Inspect FBX with Blender -> .fbx_material_manifest.json
2. Generate request JSON and .mtl in the same material table order
3. Run RC
4. Read material_report.json fixture_material_semantic_alignment
```

## Limits

- The inspector uses Blender's imported view of the FBX, not CryEngine's internal FBX SDK objects.
- It infers material table order from first material encounter across sorted mesh objects.
- This matched the controlled `.001` probe, but more real-world FBX files should be checked before treating it as complete.
- The report field is still named `fixture_material_semantic_alignment` for compatibility, even when the sidecar comes from the Blender inspector.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_blender_material_inspector.py tests\test_material_mapping_report.py
```

Real Blender/RC check:

```text
Inspector sidecar discovered by material report
DuplicateSurface -> slot 0
DuplicateSurface.001 -> slot 1
fixture_material_semantic_alignment.ok = true
```

## Remaining Work

- Run the inspector on larger real FBX files and compare against RC output.
- Feed inspector manifests into the PySide model import diagnostics.
- Consider renaming `fixture_material_semantic_alignment` to `source_material_semantic_alignment` after UI consumers are updated.
