# v2 UI 重構規格 — Stage Evolution (H2) 遷移

> 2026-07-30，分支 `v2-ui-refactor`。設計定案：`docs/ux-demos/r2-hybrid2-stage-evo.html`
> （基準截圖：`docs/ui-v2/reference/mockup-textures-default.png`、`mockup-models.png`）。
> 原則：**不添加新程式功能**——全部現有功能遷移到新 UI；UI 完全重作，不保留舊版元素。

## 0. 範圍裁定（哪些 mockup 元素做、哪些不做）

mockup 是為「未來功能齊備」畫的。本次試做只遷移現有功能，裁定如下：

**做（設計機制，UI 層即可成立）**
- [A] 左側 mode rail + per-mode 面板記憶 + 綠色 memdot
- [B] Workspace preset 列（Minimal / Review / Export / Custom●），per-mode
- [B2] 面板標題 ●N 修改徽章 + hover「Reset to defaults」
- [E] 底部常駐大動詞（Convert All / Export All）
- [21] 底部 timeline work center（任務膠囊 + session 進度 + 狀態行）
- [22] 頂欄診斷 chip + popover（現有 diagnostics() 資料）
- [19] 頂欄語言選單（現有 en / zh-cn）
- [20] 頂欄輸出目錄欄（繫結依 mode 切換：貼圖/模型輸出目錄）
- [23] 頂欄 Profile ▾（= 現有 settings 檔 Save / Load / Save As / 路徑）
- Toast（工作完成/失敗的暫態通知；資料源 = 現有 status 事件）
- 中央 stage：Textures = 現有貼圖預覽（PreviewState 是既有功能）；
  Models = 現有材質槽工作區（model_workspace 的內容重排）

**不做（依賴不存在的功能，列入排除清單）**
- Proxy 模式、PBR 模式的「功能」——rail 上保留兩顆**停用**按鈕
  （muted、無 hover 反應、tooltip「Planned — not in this build」），只當設計占位
- Viewport 視圖切換 tabs（2D/3D/Proxy）與 Split 分割視圖（只有一種預覽）
- Material Preview / Model Preview 參數面板（tiling、channel、shape/light、wireframe…）
- 群組級覆寫 + 批次覆寫編輯器 [3][D]（現有 app 的轉換設定全是全域，
  **沒有** per-group resolution/flip/metal；群組列維持現況=單選）
- 群組列表的「Delete Selected」（現有刪除是**檔案級**，見 Import 面板）

## 1. 視覺 tokens（theme.rs 的唯一真相）

從 mockup CSS 逐字轉譯。egui `Color32::from_rgb`：

| token | hex | 用途 |
|---|---|---|
| BG | `#181b21` | 右堆疊背景、視窗底 |
| STAGE | `#101216` | 中央舞台底（viewport 再疊 `#0d0f13` 漸層感可簡化為此色）|
| PANEL | `#22262e` | 面板體 |
| PANEL2 | `#292e37` | 面板 hover / 開啟的 header / 按鈕 |
| PANEL3 | `#2f353f` | 按鈕 hover |
| BORDER | `#363c47` | 一般邊線 |
| BORDER2 | `#434b58` | 按鈕邊線、強邊線 |
| INK | `#e6e9ef` | 主文字 |
| MUTED | `#9aa3b2` | 次文字 |
| MUTED2 | `#6c7480` | 弱文字 / 標籤 |
| ACCENT | `#4d8dff` | 主色（primary 按鈕、進度、選中）|
| ACCENT2 | `#7c5cff` | 品牌 logo 漸層第二色 |
| ACCENT_WEAK | rgba(77,141,255,0.16) | 選中底 |
| ACCENT_TEXT | `#8fb6ff` | 選中文字 |
| ACCENT_BORDER | `#31508c` | 選中邊 |
| OK | `#41c072` | 成功 / memdot / done |
| OK_WEAK | rgba(65,192,114,0.15) | 成功底 |
| WARN | `#e2a13c` | 警告 / 修改徽章 |
| WARN_WEAK | rgba(226,161,60,0.15) | 警告底 |
| WARN_BORDER | `#5a4620` | 警告邊 |
| HAZARD | `#e5564c` | 錯誤 / 危險 |

