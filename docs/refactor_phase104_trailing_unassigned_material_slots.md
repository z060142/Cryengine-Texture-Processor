# Phase 104 - Trailing Unassigned Material Slots

## Goal

Make the material report distinguish two different CGF `MtlName` gaps:

1. a trailing unused `<unassigned>` slot that RC keeps in ImportSettings/MTL but omits from CGF `MtlName`
2. a real material slot that disappeared from CGF `MtlName`

The first case is expected CE behavior. The second case is a converter hazard.

## Evidence

Sample bundle:

- `S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.cgf`
- `S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.mtl`

Report:

- `docs/phase104_car_trailing_unassigned_material_report.json`

Key values from the report:

```json
{
  "import_settings_meta": {
    "chunk_id": 173,
    "version": 0,
    "material_count": 17
  },
  "cgf_mtl_name_sub_material_count": 16,
  "extra_import_settings_slots": [
    {
      "ok": true,
      "type": "trailing_unassigned_slot_omitted_from_cgf",
      "sub_index": 16,
      "name": "<unassigned>",
      "physicalize": "no",
      "trailing": true,
      "unassigned": true,
      "cgf_mtl_name_sub_material_count": 16
    }
  ],
  "material_ids": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
}
```

## Rule

When comparing CGF embedded ImportSettings materials to CGF `MtlName` sub-materials:

- a missing CGF `MtlName` slot is accepted only when the ImportSettings slot is trailing and its normalized name is `<unassigned>` or `unassigned`
- that accepted case is reported as `trailing_unassigned_slot_omitted_from_cgf`
- any missing slot with a real material name is reported as `missing_cgf_mtl_name_slot` and fails the report

This rule does not change request or MTL generation. It only prevents diagnostics from treating RC's unused trailing placeholder as a material mapping failure.

## Implementation

Updated `tools/material_mapping_report.py`:

- added `_is_unassigned_slot_name()`
- added `_classify_extra_import_settings_slot()`
- added `extra_import_settings_slots_ok`
- made non-placeholder extra ImportSettings slots fail `import_settings_vs_cgf_mtl_name.ok`

Updated `tests/test_material_mapping_report.py`:

- expanded the expected trailing `<unassigned>` case
- added a negative case where a real `Proxy` material is present in ImportSettings/MTL but absent from CGF `MtlName`

## Verification

```powershell
uv run python -m pytest tests\test_material_mapping_report.py
uv run python -m tools.existing_material_bundle_report "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.cgf" --mtl "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.mtl" --output docs\phase104_car_trailing_unassigned_material_report.json
```

Results:

- `34 passed`
- `cgf_import_settings_alignment_ok: true`
