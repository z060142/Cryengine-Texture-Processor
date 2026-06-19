# Phase 120 - Model Texture Resolver DDN Alias

## Why this exists

Phase 119 moved processed texture output naming into a shared policy. That made
one model-flow gap visible:

```text
DDNAExporter can output *_ddn.tif when no gloss alpha is available.
```

The model texture resolver only searched for:

```text
*_ddna.tif
```

That meant a rough batch texture run could produce a valid CryEngine Bumpmap
output that later FBX/MTL export failed to pick up.

## Change

`model_processing.material_texture_resolver` now imports:

```text
output_formats.texture_output_paths.texture_output_suffix
```

The suffix maps now support multiple candidate suffix templates.

FBX texture data:

```text
diff -> *_diff.tif
ddna -> *_ddna.tif, then *_ddn.tif
```

MTL material data:

```text
diffuse      -> *_diff.tif
normal       -> *_ddna.tif, then *_ddn.tif
specular     -> *_spec.tif
displacement -> *_displ.tif
emissive     -> *_em.tif
opacity      -> *_opacity.tif
sss          -> *_sss.tif
```

`*_ddna` remains preferred when both files exist because it carries normal alpha
information. `*_ddn` is accepted as the no-alpha Bumpmap output.

## Boundary

The output key for FBX texture data is still named `ddna` for compatibility with
the existing `FbxExporter` texture contract. The path may now point to either
`*_ddna.tif` or `*_ddn.tif`.

## Verification

- `uv run python -m pytest tests/test_material_texture_resolver.py tests/test_texture_output_paths.py tests/test_texture_output_diagnostics.py tests/test_converter_schema.py tests/test_model_export_context.py`
- `uv run python tools/converter_schema.py --check docs/converter_schema.json`
