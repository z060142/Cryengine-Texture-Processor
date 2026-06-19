# Asset Flow Validator

Date: 2026-06-20

## Purpose

`tools.asset_flow_validator` is a rough validation runner for the current
practical acceptance bar:

- FBX can be copied into an ASCII work directory and converted by `rc.exe`.
- RC JSON, CryEngine XML MTL, and CGF material ids agree with the FBX material
  slot manifest.
- Generated MTL passes the CryEngine schema gate.
- Optional processed texture outputs pass the texture output gate.
- Optional raw texture inputs can be processed through the existing
  `TextureManager + BatchProcessor` path before RC validation.
- Optional OBJ MTL evidence can connect FBX material names to processed texture
  names.
- Blender material inspection writes its FBX material manifest under the ASCII
  case work directory by default, then passes that explicit manifest path into
  RC smoke validation. This avoids writing sidecar JSON into external asset
  libraries or Chinese/non-ASCII source paths.
- Markdown reports include generated MTL values and the MTL schema gate report
  path, so Shader/MtlFlags/GenMask/StringGenMask/Texture Map choices have an
  evidence trail instead of being invisible pass/fail flags.

It is intentionally a small JSON-driven tool, not a polished UI.

## Batch Spec Builder

Use `tools.asset_flow_spec_builder` when the next step is to run real user
flows across a folder instead of hand-writing every case. It scans FBX files or
folders, keeps the smallest files first, optionally attaches same-name OBJ
`.mtl` evidence, and writes `rc` cases that `tools.asset_flow_validator` can
run directly.

Example:

```powershell
uv run python -m tools.asset_flow_spec_builder `
  "Z:\Dark Fantasy\models" `
  "D:\DATA\00_DATA2\Art Assets\Models" `
  "D:\DATA\3D模型" `
  --output "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\small_fbx_batch_spec.json" `
  --work-root "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\small_fbx_batch" `
  --limit 5 `
  --max-mb 1
```

Then run the generated spec through the same validator:

```powershell
uv run python -m tools.asset_flow_validator `
  --spec "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\small_fbx_batch_spec.json" `
  --output "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\small_fbx_batch_report.json" `
  --markdown-output "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\small_fbx_batch_report.md"
```

Observed small-batch result:

```text
ok: True
case_count: 5
ok_count: 5
failed_count: 0
Trash_Paper_C_3a7b4004: True
Trash_Paper_D_75807579: True
RoadDecal_BusLane_e2c00bfb: True
Scaffolding_Tarp_7ec8bfd8: True
GardenDecorationTrim_67576cbd: True
```

This batch is model-only: it proves FBX copy/import, generated JSON, generated
MTL, material slot evidence, schema gate, and CGF output. It does not prove
material-texture matching because these cases do not provide texture evidence.

For asset packs with `FBX` and `OBJ` sibling folders, pass an OBJ MTL root:

```powershell
uv run python -m tools.asset_flow_spec_builder `
  "D:\DATA\00_DATA2\Art Assets\Models\Unreal Engine\polypixel\PostApocalypticWorld\Models\FBX" `
  --obj-mtl-root "D:\DATA\00_DATA2\Art Assets\Models\Unreal Engine\polypixel\PostApocalypticWorld\Models\OBJ" `
  --output "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\obj_mtl_batch_spec.json" `
  --work-root "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\obj_mtl_batch" `
  --limit 8 `
  --max-mb 2
```

Observed OBJ MTL batch result:

```text
ok: True
case_count: 8
ok_count: 8
failed_count: 0
```

All eight generated cases attached same-name OBJ `.mtl` evidence. Without a
`texture_output_dir`, this remains model-only validation; the evidence is ready
for texture-backed MTL export once processed textures are available.

To build a texture-backed case, also attach the processed texture output
directory:

