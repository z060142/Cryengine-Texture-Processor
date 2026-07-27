# Refactor Phase 71: CGF Subset Evidence Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: stabilize FBX-to-RC material mapping reports without changing existing conversion behavior

## Goal

The material mapping report must not crash when CGF subset evidence is malformed.

The CGF reader normally returns numeric subset centers and material ids from binary RC output. However, the report layer also handles loaded or fixture-provided summaries during tests and probes. Those summaries are evidence, not trusted control flow. If a malformed subset row reaches the semantic report, the converter should preserve the failure as report data instead of aborting the whole RC smoke result.

## New Report Evidence

Added to `fixture_material_semantic_alignment`:

```text
invalid_subset_entries
```

Each entry marks malformed CGF summary evidence with `ok: false` and an `error` value.

Current error values:

```text
invalid_cgf_meshes_collection
invalid_cgf_mesh_row
invalid_cgf_mesh_subsets_collection
invalid_cgf_subset_row
invalid_cgf_subset_center
invalid_cgf_subset_material_id
```

Valid subset evidence still appears in:

```text
subset_entries
```

## What Changed

Updated:

```text
tools/material_mapping_report.py
```

Added a report-local parser for CGF subset evidence:

```text
_coerce_cgf_subset_center_x()
_invalid_subset_entry()
```

`_fixture_polygon_actual_ids()` now validates:

```text
cgf_material_summary["meshes"] is a list
each mesh row is an object
mesh["subsets"] is a list when present
each subset row is an object
subset["center"][0] is a finite numeric value
subset["material_id"] is non-negative integer evidence
```

Malformed rows are skipped for polygon material-id comparison and recorded in `invalid_subset_entries`.

`evaluate_fixture_material_semantics()` now marks the semantic alignment as not ok when invalid CGF subset evidence exists.

The invalid manifest-root path now also returns:

```text
invalid_subset_entries: []
```

so report consumers can read a stable schema.

## Current Boundary

This phase does not modify the binary CGF reader.

The reader still decodes RC output as before. This phase only hardens the report layer against malformed or fixture-provided CGF summary dictionaries.

This phase also does not try to repair malformed subset evidence. Rows without a usable center or material id cannot be matched back to source polygon evidence, so they remain diagnostic report data.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_mapping_report.py
uv run python -m pytest tests\test_material_mapping_report.py tests\test_rc_smoke_test.py
```

Result:

```text
16 passed
42 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv lock --check
```

Result:

```text
269 passed
uv lock --check succeeded
```

New coverage proves:

```text
malformed CGF mesh rows do not crash semantic reports
malformed CGF subsets collections do not crash semantic reports
malformed CGF subset rows do not crash semantic reports
missing or non-numeric subset centers are reported
boolean material ids are rejected
numeric-string material ids are normalized through existing integer evidence rules
valid subset evidence still contributes to polygon material-id comparison
invalid subset evidence makes semantic alignment not ok
```
