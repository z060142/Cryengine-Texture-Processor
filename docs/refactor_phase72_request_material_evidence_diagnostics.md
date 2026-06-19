# Refactor Phase 72: Request Material Evidence Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: stabilize RC smoke material reports without changing existing conversion behavior

## Goal

The material mapping report must not crash when the RC request JSON contains malformed `materials[]` evidence.

Generated requests normally contain material rows shaped like:

```json
{"name": "Stone", "physicalize": "no_collide", "sub_index": 0}
```

However, hand-edited requests or third-party converter output can contain malformed rows, invalid material names, or non-comparable `sub_index` values. The report layer previously trusted those fields and could fail before writing a useful material mapping report.

## New Report Evidence

Added to `fixture_material_semantic_alignment`:

```text
invalid_request_entries
```

Each entry marks malformed RC request material evidence with `ok: false` and an `error` value.

Current error values:

```text
invalid_request_materials_collection
invalid_request_material_row
invalid_request_material_name
invalid_request_sub_index
```

The top-level alignment report also emits failed checks with matching `type` values.

## What Changed

Updated:

```text
tools/material_mapping_report.py
```

Added request-side sub-index parsing:

```text
_coerce_request_sub_index()
```

Accepted request `sub_index` evidence:

```text
null
-1
0
127
"-1"
"2"
" 2 "
```

Rejected request `sub_index` evidence:

```text
true
1.5
-2
"1.0"
"bad"
```

`load_request_materials()` now:

```text
validates request.materials is a list
validates each material row is an object
normalizes numeric-string sub_index values
preserves invalid row/name/sub_index evidence as explicit error records
```

`evaluate_material_slot_alignment()` now records malformed request material rows as failed checks instead of comparing bad `sub_index` values.

`evaluate_fixture_material_semantics()` now reports malformed request material rows in `invalid_request_entries` and excludes those rows from request-name, duplicate-name, and duplicate-sub-index comparisons.

`evaluate_cgf_material_ids()` now uses only valid request material rows when checking CGF material ids against request sub-indices.

## Current Boundary

This phase does not alter the request builder.

The generated request format is unchanged. This phase only hardens the report layer against malformed input so RC smoke runs can still leave actionable evidence.

This phase also does not normalize out-of-range request values to RC's delete behavior. Out-of-range handling remains covered by the existing request-builder and material-index diagnostics.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_mapping_report.py
uv run python -m pytest tests\test_material_mapping_report.py tests\test_rc_smoke_test.py tests\test_verify_controlled_fixture.py
```

Result:

```text
20 passed
53 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv lock --check
```

Result:

```text
273 passed
uv lock --check succeeded
```

New coverage proves:

```text
malformed request materials collections do not crash request loading
non-object request material rows are preserved as failed evidence
empty or non-string request material names are reported
boolean, float, and otherwise invalid request sub_index values are reported
numeric-string request sub_index values are normalized for report comparison
deleted request rows using -1 or "-1" remain valid deleted/unassigned evidence
semantic material alignment reports invalid request entries without poisoning valid rows
CGF material-id alignment ignores invalid request rows
```
