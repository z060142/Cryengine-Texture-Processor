# Refactor Phase 64: Material Manifest Invalid Slot Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: FBX material manifest integrity

## Goal

Malformed material manifest slots must become diagnostics, not Python exceptions.

The manifest sidecar is the planned bridge between Blender/source FBX material identity and RC request/MTL slot assignment. A bad slot value means the converter cannot prove which RC sub-index a material or polygon should target.

## New Diagnostics

Added:

```text
material_manifest_invalid_material_slot
```

This is emitted when a `materials[]` row has a non-integer `slot`.

Added:

```text
material_manifest_invalid_polygon_slot
```

This is emitted when a `polygons[]` row has a non-integer `material_table_slot`, `expected_cgf_material_id`, or `material_slot`.

## What Changed

Updated:

```text
model_processing/material_manifest.py
```

`coerce_material_slot()` is now the shared manifest slot parser. Invalid values return `None`.

`material_manifest_table_diagnostics()` now reports invalid material and polygon slots before any slot matching rules run.

`material_manifest_materials()` now skips manifest rows and polygon usage rows whose slot cannot be parsed. This avoids fabricating a slot for data that cannot be proven.

Updated:

```text
tools/rc_smoke_test.py
```

`source_material_specs_from_manifest()` now uses the shared slot parser and ignores invalid slot evidence. The copied manifest is still passed to preflight diagnostics, so the invalid slot appears as a hazard instead of crashing the smoke bundle.

Updated:

```text
tools/material_mapping_report.py
```

Fixture/material semantic alignment now records invalid manifest slots as failed checks:

```text
invalid_manifest_material_slot
invalid_manifest_polygon_slot
```

The report therefore stays readable and marks alignment as not OK instead of aborting.

## Current Boundary

This phase does not repair malformed manifests.

Invalid slots are skipped for request/MTL material expansion because assigning a guessed fallback slot would make later RC evidence look cleaner than it really is.

The safe repair path is still:

```text
fix the Blender/FBX manifest writer or source material table
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
76 passed
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
236 passed
compileall succeeded
uv lock --check succeeded
git diff --check reported only expected LF/CRLF working-copy warnings
```

New coverage proves:

```text
invalid material slots are diagnosed without crashing
invalid polygon slots are diagnosed without crashing
manifest-driven material expansion skips unprovable slots
sidecar diagnostics include invalid slot hazards
PySide import diagnostics include invalid slot hazards
RC smoke preflight includes invalid slot hazards
material mapping semantic alignment records invalid slots as failed checks
```