- 圓角：面板 8、按鈕/輸入框 6、rail 按鈕 10、chip 14（膠囊）
- 字級：Body 13、Small 10.5、按鈕 12、面板標題 12.5（strong）、
  section 標籤 10（大寫、letter-spacing、MUTED2）
- 尺寸：topbar 44、rail 76（按鈕 60×60）、右堆疊 **344 固定**、
  stagebar 40、timeline 64
- 字型：沿用現有 CJK fallback（msyh.ttc）；不新增字型依賴
- Stage 底：STAGE 色 + 44px 間距的細格線（白 alpha≈0x08 的 hline/vline），
  不做 radial mask（egui 不支援，可接受的翻譯損失）

## 2. 版面骨架（egui 面板序）

```
TopBottomPanel::top("topbar")      h=44   → topbar.rs
TopBottomPanel::bottom("timeline") h=64   → timeline.rs
SidePanel::left("rail")   w=76 固定       → rail.rs
SidePanel::right("stack") w=344 固定      → stack_*.rs（依 mode 路由）
CentralPanel = stage（stagebar 40 + viewport）→ stage_*.rs（依 mode 路由）
浮層：diagnostics popover（topbar chip 下方）、toast（右下、timeline 上方）、
      3 個既有 Modal（process / export / batch，重新套 theme）
```

`UiMode { Textures, Models }`（rail 另有 Proxy/PBR 停用鈕）。
取代舊 `WorkflowTab`（雙 tab 語意 1:1 對映，drag-drop / 匯入的自動跳頁邏輯保留）。

## 3. 頂欄（topbar.rs）

左→右：
1. 品牌：22×22 圓角方塊（ACCENT→ACCENT2 對角漸層，egui 用兩色 mesh 或簡化純 ACCENT）
   + `CryEngine Texture Processor`（13.5 semibold）+ MUTED2 小字版本 `v2.1`
2. 彈性空白
3. `LANG` 標籤（10px 大寫 MUTED2）+ 語言 ComboBox（endonym：English / 简体中文）
   → `preferences.language` + save（現有行為）
4. 分隔線（1×22 BORDER）
5. `OUT` 標籤 + 路徑輸入（寬 210）+ `…` browse 鈕
   → Textures mode 繫結 `texture_output_directory`，Models mode 繫結
   `model_output_directory`；標籤顯示 `OUT · TEX` / `OUT · MDL`；改動即 save
6. 分隔線
7. `Profile ▾` 按鈕 → 選單：目前 settings 檔名（弱字）、`Load…`（choose_file_open
   + load_settings）、`Save`（save_settings）、`Save As…`（choose_file_save）
   —— 對映現有 settings_file_inputs + save/load 按鈕，全數保留
8. 診斷 chip：`● N diagnostics`（N>0 = WARN 配色，N=0 = OK 配色 `No issues`）
   → 點擊切換 popover（現有 show_diagnostics / diagnostics()）

舊頂欄的 subtitle、models-loaded、drop-hint：subtitle 移除（品牌已足）；
models-loaded 資訊由 Models rail 鈕的 pcount 承載（見 §4）；drop-hint 移到
Textures stage 空狀態（§6）。

## 4. 左側 rail（rail.rs）

- 60×60 按鈕：24px 手繪線條圖示（icons.rs，轉譯 mockup SVG path）+ 10px 標籤
- `Textures`（grid 圖示）、`Models`（cube 圖示）：切換 UiMode；
  active = ACCENT_WEAK 底 + ACCENT_BORDER 邊 + ACCENT_TEXT 字
- Models 鈕右上角疊一枚小 pcount（載入模型數，>0 時顯示）——承載舊 subtitle 資訊
- memdot：6px OK 圓點（右上角），該 mode 有展開面板時顯示
- `Proxy`、`PBR`：**停用**（MUTED2、40% alpha、tooltip t.planned_tooltip）
- 底部：Help 圓問號鈕 → toast（一句操作提示 t.help_toast，對映 mockup railHelp）

## 5. 右側面板堆（stack 共用機構 → widgets.rs + ui/mod.rs）

- stackhead：mode 標題（`Texture Parameters` / `Model Parameters`）+ 右側弱字副題
- presetbar：`WORKSPACE` 小標 + 4 顆 preset 鈕。行為照 mockup JS：
  - `minimal` = 全收合；`review` / `export` = 開啟 data-preset 含該值的面板
  - 手動開合任何面板 → active=custom、記快照（cdot 變 WARN 發光）
  - 點 `Custom` → 還原快照；per-mode 記憶；切 mode 還原該 mode 狀態
