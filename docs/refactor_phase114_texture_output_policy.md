# Phase 114 - Texture Output Policy Diagnostics

## Why this exists

The converter now has source-backed MTL texture map and RC source-extension
diagnostics, but the raw texture batch path did not attach those checks to the
processed texture outputs themselves.

This phase makes each processed `TextureGroup` carry a small output policy
report after batch export.

## Output key mapping

Processed output keys map to CE material texture types as follows:

```text
diff     -> diffuse      -> Diffuse    -> _diff
spec     -> specular     -> Specular   -> _spec
ddna     -> normal       -> Bumpmap    -> _ddn / _ddna accepted
displ    -> displacement -> Heightmap  -> _displ
emissive -> emissive     -> Emittance  -> _em
sss      -> subsurface   -> SubSurface -> _sss
```

The policy uses the shared rules from:

```text
output_formats.cryengine_mtl_schema
```

That means the texture batch path now checks the same CE suffix and RC source
extension expectations used by material diagnostics.

## New module

```text
output_formats.texture_output_diagnostics
```

Main entry point:

```text
build_texture_output_policy(output_paths)
```

Returns:

```text
entries
diagnostics
diagnostic_count
ok
```

Diagnostic codes:

- `unsupported_rc_texture_output_extension`
- `mismatch_texture_output_suffix`
- `unknown_texture_output_key`

## BatchProcessor integration

After `_generate_output_formats(group)`, each `TextureGroup` now has:

```text
group.output_policy
group.output_diagnostics
```

These diagnostics do not block export. They are meant to make rough batch runs
tell us when output filenames or extensions drift away from RC/CE expectations.

## Current boundary

The policy reports on paths currently present in `group.output`. It does not
yet write a separate sidecar file for texture batches and does not rewrite
filenames. Exporter filename fixes should remain explicit, source-backed edits.

## Verification

- `uv run python -m pytest tests/test_texture_output_diagnostics.py tests/test_core_managers.py tests/test_material_texture_resolver.py tests/test_emissive_exporter.py`
