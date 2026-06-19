# Refactor Phase 52: Source-Backed MTL Mask Load Policy

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: material mask evidence

## Goal

Start Phase 2 by turning CryEngine source evidence for `.mtl` shader mask loading into a machine-testable policy.

This phase does not change exported `GenMask` values yet. It records which field CryEngine runtime/editor load paths treat as authoritative, so later exporter changes can be made against evidence instead of guesses.

## Source Evidence

Runtime material loading:

```text
CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MatMan.cpp:451-475
```

Observed rule:

```text
read GenMask
if StringGenMask exists:
    EF_GetShaderGlobalMaskGenFromString(shaderName, StringGenMask, GenMask)
else:
    EF_GetRemapedShaderMaskGen(shaderName, GenMask)
```

Editor material loading:

```text
CRYENGINE_Source-release/Code/Sandbox/EditorQt/Material/Material.cpp:887-915
```

It follows the same precedence:

```text
GenMask first
StringGenMask overrides/recomputes through EF_GetShaderGlobalMaskGenFromString when present
GenMask remap fallback when StringGenMask is absent
```

Editor material saving:

```text
CRYENGINE_Source-release/Code/Sandbox/EditorQt/Material/Material.cpp:1132-1137
```

It writes both:

```text
GenMask
StringGenMask
```

Public params:

```text
CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MatMan.cpp:813-830
CRYENGINE_Source-release/Code/Sandbox/EditorQt/Material/Material.cpp:1228-1235
```

The runtime parses `PublicParams` XML attributes into shader params as vector values. The editor saves cached public params, or writes current shader params when no cache exists.

## What Changed

Updated:

```text
output_formats/cryengine_mtl_schema.py
tools/mtl_mask_report.py
```

Added source-backed constants:

```text
MTL_FLAG_MULTI_SUBMTL = 0x0100
MTL_64BIT_SHADERGENMASK = 0x80000
MTL_SHADER_MASK_LOAD_POLICY
```

Added:

```text
shader_mask_load_policy(material_attrs)
```

The policy returns:

```text
StringGenMask -> EF_GetShaderGlobalMaskGenFromString
GenMask -> EF_GetRemapedShaderMaskGen
sub_materials -> skip multi-submaterial container shader mask
shader_default -> no mask attrs present
```

`tools.mtl_mask_report` now includes per-material:

```text
source_load_policy.effective_source
source_load_policy.operation
source_load_policy.source_evidence
```

and summary counts:

```text
source_load_effective_source_counts
```

## Why Exporter Values Did Not Change Yet

The source tells us precedence, not the final numeric mask table for every installation.

`StringGenMask` conversion depends on renderer behavior and common/global shader flag tables. Earlier probes showed that `.ext`, generated globals, and persisted sample `.mtl` values can disagree. Therefore, this phase only makes the effective source visible and testable.

The safe Phase 2 sequence is:

```text
1. Record load/save precedence from source.
2. Compare real Material Editor / RC round-trip output.
3. Replace exporter GenMask/StringGenMask/PublicParams generation only after the numeric behavior is proven.
```

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_mtl_mask_report.py tests\test_mtl_schema_report.py
uv run python -m compileall output_formats\cryengine_mtl_schema.py tools\mtl_mask_report.py tests\test_cryengine_mtl_schema.py tests\test_mtl_mask_report.py
```

New tests cover:

```text
MTL flag constants from IMaterial.h
StringGenMask precedence over GenMask
GenMask remap fallback when StringGenMask is absent
multi-submaterial root shader-mask skip
mtl mask report source_load_policy output
summary counts for effective shader-mask source
```
