# syno-photo-tidy — v0.1 工作分解與檔案結構

## 關鍵規則確認

### 1. Rollback Last Run 規則
- **只針對「同一次 Processed_YYYYMMDD_HHMMSS/ 目錄內的 manifest.jsonl」執行回滾**
- GUI 的 "Rollback Last Run" 按鈕需要讓使用者選擇特定的 Processed_* 目錄
- 不支援跨目錄批次回滾

### 2. Scan 排除規則
已在 execution-plan.md 明確定義，Phase 1 自動排除：
- 名稱匹配 `Processed_*` 的資料夾（所有）
- `TO_DELETE/`、`KEEP/`、`REPORT/` 目錄
- `ROLLBACK_CONFLICTS/`、`ROLLBACK_TRASH/` 目錄
- 符號連結（symlink / junction）：跳過不掃描，記錄 `SKIPPED_SYMLINK`

### 3. Mode B 原地改名 (in-place rename)
- 屬於「重新命名」權限範圍（符合三類行為承諾）
- **必須寫 manifest**：action=RENAME，已在 Phase 7 與 manifest 規格涵蓋
- 即使原地改名也需產生 `REPORT/manifest.jsonl` 以支援回滾

---

## v0.1 目標

建立基礎架構與 GUI 骨架，實現：
1. **Dry-run scan** - 掃描檔案並收集 metadata
2. **Thumbnail isolation** - 偵測縮圖並產生分離計畫
3. **Manifest 基礎架構** - 資料模型與 JSONL 寫入準備（v0.2 完整實作）
4. **GUI 主框架** - Tkinter 介面與背景執行緒架構
5. **設定系統** - 三層設定管理（預設/使用者/執行期）

**預計時間**：2-3 天  
**版本號**：0.1.0

---

## v0.1 工作分解（按 PR 順序）

### PR #1: 專案初始化與設定系統 (0.5天)

**工作內容**：
- [ ] 建立完整專案資料夾結構（見下方詳細結構）
- [ ] 實作 `config/manager.py` - JSON設定檔載入/儲存/驗證
- [ ] 實作 `config/schema.py` - 設定檔驗證邏輯與範圍檢查
- [ ] 實作 `config/defaults.py` - 預設設定值定義（對應 execution-plan.md §15）
- [ ] 實作 `utils/logger.py` - 多層次日誌系統（error.log + GUI log 區）
- [ ] 建立 `config/default_config.json` 檔案
- [ ] 建立 `requirements.txt` 與 `requirements-dev.txt`
- [ ] 建立 `setup.py` 與專案 metadata
- [ ] 建立 `.gitignore`（排除 venv/, *.pyc, __pycache__, dist/, build/ 等）

**驗收標準**：
```python
# 可成功執行
from syno_photo_tidy.config import ConfigManager
config = ConfigManager()
print(config.get('phash.threshold'))  # 應輸出 8
print(config.get('thumbnail.max_size_kb'))  # 應輸出 120

# 驗證機制
errors = config.validate_config()
assert len(errors) == 0
```

**產出檔案**：
- `config/default_config.json` - 完整預設設定（對應 execution-plan.md §15）
- `requirements.txt` - 生產環境依賴
- `requirements-dev.txt` - 開發環境依賴（pytest, black, mypy）

---

### PR #2: 基礎資料模型 (0.5天)

**工作內容**：
- [ ] 實作 `models/file_info.py` - FileInfo dataclass（包含所有 Phase 1 收集的欄位）
- [ ] 實作 `models/action_item.py` - ActionItem dataclass（dry-run 計畫項目）
- [ ] 實作 `models/error_record.py` - ProcessError 分級錯誤處理（E/W/I 三級）
- [ ] 實作 `models/manifest_entry.py` - ManifestEntry dataclass（v0.2 擴充，v0.1 先定義骨架）
- [ ] 實作 `utils/error_handler.py` - 錯誤收集、分類與報告機制

