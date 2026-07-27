# Refactor Phase 49: FBX Texture Fallback Warning

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 1 item: `P1-2`

## Goal

Keep the existing FBX diffuse texture fallback behavior, but make it machine-testable and visible.

Before this phase, `FbxExporter` silently guessed:

```text
<material base>_diff.tif
```

when no processed diffuse texture path was available for a material. The printed log line was not enough for tools or tests to detect that fallback.

## What Changed

Updated:

```text
model_processing/fbx_exporter.py
```

Added:

```text
resolve_diffuse_texture_assignment()
FbxExporter.last_texture_warnings
```

When a processed diffuse path exists, the assignment returns:

```text
used_fallback = false
warning = null
```

When no processed diffuse path exists, the assignment returns:

```text
used_fallback = true
warning.code = fbx_diffuse_texture_fallback
```

`FbxExporter._setup_materials_for_export()` now returns the collected warnings, and `FbxExporter.export()` stores them on:

```text
last_texture_warnings
```

## Preserved Behavior

The exporter still creates Blender image placeholders and still uses the compatibility fallback path when needed.

The exported FBX path behavior remains unchanged.

No RC request JSON fields are added.

## Why This Matters

Phase 1 allows compatibility fallbacks, but they must not hide uncertainty.

This makes the FBX material texture path chain auditable:

```text
processed texture data present -> use exact processed path
processed texture data missing -> use fallback and emit warning
```

Phase 2 can later decide whether fallback should become an error under stricter CryEngine/RC conversion rules.

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_fbx_exporter.py tests\test_model_export_context.py
uv run python -m compileall model_processing\fbx_exporter.py tests\test_fbx_exporter.py
```

New tests cover:

```text
processed diffuse path assignment without warning
fallback diffuse path assignment with fbx_diffuse_texture_fallback warning
relative texture path preservation
legacy material-name fallback base behavior
```
