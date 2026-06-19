# Refactor Phase 48: Diagnostics Texture Evidence

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: `P1-1`

## Goal

Surface the degraded model/texture evidence collected in earlier Phase 1 work through diagnostics outputs.

Before this phase:

```text
load_status existed on model dictionaries
source_mode existed on TextureReference objects
texture_ref_evidence existed in material texture data
```

but material diagnostics sidecars and the PySide diagnostics view did not show that evidence.

## What Changed

Updated:

```text
output_formats/material_diagnostics_exporter.py
ui_pyside/model_import.py
```

Material diagnostics reports now include `texture_ref_evidence` per material when available.

When a material uses non-authoritative texture evidence such as:

```text
filesystem_no_bpy
filesystem_import_only
filesystem_legacy
```

the diagnostics report adds:

```text
severity: warning
code: degraded_texture_reference_source
```

The PySide model import diagnostics helper now also reports:

```text
degraded_model_load_status
degraded_texture_reference_source
```

The extracted texture table now has a Source column so `source_mode` is visible without reading JSON sidecars.

## Preserved Behavior

No RC request JSON fields were added.

Existing material slot hazards and warnings are preserved.

Authoritative Blender texture evidence does not produce a degraded-source warning.

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py tests\test_material_texture_resolver.py
uv run python -m compileall output_formats\material_diagnostics_exporter.py ui_pyside\model_import.py tests\test_material_diagnostics_exporter.py tests\test_pyside_model_import_diagnostics.py
```

New tests cover:

```text
texture_ref_evidence in material diagnostics sidecars
degraded texture source warnings
no warning for blender source_mode
PySide degraded load_status diagnostics
PySide degraded texture source diagnostics
```
