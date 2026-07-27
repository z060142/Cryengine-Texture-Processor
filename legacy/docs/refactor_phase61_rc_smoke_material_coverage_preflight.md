# Refactor Phase 61: RC Smoke Material Coverage Preflight

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: RC smoke preflight and material coverage

## Goal

Make the RC smoke harness catch incomplete request material coverage before invoking RC.

Phase 60 added coverage diagnostics to sidecars and PySide import diagnostics. This phase brings the same rule into `tools.rc_smoke_test`, so smoke reports do not miss manifest/source material omissions.

## Source Evidence

The RC behavior is the same request material coverage rule documented in Phase 60:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:82-109
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:214-239
```

If request materials is non-empty, an unmatched source scene material keeps remap id `-1`, and faces using that material are deleted.

## What Changed

Updated:

```text
tools/rc_smoke_test.py
```

Added:

```text
source_material_specs_from_manifest()
```

This helper reads the copied/source FBX material manifest and builds a source material list from:

```text
manifest.materials[]
manifest.polygons[].material_name
```

That matters because an incomplete material manifest can omit a material row while polygon evidence still proves the source FBX uses that material.

Updated:

```text
collect_material_slot_diagnostics()
```

It now accepts:

```text
material_manifest_info
source_materials
```

and calls the shared `build_omitted_material_diagnostics()` rule.

Updated:

```text
prepare_smoke_bundle()
```

Smoke bundle preflight diagnostics now compare generated request/MTL materials against source materials inferred from the manifest when available.

## Current Boundary

The smoke harness still does not parse arbitrary FBX files directly. It uses the material manifest sidecar when present.

That is acceptable for this phase because the material manifest is the same planned bridge for the future Blender plugin and custom converter workflow.

If no manifest is present, smoke preflight falls back to the explicitly supplied material specs.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_rc_smoke_test.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py tests\test_material_index_assigner.py
```

Result:

```text
63 passed
```

New coverage proves:

```text
source_material_specs_from_manifest includes polygon-only material names
prepare_smoke_bundle reports rc_omitted_source_material_faces_deleted for manifest omissions
existing smoke bundle request/MTL generation behavior is preserved
```
