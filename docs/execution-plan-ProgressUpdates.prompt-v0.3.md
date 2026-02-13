## Plan: Execute 持續進度更新 (Continuous Progress Updates)

此計畫將 Execute 階段從「黑盒子」轉變為即時可見的處理流程，透過 bytes 級進度、心跳機制、節流更新，讓使用者隨時掌握狀態。針對網路磁碟環境特別設計慢速偵測與友善提示。現有的 queue + threading 架構（100ms 輪詢）將重用並強化，新增事件模型統一進度回報。保持安全邊界：不刪檔、manifest/resume/rollback 一致性不變。

**Steps**

### Phase 1: Progress Event Infrastructure (v0.3.0)

1. **新增進度事件模型** 在 [models/](src/syno_photo_tidy/models/) 建立 `progress_event.py`：
   - `ProgressEventType` enum：`PHASE_START`, `PHASE_END`, `FILE_START`, `FILE_PROGRESS`, `FILE_DONE`, `HEARTBEAT`, `SLOW_NETWORK_WARNING`
   - `ProgressEvent` dataclass：包含 `event_type`, `timestamp`, `phase_name`, `file_path`, `file_size`, `processed_bytes`, `total_bytes`, `op_type` (hash/copy/move/rename), `status`, `elapsed_ms`, `speed_mbps`
   - 所有欄位用 `Optional` 支援不同事件類型

2. **增強 queue 訊息處理** 在 [gui/main_window.py](src/syno_photo_tidy/gui/main_window.py)：
   - 新增 queue 訊息類型：`"progress_event"` 接收 `ProgressEvent` 物件
   - 現有 100ms `_poll_queue()` 改為可配置間隔（250–500ms，預設 250ms）
   - 新增心跳追蹤：記錄 `last_update_time`，在 UI 顯示 "Last update: X.Xs ago"

3. **升級 ProgressDialog** 在 [gui/progress_dialog.py](src/syno_photo_tidy/gui/progress_dialog.py)：
   - 新增 UI 元素：
     - `current_file_label`: 顯示目前檔案名稱（長路徑截斷中段，如 `src/.../folder/file.jpg`）
     - `current_op_label`: 顯示目前動作（hash/copy/move/rename，中文友善顯示）
     - `speed_label`: 顯示速度（MB/s，滑動平均 5 秒）
     - `eta_label`: 顯示 ETA（基於 bytes 計算）
     - `heartbeat_label`: "Last update: X.Xs ago"
     - `network_warning_label`: 慢速警告區域（預設隱藏，偵測到時顯示黃色背景）
   - 新增方法 `handle_progress_event(event: ProgressEvent)`：
     - 根據事件類型更新對應 UI 元素
     - 維護速度計算用的滑動視窗（deque，5 秒內的資料點）
     - 計算 ETA：`(total_bytes - processed_bytes) / avg_speed`
     - 接收 `SLOW_NETWORK_WARNING` 時顯示友善提示

4. **新增配置項** 在 [config/default_config.json](config/default_config.json)：
   ```json
   "progress": {
     "ui_update_interval_ms": 250,
     "heartbeat_interval_sec": 2.0,
     "bytes_update_threshold": 1048576,  // 1MB
     "speed_window_sec": 5,
     "slow_network_threshold_mbps": 5.0,
     "slow_network_check_count": 3
   }
   ```

### Phase 2: Byte-Level Progress in Core Operations (v0.3.1)

5. **改造 hash_calc** 在 [utils/hash_calc.py](src/syno_photo_tidy/utils/hash_calc.py)：
   - `compute_hashes()` 新增參數：`progress_callback: Optional[Callable[[int, int], None]] = None`
   - 在 chunk 迴圈內每讀一塊後呼叫：`progress_callback(bytes_read, total_size)`
   - 節流處理：只在累積超過 `bytes_update_threshold` 或超過 100ms 才回報
   - 返回值新增處理時間，供速度計算使用

