# Fixtures（不進 git，見 .gitignore / Q3）

| 路徑 | 來源 | 用途 |
|---|---|---|
| `car/car.fbx` | `S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.fbx` | T-003 ufbx 對齊、C1–C5 golden 主資產 |
| `car/car-reference.mtl` | 同上目錄 `.mtl` | C3 的 MTL 比對參考 |
| `car/car-reference.material_report.json` | 同上目錄 `.material_report.json` | T-003 比對證據（既有工具鏈產出） |
| `KB3D_ENC_PropAxe_A_grp.fbx` | `Z:\enchanted\output\` | 最小重現用小型 FBX（128 KB） |
| `textures/KB3D_ENC_AtlasA_*.png` | `Z:\enchanted\KB3DTextures\4k\` | texproc 線（T 線）輸入樣本：ao/basecolor/height/metallic/normal/opacity/roughness 一套 |

遺失時依上表路徑重新複製。更多 FBX 素材：`Z:\enchanted\output\`（同名 `_grp.fbx`，大小 128 KB～300 MB 皆有）。
