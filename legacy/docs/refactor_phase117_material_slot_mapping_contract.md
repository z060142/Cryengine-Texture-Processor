# Phase 117 - Material Slot Mapping Contract

## Why this exists

The material slot rules were already encoded in assignment code, RC smoke
reports, and older probe notes. The problem was discoverability: building a
custom converter or Blender add-on still required reading several modules and
phase documents to answer one question:

```text
Which number is the FBX source slot, and which number is the final CryEngine slot?
```

This phase adds a compact mapping contract to material diagnostics.

## New module

```text
model_processing.material_slot_mapping
```

Main entry point:

```text
build_material_slot_mapping_contract(material_items)
```

Schema id:

```text
cryengine_material_slot_mapping.v1
```

## Contract rules

The contract repeats the rules that matter to tool authors:

```text
request_sub_index_is_final_slot
mtl_child_order_matches_final_slots
cgf_subset_material_id_indexes_final_slots
raw_fbx_id_is_one_based
sub_index_limit
```

Important mapping:

```text
FBX material id      -> one-based source id
raw_fbx_slot         -> fbx_material_id - 1
materials[].sub_index -> final CryEngine sub-material id
MTL SubMaterials order -> final sub_index table
CGF MeshSubset material_id -> final sub_index table
```

This means source FBX slot order is useful evidence, but `sub_index` is the
number RC writes into the final CGF material table.

## Report integration

`output_formats.material_diagnostics_exporter` now includes:

```text
slot_mapping_contract
```

Top-level contract fields:

```text
schema
rules
summary
mappings
```

`summary` contains:

```text
material_count
emitted_material_count
deleted_material_count
out_of_range_deleted_count
duplicate_final_slot_count
final_slot_count
gap_slot_count
gap_slots
assignment_reason_counts
status_counts
```

Each mapping contains:

```text
name
original_name
source_order
fbx_material_id
raw_fbx_slot
final_sub_index
mtl_slot
cgf_material_id
requested_sub_index
assignment_reason
status
deleted
duplicate_final_slot
duplicate_final_slot_material_names
```

## Status meanings

```text
emitted_final_slot
```

The material is emitted to request JSON and MTL. `final_sub_index`, `mtl_slot`,
and `cgf_material_id` are the same final CryEngine slot id.

```text
deleted
```

The material has `sub_index = -1` and is not emitted into the final MTL slot
table.

```text
out_of_range_deleted
```

The requested final slot was at or above RC's `MAX_SUB_MATERIALS` limit and was
normalized to `-1`.

```text
not_emitted
```

The material did not produce a valid final slot for another reason.

## Unassigned placeholders

Gap slots are reported in:

```text
summary.gap_slots
```

Those gaps are expected to become `unassigned` placeholders in the expanded MTL
slot table. A placeholder is not a failure unless CGF geometry actually uses
that slot; that check remains in RC material mapping reports.

## Verification

- `uv run python -m pytest tests/test_material_slot_mapping.py tests/test_material_diagnostics_exporter.py tests/test_material_slot_table.py tests/test_material_index_assigner.py`
