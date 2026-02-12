# syno-photo-tidy — v0.2 工作分解與執行計畫

## 版本總覽

**v0.2.0**：NAS/網路磁碟機支援 + 斷線容錯 + Resume  
**v0.2.1**：檔案類型分流（IMAGE/VIDEO/OTHER）  
**v0.2.2**：iPhone Live Photo 配對與共用命名  
**v0.2.3**：GUI 新增「啟用重新命名」選項  
**v0.2.4**：螢幕截圖集中歸檔（Screenshots Bucket）

**預計總時間**：5-7 天  
**核心原則**：不刪除、可重跑 No-op、manifest.jsonl 可回滾

---

## 關鍵規則確認（v0.2 增補）

### 1. 網路磁碟機容錯規則
- 所有檔案 I/O 操作必須透過 `safe_op` 包裝
- 遇到 `WinError`、網路 I/O 失敗時進行 3-5 次重試，採用指數退避（1s → 2s → 4s）
- 最終失敗時寫入 manifest.jsonl（status=FAILED），繼續處理下一個檔案
- 不中斷整體流程，確保部分成功的結果可被保留

### 2. Resume 續跑規則
- manifest.jsonl 記錄狀態：`PLANNED` → `STARTED` → `SUCCESS` | `FAILED`
- 每個操作必須有唯一 `op_id`（以操作內容計算 SHA-256，可重現）
- Resume 時自動跳過 `status=SUCCESS` 的操作
- Resume 目標選擇：
  - **預設**：自動選擇輸出根目錄下「最近一次」的 `Processed_*/REPORT/manifest*.jsonl`
  - **手動**：允許使用者在 GUI 選擇特定 manifest.jsonl 檔案
  - **限制**：僅針對同一個 `Processed_*` run 續跑，不跨 run 合併

### 3. 檔案類型分流規則
- **IMAGE**：維持縮圖偵測 + exact dedupe + near dedupe（pHash）
- **VIDEO**：只做 exact dedupe（不做縮圖判定、不做 pHash）
- **OTHER**：預設只統計報告；可選 `move_other_to_keep` 才搬到 `KEEP/OTHER/`
- 所有 report.csv 與 manifest.jsonl 必須記錄 `file_type` 欄位

### 4. Live Photo 配對規則
- **高信心配對條件**：
  1. 同資料夾
  2. `timestamp_locked` 差異 <= 2 秒
  3. 影像副檔名 in `[.heic, .jpg, .jpeg]` 且 影片副檔名 in `[.mov, .mp4]`
- **命名規則**（Synology 排序一致）：
  - 照片與影片都使用 `IMG_` 前綴，僅副檔名不同
  - 格式：`IMG_yyyyMMdd_HHmmss_####.ext`
- **穩定性要求**：
  - 相同資料集重跑必須產生相同序號與配對結果
  - 排序規則：timestamp_locked ASC → original_filename ASC → path ASC
- manifest.jsonl/report.csv 必須記錄：`is_live_pair`, `pair_id`, `pair_confidence`

### 5. 重新命名開關規則
- GUI 新增 checkbox「啟用重新命名」（預設關閉）
- **未勾選**：不執行任何 RENAME 操作（只做搬移/報告/manifest）
- **勾選**：啟用 RENAME（所有動作寫 manifest，支援 rollback）
- 命名規則：
  - 影像（IMAGE）：`IMG_yyyyMMdd_HHmmss_####.ext`
  - 一般影片（VIDEO，未配對）：`VID_yyyyMMdd_HHmmss_####.ext`
  - Live Photo 配對影片：使用與照片相同基底 `IMG_yyyyMMdd_HHmmss_####.ext`

### 6. 螢幕截圖歸檔規則
- **判定模式**：
  - `strict`：僅 metadata 明確標示為截圖時才判定 `is_screenshot=true`
  - `relaxed`：可額外允許可配置的檔名規則（例如包含 "Screenshot"）
- **行為**：
  - 若 `group_screenshots=true` 且 `is_screenshot=true`：
    1. 先 MOVE 到 `screenshots_dest`（依 `timestamp_locked` 的 `{YYYY}-{MM}/`）
    2. 再視「啟用重新命名」決定是否 RENAME
  - 所有操作寫 manifest，支援 Rollback/Resume
- **證據記錄**：
  - report.csv 與 manifest.jsonl 必須記錄 `evidence`/`reason`（例如 metadata 欄位或命中規則）


### 7. 命名衝突處理規則
- **原則**：任何 MOVE/RENAME 都 **不得覆蓋既有檔案**（no overwrite）
- **衝突定義**：目的地路徑已存在檔案（同名），或計畫中的多個動作會產生相同目的地名稱
- **處理策略（需一致且可重現）**：
  1. 先判定「是否為同檔」：若目的地已存在且（size + hash）相同 → 視為 **已完成**，本次動作標記為 `SKIP_ALREADY_DONE`
  2. 若不同檔 → 透過 `resolve_name_conflict()` 產生不重名的新檔名（例如在檔名末尾加 `_0001`, `_0002`…），並在 report/manifest 記錄 `conflict_resolved=true`
  3. 若仍無法安全處理（例如權限/路徑長度）→ 將該操作寫入 manifest（status=FAILED）並繼續處理下一檔
- **可回滾要求**：衝突處理後的實際目的地路徑必須寫入 manifest，Rollback 以該路徑為準

---

## v0.2.0：NAS/網路磁碟機支援 + 斷線容錯 + Resume

**目標**：支援直接在 NAS/SMB mapped drive 執行整理，並具備網路斷線重試與中斷續跑能力。

**預計時間**：2 天

---

### PR #17: Safe Operation 包裝與重試機制 (0.5天)

**工作內容**：
- [ ] 實作 `utils/file_ops.py` 新增 `safe_op` 裝飾器
  - 支援 3-5 次重試（可配置）
  - 指數退避：1s → 2s → 4s → 8s
  - 捕捉 `OSError`、`PermissionError`、`WinError` 等常見網路 I/O 錯誤
- [ ] 包裝所有檔案操作函式：
  - `safe_copy2(src, dst)` - 複製檔案（含 metadata）
  - `safe_move(src, dst)` - 移動檔案（同磁碟）
  - `safe_makedirs(path)` - 建立目錄
  - `safe_stat(path)` - 取得檔案資訊
