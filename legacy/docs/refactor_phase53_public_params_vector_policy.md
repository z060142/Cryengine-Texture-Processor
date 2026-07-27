# Refactor Phase 53: Source-Backed PublicParams Vector Policy

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

Phase 2 item: material `PublicParams` evidence

## Goal

Turn CryEngine source evidence for `.mtl` `PublicParams` parsing into a machine-testable converter rule.

This phase does not change exported `PublicParams` defaults yet. It records how CryEngine reads and writes the XML values so later exporter changes can be made against source-backed behavior.

## Source Evidence

Runtime material loading:

```text
CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MatMan.cpp:800-830
```

Observed rule:

```text
Param.m_Value.m_Color[0..3] = 0
sscanf(value, "%f,%f,%f,%f", &x, &y, &z, &w)
```

Therefore:

```text
PublicParams SSSIndex="0"              -> [0, 0, 0, 0]
PublicParams EmittanceMapGamma="1"     -> [1, 0, 0, 0]
PublicParams IndirectColor="0.25,0.25,0.25" -> [0.25, 0.25, 0.25, 0]
```

Editor/material helper save path:

```text
CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp:774-803
```

Observed rule:

```text
byte/short/int/float shader params are saved as scalar XML attributes
FCOLOR/VECTOR shader params are saved as Vec3 XML attributes
```

Editor cache path:

```text
CRYENGINE_Source-release/Code/Sandbox/EditorQt/Material/Material.cpp:523-533
CRYENGINE_Source-release/Code/Sandbox/EditorQt/Material/Material.cpp:1228-1235
```

Observed rule:

```text
if cached PublicParams exist, save the cache
otherwise save current shader resource params through MaterialHelpers::SetXmlFromShaderParams
```

## What Changed

Updated:

```text
output_formats/cryengine_mtl_schema.py
tools/mtl_schema_report.py
```

Added:

```text
MTL_PUBLIC_PARAMS_POLICY
parse_public_param_value(value)
analyze_public_params(public_params)
```

`tools.mtl_schema_report` now includes per-material:

```text
public_param_analysis.<param>.raw
public_param_analysis.<param>.components
public_param_analysis.<param>.parsed_component_count
public_param_analysis.<param>.source_evidence
```

and schema summary:

```text
public_param_component_counts
```

## Why Exporter Values Did Not Change Yet

`PublicParams` names are shader-dependent. The source proves the XML value shape and load/save mechanics, but not the complete valid parameter list for every shader/genmask combination.

The safe Phase 2 sequence is:

```text
1. Record PublicParams parse/save mechanics from source.
2. Use real `.mtl` samples and Material Editor / RC round-trip output to identify stable defaults.
3. Replace exporter `BASE_PUBLIC_PARAMS` and displacement params only after the shader-specific evidence is proven.
```

## Verification

Passed targeted verification:

```powershell
uv run python -m pytest tests\test_cryengine_mtl_schema.py tests\test_mtl_schema_report.py tests\test_material_editor_roundtrip.py
uv run python -m compileall output_formats\cryengine_mtl_schema.py tools\mtl_schema_report.py tests\test_cryengine_mtl_schema.py tests\test_mtl_schema_report.py
```

New tests cover:

```text
scalar PublicParams parsing as vector4 first component
Vec3-style PublicParams parsing with missing W component set to zero
invalid values producing zero parsed components
schema report public_param_analysis output
schema summary component-count distribution
```
