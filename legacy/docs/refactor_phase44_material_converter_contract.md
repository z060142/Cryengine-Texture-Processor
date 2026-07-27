# Refactor Phase 44: Material Converter Contract

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Remove placeholder behavior from `model_processing/material_converter.py` while preserving its public `MaterialConverter` API.

Before this phase, the converter returned a shallow copy of a hard-coded CryEngine-looking template and always treated unknown texture nodes as diffuse. It also claimed Blender material mutation behavior that was not actually implemented.

## What Changed

Replaced the placeholder implementation with a conservative, tested data converter:

```text
model_processing/material_converter.py
```

Main helpers:

```text
normalize_texture_type()
infer_texture_type_from_path()
MaterialConverter.convert()
MaterialConverter.apply_to_material()
```

Supported input texture maps now include:

```text
classified key -> processed path
  diffuse -> wall_diff.tif
  normal -> wall_ddna.tif
  specular -> wall_spec.tif

original/source path -> processed path
  source/wall_albedo.png -> processed/wall_diff.tif
  source/wall_normal.png -> processed/wall_ddna.tif
```

Texture types are normalized through the same CryEngine material schema table used by the `.mtl` exporter where possible.

## Preserved Behavior

The class name and method names remain:

```text
MaterialConverter.convert()
MaterialConverter.apply_to_material()
MaterialConverter._determine_texture_type()
MaterialConverter._set_texture_node()
```

`convert()` still returns a dictionary with:

```text
Name
Shader
GenMask
StringGenMask
SubMtlCount
Textures
PublicParams
```

The method does not claim to edit live Blender materials. Dict materials can receive the converted data under `cryengine_material`; non-dict objects are returned unchanged when attributes cannot be set.

## Why This Matters

This module was not wired into the main export path, but it was dangerous documentation-by-code: it looked like a material conversion implementation while encoding guessed values.

The new contract makes the current boundary explicit:

```text
known texture names or filename suffixes
  -> normalized internal texture types
  -> CryEngine texture map fields
  -> compatibility-preserved shader masks
```

The next material phase can replace the compatibility mask behavior with real Material Editor / RC evidence without also having to untangle fake Blender-node mutation code.

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_material_converter.py tests\test_mtl_exporter.py
uv run python -m compileall model_processing\material_converter.py tests\test_material_converter.py
```

New tests cover:

```text
common texture type aliases
filename suffix inference
CryEngine texture field mapping
source-to-processed path inference
template deep-copy behavior
dict material application
normalized texture assignment recording
```