- [ ] 實作重試日誌記錄（每次重試寫 log）
- [ ] 實作最終失敗處理（回傳 `OperationResult` 物件，含 success/error_message）

**驗收標準**：
```python
from syno_photo_tidy.utils.file_ops import safe_copy2, safe_move, OperationResult

# 測試正常操作
result = safe_copy2(Path("src.jpg"), Path("dst.jpg"))
assert result.success == True

# 測試重試機制（模擬網路錯誤）
with patch('shutil.copy2', side_effect=[OSError, OSError, None]):
    result = safe_copy2(Path("src.jpg"), Path("dst.jpg"))
    assert result.success == True
    assert result.retry_count == 2

# 測試最終失敗
with patch('shutil.copy2', side_effect=OSError("Network error")):
    result = safe_copy2(Path("src.jpg"), Path("dst.jpg"))
    assert result.success == False
    assert "Network error" in result.error_message
```

**產出介面**：
```python
@dataclass
class OperationResult:
    success: bool
    error_message: Optional[str] = None
    retry_count: int = 0
    elapsed_time: float = 0.0

def safe_op(*,
            config,
            max_retries: Optional[int] = None,
            backoff_base_sec: Optional[float] = None,
            backoff_cap_sec: Optional[float] = None,
            exceptions: Optional[Tuple] = None):
    """
    裝飾器：包裝檔案操作，提供重試與退避機制（NAS/SMB 容錯）

    參數來源優先順序：
      1) 呼叫端顯式傳入（max_retries/backoff_*）
      2) config 設定（retry.*）
      3) 預設值（max_retries=5, backoff_base_sec=1.0, backoff_cap_sec=30.0）

    建議的 config keys：
      - retry.max_retries
      - retry.backoff_base_sec
      - retry.backoff_cap_sec
      - retry.retryable_exceptions

    Returns:
        OperationResult
    """
    resolved_max = max_retries if max_retries is not None else config.get("retry.max_retries", 5)
    resolved_base = backoff_base_sec if backoff_base_sec is not None else config.get("retry.backoff_base_sec", 1.0)
    resolved_cap = backoff_cap_sec if backoff_cap_sec is not None else config.get("retry.backoff_cap_sec", 30.0)
    resolved_exceptions = exceptions if exceptions is not None else (OSError, PermissionError)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs) -> OperationResult:
            start_time = time.time()
            last_error = None

            for attempt in range(resolved_max + 1):
                try:
                    func(*args, **kwargs)
                    elapsed = time.time() - start_time
                    return OperationResult(success=True, retry_count=attempt, elapsed_time=elapsed)
                except resolved_exceptions as e:
                    last_error = e
                    if attempt < resolved_max:
                        wait_time = min(resolved_base * (2 ** attempt), resolved_cap)
                        logger.warning(f"Retry {attempt+1}/{resolved_max} after {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Operation failed after {resolved_max} retries: {e}")

            elapsed = time.time() - start_time
            return OperationResult(success=False, error_message=str(last_error), retry_count=resolved_max, elapsed_time=elapsed)
        return wrapper
    return decorator
```

---

### PR #18: Manifest 狀態管理與 op_id 系統 (0.5天)

**工作內容**：
- [ ] 更新 `models/manifest_entry.py`：
  - 新增 `op_id: str` 欄位（唯一識別碼）
  - 新增 `status: str` 欄位（`PLANNED` | `STARTED` | `SUCCESS` | `FAILED`）
  - 新增 `error_message: Optional[str]` 欄位
  - 新增 `retry_count: int` 欄位
  - 新增 `elapsed_time_sec: float` 欄位
- [ ] 實作 `core/manifest.py` 新增函式：
  - `generate_op_id(action, src_path, dst_path, extra) -> str` - 產生可重現的 op_id（SHA-256）
  - `update_manifest_status(op_id, status, ...)` - 更新特定操作狀態
  - `load_manifest_with_status(path) -> List[ManifestEntry]` - 讀取並解析狀態
- [ ] 實作 manifest.jsonl 寫入邏輯：
  - Phase 5（Dry-run）：寫入 `status=PLANNED`
  - Phase 6（Execute）開始時：更新為 `status=STARTED`
  - Phase 6 完成時：更新為 `status=SUCCESS` 或 `FAILED`

**驗收標準**：
```python
from syno_photo_tidy.core.manifest import generate_op_id, update_manifest_status
from syno_photo_tidy.models import ManifestEntry

# 測試 op_id 產生（唯一性 + 可重現）
ops = [
    ("MOVE", Path("a.jpg"), Path("KEEP/a.jpg"), {}),
    ("MOVE", Path("b.jpg"), Path("KEEP/b.jpg"), {}),
    ("RENAME", Path("c.jpg"), Path("KEEP/c.jpg"), {"new_name": "IMG_20240101_000000_0001.jpg"}),
]
op_ids = [generate_op_id(a, s, d, x) for (a, s, d, x) in ops]
assert len(set(op_ids)) == len(ops)  # 不同操作 → 不同 op_id

# 同一個操作 → op_id 必須相同
same1 = generate_op_id("MOVE", Path("a.jpg"), Path("KEEP/a.jpg"), {})
same2 = generate_op_id("MOVE", Path("a.jpg"), Path("KEEP/a.jpg"), {})
assert same1 == same2

# 測試狀態更新
entry = ManifestEntry(
    op_id="op_3f4a8c2d9a10b4c1",
    action="MOVE",
    src_path=Path("a.jpg"),
    dst_path=Path("KEEP/a.jpg"),
    status="PLANNED"
)

# 更新狀態
entry.status = "SUCCESS"
entry.elapsed_time_sec = 1.234

# 測試序列化
manifest_dict = entry.to_dict()
assert manifest_dict['status'] == 'SUCCESS'
assert 'op_id' in manifest_dict
```

