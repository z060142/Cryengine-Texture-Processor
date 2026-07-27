# OBJ MTL Texture Evidence Fallback

Date: 2026-06-20

## Purpose

Some asset packs provide Wavefront OBJ `.mtl` files next to FBX models. These
files are not CryEngine XML materials, but they are useful evidence for mapping
short material names to source texture base names.

Example from Dark Fantasy:

```text
newmtl metalA
map_Kd KB3D_DKF_metalA_Diffuse.jpg
map_Ks KB3D_DKF_metalA_Spec.jpg
map_bump Map__19_Normal Bump.tga
```

The practical rule is:

- FBX/RC material slot name: `metalA`
- Source texture base name: `KB3D_DKF_metalA`
- Processed CE outputs:
  - `KB3D_DKF_metalA_diff.tif`
  - `KB3D_DKF_metalA_spec.tif`
  - `KB3D_DKF_metalA_ddna.tif`
  - `KB3D_DKF_metalA_displ.tif`

## Implemented Behavior

`tools.obj_mtl_report` parses the useful subset of Wavefront `.mtl`:

- `newmtl`
- `map_Ka`
- `map_Kd`
- `map_Ks`
- `map_bump` / `bump`
- `disp`
- `map_d`
- `map_refl`
- `map_Ke`

The parser intentionally stays rough and practical. It also handles unquoted
filenames with spaces such as `Map__19_Normal Bump.tga`, and trailing texture
options such as `bump Bark_Birch_n.tga -bm 1`.

`model_processing.material_texture_resolver` now accepts
`external_material_texture_evidence` or `obj_mtl_report` in `model_data`. When
FBX texture refs are missing, it can use OBJ MTL evidence to resolve the
processed texture base name.

`tools.rc_smoke_test` exposes this as:

```powershell
uv run python -m tools.rc_smoke_test `
  --fbx "Z:\Dark Fantasy\models\Part_barrelA_grp.fbx" `
  --work-dir "S:\Crytek\crytek\Stripped to the bone\e2e_dark_fantasy_barrelA\rc_work_with_obj_mtl_evidence" `
  --materials-from-manifest `
  --texture-output-dir "S:\Crytek\crytek\Stripped to the bone\e2e_dark_fantasy_barrelA\textures" `
  --texture-output-format tif `
  --obj-mtl-evidence "Z:\Dark Fantasy\Kitbash3d_DarkFantasy-Native.mtl" `
  --no-rc-log `
  --report-summary
```

## Verification

Dark Fantasy native OBJ MTL parse:

```text
material_count: 34
texture_reference_count: 170
diagnostic_count: 0
ok: true
```

Dark Fantasy barrelA RC smoke with OBJ MTL evidence:

```text
rc_success: True
action_required: False
slot_alignment_ok: True
material_slot_evidence_ok: True
texture_output_gate_ok: True
mtl_schema_gate_ok: True
```

Generated CryEngine MTL included:

```xml
<Texture Map="Diffuse" File="../textures/KB3D_DKF_metalA_diff.tif">
<Texture Map="Bumpmap" File="../textures/KB3D_DKF_metalA_ddna.tif">
<Texture Map="Specular" File="../textures/KB3D_DKF_metalA_spec.tif">
<Texture Map="Heightmap" File="../textures/KB3D_DKF_metalA_displ.tif">
```

Relevant test command:

```powershell
uv run pytest tests/test_material_texture_resolver.py tests/test_obj_mtl_report.py tests/test_rc_smoke_test.py -q
```

Last observed result:

```text
61 passed
```
