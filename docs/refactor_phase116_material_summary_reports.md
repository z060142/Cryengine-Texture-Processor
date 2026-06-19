# Phase 116 - Material Diagnostic Summary Reports

## Why this exists

The converter already writes detailed material diagnostics, but the reports were
too deep for the normal user flow. A developer had to open the full JSON and
manually count whether a finding was a real blocker, a texture-map warning, or a
benign CryEngine `unassigned` placeholder.

This phase adds stable summary fields so model export and RC smoke flows can
surface material state without re-parsing the full evidence tree.

## General material diagnostics

`output_formats.material_diagnostics_exporter` now adds:

```text
diagnostic_summary
```

Fields:

```text
severity_counts
code_counts
hazard_count
warning_count
mtl_texture_map_warning_count
action_required
```

The existing `summary` block is unchanged:

```text
material_count
diagnostic_count
hazard_count
```

This keeps old callers stable while giving UI/tools a safer summary surface.

## RC material mapping reports

`tools.material_mapping_report` now adds a top-level:

```text
summary
```

Fields include:

```text
slot_alignment_ok
cgf_material_id_alignment_ok
cgf_import_settings_alignment_ok
fixture_material_semantic_alignment_ok
request_material_count
mtl_slot_count
cgf_material_id_count
failed_material_id_check_count
unassigned_slot_counts
unassigned_placeholder_count
used_unassigned_material_count
unassigned_slots_ok
action_required
```

Both report builders use the same summary helper:

```text
summarize_material_mapping_report(report)
```

This applies to fresh RC smoke output reports and existing CGF/MTL report
inspection.

## Unassigned rule

`unassigned` / `<unassigned>` is treated as a normal CryEngine condition.

Benign:

```text
gap_unassigned_placeholder
trailing_unassigned_placeholder
```

Hazard:

```text
used_unassigned_material
```

The PySide RC smoke summary now prefers the report summary:

```text
unassigned placeholders xN
used unassigned xN
```

This keeps permanent placeholders visible without turning them into false
failures.

## Verification

- `uv run python -m pytest tests/test_material_diagnostics_exporter.py tests/test_material_mapping_report.py tests/test_pyside_model_import_diagnostics.py`
