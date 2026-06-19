# Phase 118 - Converter Schema Export

## Why this exists

The converter now has source-backed rules for texture outputs, MTL texture map
names, material attributes, shader-mask policy, and material slot mapping. Those
rules were still spread across Python modules and JSON sidecars.

External tools, especially a future Blender add-on, need one machine-readable
schema that can be generated without importing a model first.

## New tool

```text
tools/converter_schema.py
```

Print schema to stdout:

```text
uv run python tools/converter_schema.py
```

Write schema to a file:

```text
uv run python tools/converter_schema.py --output docs/converter_schema.json
```

## Schema id

```text
cryengine_converter_schema.v1
```

Top-level sections:

```text
material_slot_mapping
texture_outputs
mtl
```

## Material Slot Mapping

The schema exports the same rules as Phase 117:

```text
request_sub_index_is_final_slot
mtl_child_order_matches_final_slots
cgf_subset_material_id_indexes_final_slots
raw_fbx_id_is_one_based
sub_index_limit
```

This is the Blender-plugin-facing rule:

```text
raw_fbx_slot = fbx_material_id - 1
materials[].sub_index = final CryEngine slot
MTL slot = final CryEngine slot
CGF MeshSubset material_id = final CryEngine slot
```

## Texture Outputs

The schema exports batch texture output keys:

```text
diff
spec
ddna
displ
emissive
sss
```

For each key it includes:

```text
texture_type
ce_map_type
expected_suffix
accepted_suffixes
supported_source_extensions
source_evidence
```

The supported RC source image extensions are:

```text
dds
hdr
tif
```

## MTL Rules

The `mtl` section includes:

```text
texture_maps
texture_modifier
material_attributes
mtl_flags
shader_policy
```

`texture_maps.entries` includes both exported CE texture maps and known
internal channels such as `ao` / `glossiness` that are not emitted as MTL
`Texture` nodes.

## Current Boundary

This schema is descriptive, not a validator. It exposes the converter's current
source-backed policy so external tools can generate matching request JSON, MTL
slots, and texture filenames.

Validation remains in the existing diagnostic reports:

```text
texture_output_diagnostics.json
*.material_diagnostics.json
*.material_report.json
```

## Verification

- `uv run python -m pytest tests/test_converter_schema.py tests/test_cryengine_mtl_schema.py tests/test_texture_output_diagnostics.py tests/test_material_slot_mapping.py`
- `uv run python tools/converter_schema.py --output %TEMP%/cryengine_converter_schema_test.json`