**op_id 格式規範**：
```python
def generate_op_id(action: str, src_path: Path, dst_path: Path, extra: dict | None = None) -> str:
    """
    產生可重現的操作 ID（避免時間戳造成不穩定）

    核心原則：
    - op_id 應只依賴「操作內容」而非當下時間
    - 對同一個操作（相同 action/src/dst/關鍵參數），多次計算必須得到相同結果

    建議 canonical payload（需先做路徑正規化）：
      {
        "action": "MOVE" | "RENAME" | ...,
        "src": "<normalized_src>",
        "dst": "<normalized_dst>",
        "extra": { ... }  # 例如 new_name、pair_id、rename_base 等（可選）
      }

    回傳格式：
      op_<sha256 前 16 碼>
    """
    payload = {
        "action": action,
        "src": str(src_path).replace("\", "/"),
        "dst": str(dst_path).replace("\", "/"),
        "extra": extra or {}
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"op_{digest[:16]}"
```

---

### PR #19: Resume 邏輯與 GUI 整合 (0.5天)

**工作內容**：
- [ ] 實作 `core/resume_manager.py`：
  - `find_latest_manifest(output_root) -> Optional[Path]` - 自動尋找最近的 manifest
  - `load_resume_plan(manifest_path) -> List[ManifestEntry]` - 載入並過濾待續操作
  - `is_resumable(manifest_path) -> bool` - 檢查 manifest 是否可續跑
  - `validate_manifest(manifest_path) -> ValidationResult` - 驗證 manifest 完整性（解析/欄位/重複 op_id）
- [ ] 新增 `validate_manifest(manifest_path) -> ValidationResult`：驗證 jsonl 可解析、必要欄位齊全、op_id 不重複、status 合法
- [ ] 更新 `core/executor.py`：
  - 執行前檢查 `status`，跳過 `SUCCESS` 的操作
  - 執行時先更新為 `STARTED`，完成後更新為 `SUCCESS`/`FAILED`
- [ ] GUI 新增「Resume 上次執行」按鈕與選擇對話框
- [ ] 實作 Resume 進度顯示（顯示已完成/待處理比例）

**驗收標準**：
```python
from syno_photo_tidy.core.resume_manager import ResumeManager

manager = ResumeManager()

# 測試自動尋找最近的 manifest
latest = manager.find_latest_manifest(Path("test_output"))
assert latest is not None
assert latest.name == "manifest.jsonl"

# 測試載入 Resume plan（過濾已完成）
plan = manager.load_resume_plan(latest)
assert all(entry.status != "SUCCESS" for entry in plan)

# 測試可續跑檢查
assert manager.is_resumable(latest) == True

# 測試 manifest 驗證
validation = manager.validate_manifest(latest)
assert validation.is_valid == True

# 測試空 plan（全部已完成）
empty_plan = []
assert len(empty_plan) == 0  # 應顯示 "No changes needed"
```

**GUI Resume 流程**：
```
[主視窗]
┌─────────────────────────────────────┐
│ [Dry-run Scan] [Execute] [Resume]  │
│                                     │
│ Resume 對話框:                      │
│ ┌─────────────────────────────────┐ │
│ │ 選擇要續跑的 manifest:          │ │
│ │ ○ 自動選擇最近一次 (推薦)       │ │
│ │   → Processed_20260212_143000/  │ │
│ │      REPORT/manifest.jsonl      │ │
│ │      (已完成: 234/500)          │ │
│ │                                 │ │
│ │ ○ 手動選擇特定 manifest         │ │
│ │   [瀏覽...]                     │ │
│ │                                 │ │
│ │ [確定] [取消]                   │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

---

### PR #20: 斷線容錯測試與整合 (0.5天)

**工作內容**：
- [ ] 新增測試 `tests/integration/test_network_resilience.py`：
  - 模擬網路中斷（使用 `unittest.mock.patch` 模擬 I/O 錯誤）
  - 驗證重試機制是否正確執行
  - 驗證最終失敗時 manifest 記錄正確
  - 驗證部分成功/部分失敗的情境
- [ ] 新增測試 `tests/unit/test_resume_manager.py`：
  - 測試自動尋找 manifest
  - 測試過濾已完成操作
  - 測試 Resume 邏輯正確性
- [ ] 更新 README：
  - 新增 v0.2.0 功能說明
  - 新增 Resume 使用指引
  - 新增網路磁碟機注意事項

**驗收標準**：
```python
# tests/integration/test_network_resilience.py
def test_network_failure_retry():
    """測試網路失敗重試機制"""
    with patch('shutil.copy2', side_effect=[
        OSError("Network error"),
        OSError("Network error"),
        None  # 第三次成功
    ]):
        result = safe_copy2(Path("src.jpg"), Path("dst.jpg"))
        assert result.success == True
        assert result.retry_count == 2

def test_partial_success_manifest():
    """測試部分成功時 manifest 記錄正確"""
    # 模擬 5 個檔案，其中 2 個失敗
    results = execute_plan_with_failures(plan, fail_indices=[1, 3])
    
    manifest = load_manifest(output_dir / "REPORT" / "manifest.jsonl")
    success_count = sum(1 for e in manifest if e.status == "SUCCESS")
    failed_count = sum(1 for e in manifest if e.status == "FAILED")
    
    assert success_count == 3
    assert failed_count == 2

def test_resume_skip_completed():
    """測試 Resume 正確跳過已完成操作"""
    # 第一次執行（部分完成）
    first_run_result = executor.execute_plan(plan[:30])
    
    # Resume（應跳過前 30 個）
    resume_plan = manager.load_resume_plan(manifest_path)
    assert len(resume_plan) == 70  # 100 - 30
    
    # Resume 執行
    second_run_result = executor.execute_plan(resume_plan)
    
    # 驗證總結果
    final_manifest = load_manifest(manifest_path)
    assert all(e.status == "SUCCESS" for e in final_manifest)
