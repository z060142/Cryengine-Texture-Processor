# Refactor Phase 92: Texture Modifier Policy Diagnostics

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Make the exporter `.mtl` `<Texture><TexMod ... /></Texture>` defaults explicit
and visible in diagnostics.

The exporter currently writes a minimal `TexMod` child for every exported
texture:

```text
TexMod_RotateType=0
TexMod_TexGenType=0
TexMod_bTexGenProjected=0
```

This phase preserves that behavior but moves the attributes into the shared
schema policy layer.

## Source Evidence

CryEngine source:

```text
CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp
lines 263-324
```

Important source behavior:

```text
MaterialHelpers saves a TexMod child only when the texture modifier differs
from CryEngine's default texture modifier.
```

That means the current exporter behavior is compatibility-preserved, not proven
final round-trip behavior. If future Material Editor or RC probes show default
TexMod nodes should be omitted, this policy gives us one place to change it.

## Code Changes

Added to `output_formats/cryengine_mtl_schema.py`:

```text
CE_TEXMOD_SOURCE
EXPORT_TEXMOD_DEFAULT_ATTRS
exported_texture_modifier_policy()
```

Updated `output_formats/mtl_exporter.py`:

```text
TexMod attributes now come from exported_texture_modifier_policy()
```

Updated texture map diagnostics:

```text
exported texture map entries now include texmod_policy
mtl_texture_map_policy_summary.texmod_emission_policy_counts
mtl_texture_map_policy_summary.texmod_attribute_status_counts
```

## Boundary

This phase does not change `.mtl` XML output.

It intentionally labels the minimal TexMod emission as:

```text
compatibility_preserved_emits_minimal_texmod
```

and the three default attributes as:

```text
compatibility_preserved_default_texmod
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_mtl_exporter.py tests\test_material_diagnostics_exporter.py
```

Result:

```text
58 passed
```