**驗收標準**：
```python
from syno_photo_tidy.models import FileInfo, ActionItem, ProcessError
from syno_photo_tidy.models.error_record import ErrorLevel

# 資料模型可正常實例化
file_info = FileInfo(
    path=Path("test.jpg"), 
    size_bytes=12345,
    ext=".jpg",
    resolution=(4000, 3000),
    timestamp_locked="2024-07-15 14:30:00",
    timestamp_source="exif"
)

action = ActionItem(
    action="MOVE", 
    reason="THUMBNAIL", 
    src_path=Path("a.jpg"),
    dst_path=Path("TO_DELETE/THUMBNAILS/a.jpg")
)

error = ProcessError(
    code="W-101",
    level=ErrorLevel.RECOVERABLE,
    message="Permission denied",
    file_path="locked.jpg"
)

# 測試序列化（JSON 相容）
import json
assert isinstance(file_info.to_dict(), dict)
```

**FileInfo 必須包含欄位**（對應 execution-plan.md §7 Phase 1）：
- `path: Path` - 檔案完整路徑
- `size_bytes: int` - 檔案大小
- `ext: str` - 副檔名（含 .）
- `drive_letter: str` - 磁碟代號（用於跨磁碟檢測）
- `resolution: Optional[Tuple[int, int]]` - (width, height)
- `exif_datetime_original: Optional[str]` - EXIF 時間
- `windows_created_time: float` - st_ctime (fallback)
- `timestamp_locked: str` - 格式 "YYYY-MM-DD HH:MM:SS"
- `timestamp_source: str` - "exif" | "created_time" | "unknown"
- `scan_machine_timezone: str` - 例如 "UTC+8"

---

### PR #3: GUI 主框架 (0.5天)

**工作內容**：
- [ ] 實作 `gui/main_window.py` - Tkinter 主視窗佈局與事件處理
- [ ] 實作 `gui/widgets/file_selector.py` - 資料夾選擇器（支援瀏覽與手動輸入）
- [ ] 實作 `gui/settings_panel.py` - 基礎設定面板（摺疊式，包含縮圖規則調整）
- [ ] 實作背景執行緒架構基礎（`queue.Queue` 通訊、`threading.Event` 取消旗標）
- [ ] 實作 `gui/widgets/progress_bar.py` - 進度條元件（顯示百分比與階段）
- [ ] 實作 `gui/widgets/log_viewer.py` - 日誌顯示區（最近 20 條，自動捲動）
- [ ] 實作 `main.py` - GUI 啟動入口

**驗收標準**：
- GUI 可啟動並顯示完整介面
- 資料夾選擇器可正常開啟檔案瀏覽對話框
- 進度條與日誌區顯示測試訊息
- 背景執行緒可正常啟動與取消（測試用 sleep 模擬耗時操作）

**GUI 佈局要求**（對應 execution-plan.md §9）：
```
[主視窗]
┌─────────────────────────────────────┐
│ 來源資料夾: [________] [瀏覽]        │
│ 輸出目錄:   [________] [瀏覽]        │
│ 模式: [Full Run ▼]                  │
│                                     │
│ [Dry-run Scan] [Execute(灰)]       │
│                                     │
│ 進階設定 [▼]                        │
│   縮圖判定: 大小 [120] KB           │
│             解析度 [640] px         │
│                                     │
│ 進度: [████████░░░░] 80%           │
│ 階段: Scanning... (234/300)        │
│                                     │
│ 日誌:                               │
│ ┌─────────────────────────────────┐ │
│ │ [14:30:15] 開始掃描...          │ │
│ │ [14:30:18] 發現 300 個檔案      │ │
│ │ [14:30:20] 偵測到 45 個縮圖     │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

---

### PR #4: 檔案掃描引擎 (0.5天)

**工作內容**：
- [ ] 實作 `core/scanner.py` - Phase 1 核心：檔案發現與 metadata 收集
- [ ] 實作 `utils/image_utils.py` - 解析度讀取（Pillow）、EXIF 讀取（piexif）
- [ ] 實作 `utils/time_utils.py` - 時間戳處理邏輯（EXIF 解析、格式化）
- [ ] 實作 `utils/path_utils.py` - 路徑處理、跨磁碟檢測、排除規則判定
- [ ] 實作重跑安全的排除邏輯（排除 `Processed_*`、`ROLLBACK_*`、symlink）
- [ ] 整合到 GUI 背景執行緒

**驗收標準**：
```python
from syno_photo_tidy.core import FileScanner
from syno_photo_tidy.config import ConfigManager