```

**網路磁碟機測試情境**：
1. 正常執行（無錯誤）
2. 暫時性網路錯誤（重試成功）
3. 持續性網路錯誤（最終失敗）
4. 中斷後 Resume（跳過已完成）
5. 跨磁碟操作（SMB → 本地）

---

## v0.2.1：檔案類型分流（IMAGE/VIDEO/OTHER）

**目標**：支援不同檔案類型的差異化處理，VIDEO 不做 pHash，OTHER 可選擇性搬移。

**預計時間**：1 天

---

### PR #21: 檔案類型辨識與資料模型更新 (0.5天)

**工作內容**：
- [ ] 更新 `models/file_info.py`：
  - 新增 `file_type: str` 欄位（`IMAGE` | `VIDEO` | `OTHER`）
- [ ] 實作 `utils/file_classifier.py`：
  - `classify_file_type(file_info) -> str` - 依副檔名分類
  - 支援配置檔案定義副檔名清單
- [ ] 更新 `config/defaults.py`：
  - 新增 `file_extensions.image` - 影像副檔名清單
  - 新增 `file_extensions.video` - 影片副檔名清單
  - 新增 `move_other_to_keep` - 是否搬移 OTHER（預設 false）
- [ ] 更新 `core/scanner.py`：
  - 掃描時自動分類 `file_type`

**驗收標準**：
```python
from syno_photo_tidy.utils.file_classifier import classify_file_type
from syno_photo_tidy.models import FileInfo

# 測試分類
image_file = FileInfo(path=Path("photo.jpg"), ext=".jpg", ...)
assert classify_file_type(image_file) == "IMAGE"

video_file = FileInfo(path=Path("video.mp4"), ext=".mp4", ...)
assert classify_file_type(video_file) == "VIDEO"

other_file = FileInfo(path=Path("doc.pdf"), ext=".pdf", ...)
assert classify_file_type(other_file) == "OTHER"

