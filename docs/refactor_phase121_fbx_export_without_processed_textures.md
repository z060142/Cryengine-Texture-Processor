# Phase 121 - FBX Export Without Processed Textures

## Why this exists

The FBX/JSON/RC export path was still coupled to processed texture discovery:

```text
if not export_context.fbx_texture_data:
    skip FBX export
```

That is wrong for the material-slot goal. A model can have valid material slots
and a valid RC request even when the texture batch has not been run yet.

Texture availability should be a warning, not a blocker for checking whether
RC produces a CGF with correct material ids.

## Change

`main.run_model_fbx_export()` no longer skips export when `fbx_texture_data` is
empty.

Instead it asks:

```text
model_processing.model_export_context.fbx_texture_export_diagnostics(context)
```

When no processed texture paths were resolved, the diagnostic is:

```text
fbx_export_no_processed_textures
```

Severity:

```text
warning
```

The export continues:

```text
FBX -> JSON -> optional RC import -> material diagnostics sidecar
```

`FbxExporter` already has diffuse fallback behavior for material texture nodes,
so this change lets that fallback run instead of being blocked by the UI flow.

## Sidecar integration

`output_formats.material_diagnostics_exporter` now accepts:

```text
extra_diagnostics
```

The FBX/JSON export flow passes `fbx_export_no_processed_textures` into the
material diagnostics sidecar, so the warning is durable and visible in reports.

## Boundary

This does not claim textures are correct when they are absent. It only prevents
missing processed texture paths from blocking material-slot verification.

Texture correctness remains covered by:

```text
texture_output_diagnostics.json
*.material_diagnostics.json
```

## Verification

- `uv run python -m pytest tests/test_model_export_context.py tests/test_material_diagnostics_exporter.py tests/test_fbx_exporter.py`
- `uv run python -m compileall main.py model_processing output_formats tests`
- `uv run python -m pytest`
- `uv lock --check`
- `uv run python tools/converter_schema.py --check docs/converter_schema.json`
- `git diff --check`
