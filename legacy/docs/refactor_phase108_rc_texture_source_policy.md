# Phase 108 - RC Texture Source Policy

## Goal

Make texture-output validation follow CryEngine TextureCompiler evidence instead of assuming that every processed texture must already be DDS.

CryEngine accepts source textures and can compile them through RC. The converter should therefore validate whether a texture path is a valid RC source texture and whether the filename carries the expected CE material suffix.

## Source Evidence

CryEngine source:

- `Code/CryEngine/RenderDll/Common/Textures/TextureCompiler.h`
  - `CTextureCompiler::IsImageFormatSupported()` accepts `dds`, `hdr`, and `tif` when texture compiling is enabled
  - comments describe source files as usually TIFF and destination files as usually DDS
- `Code/CryEngine/RenderDll/Common/Textures/TextureCompiler.cpp`
  - `GetInputFilename()` maps a DDS destination back to a TIF source candidate
  - delayed/error texture placeholders distinguish `_ddn` and `_ddna`
- `Code/CryEngine/RenderDll/Common/Textures/TextureHelpers.cpp`
  - CE texture slot suffixes include `_diff`, `_ddn`, `_ddna`, `_spec`, `_displ`, `_sss`, and related map suffixes

## Implementation

Updated `output_formats/cryengine_mtl_schema.py`:

- added `RC_TEXTURE_SOURCE_EXTENSIONS = {"dds", "hdr", "tif"}`
- added `analyze_rc_texture_source_extension()`
- attached `rc_source_extension_analysis` to each `resolve_ce_texture_map()` result

Updated `output_formats/material_diagnostics_exporter.py`:

- `unsupported_rc_texture_source_extension`
  - warning when an exported MTL texture path has an extension not listed by TextureCompiler
- `mismatch_ce_texture_suffix`
  - warning when a texture path does not contain the CE suffix expected for its material map

This does not block export. It makes non-RC-ready texture paths visible in reports.

## Behavior

Supported RC texture source extensions:

```text
dds, hdr, tif
```

Example diagnostics:

```json
[
  {
    "code": "unsupported_rc_texture_source_extension",
    "texture_path": "stone_basecolor.png",
    "extension": "png",
    "supported_extensions": ["dds", "hdr", "tif"]
  },
  {
    "code": "mismatch_ce_texture_suffix",
    "texture_path": "stone_s.tif",
    "expected_suffix": "_spec"
  }
]
```

## Verification

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_material_diagnostics_exporter.py tests\test_mtl_exporter.py
```

Result:

- `63 passed`
