# syno-photo-tidy

A Windows photo organizer that **never deletes files**. It isolates recovered thumbnails, deduplicates photos (exact hash + perceptual hash), keeps only the highest-resolution version per duplicate group, and moves everything else into a `TO_DELETE` folder. Optional features include Synology Photos–style renaming and year/month archiving. Every run generates a `manifest.json` to support full rollback (undo).

## Key Features
# syno-photo-tidy

一個以 Windows 為主的相片整理工具，核心原則是**永不刪除檔案**。透過乾跑（dry-run）與完整報告，先安全預覽，再進行後續操作。

## v0.1 特色（目前進度）
- 設定管理骨架（預設值、驗證）
- 排除掃描規則（含 `Processed_*`、`KEEP/`、`TO_DELETE/`、`REPORT/`、`ROLLBACK_*`）
- 縮圖判定函式（規則 A/B）
- 基礎資料模型（FileInfo / ActionItem / ProcessError / ManifestEntry）
- 錯誤收集器（ErrorHandler）
- GUI 主框架（Tkinter 介面、背景執行緒骨架、進度條與日誌區）
- 檔案掃描引擎（metadata 收集、EXIF/解析度讀取、時間戳鎖定）
- 縮圖偵測整合與 dry-run 報告（summary.txt、manifest.jsonl）
- 最小可執行入口：`python -m syno_photo_tidy`
- 基礎單元測試（排除規則、縮圖判定、設定驗證、資料模型）

## v0.2 已完成
- 精確去重（Hash: SHA256/MD5）
- Manifest.jsonl 完整化（RUN + ACTION 記錄）
- Dry-run 報告新增重複檔案統計
- 單元測試與整合測試更新

## v0.2.0（進行中）
- 新增 `safe_op` 配置化重試機制（`retry.max_retries`、`retry.backoff_base_sec`、`retry.backoff_cap_sec`）
- 檔案操作新增 `safe_copy2`、`safe_move`、`safe_makedirs`、`safe_stat`，失敗時回傳 `OperationResult`
- `move_or_copy` 改為透過安全包裝執行，支援網路磁碟暫時性錯誤重試
- manifest 新增 `op_id` 與狀態流轉欄位（`PLANNED`/`STARTED`/`SUCCESS`/`FAILED`）
- 新增 `generate_op_id()`、`update_manifest_status()`、`load_manifest_with_status()`
- 新增 `ResumeManager` 與 GUI `Resume` 按鈕，可自動找最近一次 `manifest.jsonl` 並續跑未完成操作
- Executor 執行前會略過 `SUCCESS` 的 `op_id`，並在執行中更新 manifest 狀態
- 新增網路容錯整合測試（重試成功、部分失敗、Resume 跳過已完成）
- 掃描階段新增 `file_type` 分類（`IMAGE`/`VIDEO`/`OTHER`）
- 新增 `file_extensions.image`、`file_extensions.video`、`move_other_to_keep` 設定
- `VIDEO`/`OTHER` 不做縮圖判定與 pHash；`VIDEO` 保留 exact dedupe、`OTHER` 預設只統計
- `move_other_to_keep=true` 時，`OTHER` 會搬移到 `KEEP/OTHER/`
- 新增 Live Photo 配對（同資料夾 + 時間差 <= 2 秒 + 副檔名條件），採兩階段候選 + 最小時間差一對一匹配
- Live Photo 重新命名共用基底：`IMG_yyyyMMdd_HHmmss_####.ext`（照片與配對影片同基底）
- 新增 `enable_rename`（預設 `false`）與 GUI「啟用重新命名」勾選
- 新增 `resolve_name_conflict()`，命名衝突採可重現 `_0001`、`_0002`…遞增
- 新增螢幕截圖偵測與歸檔：`group_screenshots`、`screenshots_dest`、`screenshot_detection_mode`（strict/relaxed）
- strict 模式支援 PNG metadata（`img.info`，含 tEXt/iTXt/XMP 關鍵字命中），relaxed 可加檔名規則
- 截圖歸檔流程：先 MOVE 到 `KEEP/Screenshots/{YYYY}-{MM}/`，若開啟重新命名再追加 RENAME

## v0.3 已完成
- 安全搬移/跨磁碟 copy 機制
- Execute 流程接線（GUI + manifest 追加執行結果）

