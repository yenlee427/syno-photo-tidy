## Plan: Execute 持續進度更新 (Continuous Progress Updates) — v0.3 (Fixed)

此計畫將 Execute 階段從「黑盒子」轉變為即時可見的處理流程，透過 **bytes 級進度**、**心跳機制**、**節流更新**，讓使用者隨時掌握狀態。針對 **網路磁碟（SMB / NAS）**環境特別設計慢速偵測與友善提示。既有的 queue + threading 架構將重用並強化，新增事件模型統一進度回報。保持安全邊界：**不刪檔**、manifest/resume/rollback 一致性不變。

> 本 Fixed 版已套用以下必要修正：
> - 跨磁碟「移動」不得使用 delete；改為 **COPY（保留來源）** 或直接阻擋（擇一以設定決定）
> - 多執行緒 hash 進度事件需 **聚合/節流**，避免「目前檔案」跳來跳去
> - 新增 **CancellationToken**，確保取消可即時生效
> - 慢速偵測需排除小檔案失真，並確保心跳在長操作中仍定期更新
> - log 寫檔建議使用 logging queue，避免 I/O 反過來拖慢 UI

---

## Steps

### Phase 1: Progress Event Infrastructure (v0.3.0)

1. **新增進度事件模型** 在 `src/syno_photo_tidy/models/` 建立 `progress_event.py`：
   - `ProgressEventType` enum：
     - `PHASE_START`, `PHASE_END`, `FILE_START`, `FILE_PROGRESS`, `FILE_DONE`,
     - `HEARTBEAT`, `SLOW_NETWORK_WARNING`
   - `ProgressEvent` dataclass（欄位用 `Optional` 支援不同事件類型）：
     - `event_type`, `timestamp`, `phase_name`
     - `file_path`, `op_type`（hash/copy/move/rename/read-metadata）
     - **單檔維度**：`file_total_bytes`, `file_processed_bytes`
     - **整體 run 維度**：`run_total_bytes`, `run_processed_bytes`
     - `status`, `elapsed_ms`, `speed_mbps`
     - `evidence`（用於慢速警告/診斷訊息）
   - 規則：
     - ETA/速度的計算以 **run_total_bytes/run_processed_bytes** 為主（多執行緒也穩定）
     - `FILE_PROGRESS` 事件至少要能帶：`file_*` 與 `run_*` 其一（允許只有 run 級）

2. **增強 queue 訊息處理（UI 節流）** 在 `src/syno_photo_tidy/gui/main_window.py`：
   - 新增 queue 訊息類型：`"progress_event"`（payload: `ProgressEvent`）
   - `_poll_queue()` 的輪詢間隔改為可配置（250–500ms，預設 250ms）
   - UI 心跳顯示：
     - 記錄 `last_update_time`（**每次接收任何 progress_event** 更新）
     - 另開 UI timer 每 250–500ms 更新 "Last update: X.Xs ago"（即使沒有新事件也更新）

3. **升級 ProgressDialog** 在 `src/syno_photo_tidy/gui/progress_dialog.py`：
   - 新增 UI 元素：
     - `current_file_label`：顯示目前檔案名稱（長路徑截斷中段，如 `src/.../folder/file.jpg`）
     - `current_op_label`：顯示目前動作（hash/copy/move/rename/read-metadata，中文友善顯示）
     - `speed_label`：顯示速度（MB/s，滑動平均 5 秒）
     - `eta_label`：顯示 ETA（以 run_total_bytes/run_processed_bytes 計算）
     - `heartbeat_label`："Last update: X.Xs ago"
     - `network_warning_label`：慢速警告區域（預設隱藏，偵測到時顯示黃色背景）
   - 新增 `handle_progress_event(event: ProgressEvent)`：
     - 根據事件類型更新對應 UI 元素
     - 速度計算用滑動視窗（deque，5 秒內資料點）
     - **重要：多執行緒事件避免抖動**
       - 當 `phase_name == "Hashing"` 且 worker > 1：`current_file_label` 固定顯示 `"Hashing (N workers)..."`，不要每個 worker 事件都改 current file
       - `FILE_PROGRESS` 僅更新 run 級進度與速度/ETA（可選：log 顯示「最近處理的檔案」）

4. **新增配置項** 在 `config/default_config.json`：
   ```json
   "progress": {
     "ui_update_interval_ms": 250,
     "heartbeat_interval_sec": 2.0,
     "bytes_update_threshold": 1048576,
     "speed_window_sec": 5,

     "slow_network_threshold_mbps": 5.0,
     "slow_network_check_count": 3,
     "slow_network_min_bytes": 5242880,
     "slow_network_min_elapsed_ms": 300,

     "hash_progress_workers": 4,
     "log_max_lines": 500
   }
   ```
   - `slow_network_min_bytes` / `slow_network_min_elapsed_ms`：避免小檔案造成速度誤判
   - `hash_progress_workers`：明確化多執行緒數量（UI 也用）

