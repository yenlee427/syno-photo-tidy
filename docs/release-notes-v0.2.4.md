# v0.2.4 Release Notes

## 摘要

v0.2 版本完成 NAS 容錯、Resume、檔案分流、Live Photo 配對命名與截圖集中歸檔，維持「不刪除、可重跑、可回滾」核心原則。

## 新增功能

- **NAS/網路磁碟容錯（v0.2.0）**
  - `safe_op` 重試與指數退避
  - 檔案操作安全包裝：`safe_copy2`、`safe_move`、`safe_makedirs`、`safe_stat`
  - manifest 狀態流轉與可重現 `op_id`
  - Resume 續跑（跳過已成功項目）

- **檔案類型分流（v0.2.1）**
  - `IMAGE`：縮圖 + exact dedupe + pHash
  - `VIDEO`：僅 exact dedupe
  - `OTHER`：預設只統計，可選搬至 `KEEP/OTHER`

- **Live Photo 與命名規則（v0.2.2 / v0.2.3）**
  - 同資料夾 + 時差門檻的高信心配對
  - 配對後照片/影片共用 `IMG_yyyyMMdd_HHmmss_####`
  - 命名衝突以 `_0001` 遞增，確保可重現
  - GUI 可切換 `enable_rename`（預設關閉）

- **截圖集中歸檔（v0.2.4）**
  - `strict/relaxed` 判定模式
  - strict 支援 PNG metadata（`img.info`）
  - `group_screenshots=true` 時集中到 `KEEP/Screenshots/{YYYY}-{MM}/`
  - 可選是否再套用 rename

## 設定鍵

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

## 品質驗證

- 測試：`python -m pytest -q`
- 結果：`70 passed, 1 skipped`

## 注意事項

- 本版本仍堅持「不刪除檔案」設計
- 建議首次導入時先跑 dry-run 驗證規則
- 若要啟用重新命名，請於 GUI 勾選 `enable_rename`
