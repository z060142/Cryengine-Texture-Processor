# Refactor Phase 77: Shared Evidence Coercion

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: reduce duplicated material-mapping evidence parsing rules

## Goal

Material mapping evidence coercion rules should live in one place.

Recent stabilization phases added defensive parsing in several consumers:

```text
model_processing/material_manifest.py
tools/material_mapping_report.py
tools/verify_controlled_fixture.py
```

Those paths were intentionally hardened first. This phase reduces the duplication so future RC-spec changes can update shared parsing behavior without chasing multiple local copies.

## New Shared Module

Added:

```text
model_processing/evidence_coercion.py
```

Shared helpers:

```text
coerce_non_negative_int()
coerce_request_sub_index()
coerce_center_x()
```

## What Changed

Updated:

```text
model_processing/material_manifest.py
```

`coerce_material_slot()` now delegates to:

```text
coerce_non_negative_int()
```

Updated:

```text
tools/material_mapping_report.py
```

Request `sub_index` and CGF subset center parsing now delegate to shared helpers while preserving the existing local wrapper names used by the report code.

Updated:

```text
tools/verify_controlled_fixture.py
```

Verifier-side integer, request sub-index, and center parsing now delegate to shared helpers while preserving existing local wrapper names.

## Current Boundary

This phase is a refactor only.

It does not change request generation, MTL generation, RC execution, report schema, or verifier output shape.

The helper rules remain intentionally narrow:

```text
non-negative integer evidence rejects bool, floats, negatives, and decimal strings
request sub_index accepts -1 and "-1" as delete/unassigned evidence
center_x accepts only finite numeric first coordinates
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_evidence_coercion.py tests\test_material_manifest.py tests\test_material_mapping_report.py tests\test_verify_controlled_fixture.py
uv run python -m pytest tests\test_material_mapping_report.py tests\test_rc_smoke_test.py tests\test_verify_controlled_fixture.py
```

Result:

```text
57 passed
60 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv lock --check
```

Result:

```text
283 passed
uv lock --check succeeded
```

New coverage proves:

```text
shared non-negative integer coercion preserves manifest slot behavior
shared request sub_index coercion preserves deleted -1 handling
shared center_x coercion rejects non-finite coordinates
manifest, report, smoke, and verifier tests still pass through the shared helpers
```
