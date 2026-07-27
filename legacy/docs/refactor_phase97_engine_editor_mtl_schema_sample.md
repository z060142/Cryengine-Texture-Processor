# Refactor Phase 97: Engine/Editor MTL Schema Sample

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Run the current `.mtl` schema report against real CryEngine source-release
material samples and preserve the result as a durable evidence artifact.

This phase does not change converter behavior. It turns the schema-report
tooling from previous phases into a concrete sample baseline.

## Sample Set

Input roots:

```text
S:\Crytek\crytek\CRYENGINE_Source-release\Engine
S:\Crytek\crytek\CRYENGINE_Source-release\Editor
```

Generated report:

```text
docs/phase97_engine_editor_mtl_schema_report.json
```

Command:

```powershell
uv run python -m tools.mtl_schema_report S:\Crytek\crytek\CRYENGINE_Source-release\Engine S:\Crytek\crytek\CRYENGINE_Source-release\Editor --output docs\phase97_engine_editor_mtl_schema_report.json
```

## High-Level Results

The report scanned:

```text
33 .mtl files
33 material records
0 multi-submaterial files
13 materials with StringGenMask tokens
```

Most common shaders:

```text
Illum: 17
FogVolume.* / Water* / SkyHDR / Terrain.Layer / helper/editor shaders: sparse singletons
```

Most common material attributes:

```text
Diffuse: 33
GenMask: 33
MtlFlags: 33
Opacity: 33
Shader: 33
Specular: 33
SurfaceType: 33
Shininess: 31
Emissive: 29
MatTemplate: 21
StringGenMask: 21
LayerAct: 15
```

## Attribute Policy Evidence

Compared against the current exporter attribute policy:

```text
matches_export_attribute: 115
missing_export_attribute: 46
differs_from_export_attribute: 136
```

Notable differences:

```text
Shininess=10: 25
Specular=0,0,0: 23
MtlFlags=524288: 14
MtlFlags=0: 12
Opacity=0.99000001: 8
SurfaceType=mat_concrete: 7
```

This supports the Phase 91 decision to treat `Shininess=255` as compatibility
preserved rather than source-backed. In this sample set, `Shininess=10` appears
far more often.

## Texture Evidence

Texture maps found:

```text
Diffuse: 21
Bumpmap: 2
Specular: 2
Custom: 1
```

All texture map names in this sample set are source-backed CE map names:

```text
source_backed_ce_map: 26
unknown_ce_map_type: 0
```

Suffix status:

```text
mismatch_expected_suffix: 25
no_source_backed_suffix: 1
```

This means Engine/Editor materials often use texture file paths that do not
end with the conventional suffix for their `Map` slot. The suffix policy should
remain diagnostic for now, not an export blocker.

TexMod status:

```text
missing_texmod: 25
partial_export_minimal_texmod: 1
```

This supports the Phase 92 caution: default/minimal `TexMod` output should stay
marked compatibility-preserved until round-trip evidence proves whether it
should be omitted for default texture modifiers.

## PublicParams Evidence

Most common `PublicParams` names:

```text
IndirectColor: 12
SSSIndex: 11
EmittanceMapGamma: 3
FresnelBias: 3
FresnelPower: 3
AmbientMultiplier: 2
BlendFactor: 2
BlendFalloff: 2
FresnelScale: 2
GlossFromDiffuse*: 2 each
```

Most common raw values:

```text
IndirectColor=0.25,0.25,0.25: 12
SSSIndex=0: 11
EmittanceMapGamma=1: 3
FresnelBias=1: 2
FresnelPower=4: 2
FresnelScale=1: 2
```

Parsed component counts:

```text
scalar-like values: 59
vec3-like values: 12
```

This is useful evidence for future `PublicParams` replacement work: the
current exporter base params are present in real Engine/Editor samples, but
shader-specific params are also common enough that `PublicParams` must remain
shader/mask-dependent rather than treated as one fixed global schema.

## Boundary

This is a baseline sample, not a final correctness proof.

The sample set is limited to CryEngine source-release Engine/Editor materials.
It does not include user project materials, RC-generated output from arbitrary
FBX files, or Material Editor round-trip output from this machine.

Future sample sets should be kept separate so we can compare:

```text
Engine/Editor source materials
controlled Blender fixture exports
RC-generated material bundles
user project materials
Material Editor round-trip outputs
```

## Verification

The generated JSON artifact is:

```text
docs/phase97_engine_editor_mtl_schema_report.json
```

Checks run:

```text
JSON validity and summary assertions passed
uv run python -m pytest tests\test_mtl_schema_report.py
uv run python -m pytest tests
uv run python -m compileall tools tests
uv lock --check
git diff --check
```

Results:

```text
schema report tests: 2 passed
full test suite: 314 passed
compileall: passed
uv lock --check: passed
git diff --check: passed
```
