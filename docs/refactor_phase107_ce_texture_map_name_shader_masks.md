# Phase 107 - CE Texture Map Name Shader Masks

## Goal

Make MTL shader-mask generation accept CryEngine material texture map names as texture keys.

Before this phase, the exporter handled internal keys such as `normal` and `displacement`, but a caller that already used CE map names such as `Bumpmap` or `Heightmap` could export `<Texture Map="Bumpmap">` incorrectly or miss the matching `StringGenMask` tokens.

## Rule

The schema now treats these keys as source-backed CE map aliases:

- `bumpmap` -> `Bumpmap`
- `heightmap` -> `Heightmap`

They also drive shader-mask policy:

- `Bumpmap` / `bumpmap` -> `%NORMAL_MAP`
- `Heightmap` / `heightmap` -> `%DISPLACEMENT_MAPPING` and `%PHONG_TESSELLATION`
- `Heightmap` / `heightmap` also enables tessellation `PublicParams`

This does not replace the existing compatibility `GenMask` integer values. `StringGenMask` remains the important source-backed token field because CryEngine load policy treats a present `StringGenMask` as authoritative.

## Smoke Output

Input texture keys:

```python
{
    "Bumpmap": "asset_ddn.dds",
    "Specular": "asset_spec.dds",
    "Heightmap": "asset_displ.dds",
}
```

Generated material evidence:

```text
StringGenMask = %DISPLACEMENT_MAPPING%NORMAL_MAP%PHONG_TESSELLATION%SPECULAR_MAP%SUBSURFACE_SCATTERING
GenMask = 5664683906826272
Textures = Bumpmap, Specular, Heightmap
PublicParams include TessellationFactorMax = 32
```

## Files

- `output_formats/cryengine_mtl_schema.py`
- `tests/test_cryengine_mtl_schema.py`
- `tests/test_mtl_exporter.py`

## Verification

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_mtl_exporter.py tests\test_material_diagnostics_exporter.py
```

Result:

- `61 passed`
