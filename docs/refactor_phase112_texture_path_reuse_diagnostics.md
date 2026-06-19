# Phase 112 - Texture Path Reuse Diagnostics

## Why this exists

Phase 110's rough `dev_example` run showed a remaining material mapping smell:

```text
cliff_bush:
  Diffuse   -> ./model/rock_face_01_diff.dds
  Specular  -> ./model/rock_face_01_diff.dds
  Heightmap -> ./model/rock_face_01_diff.dds
  Opacity   -> ./model/rock_face_01_diff.dds
```

The existing suffix diagnostics caught the Specular and Heightmap mismatches,
but the more useful workflow signal is that one texture path is being reused
across different CryEngine texture map slots with different source-backed suffix
expectations.

## Rule

The diagnostic is intentionally conservative.

Warn only when:

1. one normalized texture path is assigned to more than one CE texture map slot
2. at least two of those slots have source-backed expected suffixes
3. those expected suffixes are different

This means `Diffuse + Opacity` sharing a diffuse texture does not warn by
itself, because the current CE suffix table has no source-backed Opacity suffix
and diffuse alpha can be a plausible authoring path.

## New diagnostic

```text
code: shared_texture_path_across_ce_maps
severity: warning
```

Payload includes:

- `texture_path`
- `normalized_texture_path`
- `ce_map_types`
- `expected_suffixes`
- `suffix_statuses`
- `entries`
- `source_evidence`

The diagnostic is not an RC blocker. It is evidence that the material mapping
probably needs author review or exporter repair.

## Implementation

Shared helper:

```text
output_formats.cryengine_mtl_schema.analyze_ce_texture_path_reuse()
```

Consumers:

- `output_formats.material_diagnostics_exporter`
- `tools.mtl_schema_report`

The same logic now covers generated material diagnostics and direct `.mtl`
sample audits.

## Dev example result

Generated:

```text
docs/phase112_dev_example_texture_reuse_report.json
```

The report finds exactly one reuse warning:

```text
file: dev_example/cliff_side1.mtl
material: cliff_bush
code: shared_texture_path_across_ce_maps
texture_path: ./model/rock_face_01_diff.dds
ce_map_types: Diffuse, Heightmap, Opacity, Specular
expected_suffixes: _diff, _displ, _spec
```

This preserves `_ddna` Bumpmap alias handling and does not flag the benign
Diffuse/Opacity-only boundary.

## Blender/plugin impact

When building a Blender exporter or material repair UI, this diagnostic should
surface as a material mapping warning:

- likely wrong Specular assignment when a `_diff` path is used as Specular
- likely wrong Heightmap assignment when a `_diff` path is used as Heightmap
- not enough by itself to delete or rewrite Opacity

## Verification

- `uv run python -m pytest tests/test_cryengine_mtl_schema.py tests/test_material_diagnostics_exporter.py tests/test_mtl_schema_report.py`
- `uv run python tools/mtl_schema_report.py dev_example --output docs/phase112_dev_example_texture_reuse_report.json`
