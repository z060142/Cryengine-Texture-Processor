# Refactor Phase 98: Car Example Material Alignment

Date: 2026-06-19
Branch: `feat/fbx-material-mapping`

## Goal

Use the user-provided real car sample to compare the material identity chain
across:

```text
source FBX
RC output CGF
RC output MTL
CryAsset metadata
```

The sample lives outside the converter repository:

```text
S:\Crytek\crytek\Stripped to the bone\example\car
```

This phase adds evidence extraction and documentation only. It does not change
export behavior.

## Sample Files

```text
kb3d_citycarsessentialssedan-native.fbx
kb3d_citycarsessentialssedan-native.cgf
kb3d_citycarsessentialssedan-native.cgf.cryasset
kb3d_citycarsessentialssedan-native.mtl
kb3d_citycarsessentialssedan-native.mtl.cryasset
KB3D_CEV_* texture files
```

Generated evidence artifacts:

```text
docs/phase98_car_example_cgf_material_probe.json
docs/phase98_car_example_material_alignment.json
docs/phase98_car_example_mtl_schema_report.json
```

The temporary Blender FBX polygon manifest was intentionally not kept because
it was about 58 MB. The durable alignment JSON preserves the material table
facts without storing every polygon row.

## Commands

```powershell
uv run python -m tools.mtl_schema_report "S:\Crytek\crytek\Stripped to the bone\example\car" --output docs\phase98_car_example_mtl_schema_report.json
uv run python -m tools.cgf_material_probe "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.cgf" > docs\phase98_car_example_cgf_material_probe.json
uv run python -m tools.blender_material_inspector --fbx "S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.fbx" --manifest docs\phase98_car_example_fbx_material_manifest.json
```

The Blender inspector used:

```text
C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe
Blender 5.1.2
FBX version: 7400
```

## CGF MtlName Chunk

The CGF reader now decodes `ChunkType_MtlName` version `0x0802`.

Source-release evidence:

```text
Code\CryEngine\CryCommon\Cry3DEngine\CGF\CryHeaders.h
Code\CryEngine\Cry3DEngine\CGF\CGFSaver.cpp
Code\CryEngine\Cry3DEngine\CGF\CGFLoader.cpp
```

The relevant structure is:

```text
char name[128]
int nSubMaterials
int32 physicalize_types[slot_count]
char sub_material_names[]
```

For multi-materials, `CGFSaver.cpp` writes one physicalize value per child
material, followed by null-terminated child material names. `CGFLoader.cpp`
reads those names back with `GetNextAsciizString`.

## Alignment Result

The sample has:

```text
FBX first-seen material table: 16 materials
CGF MtlName sub-material table: 16 materials
CGF used material IDs: 0..15
MTL sub-material table: 17 materials
MTL root-inclusive schema records: 18 materials
CGF mesh count: 21
CGF subset count: 68
```

Key result:

```text
CGF MtlName order == MTL sub-material order prefix: true
CGF MtlName order == Blender FBX first-seen order: false
```

The CGF `MtlName` sub-material table matches the first 16 MTL sub-materials:

```text
0  KB3D_CEV_UndercarriageTrim
1  KB3D_CEV_SeatsDriverATrim
2  KB3D_CEV_TiresSedans
3  KB3D_CEV_WheelRimsA
4  KB3D_CEV_RubberTrim
5  KB3D_CEV_PlasticTileableA
6  KB3D_CEV_PlasticTrimA
7  KB3D_CEV_SedanExteriorBody
8  KB3D_CEV_CarAtlas
9  KB3D_CEV_CarsLicensePlates
10 KB3D_CEV_TapesTrimA
11 KB3D_CEV_WindowFritsTrim
12 KB3D_CEV_FeltA
13 KB3D_CEV_FeltB
14 KB3D_CEV_GlassMirror
15 KB3D_CEV_TranslElemSedans
```

The MTL contains one extra slot:

```text
16 <unassigned>
```

That `<unassigned>` slot is not present in the CGF `MtlName` table and no CGF
mesh subset uses material id 16. It appears to be a material-asset fallback
slot rather than a mesh material table entry.

## FBX Order Warning

The Blender FBX inspector reports a different first-seen material order:

```text
0  KB3D_CEV_UndercarriageTrim
1  KB3D_CEV_SeatsDriverATrim
2  KB3D_CEV_RubberTrim
3  KB3D_CEV_PlasticTileableA
4  KB3D_CEV_PlasticTrimA
5  KB3D_CEV_SedanExteriorBody
6  KB3D_CEV_CarAtlas
7  KB3D_CEV_CarsLicensePlates
8  KB3D_CEV_TapesTrimA
9  KB3D_CEV_WindowFritsTrim
10 KB3D_CEV_FeltA
11 KB3D_CEV_FeltB
12 KB3D_CEV_GlassMirror
13 KB3D_CEV_TranslElemSedans
14 KB3D_CEV_TiresSedans
15 KB3D_CEV_WheelRimsA
```

Therefore a converter or Blender plugin must not assume that Blender's
first-seen material order is the final CryEngine sub-material order.

For this sample, the authoritative final mesh material table is the CGF
`MtlName` table, and it aligns with the MTL sub-material order, not the
Blender first-seen order.

## Texture And Shader Evidence

The MTL schema report found:

```text
Diffuse: 17
Bumpmap: 17
Specular: 16
Heightmap: 15
Emittance: 3
Opacity: 1
```

Texture suffix status:

```text
matches_expected_suffix: 48
mismatch_expected_suffix: 20
no_source_backed_suffix: 1
```

All texture modifiers match the current minimal exporter `TexMod` shape:

```text
matches_export_minimal_texmod: 69
```

Shader mix:

```text
Illum: 15
Multilayeredmaterials: 1
Glass: 1
```

The `Illum` materials mostly use:

```text
GenMask="6000000000020"
StringGenMask="%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING"
```

The glass material uses:

```text
Shader="Glass"
GenMask="2080000000000"
StringGenMask="%SPECULAR_MAP%TINT_MAP"
```

The multilayer material uses shader-specific public params such as:

```text
BackLightScale
BumpMapTile
BumpScale
Layer0ReflectivityScale
Layer1ReflectivityScale
Layer1Smoothness
Layer1Thickness
Layer2ReflectivityScale
Layer2Smoothness
Layer2Thickness
```

## Rule Implications

Evidence-supported rules from this sample:

```text
CGF MeshSubsets.material_id indexes the CGF MtlName sub-material table.
The CGF MtlName sub-material table matches the MTL sub-material order prefix.
The MTL may contain fallback/unassigned slots that are not in the CGF MtlName table.
Blender first-seen material order is not sufficient as the CryEngine sub_index order.
```

Open rule gap:

```text
We still need the RC import request JSON that generated this sample, or an
equivalent RC round-trip we can run ourselves, to explain why RC chose this
specific MTL/CGF order from the source FBX.
```

## Verification

Checks run:

```text
uv run python -m pytest tests\test_cgf_material_probe.py
uv run python -m pytest tests\test_cgf_material_probe.py tests\test_rc_smoke_test.py tests\test_material_mapping_report.py
uv run python -m pytest tests
uv run python -m compileall utils tools tests
uv lock --check
git diff --check
```

Results:

```text
CGF probe tests: 2 passed
targeted material/RC tests: 54 passed
full test suite: 315 passed
compileall: passed
uv lock --check: passed
git diff --check: passed
```
