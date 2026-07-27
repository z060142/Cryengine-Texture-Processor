# Refactor Phase 60: Request Material Coverage Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: request material coverage and Blender/plugin safety

## Goal

Generalize Phase 59's omitted-material warning from default-name filters to full request material coverage.

Phase 59 proved the RC behavior:

```text
if request materials is non-empty, unmatched source materials keep remap id -1
faces using remap id -1 are deleted
```

This phase makes diagnostics compare the source material list against the actual material records the converter will emit, including manifest-driven exports.

## Source Evidence

The RC behavior is still the same source-backed rule:

```text
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:82-109
CRYENGINE_Source-release/Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp:214-239
```

Important consequence:

```text
When request materials is non-empty, every source material used by geometry needs a matching request material.
```

This includes source materials omitted by:

```text
default-name filters
incomplete FBX material manifests
future plugin/tool-generated material tables
```

## What Changed

Updated:

```text
model_processing/material_index_assigner.py
```

`build_omitted_material_diagnostics()` now reports any source material missing from emitted request material records, not only `Material` / `Dots Stroke`.

The diagnostic now includes:

```text
omitted_reason = default_name_filter
omitted_reason = not_in_request_materials
```

Updated:

```text
output_formats/material_diagnostics_exporter.py
```

The diagnostics API now accepts:

```text
material_manifest_info
source_materials
```

This allows callers to preserve the output material list used for MTL/request diagnostics while still checking coverage against the original source material list.

Updated:

```text
main.py
```

FBX/JSON diagnostics now pass the loaded model's material manifest and source materials. MTL diagnostics pass source materials separately from the already-resolved MTL material rows.

Updated:

```text
ui_pyside/model_import.py
```

The PySide import diagnostics helper now uses the shared material slot table with `material_manifest_info` and includes omitted-source-material diagnostics, so incomplete material manifests show up before export.

## Current Boundary

This phase reports incomplete request material coverage. It does not automatically add missing source materials to the request or MTL.

That repair should be explicit because adding a material changes:

```text
request material order
sub_index assignment
.mtl child slots
expected CGF material ids
```

The safe future workflow is:

```text
detect omitted used source material -> regenerate or edit manifest/source material table -> rebuild request and MTL together
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py tests\test_material_index_assigner.py tests\test_model_export_context.py tests\test_rc_request_builder.py tests\test_rc_smoke_test.py
```

Result:

```text
80 passed
```

New coverage proves:

```text
manifest-omitted source materials are reported as rc_omitted_source_material_faces_deleted
sidecar diagnostics can check source_materials separately from output materials
PySide model import diagnostics also surface manifest coverage omissions
default-only ignored material lists remain quiet because RC automatic fallback applies
```
