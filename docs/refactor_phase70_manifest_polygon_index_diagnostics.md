# Refactor Phase 70: Manifest Polygon Index Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: FBX material manifest integrity and RC polygon material-id evidence

## Goal

Manifest polygon rows must identify the source polygon with a non-negative integer `polygon` value.

The material mapping report uses this index to compare manifest polygon evidence against the CGF subset material ids emitted by RC. If the index is missing or malformed, the converter cannot prove that a polygon kept the intended material id after FBX-to-CGF conversion.

## New Diagnostics

Added:

```text
material_manifest_invalid_polygon_index
```

This is emitted when a `polygons[]` row has a missing, boolean, float, negative, or otherwise non-integer `polygon` value.

Accepted values are:

```text
0
12
"12"
" 12 "
```

Rejected values are:

```text
missing field
true
1.5
-1
"-1"
"1.0"
```

## What Changed

Updated:

```text
model_processing/material_manifest.py
```

Added:

```text
coerce_polygon_index()
```

The helper follows the same strict non-negative integer evidence rule as material slots. It exists as a separate helper so future code can distinguish source polygon identity from material table slot identity without duplicating parser behavior.

`material_manifest_table_diagnostics()` now reports invalid polygon indices before attempting to trust a polygon row as semantic evidence.

Updated:

```text
tools/material_mapping_report.py
```

`evaluate_fixture_material_semantics()` now records malformed polygon indices as failed checks:

```text
invalid_manifest_polygon_index
```

The report continues processing the remaining rows instead of crashing on:

```text
int(polygon["polygon"])
```

`_fixture_polygon_actual_ids()` also skips malformed manifest polygon indices and malformed `center_x` values while building its auxiliary center lookup. This keeps a bad fixture evidence row from aborting the entire material mapping report.

## Current Boundary

This phase does not repair, reindex, or infer missing polygon indices.

Rows with invalid polygon indices are diagnostic evidence only. They are skipped for semantic polygon comparison because there is no stable source polygon key to compare against RC output.

This phase also does not introduce a standalone diagnostic for malformed `center_x`; the material mapping report simply avoids using malformed center lookup rows so the rest of the report can still run.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_manifest.py tests\test_material_mapping_report.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py tests\test_rc_smoke_test.py
```

Result:

```text
108 passed
```

New coverage proves:

```text
polygon indices must be non-negative integer evidence
invalid polygon indices appear in material manifest diagnostics
invalid polygon indices appear in exported material diagnostics
PySide import diagnostics surface invalid polygon indices
RC smoke preflight surfaces invalid polygon indices
material mapping semantic alignment records invalid polygon indices as failed checks
malformed center_x fixture lookup rows do not crash the semantic report
```
