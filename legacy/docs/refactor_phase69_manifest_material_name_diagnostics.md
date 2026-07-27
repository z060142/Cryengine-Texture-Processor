# Refactor Phase 69: Manifest Material Name Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: FBX material manifest integrity and RC material-name matching

## Goal

Manifest material names must be explicit non-empty strings.

RC request materials are matched to FBX source materials by name. A manifest row with no stable string name cannot target a source material, even if its slot is otherwise valid.

## New Diagnostics

Added:

```text
material_manifest_invalid_material_name
```

This is emitted when a `materials[]` row has a missing, non-string, empty, or whitespace-only `name`.

Added:

```text
material_manifest_invalid_polygon_material_name
```

This is emitted when polygon evidence has a missing, non-string, empty, or whitespace-only `material_name`.

## What Changed

Updated:

```text
model_processing/material_manifest.py
```

Added:

```text
coerce_material_name()
```

The helper accepts only non-empty strings. It preserves the original string when valid, so RC-visible material identity is not normalized or trimmed.

`material_manifest_table_diagnostics()` now reports invalid material and polygon names.

`material_manifest_materials()` now skips manifest material rows whose names are not valid string evidence. That prevents empty names or numeric names from becoming request/MTL material rows.

Updated:

```text
tools/rc_smoke_test.py
```

`source_material_specs_from_manifest()` now skips invalid manifest names while still allowing preflight diagnostics to report them.

Updated:

```text
tools/material_mapping_report.py
```

Semantic alignment reports now record invalid manifest names as failed checks:

```text
invalid_manifest_material_name
invalid_manifest_polygon_material_name
```

## Current Boundary

This phase does not strip or rename valid material names.

For example:

```text
" Stone "
```

is preserved as-is because RC-visible FBX material identity is name-sensitive. The converter only rejects values that are not non-empty strings.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_manifest.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py tests\test_rc_smoke_test.py tests\test_material_mapping_report.py tests\test_rc_request_builder.py tests\test_mtl_exporter.py
```

Result:

```text
129 passed
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
262 passed
compileall succeeded
uv lock --check succeeded
git diff --check reported only expected LF/CRLF working-copy warnings
```

New coverage proves:

```text
material names must be non-empty strings
polygon material names must be non-empty strings
manifest table display blanks invalid names instead of crashing UI code
manifest-driven material expansion skips invalid names
sidecar diagnostics include invalid manifest name hazards
PySide import diagnostics include invalid manifest name hazards
RC smoke preflight keeps reporting invalid names
material mapping semantic alignment records invalid names as failed checks
```