config = ConfigManager()
scanner = FileScanner(config)

# 測試掃描
files = scanner.scan_directory(Path("test_photos"))
assert len(files) > 0
assert all(isinstance(f, FileInfo) for f in files)

# 測試排除規則
assert all("Processed_" not in str(f.path) for f in files)
assert all("ROLLBACK_" not in str(f.path) for f in files)
```

**核心邏輯要求**：

1. **排除規則** (`should_exclude_path`)：
```python
def should_exclude_path(self, path: Path) -> bool:
    """
    判斷路徑是否應該排除（避免掃描輸出目錄）
    對應 execution-plan.md §7 Phase 1
    """
    excluded_patterns = [
        'Processed_*',      # 所有輸出根目錄
        'TO_DELETE',
        'KEEP',
        'REPORT',
        'ROLLBACK_TRASH',
        'ROLLBACK_CONFLICTS'
    ]
    
    # 檢查路徑各層級是否匹配排除模式
    for part in path.parts:
        for pattern in excluded_patterns:
            if fnmatch.fnmatch(part, pattern):
                return True
                
    # 檢查是否為符號連結
    if path.is_symlink():
        self.logger.info(f"SKIPPED_SYMLINK: {path}")
        return True
        
    return False
```

2. **時間戳鎖定** (`lock_timestamp`)：
```python
def lock_timestamp(self, file_info: FileInfo) -> Tuple[str, str]:
    """
    鎖定時間戳（優先順序：EXIF > created_time > unknown）
    回傳: (timestamp_locked, timestamp_source)
    格式: "YYYY-MM-DD HH:MM:SS"
    """
    # 1. 嘗試 EXIF DateTimeOriginal
    if file_info.exif_datetime_original:
        return (format_exif_time(file_info.exif_datetime_original), "exif")
    
    # 2. 使用 Windows created_time
    if file_info.windows_created_time:
        dt = datetime.fromtimestamp(file_info.windows_created_time)
        return (dt.strftime("%Y-%m-%d %H:%M:%S"), "created_time")
    
    # 3. 無法取得
    return ("1970-01-01 00:00:00", "unknown")
```

3. **跨磁碟檢測** (`utils/path_utils.py`)：
```python
def is_cross_drive(src_path: Path, dst_path: Path) -> bool:
    """
    檢測是否跨磁碟操作（Windows）
    比對 drive letter: C:\ vs D:\
    """
    return src_path.anchor.upper() != dst_path.anchor.upper()
```

---

### PR #5: 縮圖偵測與 dry-run (0.5天)

**工作內容**：
- [ ] 實作 `core/thumbnail_detector.py` - Phase 2 核心：縮圖判定邏輯
- [ ] 實作 `core/action_planner.py` - Phase 5 核心：dry-run 計畫產生器
- [ ] 實作基礎報告產生（`summary.txt`，包含統計與建議）
- [ ] 整合 GUI 進度顯示與背景執行緒（完整流程）
- [ ] 實作 "No changes needed" 邏輯與顯示

**驗收標準**：
```python
from syno_photo_tidy.core import ThumbnailDetector, ActionPlanner

# 測試縮圖偵測
detector = ThumbnailDetector(config)
keepers, thumbnails = detector.classify_files(scanned_files)
assert len(keepers) + len(thumbnails) == len(scanned_files)

# 測試 action plan 產生
planner = ActionPlanner(config)
plan = planner.generate_plan(keepers, thumbnails)

