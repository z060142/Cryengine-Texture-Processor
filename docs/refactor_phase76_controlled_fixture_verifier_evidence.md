# Refactor Phase 76: Controlled Fixture Verifier Evidence

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: stabilize controlled RC material verification without changing conversion behavior

## Goal

The controlled fixture verifier must not crash when manifest, request, or CGF subset evidence is malformed.

The material mapping report now preserves malformed evidence instead of aborting. The verifier is the next consumer in that chain, so it must also treat report and manifest data as evidence rather than trusted control flow.

## New Verifier Evidence

`verify_fixture_polygon_material_ids()` now returns:

```text
invalid_manifest_entries
invalid_request_entries
invalid_subset_entries
```

These arrays make polygon-level verification fail cleanly with `ok: false` while still returning the valid evidence that could be read.

Current verifier error values include:

```text
invalid_manifest_polygons_collection
invalid_manifest_polygon_row
invalid_manifest_polygon_index
invalid_manifest_polygon_slot
invalid_manifest_expected_cgf_material_id
invalid_request_materials_collection
invalid_request_material_row
invalid_request_material_mapping
invalid_cgf_meshes_collection
invalid_cgf_mesh_row
invalid_cgf_mesh_subsets_collection
invalid_cgf_subset_row
invalid_cgf_subset_center
invalid_cgf_subset_material_id
```

## What Changed

Updated:

```text
tools/verify_controlled_fixture.py
```

Added local evidence coercion helpers:

```text
_coerce_non_negative_int()
_coerce_request_sub_index()
_coerce_center_x()
_iter_manifest_polygon_evidence()
```

The verifier now validates:

```text
manifest polygons collection shape
manifest polygon row shape
manifest polygon index
manifest material_slot
manifest expected_cgf_material_id
request material collection and row shape
request material sub_index
CGF mesh/subset collection and row shape
CGF subset center
CGF subset material_id
```

Valid evidence is still used for:

```text
expected_cgf_material_id_by_polygon
raw_fbx_slot_by_polygon
actual_cgf_material_id_by_polygon
request_sub_index_by_polygon_name
```

## Current Boundary

This phase does not change RC conversion or report generation.

It only hardens `tools/verify_controlled_fixture.py`, which is a verification/probe tool used after report generation.

The verifier does not repair malformed evidence. It reports invalid rows, skips them for comparisons, and returns `ok: false` whenever invalid evidence is present.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_verify_controlled_fixture.py
uv run python -m pytest tests\test_material_mapping_report.py tests\test_rc_smoke_test.py tests\test_verify_controlled_fixture.py
```

Result:

```text
8 passed
60 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv lock --check
```

Result:

```text
280 passed
uv lock --check succeeded
```

New coverage proves:

```text
malformed manifest polygon evidence does not crash polygon verification
malformed request material evidence does not crash polygon verification
malformed CGF mesh/subset evidence does not crash polygon verification
valid rows are still compared while malformed rows are reported
invalid evidence forces ok false instead of disappearing silently
```
