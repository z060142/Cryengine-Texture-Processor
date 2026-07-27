# Phase 123 - Roughness to CE Opacity Map

## Goal

Make the model material texture resolver preserve roughness textures in the
CryEngine `.mtl` output path.

The real car sample uses a roughness texture as a CryEngine `Opacity` map:

```text
Material: KB3D_CEV_SedanExteriorBody
Map:      Opacity
File:     ./KB3D_CEV_SedanExteriorBody_roughness.dds
```

Before this phase, the converter only searched for `*_opacity` outputs for the
MTL `opacity` texture slot. A processed or existing `*_roughness` texture could
therefore be missed even though real CE assets use it.

## Rule

For exporter/model-resolver input:

```text
roughness -> CE Texture Map "Opacity"
```

For filename diagnostics:

```text
Opacity + *_roughness -> matches_observed_sample_suffix
```

This is intentionally not recorded as a source-backed MaterialHelpers suffix.
`Opacity` is a source-backed CE map name, but `_roughness` is sample-observed
compatibility evidence from the car asset.

## Implementation

- `model_processing.material_texture_resolver`
  - `opacity` now searches both `*_opacity` and `*_roughness`

- `output_formats.cryengine_mtl_schema`
  - adds `CE_TEXTURE_OBSERVED_MAP_ALIASES`
  - exports input `roughness` as CE map `Opacity`
  - adds `CE_TEXTURE_OBSERVED_SUFFIXES`
  - reports `matches_observed_sample_suffix` for `Opacity + *_roughness`

- `output_formats.mtl_exporter`
  - automatically emits `<Texture Map="Opacity">` when material texture data
    contains `roughness`

- diagnostics and schema reports now preserve the distinction between:
  - source-backed CE map names
  - source-backed CE suffixes
  - sample-observed compatibility suffixes

## Real Sample Evidence

Generated report:

```text
docs/phase123_car_roughness_opacity_mtl_schema_report.json
```

Command:

```powershell
uv run python -m tools.mtl_schema_report "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.mtl" --output docs\phase123_car_roughness_opacity_mtl_schema_report.json
```

Observed summary:

```json
{
  "texture_maps": {
    "Opacity": 1
  },
  "texture_suffix_status": "matches_observed_sample_suffix",
  "roughness_file": "./KB3D_CEV_SedanExteriorBody_roughness.dds"
}
```

## Verification

- `uv run python -m pytest tests/test_cryengine_mtl_schema.py tests/test_mtl_exporter.py tests/test_material_texture_resolver.py tests/test_mtl_schema_report.py tests/test_material_diagnostics_exporter.py`
- `uv run python -m tools.mtl_schema_report "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.mtl" --output docs\phase123_car_roughness_opacity_mtl_schema_report.json`
- `uv run python -m compileall model_processing output_formats tools tests`
- `uv run python tools/converter_schema.py --check docs/converter_schema.json`
- `uv lock --check`
- `git diff --check`
- `uv run python -m pytest`