```powershell
uv run python -m tools.asset_flow_spec_builder `
  "D:\DATA\00_DATA2\Art Assets\Models\Unreal Engine\polypixel\PostApocalypticWorld\Models\FBX\Weed_b.fbx" `
  --obj-mtl-root "D:\DATA\00_DATA2\Art Assets\Models\Unreal Engine\polypixel\PostApocalypticWorld\Models\OBJ" `
  --texture-output-dir "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\Weed_b_textures" `
  --output "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\weed_b_builder_texture_spec.json" `
  --work-root "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\weed_b_builder_texture" `
  --limit 1 `
  --max-mb 2
```

Observed texture-backed builder result:

```text
ok: True
case_count: 1
ok_count: 1
failed_count: 0
manifest_generated: true
model_format_ok: true
material_slots_ok: true
mtl_format_ok: true
texture_format_ok: true
material_texture_ok: true
```

The generated MTL used the OBJ `.mtl` material evidence to connect
`Weed_B_mat` to the processed CryEngine texture outputs:

```text
Diffuse: ../../Weed_b_textures/Weed_B_diff.tif
Bumpmap: ../../Weed_b_textures/Weed_B_ddn.tif
Specular: ../../Weed_b_textures/Weed_B_spec.tif
```

To let the builder create the raw texture-processing case too, use
`--include-texture-process` and omit `--texture-output-dir`:

```powershell
uv run python -m tools.asset_flow_spec_builder `
  "D:\DATA\00_DATA2\Art Assets\Models\Unreal Engine\polypixel\PostApocalypticWorld\Models\FBX\Weed_b.fbx" `
  --obj-mtl-root "D:\DATA\00_DATA2\Art Assets\Models\Unreal Engine\polypixel\PostApocalypticWorld\Models\OBJ" `
  --include-texture-process `
  --max-textures-per-case 2 `
  --output "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\weed_b_auto_texture_process_spec.json" `
  --work-root "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\weed_b_auto_texture_process" `
  --limit 1 `
  --max-mb 2
```

The builder reads the OBJ `.mtl`, filters texture references by the FBX stem
so shared pack-level `.mtl` files do not pull in the whole texture library, and
adds a `texture_process` case before the `rc` case. It also does a narrow
same-base expansion from names such as `_a`/`_diff` to `_n`/`_normal` and
`_s`/`_spec` when those files exist nearby.

`--max-textures-per-case` keeps the rough batch flow bounded. The generated
spec and Markdown report preserve `source_texture_count` and
`texture_limit_applied`, so a truncated case is visible instead of silently
looking complete.

Observed auto texture-process result:

```text
ok: True
case_count: 2
ok_count: 2
failed_count: 0
Weed_b_27b3df7b_raw_textures: True
Weed_b_27b3df7b: True
source_texture_count: 2
texture_limit_applied: false
```

Observed processed outputs:

```text
Weed_B_diff.tif
Weed_B_ddn.tif
Weed_B_spec.tif
```

The generated MTL values from that run:

```text
Material: Weed_B_mat
Shader: Illum
MtlFlags: 524416
GenMask: 1125899907366944
StringGenMask: %NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING
Textures: Diffuse -> Weed_B_diff.tif, Bumpmap -> Weed_B_ddn.tif, Specular -> Weed_B_spec.tif
```

## Spec Format

Example:

```json
{
  "work_root": "S:\\Crytek\\crytek\\Stripped to the bone\\e2e_asset_flow_validator",
  "texture_output_format": "tif",
  "cases": [
    {
      "name": "Weed_b_raw_textures",
      "type": "texture_process",
      "textures": [
        "D:\\DATA\\00_DATA2\\Art Assets\\Models\\Unreal Engine\\polypixel\\PostApocalypticWorld\\Textures\\Weed_B_a.tga",
        "D:\\DATA\\00_DATA2\\Art Assets\\Models\\Unreal Engine\\polypixel\\PostApocalypticWorld\\Textures\\Weed_B_n.tga"
      ],
      "output_dir": "S:\\Crytek\\crytek\\Stripped to the bone\\e2e_asset_flow_validator\\Weed_b_textures"
    },
    {
      "name": "Weed_b_texture_backed",
      "type": "rc",
      "fbx": "D:\\DATA\\00_DATA2\\Art Assets\\Models\\Unreal Engine\\polypixel\\PostApocalypticWorld\\Models\\FBX\\Weed_b.fbx",
      "texture_output_dir": "S:\\Crytek\\crytek\\Stripped to the bone\\e2e_asset_flow_validator\\Weed_b_textures",
      "obj_mtl_evidence": "D:\\DATA\\00_DATA2\\Art Assets\\Models\\Unreal Engine\\polypixel\\PostApocalypticWorld\\Models\\OBJ\\Weed_b.mtl"
    },
    {
      "name": "Trash_Paper_D_model_only",
      "type": "rc",
      "fbx": "D:\\DATA\\3D模型\\Unreal Projects\\Unreal Projects\\Downtown\\fbx\\Game\\Downtown\\Meshes\\Trash_Paper_D.FBX"
    },
    {
      "name": "Weed_b_texture_outputs",
      "type": "texture_gate",
      "paths": [
        "S:\\Crytek\\crytek\\Stripped to the bone\\e2e_asset_flow_validator\\Weed_b_textures"
      ]
    }
  ]
}
```

Run:

```powershell
uv run python -m tools.asset_flow_validator `
  --spec examples\asset_flow_validation_more_assets.json `
  --output "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\asset_flow_validation_report.json" `
  --markdown-output "S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\asset_flow_validation_report.md"
```