---

### Phase 2: Byte-Level Progress + Cancellation (v0.3.1)

5. **改造 hash_calc（支援 bytes callback + 取消）** 在 `src/syno_photo_tidy/utils/hash_calc.py`：
   - `compute_hashes()` 新增參數：
     - `progress_callback: Optional[Callable[[int, int], None]] = None`
     - `cancel_token: Optional[CancellationToken] = None`
   - chunk 迴圈中：
     - 每讀一塊後 `progress_callback(bytes_read, total_size)`
     - 節流：只在累積超過 `bytes_update_threshold` 或超過 100ms 才回報
     - **每個 chunk 檢查 cancel_token**：若取消，丟出 `CancelledError`
   - 返回值包含處理時間（供速度計算）

6. **改造 file_ops（chunked_copy + 跨磁碟策略修正 + 取消）** 在 `src/syno_photo_tidy/utils/file_ops.py`：
   - 新增 `chunked_copy()`：
     - 參數含 `progress_callback`, `cancel_token`
     - chunk size 從 config `hash.chunk_size_kb` 或新增 `file_ops.copy_chunk_size_kb` 讀取（預設 1024KB）
     - 逐 chunk 讀寫並回報進度、檢查取消
     - 保持 `@safe_op` 的重試
   - `safe_copy2()`：
     - 檔案 > 10MB 且有 callback 時使用 `chunked_copy()`，否則用 `shutil.copy2()`
   - **修正：safe_move() 跨磁碟不得 delete**
     - 同 volume：使用 move/rename（原子性較佳）
     - 跨 volume：改為 **COPY（保留來源）**
       - action type 記錄為 `COPY`（不要假裝成 MOVE）
       - 若產品策略要嚴格：可提供 `block_cross_volume_move=true` 直接阻擋並提示使用者
     - 任何情況：不得呼叫 delete/unlink/rmtree（符合安全邊界）

7. **新增取消機制（CancellationToken）**：
   - 新增 `src/syno_photo_tidy/utils/cancel.py`：
     - `class CancellationToken`：thread-safe flag（`set()` / `is_cancelled()`）
     - `class CancelledError(Exception)`：用於中止流程
   - GUI 取消按鈕：
     - 設定 token
     - ProgressDialog 顯示「正在取消...」
   - Executor 在合適邊界處捕捉 `CancelledError`：
     - 發送 `FILE_DONE(status=CANCELLED)` / `PHASE_END(status=CANCELLED)`
     - 乾淨退出（不造成 UI 卡死）

8. **升級 Executor 進度回報 + 心跳（定時器驅動）+ 慢速偵測（防誤判）** 在 `src/syno_photo_tidy/core/executor.py`：
   - `execute_plan(progress_callback=..., cancel_token=...)`
   - 每個 ActionItem：
     - 開始前發 `FILE_START`
     - 執行中 bytes callback → 轉 `FILE_PROGRESS`
     - 完成後發 `FILE_DONE`（含 elapsed_ms, status, speed_mbps）
   - **心跳（必須保證在長操作也會持續）**
     - 建立 `HeartbeatTicker`（daemon thread 或 timer），每 `heartbeat_interval_sec` 發 `HEARTBEAT`
     - ticker 只依時間驅動，不依檔案數（避免卡在單檔時沒更新）
   - **慢速網路偵測（修正版）**
     - 僅當 `file_total_bytes >= slow_network_min_bytes` 且 `elapsed_ms >= slow_network_min_elapsed_ms` 才納入速度 deque
     - 速度計算：`MBps = file_total_bytes / elapsed_sec / (1024*1024)`
     - 連續 N 次 < threshold 才警告；且同 run 只警告一次
     - 速度恢復正常時可清除警告（可選）

9. **整合 ExactDeduper（多執行緒 hash 事件聚合）** 在 `src/syno_photo_tidy/core/exact_deduper.py`：
   - 仍可保留 ThreadPoolExecutor（workers 由 config `hash_progress_workers` 控制）
   - **事件策略（避免 UI 亂跳）**
     - worker 只回報 bytes 到「聚合器」
     - 聚合器每 250ms（或 bytes_update_threshold）送出一筆 `FILE_PROGRESS`（以 run_total_bytes/run_processed_bytes 為主）
     - UI `current_file_label` 固定顯示 `"Hashing (N workers)..."`