# 測試 no-op 情境
empty_plan = planner.generate_plan([], [])
assert planner.is_no_changes_needed(empty_plan) == True
```

**縮圖判定規則**（對應 execution-plan.md §7 Phase 2）：
```python
def is_thumbnail(self, file_info: FileInfo) -> bool:
    """
    縮圖判定規則：
    (size_bytes <= 120KB AND max(width, height) <= 640) 
    OR 
    max(width, height) <= 320
    """
    # 若無法取得解析度（HEIC 解碼失敗等）
    if file_info.resolution is None:
        self.logger.warning(f"CANNOT_DETERMINE_RESOLUTION: {file_info.path}")
        return False  # 不判定為縮圖，繼續後續流程
    
    width, height = file_info.resolution
    max_dimension = max(width, height)
    
    # 規則 B: 極小圖一定是縮圖
    if max_dimension <= self.min_dimension_px:  # 320
        return True
    
    # 規則 A: 小檔 + 低解析
    if (file_info.size_bytes <= self.max_size_kb * 1000 and 
        max_dimension <= self.max_dimension_px):  # 120KB, 640px
        return True
    
    return False
```

**summary.txt 格式**：
```
=== syno-photo-tidy 執行摘要 ===
執行時間: 2026-02-11 14:30:15
模式: Full Run (Dry-run)
來源資料夾: D:\Photos
輸出目錄: D:\Photos\Processed_20260211_143015

--- 掃描結果 ---
總檔案數: 1,234 個
總大小: 15.6 GB
影像格式: JPG(890), PNG(234), HEIC(110)

--- 縮圖偵測 ---
偵測為縮圖: 345 個 (1.2 GB)
保留為原圖: 889 個 (14.4 GB)

--- 行動計畫 ---
移動到 TO_DELETE/THUMBNAILS/: 345 個檔案

--- 節省空間 ---
預計釋放: 1.2 GB

