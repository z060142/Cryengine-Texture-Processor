# Refactor Phase 46: Shared Texture Type Resolver

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Preserve current texture classification behavior while removing duplicated texture type rules from material conversion and model texture extraction.

Before this phase, the project had separate rules for:

```text
MaterialConverter texture aliases
TextureExtractor Blender socket names
TextureExtractor filesystem filename patterns
```

That made it possible for the same texture, such as `asset_ddna.tif` or `asset_opacity.tif`, to be interpreted differently depending on the entry point.

## What Changed

Added:

```text
model_processing/texture_type_resolver.py
```

Main helpers:

```text
normalize_texture_type()
infer_texture_type_from_path()
infer_texture_type_from_text()
```

Updated:

```text
model_processing/material_converter.py
model_processing/texture_extractor.py
```

The material converter now imports the shared normalization helpers while preserving its public import compatibility for `normalize_texture_type()` and `infer_texture_type_from_path()`.

The texture extractor now uses the shared resolver for:

```text
Blender linked socket names
Blender node labels/names
image filepath suffixes
filesystem scan filename suffixes
```

## Preserved Behavior

The extractor still defaults unknown texture nodes/files to `diffuse`.

The material converter still emits `.mtl`-style `Opacity` texture fields. Internally, the shared resolver names extracted alpha-like files as `alpha`; the converter maps that to its existing `opacity` material key before writing the CryEngine-style texture map.

## Why This Matters

The asset converter is moving toward RC-accurate material behavior. Before replacing material rules with source/RC evidence, all input routes need to agree on basic texture semantics:

```text
Blender node
filesystem fallback
material conversion
MTL export
```

This phase centralizes those semantics without claiming that the full CryEngine material model is complete.

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_texture_type_resolver.py tests\test_material_converter.py tests\test_model_load_degraded_status.py tests\test_material_texture_resolver.py
uv run python -m compileall model_processing\texture_type_resolver.py model_processing\material_converter.py model_processing\texture_extractor.py tests\test_texture_type_resolver.py tests\test_material_converter.py tests\test_model_load_degraded_status.py
```

New tests cover:

```text
Blender socket names and CryEngine map aliases
filename suffix inference
free-text socket/node hint inference
converter alpha-to-opacity compatibility mapping
filesystem scan use of the shared suffix resolver
```
