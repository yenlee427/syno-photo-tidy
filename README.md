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

## 安全規範（不可違反）
- 程式**不得**呼叫 delete/unlink/rmtree，且不提供刪除 UI/CLI。
- 同磁碟搬移：使用 `shutil.move`。
- 跨磁碟：使用 `shutil.copy2` 且**來源保留不動**，並在 summary 明確警告 `cross_drive_copy=true`。
- Scan 必須排除：`Processed_*`、`KEEP/`、`TO_DELETE/`、`REPORT/`、`ROLLBACK_TRASH/`、`ROLLBACK_CONFLICTS/`；遇到 symlink/junction 一律跳過並記錄 `SKIPPED_SYMLINK`。
- 若 action plan 為空：顯示 `No changes needed`，只輸出報告，不做任何 move/rename。
- 所有 planned actions 與 execute 結果都要寫入 `manifest.jsonl`（支援 `.partial` 中斷恢復骨架）。

## 安裝與執行（v0.1）
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

## 設定檔
- 預設設定：`config/default_config.json`
- 目前提供欄位：
  - `phash.threshold`
  - `thumbnail.max_size_kb`
  - `thumbnail.max_dimension_px`
  - `thumbnail.min_dimension_px`

## v0.1 限制
- 目前已完成 PR #1～PR #5，尚未提供實際搬移與回滾執行。
- 之後會依照 `docs/execution-plan.md` 依序完成 PR #2～PR #5。

## 開發路線（對照 execution-plan）
- PR #1：專案初始化與設定系統
- PR #2：基礎資料模型
- PR #3：GUI 主框架
- PR #4：檔案掃描引擎
- PR #5：縮圖偵測與 dry-run
  - `max_file_kb`