- 面板（CollapsiblePanel widget）：header = chev(▶/▼) + 15px 圖示 + 標題
  + [●N 徽章] + [右側 pcount chip]；開啟時 header 底 PANEL2 + 下邊線
- ●N 徽章：計算該面板欄位 vs 預設值的差異數；hover 顯示「Reset to defaults」
  按鈕（點擊還原該面板欄位、toast 確認）。各面板的欄位集與預設見 §7/§8
- pcount chip 樣式：一般（MUTED2）、hot（WARN 配色）、new（ACCENT 配色）

### 面板 ↔ preset 歸屬

| mode | 面板 | preset | pcount |
|---|---|---|---|
| Textures | Import | review | `N files` |
| Textures | Group Review | review | 有 unknown → hot `N unassigned` |
| Textures | Conversion Settings | export | ●N 徽章 |
| Textures | RC / DDS Export | export | DDS 進行中 → `n/m pool` |
| Models | FBX List | review | `N models` |
| Models | Material Slots → **stage**（見 §6）| — | — |
| Models | Transform | export | ●N 徽章 |
| Models | Export Options | export | ●N 徽章 |

## 6. 中央 stage

### 6.1 stagebar（40px）
- 左：mode 名（12.5 semibold）+ MUTED2 副題：Textures = 選中群組名（無則
  `texture preview`）；Models = 選中模型檔名（無則 `material slots`）
- 右：無 view tabs / Split（排除清單）；保留一顆「開啟輸出資料夾」小工具鈕
  （有 process_summary / export 完成時可用 → 現有 file_url 超連結功能的新家之一）

### 6.2 Textures stage = 貼圖預覽（現有 PreviewState 完整遷移）
- HUD chips（左上、堆疊）：`<群組名>`（strong 尾段樣式照 mockup）、
  `<檔名> · <source_type>`、`<W> × <H>`；載入中顯示 spinner chip；
  error → HAZARD 字置中（t.preview_unavailable 現有字串）
- 影像置中、等比、fit-to-available、LINEAR（現有邏輯）
- 影像下方 caption 列：群組 base_name（strong）+ 已填 slot 的 pill
  （現有 ASSIGNABLE_SOURCE_TYPES 徽章 → pill 樣式）+ unknown 數 WARN pill
- 空狀態（無 document）：置中虛線框 dropzone 視覺：
  `Drag & drop textures / FBX here`（t.drop_hint 遷移至此）+ 弱字補充
- 有 document 但無選中：t.select_group_preview（現有字串）

### 6.3 Models stage = 材質槽工作區（model_workspace 重排）
- 無選中/多選：置中空狀態（現有 t.add_fbx_left / t.select_single_model_left）
- 單選模型：
  - HUD chips（左上）：檔名、`N materials · M diagnostics`
  - 主體（ScrollArea，內容寬置中 max ~900）：
    1. **Material Slots 卡**（PANEL 底、8 圓角、mockup slottbl 樣式）：
       表頭 `FBX / Sub / Material / Physicalize / Polygons / Textures`
       （10px MUTED2）；行 hover PANEL2;
       FBX id 格可點＝多選（plain/ctrl/shift，現有 apply_click_selection）；
       Physicalize per-row ComboBox（no/default/obstruct/no_collide/proxy_only，
       manifest-aware 預設，現有邏輯原封）；
       選中 ≥1 列時表上方出現批次列：bulk combo + `Set physicalize (N)`
       （現有 apply_bulk_physicalize）
    2. **Material Details 卡**（選中 slot）：名稱、assignment reason、
       texture 引用列表（shader_prop strong + 檔名/embedded 註記）——現有內容
    3. **Diagnostics 卡**：`[severity] material · message` 列表或綠字 none——現有內容
  - 左下 axis 字幕列（mockup .axisgz）：
    `Forward <F> · Up <U>  |  scale <S> · units <unit>`，
    F/U 用現有 conversion（override 時 WARN 色、parallel 時 HAZARD）

## 7. Textures 面板堆內容（stack_textures.rs）

