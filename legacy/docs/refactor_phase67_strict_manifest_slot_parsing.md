# Refactor Phase 67: Strict Manifest Slot Parsing

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: FBX material manifest integrity

## Goal

Manifest material slots must not rely on Python's broad `int()` conversion behavior.

Before this phase, `coerce_material_slot()` used `int(value)`. That accepted values which are not trustworthy material-slot evidence:

```text
True -> 1
1.5 -> 1
```

Those conversions can make malformed manifest data look like a valid RC material slot.

## What Changed

Updated:

```text
model_processing/material_manifest.py
```

`coerce_material_slot()` now accepts only:

```text
non-negative Python int values, excluding bool
ASCII digit strings such as "0", "12", and "001"
```

It rejects:

```text
bool values
float values, including 1.0
negative values
decimal strings such as "1.0"
non-numeric strings
```

Existing diagnostics continue to surface rejected slots:

```text
material_manifest_invalid_material_slot
material_manifest_invalid_polygon_slot
```

## Why This Matters

The material manifest is evidence, not a place to guess.

If a Blender/plugin bug emits:

```json
{"slot": true, "name": "Stone"}
```

or:

```json
{"slot": 1.5, "name": "Stone"}
```

the converter must not silently target slot `1`. It should report that the manifest cannot prove a stable RC-visible material id.

## Current Boundary

This phase keeps numeric strings valid because sidecars and CLI-generated fixtures may still carry simple integer strings.

It does not introduce a new diagnostic code. The existing invalid-slot diagnostics already mean:

```text
slot evidence is not a non-negative integer RC material id
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_manifest.py tests\test_rc_smoke_test.py tests\test_material_mapping_report.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py
```

Result:

```text
82 passed
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
242 passed
compileall succeeded
uv lock --check succeeded
git diff --check reported only expected LF/CRLF working-copy warnings
```

New coverage proves:

```text
bool manifest slots are rejected instead of becoming slot 1
float manifest slots are rejected instead of being truncated
invalid material slots are still diagnosed
invalid polygon slots are still diagnosed
manifest-driven material expansion skips bool/float slot evidence
RC smoke preflight and material mapping reports preserve the invalid evidence
```
