# Phase 113 - PySide MTL Texture Diagnostics

## Why this exists

Phase 112 added `shared_texture_path_across_ce_maps` to JSON sidecar reports
and direct `.mtl` sample audits. That was useful, but a user running the PySide
model workflow would still only see slot/manifest/load-state diagnostics in the
Material Slot Diagnostics table.

The UI needs to surface the same MTL texture-map warnings so FBX/material
mapping issues are visible without manually opening JSON.

## What changed

`output_formats.material_diagnostics_exporter` now exposes:

```text
collect_mtl_texture_map_diagnostics(report_item)
```

The old private name is kept as an alias for the existing sidecar builder.

`ui_pyside.model_import.collect_model_material_diagnostics()` now builds the
same `mtl_texture_map_policy` for each assigned material record and feeds it
through that shared helper.

This makes PySide show warnings such as:

- `mismatch_ce_texture_suffix`
- `unsupported_rc_texture_source_extension`
- `shared_texture_path_across_ce_maps`

## Boundary

The UI collector does not rewrite material assignments. It only surfaces the
same warnings already used by the sidecar diagnostics.

`Diffuse + Opacity` sharing is still allowed by the shared helper, because
Opacity has no source-backed suffix in the current CE table and diffuse alpha is
a plausible authoring path.

## Verification

Targeted:

```powershell
uv run python -m pytest tests/test_pyside_model_import_diagnostics.py tests/test_material_diagnostics_exporter.py tests/test_cryengine_mtl_schema.py
```

The added PySide tests cover:

- `_diff` reused across Diffuse, Specular, Heightmap, and Opacity surfaces as
  material diagnostics
- Diffuse/Opacity-only sharing remains quiet
