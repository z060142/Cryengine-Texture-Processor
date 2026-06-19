# Refactor Phase 78: Strict Material Index Integer Evidence

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: keep RC material slot assignment evidence strict and repeatable

## Goal

Material sub-index assignment must not inherit Python's loose `int()` behavior.

Before this phase, `model_processing/material_index_assigner.py` used local `int()` coercion for FBX ids, source material indices, explicit `sub_index` values, deleted-material detection, and polygon usage evidence.

That allowed malformed evidence such as:

```text
True -> 1
1.5 -> 1
```

For report-only paths this is bad evidence hygiene. For `material_index_assigner`, it can directly change the request/MTL slot mapping sent to RC.

## New Shared Helper

Extended:

```text
model_processing/evidence_coercion.py
```

Added:

```text
coerce_int()
```

Rules:

```text
accept int values except bool
accept signed integer strings such as "12", "001", and "-12"
reject None, bool, floats, decimal strings, empty strings, and lone "-"
```

`coerce_non_negative_int()` now delegates to `coerce_int()` and keeps its existing non-negative boundary.

## What Changed

Updated:

```text
model_processing/material_index_assigner.py
```

The local `_coerce_int()` wrapper now delegates to shared `coerce_int()`.

This affects material assignment inputs used by:

```text
get_fbx_material_id()
is_deleted_material()
_known_polygon_usage()
assign_material_sub_indices()
```

## Current Boundary

This phase changes source material evidence coercion before assignment.

It does not change:

```text
RC request schema
MTL schema
report schema
normalize_rc_sub_index()
out-of-range RC sub-index normalization
```

The RC policy layer still owns the rule that sub-material indices greater than or equal to `RC_MAX_SUB_MATERIALS` normalize to `-1`.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_evidence_coercion.py tests\test_material_index_assigner.py tests\test_rc_request_builder.py tests\test_material_diagnostics_exporter.py
```

Result:

```text
60 passed
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
285 passed
compileall succeeded
uv lock --check succeeded
git diff --check succeeded
```

New coverage proves:

```text
signed integer evidence accepts only real integer evidence
non-negative integer evidence still rejects negative values
malformed explicit material sub_index values fall back to FBX material id assignment
bool and float material sub_index evidence no longer reserve explicit RC slots
```
