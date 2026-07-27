# Additional Asset Validation

Date: 2026-06-20

## Purpose

Validate the converter against small real assets outside the original Dark
Fantasy sample. RC is sensitive to non-ASCII paths, so RC smoke runs copy input
FBX files into ASCII work directories under:

`S:\Crytek\crytek\Stripped to the bone\e2e_more_assets_batch`

## Model Slot Validation

Small FBX samples were selected from:

- `D:\DATA\00_DATA2\Art Assets\Models`
- `D:\DATA\3D模型`

RC was only run against copied files in ASCII work directories.

| Asset | Source | Result |
|---|---|---|
| `Weed_a` | Polypixel PostApocalypticWorld FBX | RC success, CGF exists, material slot 0 matched, trailing `<unassigned>` unused |
| `Grass_c` | Polypixel PostApocalypticWorld FBX | RC success, CGF exists, material slot 0 matched, trailing `<unassigned>` unused |
| `Trash_Paper_D` | Downtown FBX | RC success, CGF exists, material slot 0 matched, trailing `<unassigned>` unused |
| `Sign_NoSmoking` | IndustrialCity FBX | RC success, CGF exists, material slot 0 matched, trailing `<unassigned>` unused |

All four generated:

- RC import JSON
- CryEngine XML MTL
- `.cgf`
- `.cgf.cryasset`
- material mapping report
- MTL schema gate report

## Texture-Backed Validation

`Weed_b.fbx` was used as the full texture-backed sample because it has nearby
OBJ MTL and source textures:

- FBX material: `Weed_B_mat`
- OBJ MTL material: `Weed_bSG`
- Source diffuse: `Weed_B_a.tga`
- Source normal: `Weed_B_n.tga`

Compatibility fixes added:

- Treat short `_a` source suffix as diffuse/albedo for these asset packs.
- Loosely match external OBJ MTL material names by stripping common DCC suffixes
  such as `_mat` and `SG`, so `Weed_B_mat` can match `Weed_bSG`.

Processed texture outputs:

| Source | Output |
|---|---|
| `Weed_B_a.tga` | `Weed_B_diff.tif` |
| generated default spec | `Weed_B_spec.tif` |
| `Weed_B_n.tga` | `Weed_B_ddn.tif` |

The normal output is `_ddn.tif`, not `_ddna.tif`, because no glossiness map was
available for alpha. The resolver accepts both `_ddn` and `_ddna` as CryEngine
Bumpmap sources.

Generated CryEngine MTL:

```xml
<Material Name="Weed_B_mat" Shader="Illum" AlphaTest="0.5" StringGenMask="%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING">
  <Texture Map="Diffuse" File="../Weed_b_textures/Weed_B_diff.tif">
  <Texture Map="Bumpmap" File="../Weed_b_textures/Weed_B_ddn.tif">
  <Texture Map="Specular" File="../Weed_b_textures/Weed_B_spec.tif">
</Material>
```

RC smoke summary:

```text
rc_success: True
action_required: False
slot_alignment_ok: True
material_slot_evidence_ok: True
texture_output_gate_ok: True
mtl_schema_gate_ok: True
slot_status_counts: {'matched_used_slot': 1, 'trailing_unassigned_placeholder': 1}
```

## Acceptance Notes

This batch satisfies the current practical acceptance bar:

- Model format: FBX copied into ASCII work dir, RC produced `.cgf`.
- Material slots: FBX manifest slot order matched RC JSON, MTL, and CGF material ids.
- Material to textures: `Weed_B_mat` resolved to `Weed_B_*` outputs via OBJ MTL evidence.
- Texture format: outputs are `.tif`, which RC accepts as a source texture format; `_ddn` is accepted as Bumpmap.
- MTL format: generated CryEngine XML MTL passed the schema gate and uses source-backed map names.

Summary artifact:

`S:\Crytek\crytek\Stripped to the bone\e2e_more_assets_batch\more_assets_validation_summary.json`