# 測試配置檔案
config = ConfigManager()
assert ".jpg" in config.get('file_extensions.image')
assert ".mp4" in config.get('file_extensions.video')
```

**預設副檔名配置**：
```json
{
  "file_extensions": {
    "image": [".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".gif"],
    "video": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v", ".3gp"]
  },
  "move_other_to_keep": false
}
```

---

### PR #22: 差異化處理邏輯與 pHash 跳過 (0.5天)

**工作內容**：
- [ ] 更新 `core/thumbnail_detector.py`：
  - VIDEO/OTHER 不進行縮圖判定（直接歸類為 keeper）
- [ ] 更新 `core/visual_deduper.py`：
  - VIDEO 不計算 pHash（跳過近似去重）
  - OTHER 不計算 pHash
- [ ] 更新 `core/exact_deduper.py`：
  - VIDEO 仍進行 exact dedupe（hash 比對）
  - OTHER 不進行去重（直接保留）
- [ ] 更新 `core/action_planner.py`：
  - OTHER 依 `move_other_to_keep` 配置決定是否產生 MOVE action
  - 目的地：`KEEP/OTHER/`

**驗收標準**：
```python
from syno_photo_tidy.core import ThumbnailDetector, VisualDeduper, ActionPlanner

# 測試 VIDEO 不做縮圖判定
files = [
    FileInfo(path=Path("video.mp4"), file_type="VIDEO", size_bytes=100000, ...),
]
detector = ThumbnailDetector(config)
keepers, thumbnails = detector.classify_files(files)
assert len(keepers) == 1  # VIDEO 直接保留
assert len(thumbnails) == 0

# 測試 VIDEO 不做 pHash
visual_deduper = VisualDeduper(config)
groups = visual_deduper.find_near_duplicates(files)
assert len(groups) == 0  # VIDEO 不進入近似去重

# 測試 OTHER 搬移邏輯
config.set('move_other_to_keep', True)
planner = ActionPlanner(config)
plan = planner.generate_plan(
    keepers=[FileInfo(path=Path("doc.pdf"), file_type="OTHER", ...)]
)
assert any(
    a.action == "MOVE" and "KEEP/OTHER/" in str(a.dst_path)
    for a in plan
)
```

**處理流程差異表**：

| 檔案類型 | 縮圖判定 | Exact Dedupe | Near Dedupe (pHash) | 預設處理 |
|---------|---------|--------------|---------------------|---------|
| IMAGE   | ✓       | ✓            | ✓                   | 完整流程 |
| VIDEO   | ✗       | ✓            | ✗                   | 只去重   |
| OTHER   | ✗       | ✗            | ✗                   | 只統計   |

---

## v0.2.2：iPhone Live Photo 配對與共用命名

**目標**：自動識別 Live Photo 配對（照片 + 短影片），共用命名基底，確保 Synology Photos 排序一致。

**預計時間**：1.5 天

---

### PR #23: Live Photo 配對引擎 (0.75天)

**工作內容**：
- [ ] 實作 `core/live_photo_matcher.py`：
  - `find_live_pairs(files) -> List[LivePhotoPair]` - 配對邏輯
  - `is_high_confidence_pair(image, video) -> bool` - 高信心判定
  - `calculate_pair_id(image, video) -> str` - 配對 ID 產生
- [ ] 配對策略改為「兩階段最佳匹配」（最小時間差，一對一）
- [ ] 更新 `models/file_info.py`：
  - 新增 `is_live_pair: bool` 欄位（預設 false）
  - 新增 `pair_id: Optional[str]` 欄位
  - 新增 `pair_confidence: str` 欄位（`high` | `none`）
- [ ] 實作配對演算法：
  - 同資料夾過濾
  - 時間戳差異計算（<= 2 秒）
  - 副檔名驗證
  - 排序規則確保穩定性

**驗收標準**：
```python
from syno_photo_tidy.core.live_photo_matcher import LivePhotoMatcher

matcher = LivePhotoMatcher()

# 測試配對成功
image = FileInfo(
    path=Path("IMG_1234.heic"),
    file_type="IMAGE",
    ext=".heic",
    timestamp_locked="2024-07-15 14:30:00"
)
video = FileInfo(
    path=Path("IMG_1234.mov"),
    file_type="VIDEO",
    ext=".mov",
    timestamp_locked="2024-07-15 14:30:01"
)

pairs = matcher.find_live_pairs([image, video])
assert len(pairs) == 1
assert pairs[0].image == image
assert pairs[0].video == video
assert pairs[0].confidence == "high"

# 測試時間差過大（不配對）
video_far = FileInfo(
    path=Path("IMG_9999.mov"),
    timestamp_locked="2024-07-15 14:31:00"  # 差 60 秒
)
pairs_fail = matcher.find_live_pairs([image, video_far])
assert len(pairs_fail) == 0

# 測試穩定性（相同輸入產生相同結果）
pairs1 = matcher.find_live_pairs(test_files)
pairs2 = matcher.find_live_pairs(test_files)
assert pairs1 == pairs2
```

**配對演算法詳細規範**：
```python
def find_live_pairs(self, files: List[FileInfo]) -> List[LivePhotoPair]:
    """
    Live Photo 配對邏輯（最佳匹配版）

    高信心配對條件（ALL 必須滿足）：
    1. 同資料夾（parent directory 相同）
    2. timestamp_locked 差異 <= 2 秒
    3. image.ext in [.heic, .jpg, .jpeg]
    4. video.ext in [.mov, .mp4]

    兩階段最佳匹配（避免「匹到第一個就 break」造成錯配）：
    - Phase A：枚舉所有候選配對（candidate pairs），計算 time_diff_sec
    - Phase B：依 time_diff_sec 由小到大排序，採一對一 greedy matching
             （每張 image、每段 video 最多被配對一次）

    排序規則（確保穩定性）：
    - 先以 folder path 排序處理
    - candidate sort key：time_diff_sec ASC → image.path.stem ASC → video.path.stem ASC → path ASC
    """
    folder_groups = defaultdict(list)
    for f in files:
        folder_groups[f.path.parent].append(f)

    pairs: list[LivePhotoPair] = []

    for folder in sorted(folder_groups.keys(), key=lambda p: str(p)):
        folder_files = folder_groups[folder]
        images = [f for f in folder_files if f.file_type == "IMAGE" and f.ext.lower() in [".heic", ".jpg", ".jpeg"]]
        videos = [f for f in folder_files if f.file_type == "VIDEO" and f.ext.lower() in [".mov", ".mp4"]]

        # 穩定排序（避免輸入順序影響結果）
        images.sort(key=lambda f: (f.timestamp_locked, f.path.stem, str(f.path)))
        videos.sort(key=lambda f: (f.timestamp_locked, f.path.stem, str(f.path)))

        # Phase A：建立候選清單
        candidates = []
        for img in images:
            for vid in videos:
                time_diff = abs(parse_timestamp(img.timestamp_locked) - parse_timestamp(vid.timestamp_locked))
                if time_diff <= timedelta(seconds=2):
                    candidates.append((float(time_diff.total_seconds()), img, vid))

        # Phase B：最佳匹配（最小時間差優先）
        candidates.sort(key=lambda t: (t[0], t[1].path.stem, t[2].path.stem, str(t[1].path), str(t[2].path)))

        used_images = set()
        used_videos = set()

        for diff_sec, img, vid in candidates:
            if img.path in used_images or vid.path in used_videos:
                continue

            pair_id = self.calculate_pair_id(img, vid)

            img.is_live_pair = True
            img.pair_id = pair_id
            img.pair_confidence = "high"

            vid.is_live_pair = True
            vid.pair_id = pair_id
            vid.pair_confidence = "high"

            pairs.append(LivePhotoPair(
                image=img,
                video=vid,
                pair_id=pair_id,
                confidence="high",
                time_diff_sec=diff_sec
            ))

            used_images.add(img.path)
            used_videos.add(vid.path)

    return pairs
```

---

### PR #24: Live Photo 共用命名基底 (0.75天)

**工作內容**：
- [ ] 更新 `core/renamer.py`：
  - 實作 Live Photo 配對檔案共用序號邏輯
  - 確保同一組使用相同 `yyyyMMdd_HHmmss_####` 基底
  - 照片與影片都使用 `IMG_` 前綴（Synology 排序一致）
- [ ] 新增 `resolve_name_conflict(dst_dir, filename) -> Path`：處理 RENAME/MOVE 目的地同名衝突（不覆蓋，改用 `_0001` 後綴），並確保結果可重現
- [ ] 實作序號分配演算法：
  - 全域計數器（依 timestamp 排序）
  - Live Photo 配對共享序號
  - 未配對影片使用 `VID_` 前綴（若啟用重新命名）
- [ ] 更新 manifest.jsonl 與 report.csv 記錄格式

**驗收標準**：
```python
from syno_photo_tidy.core.renamer import Renamer

renamer = Renamer(config)

# 測試 Live Photo 共用命名
image = FileInfo(
    path=Path("IMG_1234.heic"),
    is_live_pair=True,
    pair_id="pair_001",
    timestamp_locked="2024-07-15 14:30:00"
)
video = FileInfo(
    path=Path("IMG_1234.mov"),
    is_live_pair=True,
    pair_id="pair_001",
    timestamp_locked="2024-07-15 14:30:01"
)

renamed = renamer.generate_rename_plan([image, video])

# 驗證共用基底
assert renamed[0].new_name == "IMG_20240715_143000_0001.heic"
assert renamed[1].new_name == "IMG_20240715_143000_0001.mov"  # 同基底

# 測試未配對影片使用 VID_ 前綴
lone_video = FileInfo(
    path=Path("video.mp4"),
    file_type="VIDEO",
    is_live_pair=False,
    timestamp_locked="2024-07-15 15:00:00"
)

renamed_lone = renamer.generate_rename_plan([lone_video])
assert renamed_lone[0].new_name == "VID_20240715_150000_0002.mp4"

# 測試穩定性（相同輸入產生相同序號）
renamed1 = renamer.generate_rename_plan(test_files)
renamed2 = renamer.generate_rename_plan(test_files)
assert renamed1 == renamed2

# 測試命名衝突（目的地已存在時不覆蓋）
# - 假設 KEEP/ 內已存在同名檔
# - 期望 resolve_name_conflict() 產生不重名名稱（例如加 _0001）
# - 並將實際 new_name/dst_path 寫入 manifest

```

**命名規則總覽**（v0.2.2 版本）：

| 情境 | 前綴 | 格式 | 範例 |
|------|------|------|------|
| Live Photo 照片 | `IMG_` | `IMG_yyyyMMdd_HHmmss_####.ext` | `IMG_20240715_143000_0001.heic` |
| Live Photo 影片 | `IMG_` | `IMG_yyyyMMdd_HHmmss_####.ext` | `IMG_20240715_143000_0001.mov` |
| 一般照片 | `IMG_` | `IMG_yyyyMMdd_HHmmss_####.ext` | `IMG_20240715_150000_0002.jpg` |
| 一般影片（未配對） | `VID_` | `VID_yyyyMMdd_HHmmss_####.ext` | `VID_20240715_160000_0003.mp4` |

**排序一致性**：
- Synology Photos 按檔名字典序排序
- Live Photo 配對使用相同基底 → 自然相鄰排列
- `IMG_20240715_143000_0001.heic` 與 `IMG_20240715_143000_0001.mov` 會連續顯示

---

## v0.2.3：GUI 新增「啟用重新命名」選項

**目標**：提供使用者控制是否執行重新命名，避免強制改名造成困擾。

**預計時間**：0.5 天

---

### PR #25: GUI Rename Checkbox 與邏輯接線 (0.5天)

**工作內容**：
- [ ] 更新 `gui/main_window.py`：
  - 新增 checkbox「啟用重新命名」（預設關閉）
  - 位置：進階設定區塊
- [ ] 更新 `config/manager.py`：
  - 新增 `enable_rename: bool` 配置項（預設 false）
- [ ] 更新 `core/action_planner.py`：
  - 檢查 `enable_rename` 開關
  - 若關閉：不產生任何 RENAME action
  - 若開啟：按既有規則產生 RENAME action
- [ ] 更新 manifest.jsonl 記錄：
  - 記錄 `enable_rename` 狀態到 RUN 區塊

**驗收標準**：
```python
from syno_photo_tidy.core import ActionPlanner
from syno_photo_tidy.config import ConfigManager

# 測試關閉重新命名
config = ConfigManager()
config.set('enable_rename', False)

planner = ActionPlanner(config)
plan = planner.generate_plan(keepers)

# 驗證無 RENAME action
assert all(a.action != "RENAME" for a in plan)

# 測試開啟重新命名
config.set('enable_rename', True)
plan_with_rename = planner.generate_plan(keepers)

# 驗證有 RENAME action
assert any(a.action == "RENAME" for a in plan_with_rename)

# 測試 Live Photo 仍共用基底
live_photo_actions = [
    a for a in plan_with_rename 
    if a.src_file.is_live_pair
]
assert len(set(a.rename_base for a in live_photo_actions)) == 1
```

**GUI 佈局更新**：
```
[進階設定] ▼
┌─────────────────────────────────┐
│ 縮圖判定:                       │
│   大小 [120] KB                 │
│   解析度 [640] px               │
│                                 │
│ ☐ 啟用重新命名                  │
│   (Synology Photos 風格命名)    │
│                                 │
│ ☐ 啟用年/月封存                │
│                                 │
│ ☐ 將螢幕截圖集中歸檔            │
└─────────────────────────────────┘
```

---

## v0.2.4：螢幕截圖集中歸檔（Screenshots Bucket）

**目標**：自動識別螢幕截圖並集中歸檔到專屬資料夾，避免與一般照片混雜。

**預計時間**：1 天

---

### PR #26: 螢幕截圖判定引擎 (0.5天)

**工作內容**：
- [ ] 實作 `core/screenshot_detector.py`：
  - `is_screenshot(file_info, mode) -> Tuple[bool, str]` - 判定函式
  - `detect_from_metadata(file_info) -> Optional[str]` - metadata 檢測（含 EXIF、PNG tEXt/iTXt chunks、XMP）
  - `detect_from_filename(file_info) -> Optional[str]` - 檔名規則檢測
- [ ] 更新 `models/file_info.py`：
  - 新增 `is_screenshot: bool` 欄位（預設 false）
  - 新增 `screenshot_evidence: Optional[str]` 欄位（記錄判定依據）
- [ ] 更新 `config/defaults.py`：
  - 新增 `group_screenshots: bool`（預設 false）
  - 新增 `screenshots_dest: str`（預設 `"KEEP/Screenshots/{YYYY}-{MM}/"`）
  - 新增 `screenshot_detection_mode: str`（預設 `"strict"`）
  - 新增 `screenshot_filename_patterns: List[str]`（relaxed 模式使用）

**驗收標準**：
```python
from syno_photo_tidy.core.screenshot_detector import ScreenshotDetector

detector = ScreenshotDetector(config)

# 測試 strict 模式（僅 metadata）
file_with_meta = FileInfo(
    path=Path("photo.png"),
    exif_data={"UserComment": "Screenshot"}  # 假設 metadata 有標註
)
is_ss, evidence = detector.is_screenshot(file_with_meta, mode="strict")
assert is_ss == True
assert "metadata" in evidence.lower()

# 測試 strict 模式（無 metadata）
file_no_meta = FileInfo(path=Path("Screenshot_20240715.png"))
is_ss, evidence = detector.is_screenshot(file_no_meta, mode="strict")
assert is_ss == False  # strict 不看檔名

# 測試 relaxed 模式（檔名規則）
config.set('screenshot_filename_patterns', ["Screenshot*", "*螢幕截圖*"])
is_ss, evidence = detector.is_screenshot(file_no_meta, mode="relaxed")
assert is_ss == True
assert "filename" in evidence.lower()
```

**metadata 檢測邏輯**（優先可靠性）：  
> 目標：strict 模式下「只靠 metadata」也能涵蓋 EXIF 影像與部分 PNG（含 Windows 產出的 PNG 若帶有 tEXt/iTXt/XMP）

```python
def detect_from_metadata(self, file_info: FileInfo) -> Optional[str]:
    """
    從 metadata 判定是否為螢幕截圖（strict 模式核心）

    支援來源：
    1) EXIF（JPEG/HEIC 等）
    2) PNG tEXt / iTXt chunks（Pillow 可從 img.info 取得）
    3) PNG 內嵌 XMP（常見於 iTXt 或特定 key，例如 'XML:com.adobe.xmp'）

    判定方式（避免臆測，採「關鍵字命中」）：
    - 將可取得的文字型 metadata 彙整成 text_blob
    - 以 config.screenshot_metadata_keywords（預設包含 'screenshot'）做 case-insensitive 搜尋
    - 命中則回傳 evidence 字串，否則回傳 None
    """
    keywords = self.config.get("screenshot_metadata_keywords", ["screenshot"])
    text_parts = []

    # 1) EXIF
    if getattr(file_info, "exif_data", None):
        for k, v in file_info.exif_data.items():
            if v:
                text_parts.append(f"{k}={v}")

    # 2) PNG chunks / XMP（需要能從檔案讀取；示意用 Pillow）
    if file_info.ext.lower() == ".png":
        try:
            from PIL import Image
            img = Image.open(file_info.path)
            info = getattr(img, "info", {}) or {}
            for k, v in info.items():
                if v:
                    text_parts.append(f"{k}={v}")
        except Exception:
            # strict 模式下：讀不到就視為無法以 metadata 判定
            pass

    text_blob = " | ".join([str(x) for x in text_parts]).lower()

    for kw in keywords:
        if kw.lower() in text_blob:
            return f"metadata_keyword_match:{kw}"

    return None
```

---

### PR #27: 螢幕截圖歸檔邏輯與 GUI (0.5天)

**工作內容**：
- [ ] 更新 `core/action_planner.py`：
  - 若 `group_screenshots=true` 且 `is_screenshot=true`：
    1. 產生 MOVE action 到 `screenshots_dest`
    2. 依 `enable_rename` 決定是否產生 RENAME action
  - 目的地路徑生成：`KEEP/Screenshots/{YYYY}-{MM}/`（依 timestamp_locked）
- [ ] 更新 `gui/settings_panel.py`：
  - 新增 checkbox「將螢幕截圖集中歸檔」
  - 新增下拉選單「偵測模式」（strict / relaxed）
  - 新增文字欄位「目的地路徑」（可編輯）
- [ ] 更新 manifest.jsonl 與 report.csv：
  - 記錄 `is_screenshot`、`screenshot_evidence`

**驗收標準**：
```python
from syno_photo_tidy.core import ActionPlanner

config = ConfigManager()
config.set('group_screenshots', True)
config.set('screenshots_dest', 'KEEP/Screenshots/{YYYY}-{MM}/')
config.set('enable_rename', False)  # 不改名

# 測試截圖歸檔（不改名）
screenshot = FileInfo(
    path=Path("Screenshot_001.png"),
    is_screenshot=True,
    screenshot_evidence="filename:Screenshot*",
    timestamp_locked="2024-07-15 14:30:00"
)

planner = ActionPlanner(config)
plan = planner.generate_plan([screenshot])

# 驗證 MOVE action
move_actions = [a for a in plan if a.action == "MOVE"]
assert len(move_actions) == 1
assert "KEEP/Screenshots/2024-07/" in str(move_actions[0].dst_path)

# 驗證無 RENAME action（因為 enable_rename=False）
rename_actions = [a for a in plan if a.action == "RENAME"]
assert len(rename_actions) == 0

# 測試截圖歸檔（啟用改名）
config.set('enable_rename', True)
plan_with_rename = planner.generate_plan([screenshot])

# 驗證有 RENAME action
rename_actions = [a for a in plan_with_rename if a.action == "RENAME"]
assert len(rename_actions) == 1
assert rename_actions[0].new_name.startswith("IMG_20240715_")
```

**GUI 設定區塊**：
```
[進階設定] ▼
┌─────────────────────────────────┐
│ ☐ 將螢幕截圖集中歸檔            │
│   偵測模式: [嚴格 ▼]            │
│             (嚴格/寬鬆)         │
│   目的地: [KEEP/Screenshots/    │
│            {YYYY}-{MM}/]        │
│                                 │
│   說明:                         │
│   - 嚴格: 僅依 metadata 判定    │
│   - 寬鬆: 可額外使用檔名規則    │
└─────────────────────────────────┘
```

**截圖歸檔行為矩陣**：

| `group_screenshots` | `enable_rename` | 行為 |
|---------------------|-----------------|------|
| false | * | 不處理截圖（視為一般照片） |
| true | false | MOVE 到 Screenshots/ 但不改名 |
| true | true | MOVE 到 Screenshots/ 且改名為 `IMG_yyyyMMdd_HHmmss_####.ext` |

---

## 測試策略總覽（v0.2）

### 單元測試（Unit Tests）
- `tests/unit/test_file_ops.py` - safe_op 重試邏輯
- `tests/unit/test_resume_manager.py` - Resume 過濾邏輯
- `tests/unit/test_file_classifier.py` - 檔案類型分類
- `tests/unit/test_live_photo_matcher.py` - Live Photo 配對穩定性
- `tests/unit/test_screenshot_detector.py` - 截圖判定（strict/relaxed）

### 整合測試（Integration Tests）
- `tests/integration/test_network_resilience.py` - 網路斷線容錯
- `tests/integration/test_resume_workflow.py` - 完整 Resume 流程
- `tests/integration/test_file_type_workflow.py` - IMAGE/VIDEO/OTHER 分流
- `tests/integration/test_live_photo_workflow.py` - Live Photo 端到端
- `tests/integration/test_screenshot_workflow.py` - 截圖歸檔端到端

### GUI 測試（Manual/Automated）
- Resume 按鈕與對話框互動
- 檔案類型統計顯示正確
- 啟用重新命名 checkbox 行為
- 截圖歸檔設定與預覽

---

## README 更新要點（v0.2）

### v0.2.0 Release Notes
- ✅ 支援 NAS/網路磁碟機（SMB mapped drive、UNC）
- ✅ 斷線容錯：3-5 次重試 + 指數退避
- ✅ Resume 續跑：自動跳過已完成操作
- ✅ manifest.jsonl 狀態管理（PLANNED/STARTED/SUCCESS/FAILED）

### v0.2.1 Release Notes
- ✅ 檔案類型分流：IMAGE/VIDEO/OTHER
- ✅ VIDEO 不進行縮圖判定與近似去重（pHash）
- ✅ OTHER 可選擇性搬移到 KEEP/OTHER/

### v0.2.2 Release Notes
- ✅ iPhone Live Photo 自動配對（照片 + 短影片）
- ✅ 配對檔案共用命名基底（IMG_yyyyMMdd_HHmmss_####）
- ✅ Synology Photos 排序一致（相鄰顯示）
- ✅ 配對穩定性保證（相同資料集產生相同結果）

### v0.2.3 Release Notes
- ✅ GUI 新增「啟用重新命名」checkbox（預設關閉）
- ✅ 未勾選：只做掃描/搬移/報告，不改檔名
- ✅ 勾選：套用 Synology Photos 風格命名規則

### v0.2.4 Release Notes
- ✅ 螢幕截圖自動識別與集中歸檔
- ✅ 偵測模式：strict（僅 metadata）/ relaxed（可用檔名）
- ✅ 歸檔到 KEEP/Screenshots/{YYYY}-{MM}/
- ✅ 配合「啟用重新命名」選項（可選是否改名）

---

## 安全規範檢查清單（v0.2 強化版）

- [ ] **不刪除**：全程不呼叫 `delete`/`unlink`/`rmtree`
- [ ] **可重跑 No-op**：重複執行相同操作時，已完成的操作不重複執行（Resume 邏輯）
- [ ] **可回滾**：所有 MOVE/RENAME 操作記錄到 manifest.jsonl，支援 Rollback
- [ ] **跨磁碟警告**：跨磁碟操作顯示明確警告，來源檔案不刪除
- [ ] **排除規則**：自動排除 `Processed_*`、`ROLLBACK_*`、symlink
- [ ] **錯誤容忍**：部分失敗不中斷流程，記錄到 manifest 並繼續
- [ ] **狀態追蹤**：manifest.jsonl 記錄完整狀態（PLANNED → STARTED → SUCCESS/FAILED）
- [ ] **穩定性**：相同輸入產生相同輸出（排序規則固定、op_id 可重現）

---

## 版本發布檢查清單

### v0.2.0 發布前
- [ ] 所有單元測試通過（網路容錯、Resume 邏輯）
- [ ] 整合測試通過（模擬網路中斷、部分失敗）
- [ ] GUI Resume 按鈕可正常使用
- [ ] README 更新（功能說明、使用指引）
- [ ] manifest.jsonl 格式文件更新

### v0.2.1 發布前
- [ ] 檔案類型分類測試通過
- [ ] VIDEO 不進 pHash 驗證通過
- [ ] report.csv 含 file_type 欄位
- [ ] GUI 顯示檔案類型統計

### v0.2.2 發布前
- [ ] Live Photo 配對穩定性測試通過
- [ ] 共用命名基底驗證通過
- [ ] Synology Photos 排序測試
- [ ] manifest.jsonl 含 Live Photo 欄位

### v0.2.3 發布前
- [ ] GUI checkbox 行為測試
- [ ] 未勾選時無 RENAME action
- [ ] 勾選時 RENAME 正確執行
- [ ] 與 Live Photo 規則無衝突

### v0.2.4 發布前
- [ ] 截圖判定測試通過（strict/relaxed）
- [ ] 歸檔路徑生成正確（{YYYY}-{MM}）
- [ ] 與「啟用重新命名」協同正確
- [ ] GUI 設定區塊完整

---

## 時間預估總表

| 版本 | 工作項目 | 預估時間 |
|------|---------|---------|
| v0.2.0 | PR #17 Safe Operation | 0.5 天 |
| | PR #18 Manifest 狀態管理 | 0.5 天 |
| | PR #19 Resume 邏輯與 GUI | 0.5 天 |
| | PR #20 斷線容錯測試 | 0.5 天 |
| v0.2.1 | PR #21 檔案類型辨識 | 0.5 天 |
| | PR #22 差異化處理邏輯 | 0.5 天 |
| v0.2.2 | PR #23 Live Photo 配對引擎 | 0.75 天 |
| | PR #24 共用命名基底 | 0.75 天 |
| v0.2.3 | PR #25 GUI Rename Checkbox | 0.5 天 |
| v0.2.4 | PR #26 螢幕截圖判定引擎 | 0.5 天 |
| | PR #27 歸檔邏輯與 GUI | 0.5 天 |
| **總計** | | **6 天** |

---

## 下一步驟

1. **確認需求**：審閱本執行計畫，確認所有功能規格無誤
2. **建立分支**：為 v0.2.0 建立開發分支（`git checkout -b feature/v0.2.0`）
3. **依序實作**：按 PR 順序逐步完成（每個 PR 獨立提交並測試）
4. **持續整合**：每完成一個 PR 即更新 README 並執行測試
5. **發布檢查**：所有檢查清單完成後再發布對應版本

---

## 附錄：資料結構範例

### ManifestEntry（v0.2 版本）
```json
{
  "op_id": "op_3f4a8c2d9a10b4c1",
  "action": "MOVE",
  "src_path": "C:/Photos/IMG_1234.heic",
  "dst_path": "C:/Photos/Processed_20260212_143000/KEEP/IMG_20240715_143000_0001.heic",
  "status": "SUCCESS",
  "error_message": null,
  "retry_count": 0,
  "elapsed_time_sec": 1.234,
  "file_type": "IMAGE",
  "is_live_pair": true,
  "pair_id": "pair_20240715_143000_001",
  "pair_confidence": "high",
  "is_screenshot": false,
  "screenshot_evidence": null,
  "timestamp": "2026-02-12T14:30:25+08:00"
}
```

### FileInfo（v0.2 版本）
```python
@dataclass
class FileInfo:
    path: Path
    size_bytes: int
    ext: str
    drive_letter: str
    resolution: Optional[Tuple[int, int]]
    exif_datetime_original: Optional[str]
    windows_created_time: float
    timestamp_locked: str
    timestamp_source: str
    scan_machine_timezone: str
    
    # v0.2.1 新增
    file_type: str  # IMAGE | VIDEO | OTHER
    
    # v0.2.2 新增
    is_live_pair: bool = False
    pair_id: Optional[str] = None
    pair_confidence: str = "none"  # high | none
    
    # v0.2.4 新增
    is_screenshot: bool = False
    screenshot_evidence: Optional[str] = None
```

### LivePhotoPair（v0.2.2 新增）
```python
@dataclass
class LivePhotoPair:
    image: FileInfo
    video: FileInfo
    pair_id: str
    confidence: str  # high | medium | low
    time_diff_sec: float
```

---

**文件版本**：v0.2.0  
**最後更新**：2026-02-12  
**作者**：AI Development Assistant
