# PR 標題

feat(v0.3): Execute 持續進度更新（bytes 進度、取消、心跳、ring log）

## 變更範圍

本 PR 完成 `execution-plan-ProgressUpdates.prompt-v0.3.fixed.md` 的核心階段：`v0.3.0`、`v0.3.1`、`v0.3.2`、`v0.3.3`。

1. **v0.3.0（Progress Event Infrastructure）**
	- 新增 `ProgressEvent` / `ProgressEventType` 事件模型
	- `MainWindow` 新增 `progress_event` queue 訊息處理
	- UI 輪詢改為可配置（預設 250ms）
	- `ProgressDialog` 新增：目前檔案、目前動作、速度、ETA、心跳、慢速警告顯示
	- Hash 多執行緒時，`current_file` 固定為 `Hashing (N workers)...`

2. **v0.3.1（Byte-Level Progress + Cancellation）**
	- `hash_calc.compute_hashes()` 支援 bytes callback、節流、取消檢查
	- 新增 `CancellationToken` / `CancelledError`
	- `file_ops` 新增 `chunked_copy()`，大檔複製可回報 bytes
	- 跨磁碟 move 改為 COPY（保留來源），不做刪除
	- `PlanExecutor` 新增事件回報、心跳 ticker、慢速網路防誤判偵測

3. **v0.3.2（Log Management Enhancement）**
	- UI log 改為 `deque(maxlen=N)` ring buffer
	- Execute 期間新增 `REPORT/run_*.log`
	- 採 `QueueHandler + QueueListener` 佇列寫檔，降低 I/O 對 UI 影響
	- `PHASE_END` 附帶摘要資訊並顯示在進度視窗

4. **v0.3.3（Integration & Testing）**
	- Execute 流程接線完整化（worker -> queue -> UI）
	- 新增 executor 事件回呼測試，驗證 `PHASE_START/FILE_START/FILE_DONE/PHASE_END`

## 安全邊界對齊

- 不新增刪除功能，不提供刪除 UI/CLI。
- 跨磁碟 move 以 COPY 實作，來源保留。
- 取消採 cooperative cancellation（chunk 邊界生效）。
- 心跳採定時器驅動，不依賴檔案數。

## 主要設定鍵（新增/擴充）

- `progress.ui_update_interval_ms`
- `progress.heartbeat_interval_sec`
- `progress.bytes_update_threshold`
- `progress.speed_window_sec`
- `progress.slow_network_threshold_mbps`
- `progress.slow_network_check_count`
- `progress.slow_network_min_bytes`
- `progress.slow_network_min_elapsed_ms`
- `progress.hash_progress_workers`
- `progress.log_max_lines`
- `file_ops.copy_chunk_size_kb`
- `file_ops.chunked_copy_threshold_bytes`
- `file_ops.block_cross_volume_move`

## 測試結果

- 指令：`python -m pytest -q`
- 結果：`75 passed, 1 skipped`

## 手動驗證重點

- `python -m syno_photo_tidy` 可啟動 GUI 並進入 Execute 流程
- 網路磁碟大檔（>100MB）可觀察 bytes 進度、速度、ETA、心跳
- 大檔執行中按取消，可於下一個 chunk 內中止
- 慢速網路條件下可看到慢速警告，小檔案不誤判
- 長時間執行後 UI log 維持流暢，且 `REPORT/run_*.log` 完整

## Commit 切分

- `2621263` feat(v0.3.0): 新增 Execute 進度事件模型與 UI 節流顯示
- `b43d42b` feat(v0.3.1): 加入 bytes 進度、取消機制與心跳事件
- `85e3f0e` feat(v0.3.2): 加入 ring buffer 與 run log 佇列寫入
- `a374f32` test(v0.3.3): 補上 execute 進度事件接線驗證

## 風險與注意事項

- Tkinter 視窗測試需人工關閉，終端可能顯示 `KeyboardInterrupt`（非程式錯誤）
- `run_*.log` 寫入路徑依 manifest/report 目錄而定，需確保目錄具寫入權限
