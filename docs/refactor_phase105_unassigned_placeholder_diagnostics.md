# Phase 105 - Unassigned Placeholder Diagnostics

## Goal

Treat `unassigned` / `<unassigned>` as a permanent CryEngine asset-pipeline condition, not as a rare cleanup case.

The converter and Blender tooling must preserve material slot indices first. Placeholder materials can be hidden or labeled in UI, but data-layer code must not delete or compress them unless mesh material ids are rewritten and verified.

## Diagnostic Classes

`evaluate_cgf_material_ids()` now reports `unassigned_slot_diagnostics`:

- `gap_unassigned_placeholder`
  - an `unassigned` slot is below the highest CGF material id, but no CGF subset uses it
  - this is an intentional gap holder and must be preserved
- `trailing_unassigned_placeholder`
  - an `unassigned` slot is above the highest CGF material id
  - this is the common trailing CE placeholder and can be visually de-emphasized
- `used_unassigned_material`
  - the CGF actually uses a material id whose request or MTL name is `unassigned` / `<unassigned>`
  - this fails the report because model geometry is assigned to the placeholder material

## Report Fields

`cgf_material_id_alignment` and nested `cgf_import_settings_alignment.import_settings_material_id_alignment` now include:

```json
{
  "unassigned_slot_diagnostics_ok": true,
  "unassigned_slot_diagnostics": [
    {
      "ok": true,
      "type": "trailing_unassigned_placeholder",
      "slot": 16,
      "request_name": "<unassigned>",
      "mtl_slot_name": "<unassigned>",
      "source": ["request", "mtl"],
      "used_by_cgf": false,
      "max_used_material_id": 15
    }
  ]
}
```

Each material-id check also includes `used_unassigned`. If it is true, that check fails even when the id exists in both request and MTL.

## Car Sample Smoke

Generated report:

- `docs/phase105_unassigned_placeholder_diagnostics_report.json`

Command:

```powershell
uv run python -m tools.existing_material_bundle_report "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.cgf" --mtl "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.mtl" --output docs\phase105_unassigned_placeholder_diagnostics_report.json
```

Result:

- `cgf_material_id_alignment_ok: true`
- `cgf_import_settings_alignment_ok: true`
- slot 16 is `trailing_unassigned_placeholder`
- slot 16 is not used by CGF geometry
- highest used CGF material id is 15

## Design Rule

Assume `unassigned` always exists somewhere in real CE workflows.

Tooling should:

- preserve slot indices
- show or hide placeholders as UI state, not by deleting data
- treat gap and trailing placeholders as non-fatal
- fail loudly only when CGF geometry actually uses an unassigned placeholder
