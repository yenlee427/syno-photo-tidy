請全程使用繁體中文（台灣用語）回覆與撰寫文件/註解。請在不破壞既有「不刪除（不呼叫 delete/unlink/rmtree）、可重跑 No-op、manifest.jsonl 可回滾」的前提下，實作 v0.2 升級，目標如下：

v0.2.0：支援 NAS/網路磁碟機（SMB mapped drive 或 UNC）直接整理 + 斷線容錯 + Resume
- 所有檔案操作以 safe_op 包裝：遇到 WinError/網路 I/O 失敗做 3-5 次重試與退避，仍失敗寫入 manifest 並繼續下一檔
- manifest.jsonl 記錄狀態 PLANNED/STARTED/SUCCESS/FAILED，並支援中斷後重開程式 Resume（跳過已 SUCCESS 的 op_id）
- Resume 續跑目標選擇規則（需明確落地到 GUI）：
  - 預設：自動選擇輸出根目錄下「最近一次」的 Processed_*/REPORT/manifest*.jsonl 作為 Resume 目標
  - 允許：使用者在 GUI 手動選擇某個 manifest.jsonl（指定要 Resume 的 run）
  - 限制：Resume 僅針對「同一個 Processed_* run」續跑，不跨 run 合併
- action plan 空時顯示 No changes needed，只產出報告
- 斷線容錯測試：模擬網路磁碟機 I/O 失敗，驗證 safe_op 重試與退避行為，以及最終失敗記錄到 manifest 的正確性

v0.2.1：支援檔案類型分流
- IMAGE：維持縮圖 + exact dedupe + near dedupe
- VIDEO：只做 exact dedupe（不做縮圖、不做 pHash）
- OTHER：預設只統計報告；可選 move_other_to_keep 才搬到 KEEP/OTHER
- report.csv 與 manifest.jsonl 新增 file_type 欄位

v0.2.2：支援 iPhone Live Photo 配對與共用命名（修正版）
- 高信心配對：同資料夾 + (timestamp_locked 差<=2秒) + (image ext in heic/jpg 且 video ext in mov/mp4)
- 配對成功同組共用命名基底：同一組共享 yyyyMMdd_HHmmss_####
- 命名規則（Synology 排序一致）：照片與影片都使用 IMG_ 前綴，僅副檔名不同
  - image -> IMG_yyyyMMdd_HHmmss_####.ext
  - video -> IMG_yyyyMMdd_HHmmss_####.ext
- manifest.jsonl/report.csv 必須記錄 is_live_pair, pair_id, pair_confidence（high/none）
- 重跑結果必須穩定：相同資料集重跑不應產生不同序號或不同配對（排序規則固定）


v0.2.3：GUI 新增「啟用重新命名」選項（預設關閉）
- 若未勾選：不執行 rename（只做檔案掃描/搬移/報告/manifest 記錄）
- 若勾選：啟用 rename（所有 rename 動作寫入 manifest，支援 rollback）
- 命名規則需與 v0.2.2（Live Photo）一致，避免規則互相打架：
  - 影像（IMAGE）：IMG_yyyyMMdd_HHmmss_####.ext
  - 一般影片（VIDEO，且「未配對為 Live Photo」）：VID_yyyyMMdd_HHmmss_####.ext
  - Live Photo 配對成功的影片：使用與照片相同的 IMG_ 前綴（Synology 排序一致）
    - image -> IMG_yyyyMMdd_HHmmss_####.ext
    - video -> IMG_yyyyMMdd_HHmmss_####.ext


請將工作拆成多次小提交，每個版本都更新 README 與新增測試（至少包含：file_type 分類、VIDEO 不進 pHash、Live Photo 配對穩定、Resume 跳過已完成操作、GUI rename checkbox 行為）。

請新增 v0.2.4「螢幕截圖集中歸檔」功能：

1) 設定：
- group_screenshots（預設 false）
- screenshots_dest（預設 KEEP/Screenshots/{YYYY}-{MM}/）
- screenshot_detection_mode：strict/relaxed

2) 判定：
- 在 scan record 新增 is_screenshot 欄位
- strict：僅在 metadata 明確標示時才判定為截圖；未標示者一律非截圖
- relaxed：可加入可配置的檔名規則（例如含 Screenshot）作為補充條件
- 將 evidence/reason 寫入 report.csv 與 manifest.jsonl

3) 行為：
- 若 group_screenshots=true，對 is_screenshot=true 的檔案先 MOVE 到 screenshots_dest（依 timestamp_locked 的 YYYY/MM）
- rename 遵循 GUI「啟用重新命名」checkbox：未勾選不改名；勾選則套用 IMG_yyyyMMdd_HHmmss_####.ext
- 所有 MOVE/RENAME 寫 manifest，支援重跑 No-op、Rollback、Resume
- 不呼叫 delete/unlink/rmtree

4) GUI：
- 新增 checkbox「將螢幕截圖集中歸檔」
- 新增目的地與模式設定（可放在進階設定區）

5) 測試：
- 至少測：is_screenshot 判定函式（strict/relaxed）、截圖 move 目的地路徑生成、重跑 skip 規則
並更新 README（繁體中文）。
v0.2.4：螢幕截圖集中歸檔（Screenshots Bucket）
- 目的：將判定為螢幕截圖的檔案集中搬移到同一處，避免與一般照片混在一起
- GUI 新增：
  - checkbox：將螢幕截圖集中歸檔（預設關閉）
  - 選項：screenshot_detection_mode = strict | relaxed（預設 strict）
  - 選項：screenshots_dest（預設 KEEP/Screenshots/{YYYY}-{MM}/）

- 判定（優先可靠性）：
  - strict：僅在 metadata 明確標示為截圖時才判定 is_screenshot=true
  - relaxed：可額外允許檔名規則（例如包含 Screenshot）作為補充條件
  - 必須在 report.csv 與 manifest.jsonl 記錄 evidence/reason（例如 metadata 欄位或命中規則）

- 行為（必須可重跑、可回滾、可續跑）：
  - 若 group_screenshots=true 且 is_screenshot=true：
    1) 先 MOVE 到 screenshots_dest（依 timestamp_locked 的 YYYY-MM）
    2) 再視「啟用重新命名」checkbox 決定是否 RENAME
  - 重新命名規則：
    - 若 enable_rename=false：只搬移、不改名
    - 若 enable_rename=true：截圖也套用既有命名規則（預設 IMG_yyyyMMdd_HHmmss_####.ext）
  - 所有 MOVE/RENAME 動作都必須寫入 manifest.jsonl（含 status），支援 Rollback/Resume
  - 不呼叫 delete/unlink/rmtree；不提供刪除功能