### Import（preset: review）
- 按鈕列：`Add Files…` `Add Folder…`（現有 choose_files_multi / choose_folder）
- 路徑輸入 + `Add Path`（現有 split_paths 多路徑）
- 檔案列表（ScrollArea，max-h ~240）：檔名列、多選（plain/ctrl/shift）、
  hover=完整路徑、點擊=選取+請求預覽（現有）；標頭 `N files (M selected)` 弱字
- 列表下按鈕列：`Remove Selected`（有選取才 enable）、`Add Related`
  （enable 同左，hover 現有說明）、`Clear All`
- 掃描中：spinner + t.scanning

### Group Review（preset: review）
- 工具列：搜尋框（現有 group_search）+ `Unknown only` checkbox（review_only）
  + 右側 `N of M groups` 弱字（過濾後/總數）
- 群組列（mockup .grow 樣式）：**單選**（維持現況）
  - 26×26 色塊 swatch：以 group key hash 出穩定雙色對角漸層（純視覺識別）
  - 群組名（11.5 strong、truncate）+ 副行：有 unknown → WARN
    `unassigned: N`；否則 `#6f8fbf` `linked: <已填 slot 數> maps`
  - 右側 12 顆 type dots（7×7、圓角 2）：順序 = 現有 GROUP_COLUMNS
    （diffuse/normal/specular/glossiness/roughness/metallic/displacement/
    ao/alpha/emissive/sss/arm）；filled=OK、empty=`#3b414c`、
    群組有 unknown 時尾端加一顆 WARN dot；hover=型別名(+檔名)；
    **點 filled dot = 預覽該檔**（現有行為）
  - 列選中 = ACCENT_WEAK 底+邊；有 unknown 的列 = WARN_BORDER 邊（mockup .unk）
- 選中群組有 unknown 時，列表下方 subsec `ASSIGN UNKNOWN`：
  第一個 unknown 檔名（弱字、truncate）+ Assign ComboBox
  （ASSIGNABLE_SOURCE_TYPES，已占用者 disabled + DEF-19 hover）
  → 現有 assign_group_unknown(index, 0, type)。指派後自動輪到下一個 unknown。
  已全數解決且曾有 unknown → 綠字 `✓ Assigned`（ever_unknown 現有邏輯）

### Conversion Settings（preset: export，●N 徽章）
- grid2：Output Resolution（Original/4096/2048/1024/512/256）、
  Diffuse Format（albedo/diffuse_ao）
- checks：Flip normal green、Convert metallic、Generate missing spec、
  Generate DDS（RC 未配置 → disabled+hover，現有）、Delete TIF after DDS
- nested `Advanced`（details.nested 樣式）：
  - `OUTPUT TEXTURE TYPES` 小標 + 6 checkbox（diff/spec/ddna/displ/emissive/sss）
  - normalize height、dither、gen missing emissive、gen missing sss、
    gen sss from diffuse
  - ARM order combo（ARM/ORM/RMA）、height→normal strength、
    emissive brightness、sss intensity、sss contrast（DragValue，現有範圍）
  - nested `Metal Gate (Advanced)`：Metal Gate checkbox（hover 現有）+
    metallic cut / spec min / gloss cut / transition（DragValue，現有範圍）
- ●N 徽章欄位集：TextureSettings 全體 vs `TextureSettings::default()`
  （reset = 整組還原預設）

### RC / DDS Export（preset: export，●N 徽章）
- RC.exe Path：path_row + browse（choose_rc_executable）；無效時邊框 HAZARD +
  現有 resolution 狀態行（using X from Y / not configured，紅/弱字）
- DDS 進行中：poolbar（7px ACCENT 漸層條）+ 弱字
  `w workers · n/m DDS · <current>`（ProcessState.dds_* 現有資料）
- ●N 徽章欄位集：generate_dds、delete_tif_after_dds（vs false）+ rc_path（vs 空）

## 8. Models 面板堆內容（stack_models.rs）

### FBX List（preset: review）
- `Add Models…`（choose_files_multi FBX）+ 路徑輸入 + `Add Path` + `Clear All`
  + `Remove Selected`（多選 enable；現有）
- 載入中 spinner + `Loading N…`
- 模型列（.grow 樣式）：多選（現有 apply_click_selection）；swatch 同群組列作法；
  名稱 + 副行 `N materials · M diag · K helper`（diag>0 → WARN 字）