---

### Phase 3: Log Management Enhancement (v0.3.2)

10. **Ring Buffer LogViewer（UI）**：
    - 在 `gui/progress_dialog.py` 或新建 `gui/widgets/ring_log_viewer.py`
    - 內部使用 `collections.deque(maxlen=progress.log_max_lines)`（預設 500）
    - UI 僅保留最後 N 行；完整 log 另外寫檔

11. **完整 log 寫入檔案（使用 logging queue，避免拖慢 UI）**
    - Execute 開始時在 `REPORT/` 建立 `run_{timestamp}.log`
    - 推薦結構：
      - `logging.QueueHandler` + `logging.handlers.QueueListener`
      - FileHandler 寫入 `REPORT/run_*.log`
    - 所有進度事件（含慢速警告）都寫入檔案（格式：`[timestamp] [event_type] details`）
    - 結束時寫摘要：總檔案數、成功/失敗/取消數、總時間、平均速度、最慢/最快檔案

12. **階段摘要報告**
    - 每個 `PHASE_END` 事件包含摘要統計
    - GUI 可顯示於 log 視窗頂端（或單獨摘要區）

---

### Phase 4: Integration & Testing (v0.3.3)

13. **連接 Execute 流程（UI → worker → queue）**
    - `main_window._run_execute()` 建立 callback：
      - `lambda event: self.queue.put({"type": "progress_event", "event": event})`
    - 傳遞給 `executor.execute_plan(progress_callback=..., cancel_token=...)`
    - 確保 ProgressDialog 顯示新增元素
    - 慢速警告顯示使用醒目但不干擾樣式（黃色背景、可摺疊）

14. **測試驗收（更新版）**
    - **大檔案測試**：複製 >100MB 影片到網路磁碟，進度條持續更新，顯示速度/ETA
    - **小檔案測試**：1000+ 小檔案時，心跳每 2 秒更新（即使卡在單檔也要更新），UI 不凍結
    - **慢速網路測試**：限速 <5MB/s，且檔案 > slow_network_min_bytes，應在 N 次後顯示慢速警告；小檔案不應誤判
    - **混合測試**：快速本地 + 慢速網路，警告只在慢速階段出現
    - **取消測試**：處理大檔中按取消，應在下一個 chunk 內停止並顯示 CANCELLED 狀態
    - **Log 效能測試**：處理 5000+ 檔案後 UI log 仍流暢（ring buffer），log 檔完整
    - **安全邊界測試**：跨 volume 時不得 delete；若採 COPY 策略，來源需保留；manifest 需記錄 COPY

---

### Phase 5 (Optional): System Info Panel (v0.3.4)

15. **psutil 系統監控（可選）**
    - optional dependency `psutil`（預設不安裝）
    - ProgressDialog 加 checkbox "顯示系統資訊"（預設關閉）
    - 每 1 秒更新（獨立 timer），未安裝則隱藏

---

## Verification（修正版）

- Execute 階段每秒至少有可見更新（進度條/速度/ETA/心跳其中之一）
- 處理 1GB+ 檔案時能看到持續的 bytes 進度與速度顯示
- 心跳在長操作（hash/copy）期間仍會定期更新（定時器驅動）
- 慢速網路場景（<5 MB/s）在符合最小檔案/時間條件下觸發警告，且不因小檔誤判
- UI 不凍結，取消按鈕可在大檔處理中快速生效（chunk 內檢查 token）
- UI log 長時間執行仍流暢（ring buffer 生效）
- `REPORT/run_*.log` 可追溯完整事件（建議 logging queue）
- 與現有 manifest/resume/rollback 完全相容，且不引入 delete 行為

---

## Decisions（修正版）

- Queue 輪詢間隔：250ms（可配置）
- Bytes 回報閾值：1MB（可配置）
- 速度計算窗口：5 秒滑動平均
- Log ring buffer：預設 500 行（可配置）
- Chunked copy 閾值：>10MB 才使用分塊複製回報進度
- 心跳間隔：2 秒（定時器驅動，不卡在單檔）
- 慢速網路偵測：
  - 閾值：5 MB/s
  - 連續次數：3 次
  - 最小檔案：>= 5MB
  - 最小耗時：>= 300ms
- 跨 volume 行為：
  - 預設：視為 COPY（保留來源），不得 delete
  - 可選：阻擋跨 volume move（用設定開關）
- 多執行緒 hash UI 顯示策略：
  - current_file 固定顯示 `"Hashing (N workers)..."`，bytes 進度採聚合回報，避免跳動
