# Refactor Phase 66: Manifest RC Slot Limit Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: FBX material manifest integrity and RC sub-index policy

## Goal

Surface material manifest slots that exceed RC's supported sub-material range.

Phase 55 already made request/material assignment follow the source-backed RC rule:

```text
sub_index >= 128 -> -1
```

This phase brings the same rule into the manifest evidence layer.

## Why This Matters

The material manifest is used as the source of truth for request JSON and MTL slot order when present.

If the manifest says:

```json
{"slot": 128, "name": "TooHigh"}
```

that row names an FBX/source slot the current RC request path cannot target as a stable sub-material id. The assignment layer will still normalize the generated request material to `-1`, but the manifest itself should also say why that happened.

## New Diagnostics

Added:

```text
material_manifest_material_slot_out_of_rc_range
```

This is emitted when a `materials[]` row has `slot >= RC_MAX_SUB_MATERIALS`.

Added:

```text
material_manifest_polygon_slot_out_of_rc_range
```

This is emitted when polygon evidence uses `material_table_slot`, `expected_cgf_material_id`, or `material_slot` greater than or equal to RC's limit.

## What Changed

Updated:

```text
model_processing/material_manifest.py
```

`material_manifest_table_diagnostics()` now imports `RC_MAX_SUB_MATERIALS` and emits manifest-level hazards for slots at or above the RC limit.

The existing material expansion path is unchanged: it still lets the assignment layer apply RC normalization and emit `rc_sub_index_out_of_range_deleted`.

Updated:

```text
tools/material_mapping_report.py
```

Fixture/material semantic alignment now records out-of-range manifest slots as failed checks:

```text
manifest_material_slot_out_of_rc_range
manifest_polygon_slot_out_of_rc_range
```

## Current Boundary

This phase does not implement CryEngine's multi-uber-material partitioning path for assets with more than 128 material ids.

For now, an out-of-range manifest slot means:

```text
diagnose it
let request assignment normalize it exactly as RC does
do not pretend it is a stable targetable slot
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_manifest.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py tests\test_rc_smoke_test.py tests\test_material_mapping_report.py tests\test_material_index_assigner.py tests\test_material_slot_table.py tests\test_rc_request_builder.py
```

Result:

```text
117 passed
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
241 passed
compileall succeeded
uv lock --check succeeded
git diff --check reported only expected LF/CRLF working-copy warnings
```

New coverage proves:

```text
manifest material slot 127 remains valid
manifest material slot 128 is diagnosed as out of RC range
manifest polygon slot 128 is diagnosed as out of RC range
sidecar diagnostics include out-of-range manifest hazards
PySide import diagnostics include out-of-range manifest hazards
RC smoke preflight includes both manifest out-of-range hazards and RC delete normalization hazards
material mapping semantic alignment marks out-of-range manifest slots as failed checks
```
