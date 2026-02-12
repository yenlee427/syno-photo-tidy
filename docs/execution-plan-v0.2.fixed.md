# syno-photo-tidy v0.2 fixed 計畫（落地版）

> 本文件作為 v0.2 最終固定規格，若與其他 v0.2 草案衝突，以本文件為準。

## 範圍

- v0.2.0：NAS/網路磁碟容錯 + Resume
- v0.2.1：檔案類型分流（IMAGE/VIDEO/OTHER）
- v0.2.2：Live Photo 配對與共用命名
- v0.2.3：GUI 重新命名開關（`enable_rename`）
- v0.2.4：螢幕截圖集中歸檔

## 固定原則

1. **不刪除檔案**：不得呼叫 `delete/unlink/rmtree`。
2. **可重跑 No-op**：重跑時不得重複破壞既有結果。
3. **可回滾**：所有 MOVE/RENAME 都需寫入 manifest。
4. **狀態流轉**：`PLANNED -> STARTED -> SUCCESS | FAILED`。
5. **可重現 op_id**：以操作內容 canonical payload 計算 SHA-256。
6. **命名不可覆蓋**：遇衝突以可重現 `_0001/_0002...` 解法。

## 功能規格（最終）

### v0.2.0 容錯與續跑

- 檔案 I/O 透過 `safe_op` 包裝，支援重試與指數退避。
- 提供 `safe_copy2/safe_move/safe_makedirs/safe_stat`。
- manifest 記錄 `op_id/status/error_message/retry_count/elapsed_time_sec`。
- Resume 預設可找最近 `Processed_*/REPORT/manifest*.jsonl`，並可手動指定。
- Resume 執行時需跳過 `status=SUCCESS` 的操作。

### v0.2.1 檔案分流

- `IMAGE`：縮圖 + exact dedupe + pHash。
- `VIDEO`：只做 exact dedupe，不進縮圖與 pHash。
- `OTHER`：預設只統計；`move_other_to_keep=true` 才搬到 `KEEP/OTHER`。
- report/manifest 需可帶出 `file_type`。

### v0.2.2 Live Photo

- 配對條件：同資料夾、時間差 <= 2 秒、影像副檔名與影片副檔名在白名單。
- 配對策略：兩階段候選 + 最小時間差一對一匹配。
- 配對後需記錄 `is_live_pair/pair_id/pair_confidence`。

### v0.2.3 重新命名開關

- GUI 提供 `enable_rename`（預設關閉）。
- 未開啟時不得執行 rename。
- 開啟後命名規則：
  - IMAGE：`IMG_yyyyMMdd_HHmmss_####.ext`
  - Live Photo 配對影片：與照片同一個 `IMG_...` 基底
  - 一般 VIDEO：`VID_yyyyMMdd_HHmmss_####.ext`

### v0.2.4 截圖歸檔

- 設定鍵：
  - `group_screenshots`（bool）
  - `screenshots_dest`（預設 `KEEP/Screenshots/{YYYY}-{MM}/`）
  - `screenshot_detection_mode`（`strict|relaxed`）
- `strict`：僅 metadata 明確命中才算截圖。
- `relaxed`：可加檔名規則作補充。
- 行為：先 MOVE 到 Screenshots 目的地；若 `enable_rename=true` 再 RENAME。

## 驗收基準

- 每次變更需通過：
  - `python -m pytest -q`
  - `python -m syno_photo_tidy` 可啟動
- README 需同步更新。

## 目前狀態（2026-02-12）

- v0.2.0 ~ v0.2.4 已完成落地。
- 測試結果：`70 passed, 1 skipped`。
- 已建立並推送 tag：`v0.2.4`。
