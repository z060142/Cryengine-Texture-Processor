# Phase 101 - CGF ImportSettings Roundtrip Alignment

## Goal

Make the material mapping report verify the RC output path that matters for FBX conversion:

1. original request JSON `materials[]`
2. CGF embedded `ImportSettings` JSON `materials[]`
3. generated MTL sub-material slots
4. CGF `MtlName` sub-material table and used mesh material ids

Phase 99 proved that `sub_index` in `ImportSettings` is the RC-facing final material slot. Phase 101 turns that evidence into a reusable report check, so a real RC output can be inspected without manually comparing three files.

## Implementation

Updated `tools/material_mapping_report.py`:

- refactored request material normalization into `_normalize_request_material_rows()`
- added `evaluate_cgf_import_settings_roundtrip()`
- added `cgf_import_settings_alignment` to `build_material_mapping_report()`

The new report section contains:

- `import_settings_materials`: normalized material rows from the CGF embedded request
- `request_vs_import_settings`: order/name/`sub_index`/`physicalize` comparison
- `import_settings_vs_mtl`: existing request-to-MTL slot alignment applied to embedded ImportSettings
- `import_settings_vs_cgf_mtl_name`: CGF `MtlName` sub-material name checks by slot
- `import_settings_material_id_alignment`: used CGF material ids must exist in ImportSettings and MTL
- `invalid_request_entries` and `invalid_import_settings_entries`: malformed material rows on either side
- `extra_import_settings_slots`: request slots that are not present in CGF `MtlName`; this is expected for unused slots such as `<unassigned>`

This deliberately does not remove fixture-level `expected_cgf_material_id`. Controlled fixtures still need explicit expected polygon ids; the new checker covers real RC output metadata.

## Car Sample Smoke

Sample:

- `S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.cgf`
- `S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.mtl`

Result from the new evaluator:

```json
{
  "ok": true,
  "import_settings_error": "",
  "request_vs_import_settings_ok": true,
  "import_settings_vs_mtl_ok": true,
  "import_settings_vs_cgf_mtl_name_ok": true,
  "material_id_alignment_ok": true,
  "extra_import_settings_slots": [
    {
      "sub_index": 16,
      "name": "<unassigned>"
    }
  ],
  "cgf_mtl_name_sub_material_count": 16,
  "material_count": 17
}
```

Interpretation:

- CGF embeds the RC request material table.
- The embedded `materials[].sub_index` values align with MTL slots.
- CGF `MtlName` contains the used sub-material prefix, not every request/MTL slot.
- An unused `<unassigned>` request slot can remain in ImportSettings and MTL without appearing in CGF `MtlName`.

## Verification

```powershell
uv run python -m pytest tests\test_material_mapping_report.py
```

Result:

```text
29 passed
```
