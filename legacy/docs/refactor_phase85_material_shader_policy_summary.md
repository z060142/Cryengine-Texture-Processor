# Refactor Phase 85: Material Shader Policy Summary

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: material `GenMask`, `StringGenMask`, and `PublicParams` evidence

## Goal

Make the material diagnostics sidecar easier for tools and Blender plugin work to scan.

Phase 84 added per-material `mtl_shader_policy`. That is detailed enough for inspection, but a plugin or report UI still had to iterate every material just to answer:

```text
which StringGenMask tokens are present in this model
which PublicParams are being emitted
which policies are still compatibility-preserved guesses
```

This phase adds a root-level summary.

## What Changed

Updated:

```text
output_formats/material_diagnostics_exporter.py
```

Added:

```text
mtl_shader_policy_summary
```

Summary fields:

```text
material_count
token_counts
gen_mask_policy_counts
string_gen_mask_source_counts
public_params_policy_counts
public_param_counts
```

The summary is derived from the existing per-material `mtl_shader_policy` rows.

## Current Boundary

This phase does not change generated `.mtl` XML.

It does not change diagnostics severity or hazard counts.

It does not replace compatibility `GenMask` or `PublicParams` values.

The summary is intentionally compact. Full source evidence and per-texture reasons remain in each material row.

## Why This Helps Blender Plugin Work

A plugin can first inspect:

```text
mtl_shader_policy_summary.token_counts
mtl_shader_policy_summary.public_param_counts
mtl_shader_policy_summary.gen_mask_policy_counts
```

Then it can drill into `materials[].mtl_shader_policy` only when it needs material-level reasons.

That avoids treating the sidecar as an opaque blob and makes material-policy problems visible before writing `.mtl`.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_diagnostics_exporter.py tests\test_cryengine_mtl_schema.py
```

Result:

```text
35 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv run python -m compileall core model_processing output_formats tests tools ui ui_pyside utils main.py legacy_tk_main.py
uv lock --check
git diff --check
```

Result:

```text
300 passed
compileall succeeded
uv lock --check succeeded
git diff --check succeeded
```

New coverage proves:

```text
root-level mtl_shader_policy_summary aggregates token counts
summary tracks GenMask/StringGenMask/PublicParams policy labels
summary tracks emitted PublicParams names
written material_diagnostics JSON preserves the summary payload
```
