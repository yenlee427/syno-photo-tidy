# PR 標題

feat(v0.2): NAS 容錯、Resume、檔案分流、Live Photo 命名、截圖歸檔

## 變更範圍

本 PR 完成 v0.2.0 ~ v0.2.4 的落地，涵蓋以下主題：

1. **v0.2.0（容錯 + Resume）**
	- 新增 `safe_op` 重試/退避與 `safe_copy2`、`safe_move`、`safe_makedirs`、`safe_stat`
	- manifest 新增 `op_id`（可重現 SHA-256）與狀態流轉（`PLANNED/STARTED/SUCCESS/FAILED`）
	- Executor 支援 Resume：跳過已 `SUCCESS` 操作，並更新狀態
	- GUI 新增 Resume 流程（可自動找最近 manifest 或手動選擇）

2. **v0.2.1（檔案類型分流）**
	- 掃描階段分類 `IMAGE/VIDEO/OTHER`
	- `VIDEO` 不做縮圖與 pHash，只保留 exact dedupe
	- `OTHER` 預設只統計；可用 `move_other_to_keep` 搬到 `KEEP/OTHER`

3. **v0.2.2 ~ v0.2.3（Live Photo + 命名開關）**
	- 新增 Live Photo 最佳匹配（兩階段候選 + 最小時間差一對一）
	- 新命名規則：Live Photo 共用 `IMG_yyyyMMdd_HHmmss_####`
	- 命名衝突處理：可重現 `_0001/_0002...`，不覆蓋既有檔案
	- GUI `enable_rename` 開關（預設關閉）

4. **v0.2.4（截圖集中歸檔）**
	- 新增 `ScreenshotDetector`（`strict/relaxed`）
	- `strict` 支援 metadata 判定（含 PNG `img.info`）
	- `group_screenshots=true` 時先 MOVE 到 `KEEP/Screenshots/{YYYY}-{MM}/`
	- 若 `enable_rename=true` 再追加 RENAME

## 主要設定鍵

- `retry.max_retries`
- `retry.backoff_base_sec`
- `retry.backoff_cap_sec`
- `file_extensions.image`
- `file_extensions.video`
- `move_other_to_keep`
- `enable_rename`
- `group_screenshots`
- `screenshots_dest`
- `screenshot_detection_mode`

## 測試結果

- `python -m pytest -q`
- 結果：`70 passed, 1 skipped`

## 手動驗證

- `python -m syno_photo_tidy` 可正常啟動 GUI
- Resume 可選最近 manifest 並續跑未完成項目
- 截圖歸檔在 strict/relaxed 模式下符合設定預期

## Commit 切分

- `266ecc5` feat(v0.2.0): add safe_op retry wrappers for file operations
- `c675b1d` feat(v0.2.0): add manifest status lifecycle and resume flow
- `8afd957` feat(v0.2.1): add IMAGE/VIDEO/OTHER classification pipeline
- `2208c27` feat(v0.2.2): add Live Photo pairing and stable rename rules
- `4282e71` feat(v0.2.4): add screenshot detection and bucket planning
- `d8bee11` docs(v0.2): update execution plan and feature notes

## 相容性與風險

- 不包含刪除行為（不呼叫 delete/unlink/rmtree）
- 既有流程維持可重跑（No-op）與 Rollback
- 若外部檔案系統不穩定，會以重試後 FAILED 記錄並繼續下一檔