--- 下一步 ---
此為 Dry-run，未實際移動任何檔案。
若確認無誤，請點擊 [Execute] 執行實際操作。
```

---

### PR #6: 精確雜湊去重 (1天)

**工作內容**：
- [x] 實作 `core/exact_deduper.py` - 精確雜湊去重邏輯。
- [x] 實作 `utils/hash_calc.py` - 計算 MD5 和 SHA256 雜湊值的工具函數。
- [x] 單元測試：
  - [x] `test_exact_deduper.py`
  - [x] `test_hash_calc.py`

**驗收標準**：
- 精確雜湊去重功能可正確識別並移除重複檔案。
- 單元測試通過。

---

### PR #7: Manifest 管理 (1天)

**工作內容**：
- [x] 實作 `core/manifest.py` - 管理 manifest 的新增、更新與讀取。
- [x] 單元測試：
  - [x] `test_manifest.py`

**驗收標準**：
- Manifest 檔案可正確記錄 RUN 和 ACTION 資訊。
- 單元測試通過。

---

### PR #8: Dry-run 報告更新 (1天)

**工作內容**：
- [x] 更新 `reporting.py` - 在報告中新增重複檔案統計資訊。
- [x] 更新整合測試：
  - [x] `test_basic_workflow.py`

**驗收標準**：
- Dry-run 報告包含重複檔案統計資訊。
- 整合測試通過。

---

## v0.2 目標

新增功能與改進：
1. **精確雜湊去重** - 使用 MD5/SHA256 雜湊值進行檔案去重，確保精確性。
2. **Manifest 管理** - 增加 RUN 和 ACTION 記錄，支援回滾與操作追蹤。
3. **Dry-run 報告更新** - 報告中新增重複檔案統計資訊。

**預計時間**：3-4 天  
**版本號**：0.2.0

---

## v0.2 工作分解（按 PR 順序）

### PR #6: 精確雜湊去重 (1天)

**工作內容**：
- [x] 實作 `core/exact_deduper.py` - 精確雜湊去重邏輯。
- [x] 實作 `utils/hash_calc.py` - 計算 MD5 和 SHA256 雜湊值的工具函數。
- [x] 單元測試：
  - [x] `test_exact_deduper.py`
  - [x] `test_hash_calc.py`

**驗收標準**：
- 精確雜湊去重功能可正確識別並移除重複檔案。
- 單元測試通過。

---

### PR #7: Manifest 管理 (1天)

**工作內容**：
- [x] 實作 `core/manifest.py` - 管理 manifest 的新增、更新與讀取。
- [x] 單元測試：
  - [x] `test_manifest.py`

**驗收標準**：
- Manifest 檔案可正確記錄 RUN 和 ACTION 資訊。
- 單元測試通過。

---

### PR #8: Dry-run 報告更新 (1天)

**工作內容**：
- [x] 更新 `reporting.py` - 在報告中新增重複檔案統計資訊。
- [x] 更新整合測試：
  - [x] `test_basic_workflow.py`

**驗收標準**：
- Dry-run 報告包含重複檔案統計資訊。
- 整合測試通過。

---

## 完整檔案結構（v0.2）

```
syno-photo-tidy/
├── src/
│   └── syno_photo_tidy/
│       ├── core/
│       │   ├── exact_deduper.py          # v0.2: Phase 3
│       │   ├── manifest.py               # v0.2: manifest 管理
│       │   ├── pipeline.py               # v0.2: Pipeline 協調
│       │
│       ├── utils/
│       │   ├── hash_calc.py              # v0.2: MD5/SHA256
│       │
│       └── integration/
│           └── test_basic_workflow.py    # ✅ v0.2 基本流程
│
├── tests/
│   ├── unit/
│   │   ├── test_exact_deduper.py         # v0.2: 精確雜湊去重測試
│   │   ├── test_hash_calc.py             # v0.2: 雜湊計算測試
│   │   ├── test_manifest.py              # v0.2: Manifest 測試
│
├── README.md                            # ✅ 更新 v0.2 功能
└── execution-plan.md                    # 更新 v0.2 計畫
```

---

## v0.3 目標

新增功能與改進：
1. **執行/搬移引擎** - 安全 move/copy 機制，支援跨磁碟操作。
2. **Execute 接線** - GUI 執行流程與 manifest 追加執行結果。

**預計時間**：2 天  
**版本號**：0.3.0

---

## v0.3 工作分解（按 PR 順序）

### PR #9: 執行/搬移引擎 (2天)

**工作內容**：
- [x] 實作 `utils/file_ops.py` - 安全 move/copy。
- [x] 實作 `core/executor.py` - 計畫執行器。
- [x] GUI Execute 接線（執行 + 追加 manifest）。
- [x] 單元測試：
    - [x] `test_file_ops.py`
    - [x] `test_executor.py`

**驗收標準**：
- Execute 可依計畫完成搬移/複製。
- manifest 追加實際執行結果（MOVED/COPIED/ERROR）。
- 單元測試通過。

---

## v0.4 目標

新增功能與改進：
1. **相似去重** - pHash 相似度比對，篩出視覺相似重複。
2. **報告更新** - 分開統計精確/相似重複。

**預計時間**：2 天  
**版本號**：0.4.0

---

## v0.4 工作分解（按 PR 順序）

### PR #10: 相似去重 (2天)

**工作內容**：
- [x] 實作 `core/visual_deduper.py` - pHash 相似去重。
- [x] 更新 `utils/image_utils.py` - pHash 計算。
- [x] 更新 `utils/reporting.py` - 精確/相似去重分離統計。
- [x] 更新 GUI 流程與行動計畫 reason。
- [x] 測試：
    - [x] `test_visual_deduper.py`
    - [x] `test_basic_workflow.py`

**驗收標準**：
- 相似去重可依 pHash 門檻辨識重複。
- 報告分開顯示精確/相似重複統計。
- 測試通過。

---

## v0.5 目標

新增功能與改進：
1. **重新命名** - Synology Photos 風格命名規則。
2. **封存歸檔** - 年/月目錄整理。

**預計時間**：3-4 天  
**版本號**：0.5.0

---

## v0.5 工作分解（按 PR 順序）

### PR #11: 重新命名 (2天)

**工作內容**：
- [x] 實作 `core/renamer.py` - Synology Photos 命名規則。
- [x] 新增模式與設定（命名格式、衝突處理）。
- [x] manifest 記錄 action=RENAME。
- [x] 單元測試：`test_renamer.py`。

**驗收標準**：
- 依規則產生可回滾的 rename 計畫。
- 重名衝突可被偵測並避免覆寫。
- 測試通過。

---

### PR #12: 年/月封存歸檔 (2天)

**工作內容**：
- [x] 實作 `core/archiver.py` - 年/月目錄規則。
- [x] 整合到 GUI/pipeline（在 rename 之後）。
- [x] manifest 記錄 action=ARCHIVE。
- [x] 單元測試：`test_archiver.py`。

**驗收標準**：
- 依時間戳將檔案歸檔到年/月目錄。
- 跨磁碟遵循 copy 規則。
- 測試通過。

---

## v0.6 目標

新增功能與改進：
1. **Rollback Last Run** - 依 manifest 執行回滾。
2. **衝突處理** - 回滾遇到衝突時移入 ROLLBACK_CONFLICTS。

**預計時間**：2-3 天  
**版本號**：0.6.0

---

## v0.6 工作分解（按 PR 順序）

### PR #13: 回滾引擎 (2天)

**工作內容**：
- [x] 實作 `core/rollback.py` - 依 manifest 回滾。
- [x] GUI 加入 Rollback Last Run。
- [x] manifest 追加回滾記錄。
- [x] 單元測試：`test_rollback.py`。

**驗收標準**：
- 可選擇特定 Processed_* 目錄回滾。
- MOVED/RENAMED 依序回滾；COPIED 移入 ROLLBACK_TRASH。
- 衝突時移入 ROLLBACK_CONFLICTS。
- 測試通過。

---

## v0.7 目標

新增功能與改進：
1. **進階進度視窗** - 獨立進度/日誌視窗。
2. **Rollback 視窗** - 選擇 Processed_* 目錄並顯示摘要。
3. **Pipeline 協調** - 抽象化 dry-run 流程。

**預計時間**：2 天  
**版本號**：0.7.0

---

## v0.7 工作分解（按 PR 順序）

### PR #14: 進階視窗與 Pipeline (2天)

**工作內容**：
- [x] 實作 `gui/progress_dialog.py` - 進階進度視窗。
- [x] 實作 `gui/rollback_dialog.py` - 回滾選擇視窗。
- [x] 實作 `core/pipeline.py` - Pipeline 協調。

**驗收標準**：
- 進度視窗可顯示階段/日誌並支援取消。
- 回滾視窗可選擇 Processed_* 目錄並顯示摘要。
- Pipeline 可產生完整 dry-run 計畫。

---

## v0.8 目標

新增功能與改進：
1. **進度視窗強化** - 顯示細節與耗時。
2. **回滾摘要強化** - 顯示可回滾類型與數量。
3. **Pipeline 接 GUI** - Dry-run 使用 Pipeline。

**預計時間**：1-2 天  
**版本號**：0.8.0

---

## v0.8 工作分解（按 PR 順序）

### PR #15: 視窗強化與 Pipeline 接 GUI (1-2天)

**工作內容**：
- [x] 進度視窗新增細節/耗時顯示。
- [x] 回滾視窗顯示摘要（RUN 時間與狀態分布）。
- [x] GUI dry-run 改用 Pipeline。

**驗收標準**：
- 進度視窗與回滾視窗顯示內容正確。
- Pipeline 負責 dry-run 流程。

---

## v0.9 目標

新增功能與改進：
1. **CLI 介面** - dry-run/execute/rollback。
2. **設定檔 UI 強化** - 匯入/匯出與編輯。
3. **效能優化** - 掃描/雜湊與進度估計。

**預計時間**：2-3 天  
**版本號**：0.9.0

---

## v0.9 工作分解（按 PR 順序）

### PR #16: CLI 與效能優化 (2-3天)

**工作內容**：
- [x] CLI 介面（dry-run/execute/rollback）。
- [x] 設定檔 UI 強化。
- [x] 進度估計強化（更精準的階段/ETA）。
- [x] 精確去重強化（size + 多重 hash）。
- [x] hash 併行（平行計算）。

**驗收標準**：
- CLI 可完成 dry-run/execute/rollback。

**符號說明**：
- ✅ = v0.1 實作並測試通過
- v0.X = 後續版本實作

---

## requirements.txt（v0.1）

```txt
# 影像處理核心
Pillow>=10.0.0
pillow-heif>=0.13.0
imagehash>=4.3.1
piexif>=1.1.3

