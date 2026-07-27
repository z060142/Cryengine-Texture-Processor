# Refactor Phase 65: Material Manifest Non-Negative Slots

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: FBX material manifest integrity

## Goal

Material manifest slots must be non-negative integers.

Phase 64 made malformed slot values diagnostic instead of crashing. This phase tightens the rule further: negative slot values are also invalid manifest evidence.

## Why This Matters

In RC request materials, `sub_index = -1` has delete/unassigned meaning.

In the FBX material manifest, `materials[].slot`, `polygons[].material_table_slot`, `polygons[].expected_cgf_material_id`, and `polygons[].material_slot` are evidence of source/CGF material ids. Those ids must not be negative.

If a manifest row says:

```json
{"slot": -1, "name": "Stone"}
```

the converter must not silently turn that into a delete request. That would make a bad manifest look like intentional RC behavior.

## What Changed

Updated:

```text
model_processing/material_manifest.py
```

`coerce_material_slot()` now returns `None` for negative values, not only for non-integer values.

Existing diagnostics therefore cover both invalid classes:

```text
material_manifest_invalid_material_slot
material_manifest_invalid_polygon_slot
```

The diagnostic messages now describe a non-negative integer slot violation.

Updated tests:

```text
tests/test_material_manifest.py
tests/test_rc_smoke_test.py
tests/test_material_mapping_report.py
```

The invalid-slot cases now include both string values and `-1`.

## Current Boundary

This phase does not introduce a separate negative-slot diagnostic code.

The reason is practical: for downstream behavior, both `"bad-slot"` and `-1` mean the same thing in a material manifest:

```text
the converter cannot prove a stable RC-visible material slot
```

Invalid manifest rows are skipped during manifest-driven material expansion. The source sidecar remains available to diagnostics, PySide import diagnostics, RC smoke preflight, and material mapping reports.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_manifest.py tests\test_rc_smoke_test.py tests\test_material_mapping_report.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py
```

Result:

```text
76 passed
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
236 passed
compileall succeeded
uv lock --check succeeded
git diff --check reported only expected LF/CRLF working-copy warnings
```

New coverage proves:

```text
negative material slots are diagnosed as invalid manifest slots
negative polygon slots are diagnosed as invalid manifest slots
negative manifest slots are skipped during material expansion
RC smoke preflight keeps reporting the invalid source evidence
material mapping semantic alignment marks negative manifest slots as failed checks
```