6. **改造 file_ops 複製** 在 [utils/file_ops.py](src/syno_photo_tidy/utils/file_ops.py)：
   - 新增 `chunked_copy()` 函數：
     - 參數包含 `progress_callback: Optional[Callable[[int, int], None]]`
     - 使用 `chunk_size_kb` 從 config 讀取（預設 1024KB）
     - 逐 chunk 讀寫並回報進度
     - 維持 `@safe_op` 裝飾器的重試邏輯
     - 記錄開始/結束時間，返回 `OperationResult` 含 elapsed_time
   - `safe_copy2()` 判斷：檔案 > 10MB 且有 callback 時使用 `chunked_copy()`，否則用 `shutil.copy2()`
   - `safe_move()` 跨磁碟時呼叫 `chunked_copy()` + delete

7. **升級 Executor 進度回報與慢速偵測** 在 [core/executor.py](src/syno_photo_tidy/core/executor.py)：
   - `execute_plan()` 新增參數：`progress_callback: Optional[Callable[[ProgressEvent], None]] = None`
   - 每個 `ActionItem` 處理前發送 `FILE_START` 事件
   - 將檔案操作的 bytes callback 轉換為 `FILE_PROGRESS` 事件
   - 操作完成後發送 `FILE_DONE` 事件（含 elapsed_ms, status, speed_mbps）
   - 每處理 N 個檔案或超過 `heartbeat_interval_sec` 發送 `HEARTBEAT` 事件
   - **新增：網路慢速偵測邏輯**：
     - 維護最近 N 次操作的速度 deque（N 從 config `slow_network_check_count` 讀取，預設 3）
     - 每次 `FILE_DONE` 計算速度：`file_size / elapsed_time`
     - 如果連續 3 次操作速度 < `slow_network_threshold_mbps`（預設 5.0 MB/s）
     - 發送 `SLOW_NETWORK_WARNING` 事件，內容：`⚠️ 偵測到網路傳輸較慢 (平均 X.X MB/s)，這可能是網路磁碟延遲，請耐心等候...`
     - 同一次執行只警告一次，避免重複干擾
     - 速度恢復正常時（>10 MB/s 且持續 3 次）可清除警告

8. **整合 ExactDeduper hash 進度** 在 [core/exact_deduper.py](src/syno_photo_tidy/core/exact_deduper.py)：
   - `_compute_hashes()` 傳遞 bytes callback 給 `compute_hashes()`
   - 將 bytes 進度轉換為事件並透過 queue 發送
   - 維持現有 ThreadPoolExecutor (4 workers) 架構
   - Hash 操作也納入慢速偵測（網路磁碟讀取慢）

### Phase 3: Log Management Enhancement (v0.3.2)

9. **Ring Buffer LogViewer** 在 [gui/progress_dialog.py](src/syno_photo_tidy/gui/progress_dialog.py) 或新建 [gui/widgets/ring_log_viewer.py](src/syno_photo_tidy/gui/widgets/ring_log_viewer.py)：
   - 建立 `RingLogViewer` 繼承現有 `LogViewer`
   - 內部使用 `collections.deque(maxlen=500)` 儲存最後 500 行
   - `add_line()` 超過上限時自動移除最舊行
   - 新增配置：`"ui.log_max_lines": 500`

10. **完整 log 寫入檔案** 在 [core/executor.py](src/syno_photo_tidy/core/executor.py) 或 [core/pipeline.py](src/syno_photo_tidy/core/pipeline.py)：
    - Execute 開始時在 `REPORT/` 目錄建立 `run_{timestamp}.log`
    - 所有進度事件寫入此檔案（格式：`[timestamp] [event_type] details`）
    - 使用 Python `logging.FileHandler` 或直接寫檔（避免與 error.log 混淆）
    - Execute 結束時記錄摘要：總檔案數、成功/失敗數、總處理時間、平均速度、最慢/最快檔案
    - 慢速警告也記錄到檔案，方便事後分析

