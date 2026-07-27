# Phase 119 - Shared Texture Output Path Policy

## Why this exists

The converter had source-backed texture output diagnostics and a machine-readable
converter schema, but the actual exporter classes still constructed processed
texture filenames locally.

That made it possible for exporter code, diagnostics, and the external-tool
schema to drift apart.

This phase adds a shared processed texture output naming policy.

## New module

```text
output_formats.texture_output_paths
```

Main helpers:

```text
texture_output_suffix(output_key, normal_alpha=False)
texture_output_filename(output_key, base_name, normal_alpha=False, extension="tif")
texture_output_path(output_key, base_name, output_dir, normal_alpha=False, extension="tif")
```

Shared output-key mapping:

```text
diff     -> diffuse      -> _diff
spec     -> specular     -> _spec
ddna     -> normal       -> _ddn / _ddna
displ    -> displacement -> _displ
emissive -> emissive     -> _em
sss      -> subsurface   -> _sss
```

## Exporter integration

The six processed texture exporters now use `texture_output_path()`:

```text
output_formats.diff_exporter
output_formats.spec_exporter
output_formats.ddna_exporter
output_formats.displ_exporter
output_formats.emissive_exporter
output_formats.sss_exporter
```

`DDNAExporter` keeps the existing behavior:

```text
normal only        -> *_ddn.tif
normal + gloss alpha -> *_ddna.tif
```

Both suffixes remain accepted for CryEngine Bumpmap diagnostics.

## Parser boundary

`TextureNameParser` now recognizes both:

```text
*_em.tif
*_emissive.tif
```

Only `_em` is emitted by the converter. `_emissive` remains a legacy/source
alias so existing assets are still classified correctly.

## Schema and diagnostics

`texture_output_diagnostics` and `tools/converter_schema.py` now import the
output-key mapping from the shared naming policy.

The committed converter schema snapshot did not change:

```text
uv run python tools/converter_schema.py --check docs/converter_schema.json
```

## Verification

- `uv run python -m pytest tests/test_texture_output_paths.py tests/test_texture_output_diagnostics.py tests/test_converter_schema.py tests/test_core_managers.py tests/test_emissive_exporter.py`
- `uv run python tools/converter_schema.py --check docs/converter_schema.json`
- `uv run python -m compileall output_formats core tools tests`