- 單選時列表下 subsec `SUMMARY`：slots/meshes/nodes/helper/diagnostics 計數行
  + axes.summary()（undeclared → WARN + hover）——現有 model_summary 全內容
- `Resend textures to Textures` 按鈕（現有 ingest_entry_textures）

### Transform（preset: export，●N 徽章；單選模型時才有內容，否則弱字提示）
- subsec `AXIS — detected, override below`：Forward / Up ComboBox（AXIS_TOKENS）
  + `Detected: <F+U>` 弱字 + override 時 WARN `Override: <F+U>` +
  parallel 時 HAZARD 警告（全現有）
- grid2：Units combo（file/mm/cm/m/inch/foot，persisted）、
  Scale DragValue（persisted）
- checks：Merge child nodes、Scene origin
- ●N：unit(≠"file")、scale(≠1.0)、forward/up(≠detected)、merge(≠false)、
  origin(≠false)；reset 還原上述

### Export Options（preset: export，●N 徽章）
- Manifest path（optional）+ browse；Overrides path（optional）+ browse
- checks：Export textures alongside model（hover 現有）、
  Delete request .json（hover 現有）
- RC path 狀態行（同 §7 的 resolution 顯示；欄位本體在 RC/DDS 面板，
  這裡再放一個同繫結的 path_row —— 同一 pref 字串，兩處編輯皆可）
- `Export CE Model` primary block 按鈕（enable = 單選 + 軸不平行 + 未在匯出，
  現有條件）；匯出中→ `Show progress` 開 modal
- ●N：manifest/overrides(≠空)、associated(≠false)、delete_json(≠false)

## 9. 底部 timeline（timeline.rs）

- 左 tl-title：`WORK CENTER`（11 semibold）+ 第二行 = **現有 status 字串**
  （10px MUTED2、truncate、hover 全文）——status 的新家
- 中 tl-track（橫向卷動）：session 任務膠囊（UiState.session_tasks: Vec<TaskCard>）
  - 事件源→膠囊：Scan（掃描/regroup）、Convert（n/m groups + written）、
    DDS pool（n/m + workers）、Load FBX（pending count）、Export model（stage）、
    Export All（i/N + name）
  - 樣式：done（✓ OK）、run（spinner + ACCENT 邊 + 60px 進度條）、
    failed（✗ HAZARD）；完成時間以 HH:MM 註記
  - **點 run 膠囊 = 開對應 modal**（Show progress 現有功能）；
    run 膠囊尾端小 ✕ = cancel（process.cancel / batch.cancel 現有）
  - done 膠囊上限 8，舊的淘汰
- 右 session 總進度：`Session n%`（目前執行中 job 的完成比；閒置顯示上次值）
- 最右 [E] 動作叢：`Export All`（= start_batch_export，enable 現有條件）+
  `Convert All`（primary，= start_texture_process，enable 現有條件）
  （Convert All 完成後的 open-output-folder 連結 → 移到 summary modal + toast）

## 10. 浮層

- **診斷 popover**：topbar chip 正下方（Area/Window 固定位），寬 390：
  標題 `Diagnostics (N)`、列 = severity 膠囊（WARN/INFO/ERROR 配色）+
  title(strong 10.5) + message(11.5)。資料 = 現有 diagnostics()。點外面關閉。
- **Toast**（右下，timeline 上方 78px）：OK 左邊條 + ✓ 圓 + 標題/副文，
  3 秒自動消失；觸發：process 完成/取消、export 完成/失敗、batch 完成、
  scan 完成、reset-to-defaults、profile save/load。內容用現有 status 字串。
  錯誤類 toast 左邊條 HAZARD。
- **三個 Modal**（dialogs.rs）：內容/行為 1:1 保留（含 per-group ✓ 清單、
  DDS 進度、cancel、summary、open-output-folder 超連結），只換 theme 外觀。

## 11. 架構與檔案

