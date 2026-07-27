# Refactor Phase 83: Exporter MTL Shader Policy

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: material `GenMask`, `StringGenMask`, and `PublicParams` evidence

## Goal

Make the current exporter-owned `.mtl` shader mask and `PublicParams` decisions explicit and shared.

Before this phase, both the MTL exporter and the generic material converter contained their own small versions of the same rule:

```text
always emit %SUBSURFACE_SCATTERING
normal texture -> %NORMAL_MAP
specular texture -> %SPECULAR_MAP
displacement texture -> %DISPLACEMENT_MAPPING and %PHONG_TESSELLATION
displacement texture -> tessellation PublicParams
```

That duplicated policy made later CryEngine/Material Editor correction risky because one path could be updated while the other kept old guessed behavior.

## What Changed

Extended:

```text
output_formats/cryengine_mtl_schema.py
```

Added:

```text
EXPORT_SHADER_TOKEN_BY_TEXTURE_TYPE
EXPORT_DEFAULT_SHADER_TOKENS
exported_material_shader_policy()
```

`exported_material_shader_policy(textures)` returns:

```text
tokens
token_reasons
gen_mask
gen_mask_source
gen_mask_policy
string_gen_mask
string_gen_mask_source
public_params
public_param_reasons
public_params_policy
source_evidence
```

Updated:

```text
output_formats/mtl_exporter.py
model_processing/material_converter.py
```

Both now derive current `GenMask`, `StringGenMask`, and `PublicParams` from the shared policy helper.

## Current Boundary

This phase preserves the existing exporter behavior.

It does not replace numeric `GenMask` values with source-derived Illum/ext or generated-global values yet.

The policy deliberately marks:

```text
GenMask: compatibility_preserved_until_roundtrip_evidence
PublicParams: compatibility_preserved_until_roundtrip_evidence
StringGenMask token names: source_backed_token_names
```

That distinction matters because previous source and sample probes showed persisted CryEngine `GenMask` values do not cleanly match one simple table.

## Why This Helps Blender Plugin Work

A Blender plugin or external converter can now ask one helper what the current converter would emit for a material's texture set.

That makes these fields inspectable before writing `.mtl`:

```text
StringGenMask tokens
numeric GenMask
PublicParams additions
which texture triggered each token/param
which values are still compatibility guesses
```

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_mtl_exporter.py tests\test_material_converter.py tests\test_mtl_schema_report.py tests\test_mtl_mask_report.py
```

Result:

```text
39 passed
```

Full verification:

```powershell
uv run python -m pytest tests
uv run python -m compileall core model_processing output_formats tests tools ui ui_pyside utils main.py legacy_tk_main.py
uv lock --check
git diff --check
```

Result:

```text
298 passed
compileall succeeded
uv lock --check succeeded
git diff --check succeeded
```

New coverage proves:

```text
shared policy emits the same current token set for normal/specular/displacement textures
shared policy preserves current compatibility GenMask values
shared policy exposes token and PublicParams reasons
MTL exporter output remains compatible
generic MaterialConverter output remains compatible
mask and schema reports still pass with the shared policy in place
```
