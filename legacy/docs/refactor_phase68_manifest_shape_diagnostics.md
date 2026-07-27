# Refactor Phase 68: Manifest Shape Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: FBX material manifest integrity

## Goal

Malformed manifest structure must become diagnostics, not crashes or silently skipped evidence.

Earlier phases tightened manifest slot values. This phase validates the shape around those values:

```text
manifest root
materials collection
polygons collection
materials[] rows
polygons[] rows
```

## New Diagnostics

Added:

```text
material_manifest_invalid_root
material_manifest_invalid_materials_collection
material_manifest_invalid_polygons_collection
material_manifest_invalid_material_row
material_manifest_invalid_polygon_row
```

These are emitted when the manifest root is not an object, `materials` / `polygons` are not lists, or entries inside those lists are not objects.

## What Changed

Updated:

```text
model_processing/material_manifest.py
```

Added shared manifest row helpers:

```text
iter_manifest_material_rows()
iter_manifest_polygon_rows()
```

They yield only object rows. Invalid rows are still reported by `material_manifest_table_diagnostics()`.

`material_manifest_summary()`, `material_manifest_table_rows()`, and `material_manifest_materials()` now tolerate bad root/collection/row shapes without raising attribute errors.

Updated:

```text
tools/rc_smoke_test.py
```

`source_material_specs_from_manifest()` now uses the shared row helpers, so invalid manifest rows no longer break smoke preflight source-material inference.

Updated:

```text
tools/material_mapping_report.py
```

Semantic alignment reports now preserve malformed manifest structure as failed checks instead of aborting report generation.

## Current Boundary

This phase reports malformed structure and skips untrusted rows. It does not repair or infer missing rows.

The safe repair path remains:

```text
fix the Blender/FBX manifest writer
regenerate the manifest
regenerate request JSON and MTL together
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_manifest.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py tests\test_rc_smoke_test.py tests\test_material_mapping_report.py
```

Result:

```text
93 passed
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
253 passed
compileall succeeded
uv lock --check succeeded
git diff --check reported only expected LF/CRLF working-copy warnings
```

New coverage proves:

```text
non-object manifest roots are diagnosed
non-list materials/polygons fields are diagnosed
non-object materials[]/polygons[] rows are diagnosed
summary/table-row helpers tolerate malformed shapes
manifest-driven material expansion skips invalid rows
sidecar diagnostics include manifest shape hazards
PySide import diagnostics include manifest shape hazards
RC smoke preflight keeps reporting malformed sidecars
material mapping semantic alignment records malformed shape as failed checks
```
