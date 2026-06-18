# Refactor Phase 41: FBX Texture Path Resolution

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Keep the current Blender FBX export flow intact while making its material texture paths match the processed texture data produced by the converter.

Before this phase, normal model export called:

```text
FbxExporter.export(..., texture_dir="textures", texture_data=build_fbx_texture_data(...))
```

but the exporter treated `"textures"` as a process-relative directory, not a path relative to the FBX output folder. It also looked for legacy texture keys such as `diffuse` and `albedo`, while the current resolver emits CryEngine-style output keys such as `diff` and `ddna`.

The result was that exported FBX materials could fall back to guessed `_diff.tif` paths instead of the actual processed diffuse texture path.

## What Changed

Added path and texture selection helpers in:

```text
model_processing/fbx_exporter.py
```

Main helpers:

```text
resolve_texture_output_dir()
select_diffuse_texture_path()
relative_blender_texture_path()
fallback_diffuse_texture_path()
```

The FBX exporter now resolves:

```text
texture_dir=None       -> <fbx output dir>/textures
texture_dir="textures" -> <fbx output dir>/textures
absolute texture_dir   -> unchanged absolute directory
```

Diffuse texture selection now uses:

```text
diff -> diffuse -> albedo
```

`diff` is the current processed CryEngine texture key from `build_fbx_texture_data()`. `diffuse` and `albedo` remain compatibility fallbacks for older call sites.

## Preserved Behavior

The exporter still:

```text
skips Blender default placeholder materials named "Dots Stroke" and "Material"
rebuilds each Blender material with a Principled BSDF and image texture node
stores Blender paths with the // relative-prefix form
creates placeholder image data-blocks instead of loading the texture file
falls back to <material base>_diff.tif when no texture_data diffuse path exists
```

The fallback remains intentionally conservative because some model export paths may still call the exporter without resolver-produced texture data.

## Why This Matters

The FBX conversion JSON, `.mtl`, and FBX material table work only helps if the exported FBX points at the same processed texture files that the converter actually produced.

This phase closes one mismatch in the model export chain:

```text
material/texture resolver
  -> processed diff texture path
  -> Blender material image filepath
  -> FBX relative texture reference
```

This is not new CryEngine/RC evidence. It is an internal correctness fix that makes later RC/Sandbox probes more trustworthy.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_fbx_exporter.py tests\test_material_texture_resolver.py
```

New tests cover:

```text
default texture directory resolution next to the FBX output
relative texture_dir anchoring to the FBX output directory
absolute texture_dir preservation
processed `diff` key priority
legacy `diffuse` and `albedo` fallback keys
forward-slash FBX relative texture paths
legacy fallback `_diff.tif` path construction
```
