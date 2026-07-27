# Fixtures（不進 git，見 .gitignore / Q3）

| 路徑 | 來源 | 用途 |
|---|---|---|
| `car/car.fbx` | `S:\Crytek\crytek\Stripped to the bone\example\car\kb3d_citycarsessentialssedan-native.fbx` | T-003 ufbx 對齊、C1–C5 golden 主資產 |
| `car/car-reference.mtl` | 同上目錄 `.mtl` | **native 手工資產**（含手工共享 normal 等，非舊工具輸出）；僅供人工參照，不作 golden |
| `car/car-generated-reference.mtl` | `S:\...\e2e_car_user_flow_phase127_material_overrides\rc_work\` | **舊 Python 流程實際輸出的 MTL**，C3 行為等價 golden（T-005 裁決） |
| `car/car-reference.request.json` | 同上 rc_work 目錄 `.json` | C3 request golden（phase127 原檔） |
| `car/car-reference.material_report.json` | 同上目錄 `.material_report.json` | T-003 比對證據（既有工具鏈產出） |
| `car/car.fbx_material_manifest.json` | `S:\Crytek\crytek\Stripped to the bone\e2e_car_user_flow_phase127_material_overrides\rc_work\` | golden 流程實際使用的 material manifest（16 材質 explicit `physicalize: no` 的出處），T-004 起 golden 比對必用 |
| `KB3D_ENC_PropAxe_A_grp.fbx` | `Z:\enchanted\output\` | 最小重現用小型 FBX（128 KB） |
| `textures/KB3D_ENC_AtlasA_*.png` | `Z:\enchanted\KB3DTextures\4k\` | texproc 線（T 線）輸入樣本：ao/basecolor/height/metallic/normal/opacity/roughness 一套 |
| `textures/KB3D_ENC_GlassClean_*.png` | `Z:\enchanted\KB3DTextures\4k\` | T-013 第二組 metallic 有訊號樣本：只取 ao/basecolor/height/metallic/normal/roughness；刻意不取未分類的 refraction |

遺失時依上表路徑重新複製。更多 FBX 素材：`Z:\enchanted\output\`（同名 `_grp.fbx`，大小 128 KB～300 MB 皆有）。
