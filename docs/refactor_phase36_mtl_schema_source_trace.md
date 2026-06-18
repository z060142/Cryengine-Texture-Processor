# Refactor Phase 36: MTL Schema Source Trace

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Trace CryEngine `.mtl` material load/save behavior from source and summarize real material XML schema usage.

Previous phases showed:

- persisted `GenMask` values do not match the current `.ext` table
- persisted `GenMask` values do not match current `globals.txt`
- RC FBX import accepts missing or contradictory mask fields

This phase moves from RC acceptance to material runtime/editor behavior.

## Source Evidence

Runtime load path:

```text
Code/CryEngine/Cry3DEngine/MatMan.cpp
CMatMan::MakeMaterialFromXml()
```

Load rule:

1. read `MtlFlags`
2. read `Shader`
3. read `GenMask`
4. if not marked `MTL_64BIT_SHADERGENMASK`, remap 32-bit flags through renderer
5. if `StringGenMask` exists, call `EF_GetShaderGlobalMaskGenFromString(shaderName, stringGenMask, currentMask)`
6. load lighting attributes, textures, legacy migrations, `PublicParams`, material layers, then sub-materials

Editor load/save path:

```text
Code/Sandbox/EditorQt/Material/Material.cpp
CMaterial::Serialize()
```

Editor load mirrors runtime:

```text
GenMask first
StringGenMask overrides through EF_GetShaderGlobalMaskGenFromString()
```

Editor save writes:

```text
MtlFlags | MTL_64BIT_SHADERGENMASK
Shader
GenMask
StringGenMask = EF_GetStringFromShaderGlobalMaskGen(shaderName, genMask)
SurfaceType
MatTemplate
lighting attributes
textures
PublicParams
MaterialLayers
SubMaterials
```

Shader public params:

```text
Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp
MaterialHelpers::SetShaderParamsFromXml()
MaterialHelpers::SetXmlFromShaderParams()
```

Rule:

```text
PublicParams attributes are shader parameter names.
Known params are parsed by type.
Unknown params are preserved as a shader param with up to four float components.
```

So `PublicParams` is not a single fixed schema; it depends on the selected shader and generation mask.

## What Changed

Added:

```text
tools/mtl_schema_report.py
```

The report scans `.mtl` files and summarizes:

- material tags
- material attributes
- child tags
- shaders
- `GenMask` literals
- `StringGenMask` strings and tokens
- `PublicParams`
- texture map names and `TexMod` attributes
- per-shader attribute / public-param / texture-map usage

## Generated Reports

Summary report:

```text
docs/phase36_mtl_schema_engine_editor_summary.json
```

Command:

```powershell
uv run python -m tools.mtl_schema_report "S:\Crytek\crytek\CRYENGINE_Source-release\Engine" "S:\Crytek\crytek\CRYENGINE_Source-release\Editor" --summary-only --value-limit 20 --output docs\phase36_mtl_schema_engine_editor_summary.json
```

Key sample report:

```text
docs/phase36_mtl_schema_key_samples.json
```

Command:

```powershell
uv run python -m tools.mtl_schema_report "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\EngineAssets\Materials\material_default.mtl" "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\EngineAssets\Materials\MeshImporter\MI_PreviewVertexColor.mtl" "S:\Crytek\crytek\CRYENGINE_Source-release\Engine\EngineAssets\Materials\Water\ocean_default.mtl" "S:\Crytek\crytek\CRYENGINE_Source-release\Editor\Objects\mtlobjects.mtl" --value-limit 20 --output docs\phase36_mtl_schema_key_samples.json
```

## Observed Sample Shape

Engine/Editor summary:

```json
{
  "file_count": 33,
  "material_count": 33,
  "multi_material_file_count": 0,
  "tokenized_material_count": 13
}
```

Most common material attributes:

```text
Diffuse
GenMask
MtlFlags
Opacity
Shader
Specular
SurfaceType
Shininess
Emissive
MatTemplate
StringGenMask
LayerAct
vertModifType
AlphaTest
```

Most common child nodes:

```text
Textures
PublicParams
MaterialLayers
```

Most common texture maps in this sample:

```text
Diffuse
Bumpmap
Specular
Custom
```

Most common tokens:

```text
%SUBSURFACE_SCATTERING
%ALLOW_SILHOUETTE_POM
%BILLBOARD
%BLENDLAYER
%BUMP_MAP
%NORMAL_MAP
%SPECULAR_MAP
%SPEC_MAP
%TEMP_TERRAIN
%VERTCOLORS
```

## Rule

For our exporter:

1. Keep `.mtl` XML conservative and close to Editor save output.
2. Treat root `Material` and sub `Material` records as the same schema.
3. Preserve material slot order separately from shader attributes.
4. Do not treat RC success as material correctness.
5. Treat `PublicParams` as shader-dependent key/value data, not as a globally fixed field list.
6. For now, continue preserving compatibility `GenMask` behavior until Material Editor reload/save proves the correct policy.

The important mask rule from source is:

```text
If StringGenMask exists, runtime/editor load passes it through EF_GetShaderGlobalMaskGenFromString().
Editor save writes both GenMask and a regenerated StringGenMask.
```

That means the next decisive probe is still Editor reload/save:

```text
input .mtl variant -> load in Material Editor -> save -> compare GenMask/StringGenMask/PublicParams
```

## Verification

Passed:

```powershell
uv run python -m pytest tests\test_mtl_schema_report.py tests\test_mtl_mask_report.py
```

New tests cover:

- root material schema summary
- sub-material schema summary
- texture map and `TexMod` extraction
- `PublicParams` extraction
- summary-only output without per-file records
