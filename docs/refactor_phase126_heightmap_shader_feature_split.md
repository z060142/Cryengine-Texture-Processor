# Phase 126 - Heightmap Shader Feature Split

## Goal

Stop treating a CryEngine `Heightmap` texture slot as proof that the material
uses displacement or tessellation shader features.

The older exporter rule came from an exporter-side compatibility guess:

- `displacement` / `Heightmap` texture key -> `%DISPLACEMENT_MAPPING`
- `displacement` / `Heightmap` texture key -> `%PHONG_TESSELLATION`
- same texture key -> tessellation `PublicParams`

The car sample shows this is too aggressive. Native `.mtl` materials can carry
`Texture Map="Heightmap"` while their authoritative `StringGenMask` remains a
plain normal/specular/subsurface mask.

## Rule

Texture slots and shader features are separate material state:

- `displacement`, `height`, and `heightmap` still export as `Texture Map="Heightmap"`.
- `normal` / `Bumpmap` texture presence still enables `%NORMAL_MAP`.
- `specular` / `Specular` texture presence still enables `%SPECULAR_MAP`.
- `Heightmap` texture presence does not enable `%DISPLACEMENT_MAPPING`.
- `Heightmap` texture presence does not enable `%PHONG_TESSELLATION`.
- `Heightmap` texture presence does not inject tessellation public params.

If a future tool needs true tessellation export, it should model that as an
explicit material option instead of inferring it from a texture slot.

## Source/Evidence Notes

- `MaterialHelpers.cpp` loads and saves texture map entries separately from
  shader masks and public params.
- `StringGenMask` remains the important shader token field; the schema notes
  that CE load policy treats it as effective when present.
- `PublicParams` are parsed as explicit shader params. The current source-backed
  evidence does not say that `Heightmap` texture presence creates tessellation
  params.

## Native vs Generated Car Check

Native car `.mtl`:

```json
{
  "material_count": 17,
  "string_gen_masks": {
    "%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING": 14,
    "": 1,
    "%SPECULAR_MAP%TINT_MAP": 1,
    "%NORMAL_MAP%SUBSURFACE_SCATTERING": 1
  },
  "shaders": {
    "Illum": 15,
    "Multilayeredmaterials": 1,
    "Glass": 1
  },
  "texture_maps": {
    "Diffuse": 17,
    "Bumpmap": 17,
    "Specular": 16,
    "Heightmap": 15,
    "Opacity": 1,
    "Emittance": 3
  }
}
```

Generated Phase 126 `.mtl`:

```json
{
  "material_count": 17,
  "string_gen_masks": {
    "%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING": 16,
    "%SUBSURFACE_SCATTERING": 1
  },
  "shaders": {
    "Illum": 17
  },
  "texture_maps": {
    "Diffuse": 16,
    "Bumpmap": 16,
    "Specular": 16,
    "Heightmap": 16,
    "Opacity": 1
  },
  "public_params": {
    "EmittanceMapGamma": 17,
    "SSSIndex": 17
  }
}
```

The generated material count includes the trailing `<unassigned>` placeholder.
That placeholder is expected CE behavior for this flow and is kept by design.

## RC User Flow

Work directory:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase126_heightmap_shader_feature_split
```

Commands:

```powershell
$phase = 'S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase126_heightmap_shader_feature_split'
$fbx = Join-Path $phase 'kb3d_citycarsessentialssedan-native.fbx'
$work = Join-Path $phase 'rc_work'

uv run python -m tools.blender_material_inspector --fbx $fbx

uv run python -m tools.rc_smoke_test --rc "S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe" --fbx $fbx --work-dir $work --asset-name kb3d_citycarsessentialssedan-native --materials-from-manifest --texture-output-dir "S:\Crytek\crytek\Stripped to the bone\example\car" --texture-output-format "dds,tif"

uv run python -m tools.mtl_schema_report (Join-Path $work 'kb3d_citycarsessentialssedan-native.mtl') --output docs\phase126_heightmap_shader_feature_split_mtl_schema_report.json
```

Material report result:

```json
{
  "rc_success": true,
  "output_exists": true,
  "slot_alignment_ok": true,
  "cgf_material_id_alignment_ok": true,
  "cgf_import_settings_alignment_ok": true,
  "fixture_material_semantic_alignment_ok": true,
  "request_material_count": 17,
  "mtl_slot_count": 17,
  "cgf_material_id_count": 16,
  "failed_material_id_check_count": 0,
  "unassigned_placeholder_count": 1,
  "unassigned_slots_ok": true,
  "action_required": false
}
```

Generated MTL token check:

```json
{
  "string_gen_masks": {
    "%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING": 16,
    "%SUBSURFACE_SCATTERING": 1
  },
  "heightmap_count": 16,
  "public_param_counts": {
    "EmittanceMapGamma": 17,
    "SSSIndex": 17
  }
}
```

## Files

- `output_formats/cryengine_mtl_schema.py`
- `tests/test_cryengine_mtl_schema.py`
- `tests/test_mtl_exporter.py`
- `tests/test_material_converter.py`
- `tests/test_material_diagnostics_exporter.py`
- `docs/phase126_heightmap_shader_feature_split_mtl_schema_report.json`

## Remaining Gaps

- Shader family selection is still incomplete. The native car uses `Glass` and
  `Multilayeredmaterials`, while the exporter still writes all generated slots
  as `Illum`.
- Native material-specific public params such as tint, multilayer, glass, and
  bump scaling are not modeled yet.
- The explicit authoring surface for real displacement/tessellation is not
  designed yet. The important correction in this phase is that the exporter no
  longer invents that state from `Heightmap`.

## Verification

```powershell
uv run python -m pytest tests/test_cryengine_mtl_schema.py tests/test_mtl_exporter.py tests/test_material_diagnostics_exporter.py tests/test_material_converter.py
uv run python -m pytest
uv run python -m compileall model_processing output_formats tools tests
uv run python tools/converter_schema.py --check docs/converter_schema.json
uv lock --check
git diff --check
```

Result:

- `86 passed`
- `387 passed`
- `compileall` completed
- converter schema snapshot is current
- `uv lock --check` passed
- `git diff --check` had no whitespace errors