11. **階段摘要報告** 在 [core/pipeline.py](src/syno_photo_tidy/core/pipeline.py)：
    - 每個 `PHASE_END` 事件時發送摘要統計
    - 包含：處理檔案數、成功數、失敗數、總 bytes、平均速度、階段耗時
    - GUI 顯示在 log 視窗或彈出通知

### Phase 4: Integration & Testing (v0.3.3)

12. **連接 Execute 流程** 在 [gui/main_window.py](src/syno_photo_tidy/gui/main_window.py)：
    - `_run_execute()` 建立 progress event callback：`lambda event: self.queue.put({"type": "progress_event", "event": event})`
    - 傳遞給 `executor.execute_plan(progress_callback=...)`
    - 確保 Execute 期間 ProgressDialog 顯示新增的 UI 元素
    - 慢速警告顯示時使用醒目但不干擾的樣式（黃色背景、可摺疊）

13. **測試驗收**：
    - **大檔案測試**：複製 >100MB 影片到網路磁碟，進度條持續更新，顯示速度和 ETA
    - **小檔案測試**：1000+ 小檔案時，心跳每 2 秒更新，顯示處理第幾個
    - **慢速網路測試**：限速網路環境（<5 MB/s），應在第 3 個檔案後顯示慢速警告
    - **混合測試**：快速本地檔案 + 慢速網路檔案，警告應在慢速階段出現，快速階段消失
    - **UI 響應測試**：整個過程中 UI 不凍結，取消按鈕隨時可用
    - **Log 效能測試**：處理 5000+ 檔案後 log 視窗仍流暢（ring buffer 生效）
    - **記錄完整性**：`REPORT/run_*.log` 包含所有事件和慢速警告記錄

### Phase 5 (Optional): System Info Panel (v0.3.4)

14. **psutil 系統監控** 新建 [gui/widgets/system_monitor.py](src/syno_photo_tidy/gui/widgets/system_monitor.py)：
    - 新增 optional dependency `psutil` 到 [requirements.txt](requirements.txt)
    - 建立 `SystemMonitorPanel` widget：顯示 CPU%、記憶體使用、網路吞吐量
    - 在 ProgressDialog 加入 checkbox "顯示系統資訊" 切換顯示
    - 預設關閉，每 1 秒更新一次（獨立 timer）
    - 如果 psutil 未安裝則隱藏此功能
    - 網路吞吐量可與檔案傳輸速度對照，幫助診斷瓶頸

**Verification**

- Execute 階段每秒至少有可見更新（進度條、檔案名稱、或心跳時間）
- 處理 1GB+ 檔案時能看到持續的 bytes 進度和速度顯示
- 網路磁碟慢速場景（<5 MB/s）會在 3 個檔案內顯示友善警告
- 警告出現後使用者明確知道「慢是正常的」，不會誤以為當機
- UI 完全不凍結，取消按鈕隨時可用
- Log 視窗在千行日誌後仍流暢（ring buffer 生效）
- `REPORT/run_*.log` 可追溯完整執行歷程，包含速度分析資料
- 與現有 manifest/resume/rollback 功能完全相容，無副作用

**Decisions**

- **Queue 輪詢間隔**：從 100ms 增加到 250ms，減少 CPU 使用但仍流暢（可配置）
- **Bytes 回報閾值**：1MB 避免過於頻繁的 queue 訊息，大檔案也能流暢更新
- **速度計算窗口**：5 秒滑動平均，平衡反應速度與穩定性
- **Log ring buffer**：500 行上限，平衡資訊量與效能
- **Chunked copy 閾值**：>10MB 檔案才使用分塊複製回報進度，小檔案直接用 shutil 避免開銷
- **心跳間隔**：2 秒，確保即使處理慢也能證明「還活著」
- **慢速網路閾值**：5 MB/s，低於此值連續 3 次視為網路延遲（可配置）
- **慢速警告策略**：同一次執行只警告一次，避免重複干擾；速度恢復後可清除警告
- **警告 UI 設計**：黃色背景、不阻斷操作、可摺疊，友善不干擾
