# Refactor Phase 63: Material Manifest Polygon Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: FBX material manifest integrity

## Goal

Validate polygon-level material evidence against the manifest material table.

Phase 62 checks malformed `materials[]` rows. This phase checks whether `polygons[]` agrees with that table.

## Why This Matters

The manifest has two important layers:

```text
materials[] -> source material table / final request slot plan
polygons[]  -> evidence of which material each source polygon actually uses
```

If these disagree, request JSON and MTL can look well-formed while still being based on the wrong source material identity.

## New Diagnostics

Added:

```text
material_manifest_polygon_slot_name_mismatch
```

Example:

```json
{
  "materials": [
    {"slot": 0, "name": "Stone"},
    {"slot": 1, "name": "Metal"}
  ],
  "polygons": [
    {"material_name": "Stone", "material_table_slot": 1}
  ]
}
```

The polygon says slot `1` is `Stone`, but the material table says slot `1` is `Metal`.

Added:

```text
material_manifest_polygon_name_multiple_slots
```

Example:

```json
{
  "polygons": [
    {"material_name": "Stone", "material_table_slot": 0},
    {"material_name": "Stone", "material_table_slot": 1}
  ]
}
```

The same material name appears across multiple table slots. RC request materials are matched by material name, so one source material name cannot reliably target multiple final sub-indices.

## What Changed

Updated:

```text
model_processing/material_manifest.py
```

`material_manifest_table_diagnostics()` now also checks polygon evidence:

```text
polygon material_name vs materials[slot].name
polygon material_name used across multiple slots
```

Because Phase 62 already wired this function into sidecar diagnostics, PySide import diagnostics, and RC smoke preflight, these new polygon diagnostics now appear in all three places.

## Current Boundary

This phase reports inconsistent manifest evidence. It does not attempt to repair the manifest.

The safe repair path is:

```text
regenerate manifest from Blender/FBX
or fix the plugin manifest writer so materials[] and polygons[] share the same global material table
then regenerate request JSON and MTL together
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_manifest.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py tests\test_rc_smoke_test.py
```

Result:

```text
59 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv run python -m compileall core model_processing output_formats tests tools ui ui_pyside utils main.py legacy_tk_main.py
uv lock --check
git diff --check
```

Result:

```text
229 passed
compileall succeeded
uv lock --check succeeded
git diff --check reported only expected LF/CRLF working-copy warnings
```

New coverage proves:

```text
polygon/table slot-name mismatches are diagnosed
same polygon material name across multiple slots is diagnosed
sidecar diagnostics include polygon manifest diagnostics
PySide import diagnostics include polygon manifest diagnostics
RC smoke preflight includes polygon manifest diagnostics
```
