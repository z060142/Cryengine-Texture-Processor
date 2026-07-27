# Refactor Phase 62: Material Manifest Table Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: FBX material manifest integrity

## Goal

Detect malformed material manifest tables before they produce misleading request JSON, MTL files, or RC smoke results.

The material manifest is becoming the bridge between Blender/source FBX material identity and CryEngine request/MTL slot assignment. If that table is malformed, every later artifact can look internally consistent while still targeting the wrong source material.

## Problem

Two manifest hazards are now explicit:

```text
duplicate slot
duplicate exact material name
```

Duplicate slot:

```json
[
  {"slot": 0, "name": "Stone"},
  {"slot": 0, "name": "Metal"}
]
```

This maps multiple material rows to the same final RC `sub_index`.

Duplicate exact name:

```json
[
  {"slot": 0, "name": "Stone"},
  {"slot": 1, "name": "Stone"}
]
```

This is especially dangerous because the converter collapses exact duplicate request names. One manifest row can disappear before request/MTL emission.

## What Changed

Updated:

```text
model_processing/material_manifest.py
```

Added:

```text
material_manifest_table_diagnostics()
```

It emits:

```text
material_manifest_duplicate_slot
material_manifest_duplicate_name
```

Updated:

```text
output_formats/material_diagnostics_exporter.py
ui_pyside/model_import.py
tools/rc_smoke_test.py
```

The same manifest diagnostics now appear in:

```text
<model>.material_diagnostics.json
PySide import diagnostics
RC smoke preflight material diagnostics
```

## Current Boundary

This phase reports malformed manifest rows. It does not rewrite the manifest.

The safe repair path is explicit:

```text
fix material identity in source/Blender or plugin-generated manifest
regenerate request JSON and MTL together
rerun smoke preflight
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_manifest.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py tests\test_rc_smoke_test.py tests\test_material_index_assigner.py
```

Result:

```text
70 passed
```

New coverage proves:

```text
duplicate manifest slots are diagnosed
duplicate exact manifest material names are diagnosed
sidecar diagnostics include manifest table diagnostics
PySide import diagnostics include manifest table diagnostics
RC smoke preflight includes manifest table diagnostics
```
