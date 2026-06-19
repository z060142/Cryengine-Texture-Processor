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

It is intentionally a small JSON-driven tool, not a polished UI.

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
ASCII `work_root`.

The validator reruns Blender material inspection before RC smoke so stale
manifest files do not silently control the result.
