# Refactor Phase 73: MTL XML Read Error Evidence

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: stabilize RC smoke material reports without changing existing conversion behavior

## Goal

The material mapping report must still be written when generated or supplied MTL XML is malformed.

RC smoke reports read two XML files after preparing or running a conversion:

```text
asset.mtl
asset.mtl.cryasset
```

Both files are evidence. If either XML file is malformed, the smoke report should preserve that parse failure and continue writing the rest of the report instead of aborting before the user can see request, path, RC, or CGF evidence.

## New Report Evidence

Added top-level report fields:

```text
mtl_read_error
mtl_cryasset_read_error
```

Normal successful reads use empty strings:

```text
"mtl_read_error": ""
"mtl_cryasset_read_error": ""
```

Malformed XML leaves the existing data fields empty and records the parser error:

```text
"mtl_slots": []
"mtl_read_error": "<parse error text>"
"mtl_cryasset_details": {}
"mtl_cryasset_read_error": "<parse error text>"
```

## What Changed

Updated:

```text
tools/material_mapping_report.py
```

Added report-layer safe loaders:

```text
_load_mtl_slots_for_report()
_load_cryasset_details_for_report()
```

`build_material_mapping_report()` now uses these safe loaders when building RC smoke reports.

The direct loader APIs remain unchanged:

```text
load_mtl_slots()
load_cryasset_details()
```

They still parse valid files and return their original shapes.

## Current Boundary

This phase does not change MTL generation or `.cryasset` generation.

It only changes how the material mapping report records read failures after those files exist.

Malformed MTL XML still means slot alignment cannot be proven. In that case, `mtl_slots` is empty and request materials report `missing_mtl_slot`, while `mtl_read_error` explains why the MTL evidence was unavailable.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_mapping_report.py
uv run python -m pytest tests\test_material_mapping_report.py tests\test_rc_smoke_test.py tests\test_verify_controlled_fixture.py
```

Result:

```text
21 passed
54 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv lock --check
```

Result:

```text
274 passed
uv lock --check succeeded
```

New coverage proves:

```text
valid MTL and cryasset reads report empty read-error fields
malformed MTL XML does not abort material mapping report creation
malformed cryasset XML does not abort material mapping report creation
malformed MTL evidence leaves mtl_slots empty
slot alignment still reports missing_mtl_slot when MTL evidence cannot be read
```