```
texproc-gui/src/
  main.rs        ← 保留：state structs、actions、poll_*、helpers、tests；
                    刪除全部舊 draw fn；update() → ui::draw(self, ctx)
  ui/mod.rs      ← UiMode、UiState（mode、PanelMemory per-mode、toasts、
                    session_tasks、diag_popover_open）、draw() 路由
  ui/theme.rs    ← §1 tokens、apply_style(ctx)、Frame/顏色 helpers
  ui/icons.rs    ← Icon enum + painter 線條圖示（rail 4 + panel 8 + misc）
  ui/widgets.rs  ← CollapsiblePanel(+modbadge/pcount)、preset_bar、rail_button、
                    hud_chip、pill、task_chip、toast、path_row、section_label、
                    grow_row（群組/模型列）、swatch
  ui/topbar.rs   ui/rail.rs   ui/timeline.rs
  ui/stage_textures.rs   ui/stage_models.rs
  ui/stack_textures.rs   ui/stack_models.rs
  ui/dialogs.rs  ← 3 modal + 診斷 popover
  worker.rs / i18n.rs / prefs.rs / file_dialog.rs / lib.rs ← 不動語意
                    （i18n 加 key、prefs 加 ui_workspace 欄位）
```

- **不加任何新 crate 依賴**（egui-phosphor 0.13 需 egui 0.35，不相容 0.33；圖示手繪）
- prefs 新欄位：`ui_workspace`（serde_json::Value 原樣 round-trip）：
  `{ "<mode>": { "preset": "review", "custom": [bool…], "open": {panel_id: bool} } }`
  ＋ 讀不到/格式錯 → 預設（各 mode preset=review 的開合）。既有欄位不動。
- i18n：所有新文案 = Strings 新欄位（en + zh-cn 同步補齊，缺一個編不過）。
  技術詞照 T-018 政策不翻（panel 標題如 RC / DDS Export、Physicalize…）。
  舊 key 若新 UI 不再使用一律**刪除**（compile error 驅動清理）。

## 12. 派工切分與順序

- **Phase A（骨架，單一 agent）**：theme + icons + widgets + ui/mod 路由 +
  main.rs 接線（stage/stack 空殼）+ prefs.ui_workspace + i18n 全部新 key。
  驗收：cargo build 過、視窗顯示完整 chrome（rail/topbar/timeline/空 stage/空堆疊）。
- **Phase B（3 並行 agent，各自檔案，不碰彼此）**：
  - B1 `stack_textures.rs` + `stage_textures.rs`（§6.2 + §7）
  - B2 `stack_models.rs` + `stage_models.rs`（§6.3 + §8）
  - B3 `topbar.rs` + `timeline.rs` + `dialogs.rs`（§3 + §9 + §10）
- **Phase C（協調者）**：整合 build、逐項功能驗收（§13）、實機截圖 vs 基準圖
  視覺迭代、cargo test + run_gates.ps1、commit。

## 13. 驗收清單（功能把關 = 逐項打勾）

Textures：add files/folder/path、拖放、檔案多選、remove selected、add related、
clear、掃描狀態、群組列（12 型別 dot、點 dot 預覽、選群組預覽）、搜尋、
unknown-only、assign unknown（占用 disable + DEF-19）、✓ Assigned、
全部轉換設定欄位（含 Advanced + Metal Gate 4 參數）、DDS gate（無 RC disable）、
Convert All（unknown 阻擋跳轉、輸出目錄檢查、進度 modal、cancel、summary、
open folder、失敗清單）、DDS 池進度（workers 數）。

Models：add fbx/path、拖放、多選、remove、clear、載入 spinner、列 badge、
summary（含 axes declared/undeclared）、unit/scale 持久化、forward/up 偵測+覆寫
+parallel 擋匯出、merge/origin、resend textures、slots 表全欄位、physicalize
per-row + bulk、material details、slot diagnostics、manifest/overrides 路徑、
associated textures、delete json、RC path 驗證顯示、單模型匯出（modal、stage、
summary、CGF、open folder）、Export All（進度、cancel、成敗清單）。

全域：語言切換立即生效、雙輸出目錄（含 browse + 持久化）、profile save/load/
save-as、診斷 popover 全部來源、status 顯示、drag-drop 分流、初始 CLI 參數、
crash logger、CJK 顯示、prefs 全欄位 round-trip、preset/panel 記憶持久化、
既有單元測試全綠、run_gates.ps1 過。

視覺把關：實機截圖與基準圖逐區比對（topbar/rail/stack/stage/timeline 的
配色、間距、圓角、字級層次、狀態色），偏差修到肉眼一致為止。
