# Refactor Phase 33: Common Global Mask Rebuild

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Reproduce CryEngine's common global shader flag table closely enough to keep investigating `.mtl` `GenMask` values.

Phase 32 proved that real persisted `GenMask` values do not equal:

```text
Illum.ext local token OR
exporter compatibility OR
partial ShaderCore legacy-fix OR
```

This phase implements the next part of `ShaderCore.cpp` in Python.

## Source Evidence

`ShaderCore.cpp` builds common global flags by:

1. scanning `Engine/Shaders/*.ext`
2. using only `.ext` files containing `UsesCommonGlobalFlags`
3. collecting every `Name = %TOKEN`
4. storing names in a sorted map
5. assigning `1 << index`
6. applying `mfInitCommonGlobalFlagsLegacyFix`
7. swapping any duplicate masks caused by the legacy replacement

`Renderer.cpp` confirms the runtime call used by `MatMan.cpp`:

```text
EF_GetShaderGlobalMaskGenFromString(shaderName, stringGenMask, oldMask)
```

If the shader uses common globals, the renderer returns the mask computed from `StringGenMask`.

## What Changed

Added:

```text
tools/cryengine_shader_flags.py
```

It provides:

```text
extract_common_global_tokens_from_ext(ext_text)
collect_common_global_tokens(shader_ext_dir)
build_common_global_flag_table(tokens)
build_common_global_flag_table_from_dir(shader_ext_dir)
```

Updated:

```text
tools/mtl_mask_report.py
```

New option:

```powershell
--shader-ext-dir "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\Shaders"
```

When provided, reports also include:

- `common_global_generated_mask`
- `matches_common_global_generated_mask`
- generated table source path and token count

## Real Sample Report

Generated:

```text
docs/phase33_mtl_mask_common_global_samples.json
```

Command:

```powershell
uv run python -m tools.mtl_mask_report "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\EngineAssets\Materials\material_default.mtl" "S:\Crytek\crytek\CRYENGINE_Source-release\Editor\Objects\mtlobjects.mtl" "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\EngineAssets\Materials\MeshImporter\MI_PreviewVertexColor.mtl" --shader-ext-dir "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\Shaders" --output docs\phase33_mtl_mask_common_global_samples.json
```

Summary:

```json
{
  "file_count": 3,
  "material_count": 3,
  "tokenized_material_mismatch_count": 3,
  "unknown_illum_token_count": 1,
  "unknown_common_global_legacy_fix_token_count": 5,
  "unknown_common_global_generated_token_count": 1,
  "common_global_generated_match_count": 0
}
```

The current source-derived common global table has 51 tokens.

Important result:

```text
material_default.mtl
StringGenMask = %SUBSURFACE_SCATTERING
persisted GenMask = 0x80000000
source-derived common global generated mask = 0x4000000000000
```

So the current `.ext` source tree does not reproduce the persisted engine asset `GenMask` values by itself.

## Rule

Do not switch exporter `GenMask` to the current source-derived common global table yet.

The evidence now says there are at least three different mask domains in play:

```text
Illum.ext local property masks
ShaderCore common global generated/remapped masks
persisted engine asset GenMask values
```

The persisted sample values likely depend on a saved globals table, legacy asset history, build-time conditionals, or an older generated table not present in this source checkout.

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_cryengine_shader_flags.py tests\test_mtl_mask_report.py tests\test_cryengine_mtl_schema.py
```

New tests cover:

- requiring `UsesCommonGlobalFlags` before collecting `.ext` names
- token uppercasing
- sorted-map bit assignment
- legacy-fix mask replacement and duplicate swap
- loading a generated common global table from a shader directory
- using `--shader-ext-dir` data in an `.mtl` mask report

## Remaining Work

- Locate any generated `globals.txt` / shader cache created by the actual 5.7.1 installation.
- Probe real RC behavior with mismatched `GenMask` and `StringGenMask`.
- Decide whether exporter should omit `GenMask`, preserve compatibility values, or write a source-derived generated value.
- Extend the report to compare `.mtl` before/after RC or Material Editor reload/save.