# 進度顯示
tqdm>=4.65.0

# 資料處理
# dataclasses (Python 3.10+ 內建)
```

## requirements-dev.txt（v0.1）

```txt
# 測試框架
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0

# 程式碼品質
black>=23.0.0
mypy>=1.5.0
flake8>=6.0.0

# 文件
# (v0.1 階段暫不需要)
```

---

## v0.1 測試驗收標準

### 單元測試 (Unit Tests)

#### 1. 設定系統測試 (`test_config.py`)
```python
def test_config_load_defaults():
    """預設設定可正常載入"""
    config = ConfigManager()
    assert config.get('phash.threshold') == 8
    assert config.get('thumbnail.max_size_kb') == 120

def test_config_validation():
    """設定驗證機制生效"""
    config = ConfigManager()
    config.set('phash.threshold', 20)  # 超出範圍 0-16
    errors = config.validate_config()
    assert len(errors) > 0

def test_config_user_override():
    """使用者設定可覆蓋預設值"""
    # 測試三層設定優先順序
```

#### 2. 資料模型測試 (`test_models.py`)
```python
def test_file_info_creation():
    """FileInfo 可正常實例化並包含所有必要欄位"""
    
def test_action_item_serialization():
    """ActionItem 可序列化為 JSON"""
    
def test_error_record_levels():
    """錯誤分級 E/W/I 正確運作"""
