推薦的 v0.3 改善方案（可直接落地）

下面這套做完，Execute 會像「下載器」一樣持續更新：目前檔案、速度、ETA、最後心跳時間。

1) 進度事件模型（Progress Events）

在核心 pipeline 裡新增統一事件：

PHASE_START / PHASE_END

FILE_START(file_path, size_bytes, op_type)

FILE_PROGRESS(file_path, processed_bytes, total_bytes) ← 讓大檔也會動

FILE_DONE(file_path, status, elapsed_ms)

HEARTBEAT(elapsed_sec, last_file) ← 就算卡住也會有「我還活著」

2) 執行緒與 UI 溝通（Queue + after/timer）

核心執行放 worker thread / worker process

UI 用 timer 每 250ms～500ms 從 queue 取事件並更新介面
（這會同時解決「UI 凍結」與「更新太慢」）

3) 讓 Execute 的進度條真的會動：用「位元組」當分母

Dry-run 常用「檔案數」當分母；Execute 應改為：

優先用 total_bytes_planned 當總量

每個檔案在 hash/copy/read 時以 chunk 方式更新 processed_bytes

具體做法

雜湊（hash）：讀檔時就能回報 bytes（chunk_size_kb 已存在設定）

跨磁碟 copy（若有）：用 copyfileobj 逐 chunk 回報 bytes

同磁碟 move/rename：通常是 metadata 操作，瞬間完成；可用 FILE_START/FILE_DONE 顯示「目前正在處理哪個檔」

4) UI 顯示建議（你截圖那個視窗可以加）

在 Execute 視窗新增 4 個欄位，使用者會立刻安心：

目前檔案：顯示檔名/相對路徑（長路徑可省略中段）

目前動作：hash / move / rename / read-metadata

速度：MB/s（用最近 3–10 秒滑動平均）

ETA：以 bytes done / bytes total 估算

再加一個小提示：

最後更新：距離上次事件幾秒（例如 “Last update: 0.5s ago”）

5) 可選：系統/網路狀態（用 psutil）

若你真的想顯示 CPU/記憶體/網路吞吐量：

引入 psutil 可以讀到 CPU%、RSS、網路 bytes/s
但這是加分項，不是解決「像當機」的必要條件。真正關鍵是 FILE_PROGRESS + HEARTBEAT + 節流 UI 更新。

v0.3 開發計畫（建議 PR 拆分）
v0.3.0 — Progress Event Bus + UI 節流更新

交付

新增 progress event dataclass / enum

worker → UI queue

UI 每 250–500ms 拉事件更新（不阻塞）

Execute 視窗新增：目前檔案/動作/最後更新時間

驗收

Execute 期間 UI 至少每 1 秒有可見更新（狀態或心跳）

UI 不凍結，可按取消（取消先做 cooperative flag）

v0.3.1 — 位元組級進度（hash/copy/read）

交付

hash/read/copy 改成 chunk 迴圈回報 FILE_PROGRESS

全局進度條以 bytes 完成度計算

速度/ETA 計算（滑動平均）

驗收

大檔處理時進度條持續前進

log/狀態列會顯示正在處理的檔案路徑

v0.3.2 — 日誌體驗：ring buffer + log 檔 + 重要事件摘要

交付

UI log 視窗只保留最後 N 行

完整 log 寫入 REPORT/run.log

每階段結束顯示摘要：處理檔案數、成功/失敗、平均速度

驗收

長時間執行不會因 log 太多造成 UI 變慢

使用者能直接打開 log 檔查看

v0.3.3（可選）— psutil 系統資訊小面板

交付

CPU%、記憶體、網路吞吐量（可用 checkbox 開關）

預設關閉，避免多餘依賴

驗收

開啟時每 1 秒更新一次，不影響主流程