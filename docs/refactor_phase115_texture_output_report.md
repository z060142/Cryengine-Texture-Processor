# Phase 115 - Batch Texture Output Diagnostics Report

## Why this exists

Phase 114 made each processed `TextureGroup` carry CE/RC texture output
diagnostics in memory. That was useful for tests, but not enough for the user
flow: after a rough batch export, the user needs a durable file that says which
outputs are usable by RC and which ones drifted from CryEngine naming rules.

This phase writes a sidecar report at the end of texture batch processing.

## Report file

Default path:

```text
<texture_output_directory>/texture_output_diagnostics.json
```

Schema id:

```text
cryengine_texture_output_diagnostics.v1
```

Top-level fields:

```text
schema
source
summary
groups
```

`summary` contains:

```text
group_count
output_count
diagnostic_count
ok
```

Each group entry contains:

```text
base_name
outputs
output_policy
diagnostics
diagnostic_count
ok
```

The group `output_policy` is generated from the same rules introduced in Phase
114:

```text
output_formats.texture_output_diagnostics.build_texture_output_policy
```

## User-flow integration

`core.batch_processor.BatchProcessor` now writes the sidecar after all texture
outputs are generated and stores the result on:

```text
texture_output_report_path
texture_output_report
```

The PySide entry point reads those fields after the batch worker finishes and
surfaces the diagnostic count plus report path in the existing progress/status
UI.

This keeps the first UI integration intentionally small: the user can run the
normal batch texture flow, then inspect the JSON report without needing a new
panel or a separate command-line probe.

## Boundary

The report is diagnostic-only. It does not rename files, delete files, or block
export. A warning means the converter produced an output that should be
reviewed before feeding the asset to RC.

Current warning codes:

- `unsupported_rc_texture_output_extension`
- `mismatch_texture_output_suffix`
- `unknown_texture_output_key`

## Verification

- `uv run python -m pytest tests/test_texture_output_diagnostics.py`
- `uv run python -m pytest tests/test_texture_output_diagnostics.py tests/test_core_managers.py tests/test_material_texture_resolver.py tests/test_emissive_exporter.py`
- `uv run python -m pytest`
- `uv run python -m compileall core output_formats main.py`
- `uv lock --check`
- `git diff --check`
- Rough batch flow with generated 4x4 diffuse/normal inputs produced
  `texture_output_diagnostics.json` with `group_count=1`, `output_count=2`,
  `diagnostic_count=0`.
