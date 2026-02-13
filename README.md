# syno-photo-tidy

`syno-photo-tidy` 是一套以 Windows 桌面 GUI 為主的相片整理工具，核心原則是**永不刪除檔案**。

## 專案安全邊界
- 不呼叫 `delete` / `unlink` / `rmtree`，也不提供刪除 UI/CLI。
- 只做讀取、搬移、重新命名、複製（跨磁碟一律 COPY 且保留來源）。
- 所有流程都會輸出 report 與 manifest，支援 resume/rollback。

## 目前重點功能（v0.3.0）
- 新增 Execute 進度事件模型：`ProgressEvent` / `ProgressEventType`。
- GUI 佇列新增 `progress_event` 訊息型別。
- 進度輪詢改為可配置（預設 250ms）。
- 進度視窗新增欄位：
  - 目前檔案
  - 目前動作
  - 速度（MB/s）
  - ETA
  - `Last update: X.Xs ago` 心跳
  - 慢速網路警告區塊（事件觸發時顯示）
- Hashing 多執行緒時，`current file` 固定顯示 `Hashing (N workers)...`，避免 UI 跳動。

## 目前重點功能（v0.3.1）
- `hash_calc.compute_hashes()` 支援 bytes 進度回呼與 `CancellationToken`。
- `file_ops.safe_copy2()` 支援大檔 chunked copy（>10MB）與 bytes 進度回呼。
- 跨磁碟 MOVE 改為 COPY（保留來源）；可透過設定選擇阻擋跨磁碟 move。
- Execute 流程加入 cooperative cancellation：取消後在下一個 chunk 內中止。
- Executor 加入 HEARTBEAT 定時事件（與檔案數無關）與慢速網路防誤判偵測。

## 目前重點功能（v0.3.2）
- UI log 改為 ring buffer（`deque(maxlen=N)`），長時間執行仍保持流暢。
- Execute 期間建立 `REPORT/run_*.log`，完整記錄所有進度事件。
- 使用 `QueueHandler + QueueListener` 非同步寫檔，降低 I/O 對 UI 的影響。
- 每個階段結束（`PHASE_END`）會附帶摘要統計並顯示在進度視窗日誌。

## 目前重點功能（v0.3.3）
- `MainWindow._run_execute()` 已完整接線：worker 透過 queue 回傳 `progress_event`。
- `ProgressDialog` 會即時顯示 bytes 進度、速度、ETA、心跳與慢速警告。
- Execute 期間至少會有可見更新（檔案進度或 HEARTBEAT），降低「像當機」的感受。

## 設定檔
預設檔案：`config/default_config.json`

### v0.3 進度相關設定
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

### v0.3 檔案操作相關設定
```json
"file_ops": {
  "copy_chunk_size_kb": 1024,
  "chunked_copy_threshold_bytes": 10485760,
  "block_cross_volume_move": false
}
```

## 安裝與執行
1. 建立虛擬環境並安裝依賴：
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

2. 啟動 GUI：
```bash
python -m syno_photo_tidy
```

3. 執行測試：
```bash
pytest -q
```

## 手動驗證（v0.3.0）
- 啟動 GUI 後執行 Dry-run + Execute。
- 確認進度視窗可看到「目前檔案 / 目前動作 / 速度 / ETA / Last update」。
- 在 Hashing 階段（多執行緒）確認目前檔案顯示固定為 `Hashing (N workers)...`。
- 若有送出慢速網路事件，確認警告區塊顯示提示。

## 手動驗證（v0.3.1）
- 在網路磁碟準備單一大檔（例如 >100MB），執行 Execute。
- 確認進度條、速度與 ETA 持續更新，且 `Last update` 會持續刷新。
- 執行中按「取消」，確認在下一個 chunk 內停止並顯示取消狀態。
- 以跨磁碟路徑測試 MOVE 行為，確認實際為 COPY 且來源檔案仍保留。

## 手動驗證（v0.3.2 / v0.3.3）
- 連續處理大量檔案（例如 5000+）時，確認 UI log 仍順暢且只保留最後 N 行。
- 執行後到 `REPORT/` 檢查 `run_*.log`，確認含 `PHASE_START/FILE_PROGRESS/HEARTBEAT/PHASE_END`。
- 在慢速網路磁碟（SMB/NAS）跑大檔，確認符合條件（>=5MB 且 >=300ms）才出現慢速警告。
- 在 Hashing 多執行緒時，確認目前檔案固定顯示 `Hashing (N workers)...`，不會跳動。