```

#### 3. 掃描器測試 (`test_scanner.py`)
```python
def test_scanner_basic_scan():
    """基本掃描功能：可發現所有影像檔案"""
    
def test_scanner_exclude_processed_dirs():
    """排除 Processed_* 目錄"""
    
def test_scanner_exclude_rollback_dirs():
    """排除 ROLLBACK_* 目錄"""
    
def test_scanner_skip_symlinks():
    """跳過符號連結並記錄 SKIPPED_SYMLINK"""
    
def test_scanner_timestamp_locking():
    """時間戳鎖定邏輯：EXIF > created_time > unknown"""
```

#### 4. 縮圖偵測測試 (`test_thumbnail_detector.py`)
```python
def test_thumbnail_rule_a():
    """規則 A: 小檔 + 低解析"""
    
def test_thumbnail_rule_b():
    """規則 B: 極小圖（≤320px）"""
    
def test_thumbnail_no_resolution():
    """無法取得解析度時不判定為縮圖"""
```

### 整合測試 (Integration Tests)

#### test_basic_workflow.py
```python
def test_full_dry_run_workflow():
    """
    完整 dry-run 流程測試
    1. 掃描測試資料夾
    2. 偵測縮圖
    3. 產生 action plan
    4. 產生 summary.txt
    """
    # 準備測試資料：50 個原圖 + 20 個縮圖
    # 執行完整流程
    # 驗證結果正確性

def test_no_changes_needed():
    """
    重跑測試：無新檔案時顯示 No changes needed
    """
