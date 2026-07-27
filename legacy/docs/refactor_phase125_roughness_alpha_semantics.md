# Phase 125 - Roughness Opacity Map Is Not AlphaTest

## Goal

Fix a material-format bug exposed by the texture-backed car flow:

```text
roughness texture -> CE Texture Map="Opacity"
```

does not mean:

```text
material AlphaTest="0.5"
```

The generated phase124 MTL incorrectly added `AlphaTest` because the resolver
stored `*_roughness` outputs under the internal `opacity` key. The exporter then
treated that as transparency intent.

## Evidence

Native car MTL:

```text
Material: KB3D_CEV_SedanExteriorBody
Texture:  Map="Opacity" File="./KB3D_CEV_SedanExteriorBody_roughness.dds"
AlphaTest: absent
```

Source-backed rule:

- `Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp`
- lighting attrs load `Opacity` and `AlphaTest` as independent material
  attributes
- texture map names are loaded as separate `<Texture Map="...">` entries

So a CE `Opacity` texture map is not, by itself, proof that the material should
enable alpha testing.

## Changes

- `model_processing.material_texture_resolver`
  - `*_opacity` remains internal `opacity`
  - `*_roughness` now stays internal `roughness`
  - the MTL exporter still maps `roughness` to CE `Opacity` through
    `resolve_ce_texture_map()`

- `output_formats.mtl_exporter`
  - no code change was needed for alpha detection once roughness semantics were
    preserved
  - `opacity` / `alpha` inputs still trigger `AlphaTest`
  - `roughness` inputs do not

## Real Car Verification

Work dir:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase125_roughness_alpha_split
```

Commands:

```powershell
uv run python -m tools.blender_material_inspector --fbx "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase125_roughness_alpha_split\kb3d_citycarsessentialssedan-native.fbx"
uv run python -m tools.rc_smoke_test --rc "S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe" --fbx "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase125_roughness_alpha_split\kb3d_citycarsessentialssedan-native.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase125_roughness_alpha_split\rc_work" --asset-name kb3d_citycarsessentialssedan-native --materials-from-manifest --texture-output-dir "S:\Crytek\crytek\Stripped to the bone\example\car" --texture-output-format "dds,tif"
uv run python -m tools.mtl_schema_report "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase125_roughness_alpha_split\rc_work\kb3d_citycarsessentialssedan-native.mtl" --output docs\phase125_roughness_alpha_split_mtl_schema_report.json
```

Observed generated MTL row:

```json
{
  "slot": 7,
  "name": "KB3D_CEV_SedanExteriorBody",
  "alpha_test": "",
  "opacity": [
    "../../example/car/KB3D_CEV_SedanExteriorBody_roughness.tif"
  ]
}
```

RC material report still passes:

```json
{
  "rc_success": true,
  "output_exists": true,
  "request_material_count": 17,
  "mtl_slot_count": 17,
  "cgf_material_id_count": 16,
  "used_unassigned_material_count": 0,
  "action_required": false
}
```

## Verification

- `uv run python -m pytest tests/test_material_texture_resolver.py tests/test_mtl_exporter.py tests/test_rc_smoke_test.py tests/test_cryengine_mtl_schema.py`
- `uv run python -m compileall model_processing output_formats tools tests`
- real car Blender manifest generation
- real car texture-backed `tools.rc_smoke_test`
- `uv run python -m tools.mtl_schema_report "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase125_roughness_alpha_split\rc_work\kb3d_citycarsessentialssedan-native.mtl" --output docs\phase125_roughness_alpha_split_mtl_schema_report.json`
