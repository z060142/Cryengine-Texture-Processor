# Refactor Phase 45: Degraded Model Load Status

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Keep the existing fallback model import behavior while making degraded data explicit.

Before this phase, `ModelLoader` returned dummy/import-only dictionaries with only boolean flags, and `TextureExtractor` could scan nearby texture folders when `bpy` was unavailable. That behavior was useful for recovering texture files, but dangerous for RC/material work because filesystem-scanned textures can be mistaken for authoritative FBX material data.

## What Changed

Updated:

```text
model_processing/model_loader.py
model_processing/texture_extractor.py
ui_pyside/model_import.py
```

Model dictionaries now expose:

```text
load_status = loaded | import_only | dummy
load_error  = reason for dummy model creation
load_warning = reason for import-only degraded loading
```

Texture references now expose:

```text
source_mode = blender | filesystem_no_bpy | filesystem_import_only | filesystem_legacy
```

The PySide model import texture summary preserves `source_mode` so later UI/diagnostic layers can show whether a texture reference came from Blender material data or a filesystem scan.

## Preserved Behavior

Existing compatibility flags remain:

```text
is_dummy
is_import_only
```

The UI and export flow still skip dummy/import-only models for normal MTL/FBX export as before.

Import-only models still get a synthetic material named after the model stem so nearby texture scans can attach discovered textures to something meaningful.

## Bug Fixes

Dummy models no longer produce filesystem-scanned texture references.

Filesystem texture scanning now deduplicates files when both `textures/` and the model root are scanned. Previously the same texture could be found twice when the model root walk also traversed `textures/`.

## Why This Matters

The next RC/material phases must separate:

```text
authoritative FBX/Blender material evidence
degraded import-only filesystem scan evidence
dummy load failure evidence
```

This phase does not remove fallback recovery. It makes that recovery auditable so later conversion logic can avoid treating guessed data as RC-visible material truth.

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_model_load_degraded_status.py tests\test_model_loader_material_usage.py tests\test_material_texture_resolver.py
uv run python -m compileall model_processing\model_loader.py model_processing\texture_extractor.py ui_pyside\model_import.py tests\test_model_load_degraded_status.py
```

New tests cover:

```text
dummy load_status and load_error
import-only load_status and load_warning
TextureReference source_mode serialization
dummy model extraction returning no references
filesystem_no_bpy source mode
filesystem_import_only source mode
filesystem scan deduplication through observed reference count
```
