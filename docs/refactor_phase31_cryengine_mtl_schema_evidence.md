# Refactor Phase 31: CryEngine MTL Schema Evidence

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Start replacing guessed `.mtl` rules with evidence from the local CryEngine source tree.

Phase 30 made `.mtl` generation testable. This phase separates:

```text
CryEngine source evidence
current exporter compatibility values
```

so the next changes can replace one rule at a time without losing track of what is proven.

## Source Evidence

Evidence was taken from:

```text
S:\Crytek\crytek\CRYENGINE_Source-release\Code\CryEngine\Cry3DEngine\MaterialHelpers.cpp
S:\Crytek\crytek\CRYENGINE_Source-release\Code\CryEngine\Cry3DEngine\MatMan.cpp
S:\Crytek\crytek\CRYENGINE_Source-release\Engine\Shaders\Illum.ext
```

`MaterialHelpers.cpp` defines the texture slot names that `.mtl` uses:

```text
Diffuse      -> _diff
Bumpmap      -> _ddn
Specular     -> _spec
Smoothness   -> _ddna
Heightmap    -> _displ
Opacity      -> no suffix
Emittance    -> _em
```

It also shows that CryEngine reads `<Textures><Texture Map="..." File="...">` and resolves `./` paths relative to the `.mtl` file folder.

`MatMan.cpp` shows that material loading:

- reads `MtlFlags`, `MatTemplate`, `Shader`, `GenMask`, `StringGenMask`, and `SurfaceType`
- parses `StringGenMask` through the renderer when present
- loads child `<SubMaterials><Material Name="...">` in child order
- loads `PublicParams` before assigning the shader item

`Illum.ext` defines source-side Illum shader tokens such as:

```text
%NORMAL_MAP              0x1
%SPECULAR_MAP            0x10
%DISPLACEMENT_MAPPING    0x10000000
%PHONG_TESSELLATION      0x20000000
%SUBSURFACE_SCATTERING   0x80000
```

## What Changed

Added:

```text
output_formats/cryengine_mtl_schema.py
```

It contains:

- `CE_TEXTURE_MAP_TYPES`
- `CE_TEXTURE_SUFFIXES`
- `ILLUM_EXT_SHADER_MASKS`
- `EXPORT_COMPAT_SHADER_MASKS`
- material default attrs and public params currently used by the exporter

`output_formats.mtl_exporter` now imports the schema instead of owning local constants.

## Compatibility Rule

The exporter still uses `EXPORT_COMPAT_SHADER_MASKS` for `GenMask`.

This is deliberate. The source evidence proves the Illum `.ext` token masks, but it does not yet prove that blindly swapping the exporter to those numeric values will match real RC/Material Editor output in our workflow.

For now:

```text
StringGenMask tokens are source-backed
GenMask numeric values are compatibility-preserved
```

The next step is to compare real `.mtl` output from CryEngine/Material Editor or RC behavior and then replace the compatibility values with proven ones.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_mtl_exporter.py
```

New tests prove:

- texture map names match `MaterialHelpers.cpp`
- texture suffixes match `MaterialHelpers.cpp`
- Illum token masks match `Illum.ext`
- exporter compatibility GenMask values are intentionally distinct from the source evidence values
- `mtl_exporter` still emits the same current compatibility GenMask

## Remaining Work

- Generate or collect real Material Editor `.mtl` samples for the same texture combinations.
- Decide whether `GenMask` should be emitted as source `.ext` values, remapped 64-bit values, or derived solely from `StringGenMask`.
- Replace guessed `Specular`, `Shininess`, `Emittance`, and `PublicParams` defaults with evidence-backed values.
- Add a schema report that flags exported `.mtl` fields still coming from compatibility assumptions.