```

### 功能測試 (手動驗證)

1. **GUI 啟動與互動**
   - [ ] 視窗正常顯示，元件佈局正確
   - [ ] 資料夾選擇器可正常選擇路徑
   - [ ] 進度條與日誌區正常顯示

2. **掃描功能**
   - [ ] 可掃描 100+ 張混合圖片（JPG/PNG/HEIC）
   - [ ] 正確排除 `Processed_*` 輸出目錄
   - [ ] 正確跳過符號連結

3. **縮圖偵測**
   - [ ] 依規則正確分類縮圖與原圖
   - [ ] HEIC 解碼失敗時不崩潰，記錄警告

4. **Dry-run 報告**
   - [ ] 產生正確的 action plan
   - [ ] summary.txt 包含完整統計資訊
   - [ ] 無檔案時顯示 "No changes needed"

5. **設定系統**
   - [ ] GUI 調整縮圖規則參數後生效
   - [ ] 設定檔可儲存與重新載入

6. **錯誤處理**
   - [ ] 單一檔案失敗不影響整體流程
   - [ ] 錯誤訊息清晰顯示在 GUI log 區

### 效能測試

1. **掃描效能**
   - 1000 張圖片（混合格式）掃描 < 30 秒
   - 僅讀取 metadata，不計算 hash/pHash

2. **記憶體使用**
   - 處理 1000 張圖片時記憶體 < 500MB
   - 無明顯記憶體洩漏

3. **GUI 回應性**
   - 背景執行緒工作時 UI 不凍結
   - Cancel 按鈕可在 1 秒內中止操作

### 重跑測試

1. **冪等性**
   - 對已產生 `Processed_20260211_143015/` 的資料夾再次執行
   - 正確排除輸出目錄，不重複掃描
   - 無新檔案時顯示 "No changes needed"

2. **多次執行**
   - 可對同一資料夾多次執行 dry-run
   - 每次產生獨立的 summary 報告

---

## v0.1 完成檢查清單

### 開發環境
- [ ] Python 3.10+ 已安裝
- [ ] 虛擬環境已建立（`python -m venv venv`）
- [ ] 依賴套件已安裝（`pip install -r requirements.txt -r requirements-dev.txt`）
- [ ] pillow-heif 可正常載入（測試 HEIC 支援）
- [ ] VS Code + Python extension 已設定

### 程式碼品質
- [ ] 所有單元測試通過（`pytest tests/unit/ -v`）
- [ ] 整合測試通過（`pytest tests/integration/ -v`）
- [ ] 程式碼格式化完成（`black src/`）
- [ ] 型別檢查無錯誤（`mypy src/`，可選）
- [ ] 無明顯 flake8 警告（`flake8 src/`）

### 功能完整性
- [ ] GUI 可正常啟動並顯示完整介面
- [ ] Dry-run 流程完整可用（scan → detect → plan → report）
- [ ] 設定系統可正常運作（載入/修改/儲存）
- [ ] 錯誤處理優雅（單一失敗不崩潰）
- [ ] 日誌系統正常（GUI log 區 + error.log）

### 文件與提交
- [ ] README.md 包含安裝與使用說明
- [ ] 程式碼註解清晰（關鍵邏輯有註解）
- [ ] Git commit 訊息規範（按 PR 分次提交）
- [ ] v0.1 tag 已建立

---

## v0.1 完成後的下一步

**v0.1 達成目標**：
- ✅ 可用的 GUI 工具
- ✅ 安全掃描檔案（排除輸出目錄）
- ✅ 偵測縮圖並產生計畫
- ✅ Dry-run 報告系統
- ✅ 完整的設定管理
- ✅ 堅實的測試基礎

**準備進入 v0.2**（預計 3-4 天）：
- 精確去重（Hash：MD5/SHA256）
- Manifest.jsonl 完整實作（JSONL 串流寫入）
- 同磁碟 move 實際執行
- 完整 reporting 系統（report.csv + error.log）
- Pipeline 協調器（串聯 8 個 Phase）

**建議實作順序**：
1. PR #1 → PR #2（基礎設施，可並行開發）
2. PR #3（GUI 框架，依賴 PR#1, PR#2）
3. PR #4（掃描引擎，依賴 PR#2, PR#3）
4. PR #5（縮圖偵測與整合，依賴 PR#4）

準備好開始實作 v0.1 了嗎？建議從 **PR #1: 專案初始化與設定系統** 開始！
