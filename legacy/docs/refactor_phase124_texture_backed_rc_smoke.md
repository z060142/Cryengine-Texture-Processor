# Phase 124 - Texture-Backed RC Smoke Flow

## Goal

Run the car FBX user flow with real texture-backed MTL generation, not only
empty material slots.

Previous RC smoke phases proved:

- generated request material order can match RC/CGF material ids
- trailing `<unassigned>` is expected when it is unused
- roughness can export through CE `Opacity`

This phase connects those pieces in one rough user flow:

```text
FBX + Blender manifest + extracted texture refs + processed texture directory
-> generated .mtl with Texture nodes
-> generated RC request JSON
-> rc.exe
-> .cgf + material report
```

## Changes

- `tools.rc_smoke_test`
  - adds `--texture-output-dir`
  - adds `--texture-output-format`
  - when texture output is requested, loads the FBX, extracts texture refs, and
    builds MTL material data before running RC
  - writes `preflight_texture_diagnostics` into the material report

- `model_processing.material_texture_resolver`
  - resolves material texture records against the manifest material table
  - this lets manifest-only materials receive texture refs even when the basic
    Blender loader material list is incomplete
  - supports multiple output extensions such as `dds,tif`, plus `auto`

- `model_processing.texture_extractor`
  - prefers explicit filename suffix evidence over Blender socket hints
  - this prevents `*_normal.png` refs from being reported as diffuse when a
    node graph routes an image through a misleading socket

- `output_formats.mtl_exporter`
  - skips Pillow alpha probing for DDS diffuse textures
  - explicit alpha/opacity texture maps still trigger `AlphaTest`
  - this removes noisy `Unimplemented DXGI format` messages during normal CLI/UI
    export

## Real Car Flow

Work dir:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase124_texture_backed_mtl
```

Commands:

```powershell
uv run python -m tools.blender_material_inspector --fbx "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase124_texture_backed_mtl\kb3d_citycarsessentialssedan-native.fbx"
uv run python -m tools.rc_smoke_test --rc "S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe" --fbx "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase124_texture_backed_mtl\kb3d_citycarsessentialssedan-native.fbx" --work-dir "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase124_texture_backed_mtl\rc_work" --asset-name kb3d_citycarsessentialssedan-native --materials-from-manifest --texture-output-dir "S:\Crytek\crytek\Stripped to the bone\example\car" --texture-output-format "dds,tif"
```

Generated report:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase124_texture_backed_mtl\rc_work\kb3d_citycarsessentialssedan-native.material_report.json
```

Schema report:

```text
docs/phase124_texture_backed_car_mtl_schema_report.json
```

Observed summary:

```json
{
  "rc_success": true,
  "output_exists": true,
  "request_material_count": 17,
  "mtl_slot_count": 17,
  "cgf_material_id_count": 16,
  "unassigned_slot_counts": {
    "trailing_unassigned_placeholder": 1
  },
  "used_unassigned_material_count": 0,
  "texture_material_count": 16,
  "source_texture_ref_count": 71
}
```

Generated MTL texture maps:

```json
{
  "Diffuse": 16,
  "Bumpmap": 16,
  "Specular": 16,
  "Heightmap": 16,
  "Opacity": 1
}
```

The generated MTL includes:

```text
slot: KB3D_CEV_SedanExteriorBody
map:  Opacity
file: ../../example/car/KB3D_CEV_SedanExteriorBody_roughness.tif
```

The suffix report marks this as:

```text
matches_observed_sample_suffix
```

## Remaining Gaps

- The texture-backed smoke flow proves MTL references can be generated and RC
  can still produce a slot-correct CGF. It does not yet prove that every
  referenced texture has already been RC-compiled into the final runtime DDS.
- The generated car MTL is now texture-populated, but it is still not a
  byte-for-byte native MTL clone. Shader-specific params such as Glass and
  Multilayeredmaterials remain separate material-format work.
- The current flow accepts mixed processed output extensions for evidence and
  smoke testing. The normal UI still needs a clearer user-facing rule for
  whether it is writing source `.tif` files for RC or final `.dds` files for
  runtime use.

## Verification

- `uv run python -m pytest tests/test_material_texture_resolver.py tests/test_texture_type_resolver.py tests/test_rc_smoke_test.py tests/test_mtl_exporter.py`
- `uv run python -m compileall model_processing output_formats tools tests`
- real car Blender manifest generation
- real car texture-backed `tools.rc_smoke_test`
- `uv run python -m tools.mtl_schema_report "S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase124_texture_backed_mtl\rc_work\kb3d_citycarsessentialssedan-native.mtl" --output docs\phase124_texture_backed_car_mtl_schema_report.json`
