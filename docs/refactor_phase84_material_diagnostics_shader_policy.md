# Refactor Phase 84: Material Diagnostics Shader Policy

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: material `GenMask`, `StringGenMask`, and `PublicParams` evidence

## Goal

Expose the current exporter `.mtl` shader policy in the material diagnostics sidecar.

Phase 83 created one shared policy helper for current `GenMask`, `StringGenMask`, and `PublicParams` decisions. This phase makes that policy visible per material in:

```text
<model>.material_diagnostics.json
```

## What Changed

Updated:

```text
output_formats/material_diagnostics_exporter.py
```

Each material row now includes:

```text
mtl_shader_policy
```

The policy includes:

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

## Current Boundary

This phase does not change generated `.mtl` XML.

It does not replace numeric `GenMask` values.

It only makes current exporter behavior visible in diagnostics so plugin/tooling work can inspect why a material will receive a token, numeric mask, or public parameter.

The important policy labels remain:

```text
GenMask: compatibility_preserved_until_roundtrip_evidence
PublicParams: compatibility_preserved_until_roundtrip_evidence
StringGenMask token names: source_backed_token_names
```

## Why This Helps Blender Plugin Work

The diagnostics sidecar is now useful as a bridge between source material inspection and final `.mtl` output.

A Blender plugin can inspect:

```text
which texture types triggered %NORMAL_MAP, %SPECULAR_MAP, or displacement/tessellation tokens
which PublicParams came from the displacement compatibility path
which values are still guesses rather than final CryEngine/Material Editor truth
```

That keeps material authoring tools from treating compatibility values as proven CryEngine facts.

## Verification

Targeted verification:

```powershell
uv run python -m pytest tests\test_material_diagnostics_exporter.py tests\test_cryengine_mtl_schema.py tests\test_mtl_exporter.py tests\test_material_converter.py
```

Result:

```text
53 passed
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
299 passed
compileall succeeded
uv lock --check succeeded
git diff --check succeeded
```

New coverage proves:

```text
material diagnostics rows include mtl_shader_policy
normal/specular/displacement texture inputs expose token and PublicParams reasons
written material_diagnostics JSON preserves the shader policy payload
existing MTL exporter and MaterialConverter behavior remains compatible
```
