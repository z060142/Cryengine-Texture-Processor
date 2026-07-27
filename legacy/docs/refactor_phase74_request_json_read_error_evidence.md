# Refactor Phase 74: Request JSON Read Error Evidence

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: stabilize RC smoke material reports without changing existing conversion behavior

## Goal

The material mapping report must still be written when the RC request JSON cannot be parsed.

The request JSON is the center of the RC smoke report, but it is still evidence. A malformed or missing JSON file should not prevent the report from preserving path, MTL, CGF, and RC output context.

## New Report Evidence

Added top-level report field:

```text
request_read_error
```

Normal successful reads use an empty string:

```text
"request_read_error": ""
```

Malformed or unreadable JSON records the read error:

```text
"request_read_error": "<read or parse error text>"
```

When the request cannot be read, `request_materials` contains one failed evidence row:

```json
{
  "order": null,
  "name": "",
  "sub_index": null,
  "physicalize": "",
  "ok": false,
  "errors": ["invalid_request_json"],
  "path": "asset.json",
  "read_error": "<read or parse error text>"
}
```

The top-level alignment report then emits a failed check:

```text
invalid_request_json
```

## What Changed

Updated:

```text
tools/material_mapping_report.py
```

Added report-layer safe request loading:

```text
_request_read_error_entry()
_load_request_materials_for_report()
```

`build_material_mapping_report()` now uses the safe loader.

The direct loader API remains unchanged:

```text
load_request_materials()
```

It still parses valid request JSON and returns its original material row shape.

## Current Boundary

This phase does not change request generation.

It only changes how the material mapping report records request read failures after a JSON path is supplied.

If the request cannot be read, the report cannot prove request-to-MTL alignment. The alignment therefore reports `ok: false` with an `invalid_request_json` check.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_mapping_report.py
uv run python -m pytest tests\test_material_mapping_report.py tests\test_rc_smoke_test.py tests\test_verify_controlled_fixture.py
```

Result:

```text
22 passed
55 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv lock --check
```

Result:

```text
275 passed
uv lock --check succeeded
```

New coverage proves:

```text
valid request JSON reports an empty request_read_error
malformed request JSON does not abort material mapping report creation
malformed request JSON is preserved as invalid_request_json evidence
alignment reports invalid_request_json as a failed check
read-error text is available both at top level and in the failed check
```