## Current Real-Flow Result

Observed result:

```text
ok: True
case_count: 4
ok_count: 4
failed_count: 0
Weed_b_raw_textures: True
Weed_b_texture_backed: True
Trash_Paper_D_model_only: True
Weed_b_texture_outputs: True
```

Markdown report:

`S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\asset_flow_validation_report.md`

The raw texture process case checks:

```json
{
  "raw_textures_found": true,
  "texture_processing_started": true,
  "texture_format_ok": true
}
```

Observed processed outputs:

```text
Weed_B_diff.tif
Weed_B_spec.tif
Weed_B_ddn.tif
```

The texture-backed case checks:

```json
{
  "manifest_generated": true,
  "model_format_ok": true,
  "material_slots_ok": true,
  "mtl_format_ok": true,
  "texture_format_ok": true,
  "material_texture_ok": true
}
```

The Markdown report also includes an `MTL Values` section. Example from the
texture-backed case:

```text
Material: Weed_B_mat
Shader: Illum
MtlFlags: 524416
GenMask: 1125899907366944
StringGenMask: %NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING
Textures: Diffuse -> Weed_B_diff.tif, Bumpmap -> Weed_B_ddn.tif, Specular -> Weed_B_spec.tif
```

The same case lists the generated `.mtl_schema_gate.json` path as evidence for
CryEngine-backed value policy checks.

The generated FBX material manifest is also reported from the case work
directory, for example:

```text
S:\Crytek\crytek\Stripped to the bone\e2e_asset_flow_validator\Weed_b_texture_backed\Weed_b_texture_backed.fbx_material_manifest.json
```

The model-only case checks:

```json
{
  "manifest_generated": true,
  "model_format_ok": true,
  "material_slots_ok": true,
  "mtl_format_ok": true,
  "texture_format_ok": null,
  "material_texture_ok": null
}
```

`null` means the case did not ask for that dimension. For example,
`Trash_Paper_D_model_only` does not provide processed textures, so it only
validates model format, material slots, and MTL format.

## Notes

RC is sensitive to non-ASCII paths. The validator still reads source FBX files
from their original locations, but `rc.exe` receives copied files under the
ASCII `work_root`. The Blender material manifest follows the same rule: unless
the spec explicitly sets `manifest`, it is created under the case work
directory instead of next to the source FBX.

The validator reruns Blender material inspection before RC smoke so stale
manifest files do not silently control the result.