## v0.4 已完成
- 相似去重（pHash）
- 報告分開統計精確/相似重複

## v0.5 已完成
- Synology Photos 風格重新命名（規則與執行接線）
- 年/月封存歸檔（規則與執行接線）

## v0.6 已完成
- Rollback Last Run（依 manifest 回滾）

## v0.7 已完成
- 進階進度視窗（progress dialog）
- Rollback 選擇視窗（rollback dialog）
- Pipeline 協調模組

## v0.8 已完成
- 進度視窗強化（細節/耗時）
- 回滾視窗摘要強化
- GUI 改用 Pipeline

## v0.9 已完成
- CLI 介面（dry-run/execute/rollback）
- 設定檔 UI 強化
- 進度估計強化（更精準的階段/ETA）
- 精確去重強化（size + 多重 hash）
- 效能優化（hash 併行）

## v1.0 已完成
- GUI + CLI 全流程（dry-run/execute/rollback）
- 去重、命名、封存、回滾完整流程
- 進度視窗與回滾摘要

## v1.0 Release Notes
- 新增 CLI：`dry-run`/`execute`/`rollback`
- 新增設定檔編輯、匯入/匯出
- 進度視窗加入細節與 ETA
- 精確去重使用 size + 多重 hash，並支援 hash 併行

## 安全規範（不可違反）
- 程式**不得**呼叫 delete/unlink/rmtree，且不提供刪除 UI/CLI。
- 同磁碟搬移：使用 `shutil.move`。
- 跨磁碟：使用 `shutil.copy2` 且**來源保留不動**，並在 summary 明確警告 `cross_drive_copy=true`。
- Scan 必須排除：`Processed_*`、`KEEP/`、`TO_DELETE/`、`REPORT/`、`ROLLBACK_TRASH/`、`ROLLBACK_CONFLICTS/`；遇到 symlink/junction 一律跳過並記錄 `SKIPPED_SYMLINK`。
- 若 action plan 為空：顯示 `No changes needed`，只輸出報告，不做任何 move/rename。
- 所有 planned actions 與 execute 結果都要寫入 `manifest.jsonl`（支援 `.partial` 中斷恢復骨架）。

## 安裝與執行（v1.0）
1. 建立虛擬環境並安裝依賴：
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt -r requirements-dev.txt
   ```
2. 安裝本專案（可編輯模式）：
   ```bash
   pip install -e .
   ```
3. 執行最小入口：
   ```bash
   python -m syno_photo_tidy
   ```
4. 執行測試：
   ```bash
   pytest
   ```

## 換電腦使用（穩定流程）
以下方式穩定度最高，適合長期使用與除錯：
1. 複製整個專案資料夾（例如 `syno-photo-tidy/`）到新電腦。
2. 安裝 Python 3.10 以上版本。
3. 在專案根目錄建立並啟用虛擬環境：
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
4. 安裝依賴與專案：
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   pip install -e .
   ```
5. 啟動 GUI：
   ```bash
   python -m syno_photo_tidy
   ```

## 設定檔
- 預設設定：`config/default_config.json`
- 目前提供欄位：
   - `retry.max_retries`
   - `retry.backoff_base_sec`
   - `retry.backoff_cap_sec`
  - `phash.threshold`
  - `thumbnail.max_size_kb`
  - `thumbnail.max_dimension_px`
  - `thumbnail.min_dimension_px`

## v0.1 限制
- 目前尚未提供回滾執行。

## 開發路線（對照 execution-plan）
- PR #1：專案初始化與設定系統
- PR #2：基礎資料模型
- PR #3：GUI 主框架
- PR #4：檔案掃描引擎
- PR #5：縮圖偵測與 dry-run
- PR #6：精確雜湊去重
- PR #7：Manifest 管理
- PR #8：Dry-run 報告更新
- PR #9：執行/搬移引擎
- PR #10：相似去重（pHash）
- PR #11：重新命名（Synology Photos 風格）
- PR #12：年/月封存歸檔
- PR #13：回滾引擎（Rollback Last Run）
- PR #14：進階視窗與 Pipeline
- PR #15：v0.8 視窗強化與 Pipeline 接 GUI
- PR #16：CLI 與效能優化
  - `max_file_kb`
