# Phase 111 - Emissive Output Suffix Policy

## Why this exists

Phase 110's dev example flow left one naming-policy question:

```text
Map="Emittance" File="*_emissive.dds"
```

The converter also still generated `_emissive.tif` for emissive output. That is
useful as an input naming alias, but it is not the suffix CryEngine's source
uses for the Emittance texture slot.

## Source-backed rule

CryEngine source evidence:

- `Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp`
  - `EFTT_EMITTANCE -> Map="Emittance" -> "_em"`
- `Code/CryEngine/RenderDll/Common/Textures/TextureHelpers.cpp`
  - `EFTT_EMITTANCE -> "_em" -> "TM_Emittance" -> "$TEX_Emittance"`

Repository search found no material texture suffix evidence for `_emissive` in
the CryEngine source tree. It appears in sample/output data as an authoring
alias, not as the CE-backed output suffix.

## What changed

Current converter output now uses:

```text
emissive -> *_em.tif
```

Updated paths:

- `output_formats/emissive_exporter.py`
- `model_processing/material_texture_resolver.py`
- PySide/Tk export-setting labels that advertise output suffixes
- `legacy_tk_main.py` legacy MTL processed-texture lookup
- README/UI labels that advertise output suffixes

The input resolver still accepts source names such as:

- `*_emissive`
- `*_emission`
- `*_glow`
- `*_em`
- `*_e`

This is deliberate. Input classification can be broad, while generated
CryEngine/RC-facing output should be source-backed.

## Flow check

A rough end-to-end resolver/diagnostic probe was run:

1. source texture name: `wall_emissive.png`
2. processed output present: `wall_em.tif`
3. `build_mtl_material_data()` resolved:
   - `textures.emissive -> wall_em.tif`
4. `build_material_diagnostics_report()` returned:
   - no diagnostics
   - suffix status `matches_expected_suffix`

## Remaining boundary

Existing sample reports and old source assets may still contain `_emissive`.
Those should remain readable as input evidence, but new generated output should
prefer `_em`.

The dev example file `cliff_side1.mtl` still contains
`cliff_side_emissive.dds`; that remains a useful fixture for detecting non-CE
output naming.

## Verification

- `uv run python -m pytest tests/test_emissive_exporter.py tests/test_material_texture_resolver.py tests/test_texture_type_resolver.py tests/test_core_managers.py tests/test_mtl_exporter.py tests/test_material_diagnostics_exporter.py`
