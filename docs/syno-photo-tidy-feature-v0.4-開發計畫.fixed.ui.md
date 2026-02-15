# syno-photo-tidy v0.4 開發計畫
（手機狀態頁：Polling + Win11 本機 Web Server + tailscale serve + Telegram/Discord 通知）

> 版本目標：讓長時間執行時「不用 RDP」，可用手機即時查看狀態；重大事件（卡住/恢復/錯誤/完成）主動推播。

---

## 0. 目的與成功標準

### 0.1 主要痛點
- 程式 Execute 需要跑很久，現在要確認狀態必須 VPN 回家、再 remote 進 Win11 才能看到進度。
- 使用者希望：手機可隨時確認「跑到哪、是否卡住、有無錯誤」，並在重大事件時收到通知。

### 0.2 v0.4 成功標準（Done / 驗收）
- 手機連上 **Tailscale** 後，可用瀏覽器開啟：
  - `https://<win11-node>.<tailnet>.ts.net/`
- 狀態頁 **不需要 F5**，能自動更新（Polling）。
- 必顯示資訊：
  - `run_id`、`state`（RUNNING/STALE/DONE/ERROR）、`phase`、`counters`、`current_file`、`last_heartbeat`、`recent_errors`、`log_tail`
- **卡住/心跳停止（STALE）**：
  - Telegram 立即收到 STALE；恢復後收到 RECOVERED
- **完成（DONE）**：
  - Telegram 收到 DONE 摘要；Discord 收到 DONE 摘要（含 counters）
- 通知系統與狀態頁不改變既有核心約束：
  - 不新增任何「刪除檔案」行為
  - 既有 manifest/report/resume/rollback 邏輯維持不變

---

## 1. 不變約束（v0.4 仍需遵守）
1. 絕不刪除檔案：不得呼叫 delete/unlink/rmtree
2. 所有檔案操作仍以安全方式：read/move/rename/copy2（跨磁碟 copy2 後來源保留）
3. Manifest 機制仍是核心：MOVE/RENAME 必須記錄 manifest.jsonl + report.csv，並支援 Resume/Rollback/No-op
4. 寫檔採原子化策略：`*.partial` → replace（避免半寫狀態）
5. 長時間執行時，狀態更新不應「依賴 UI thread」：改用事件/心跳 + 獨立 writer 更新狀態檔

---

## 2. 範圍（Scope / Non-goals）

### 2.1 Scope（本版要做）
A) **Status 引擎（事件 → 狀態快照）**
- 建立 `StatusStore`：接收 progress events（phase/file/heartbeat/error）
- 建立 `StatusWriter`：以節流頻率輸出 `status.json`（原子寫入）

B) **本機狀態頁（Polling）**
- Win11 本機 Web Server（綁 `127.0.0.1:<port>`）
- 提供：
  - `/`：`index.html`（手機友善）
  - `/status.json`：最新狀態（no-store）

C) **Tailnet HTTPS（tailscale serve）**
- 用 `tailscale serve` 將本機站台提供給 Tailnet（HTTPS）
- 文件化：啟用/停用/查狀態/重設

D) **通知（Telegram + Discord）**
- Telegram：STALE / RECOVERED / ERROR / DONE
- Discord：RUN_START / PHASE_CHANGE / MILESTONE / DONE
- 防洗版：節流 + 去重 + 狀態遷移

### 2.2 Non-goals（本版不做）
- 不同步到 Vercel 或公網站台（全程 Tailnet）
- 不提供遠端控制（暫停/繼續/取消）— v0.4 先做「看得到、會告警」
- 不要求使用者先完成 Telegram/Discord 設定才能跑自動化測試（見第 8 節）

---

## 3. 整體架構

```
Worker/Pipeline
  └─ emit ProgressEvents (phase/file/heartbeat/error)
        ├─ StatusStore (single source of truth)
        │     ├─ StatusSnapshot (in-memory)
        │     └─ NotificationPolicy + Notifier (重大事件→通知)
        └─ StatusWriter (throttled, atomic)
              └─ REPORT/status.json

Local Web Server (127.0.0.1:PORT)
  ├─ /  -> index.html (Polling)
  └─ /status.json -> latest snapshot

tailscale serve (HTTPS in tailnet)
  └─ https://<win11-node>.<tailnet>.ts.net/  -> Local Web Server
```

---

## 4. Status 模型設計

### 4.1 StatusSnapshot（JSON schema 提案）
`REPORT/status.json`（單檔、Web 與通知共用）

```json
{
  "app": {"name":"syno-photo-tidy","version":"0.4.0"},
  "run": {
    "run_id":"2026-02-14T01:23:45Z",
    "mode":"execute",
    "source_root":"\\NAS\photo",
    "output_root":"D:\\syno_out",
    "started_at":"2026-02-14T01:23:45Z"
  },
  "state":"RUNNING",
  "heartbeat": {"updated_at":"2026-02-14T01:30:10Z","age_sec":2},
  "phase": {"name":"HASH","detail":"sha256 + phash"},
  "current": {"file":"IMG_1234.JPG","op":"HASH","progress_pct":37},
  "counters": {"scanned":12345,"processed":4567,"moved":120,"skipped":4300,"failed":2},
  "errors": [{"ts":"2026-02-14T01:29:01Z","code":"E_READ","msg":"Permission denied","file":"IMG_9999.JPG"}],
  "log_tail": ["...","..."]
}
```

### 4.2 Heartbeat / stale 判定
- `age_sec = now - heartbeat.updated_at`
- 參數：`SPT_STALE_THRESHOLD_SEC`（預設 120）
- UI 規則：
  - `age_sec <= threshold`：RUNNING（正常）
  - `age_sec > threshold`：STALE（顯示警告、觸發 Telegram 通知一次）
  - STALED → 恢復（age_sec 回到 threshold 內）：RECOVERED（通知一次）

### 4.3 狀態檔寫入（原子化）
- 寫入：`REPORT/status.json.partial`
- 完成後：replace 成 `REPORT/status.json`
- 寫入頻率：`SPT_STATUS_WRITE_INTERVAL_MS`（預設 1000ms）

---

## 5. Web 狀態頁（Polling）

### 5.1 本機 Web Server
- 綁定：`127.0.0.1:<port>`（預設 `8765`）
- 路由：
  - `/`：回傳 `index.html`
  - `/status.json`：回傳最新狀態 JSON
- Response headers（避免快取）：
  - `Cache-Control: no-store`
- 前端請求加 cache-busting：
  - `/status.json?t=${Date.now()}`

### 5.2 前端輪詢（Polling）
- `SPT_POLL_INTERVAL_MS`（預設 1000ms）
- 畫面更新項目：
  - State + heartbeat（顯示「最後更新 N 秒前」）
  - Phase
  - Counters
  - Current file（建議只顯示檔名或相對路徑，避免暴露完整私密路徑）
  - Recent errors（最多 5）
  - Log tail（最多 50，可折疊）

---

## 6. tailscale serve（Tailnet HTTPS）

### 6.1 目的
- 讓狀態頁只在 Tailnet 可見（不公開到公網）
- 讓手機用 HTTPS 直接開啟，不需要 RDP

### 6.2 常用指令（寫進 docs）
假設本機 server 在 `127.0.0.1:8765`：

```bash
# 啟用（背景執行），以 tailnet HTTPS 對外提供
tailscale serve --bg --https=443 localhost:8765

# 查看目前 serve 設定
tailscale serve status

# 停用（保留 flags）
tailscale serve --https=443 off

# 清空 serve 設定（必要時）
tailscale serve reset
```

### 6.3 手機端使用
- 手機加入同一個 Tailnet 並連線
- 開啟 `https://<win11-node>.<tailnet>.ts.net/`

---

## 7. 通知系統（Telegram + Discord）

### 7.1 為什麼要通知（與狀態頁互補）
- 狀態頁：你想看細節時再打開（即時、可 drill down）
- 通知：只在重大事件提醒（不用一直盯著頁面）

### 7.2 事件與通道（預設）
- Telegram（高優先、少量）：
  - `WARNING_STALE`, `RECOVERED`, `ERROR`, `RUN_DONE`
- Discord（可回溯、偏紀錄）：
  - `RUN_START`, `PHASE_CHANGE`, `MILESTONE`, `RUN_DONE`（ERROR 可選）

### 7.3 防洗版規則（必做）
- throttle（節流）：
  - `MILESTONE` 至少間隔 `SPT_NOTIFY_MILESTONE_MIN_SEC`（預設 1800 秒）
- dedupe（去重）：
  - 同一個 `error_signature` 在 `SPT_NOTIFY_ERROR_DEDUP_SEC`（預設 600 秒）內只送一次
- transition（狀態遷移）：
  - 正常→STALE：送一次
  - STALE→正常：送一次（RECOVERED）

### 7.4 訊息模板（建議）
Telegram（短、立即懂）
- `⚠️ STALE 120s | run_id=... | phase=HASH | current=IMG_1234.JPG`
- `✅ RECOVERED | run_id=... | phase=HASH`
- `❌ ERROR E_READ | file=IMG_9999.JPG | 詳情請看 status page`
- `🎉 DONE | processed=... moved=... failed=...`

Discord（可多行）
- Run start：來源/輸出根目錄、run_id、開始時間
- Phase change：phase、counters
- Milestone：每 30 分鐘或每 5000 張摘要一次（擇一）
- Done：完整摘要（可附 status page URL）

### 7.5 Secrets / 設定（不進 repo）
- `SPT_NOTIFY_ENABLED`：預設 false（不設即等於 false）
- Telegram
  - `SPT_TELEGRAM_BOT_TOKEN`
  - `SPT_TELEGRAM_CHAT_ID`
- Discord
  - `SPT_DISCORD_WEBHOOK_URL`

---

## 8. 測試計劃（可落地、可在無 token 情況下跑）

> 測試分級的目標：讓「單元/整合測試」不依賴外部帳號與網路；只有手動 E2E 才需要真實 Telegram/Discord 設定。

### 8.1 單元測試（Unit）— 不需任何 token/webhook、不可打外網
- StatusWriter
  - 原子寫入：`.partial` → replace，不產生破損 JSON
- StatusStore
  - counters 累計正確
  - stale 判定：heartbeat 超過 threshold → state=STALE
- NotificationPolicy（核心）
  - throttle 生效（MILESTONE 不洗版）
  - dedupe 生效（同錯誤不重複）
  - transition 生效（STALE/RECOVERED 只送一次）
- Notifier
  - 事件分流正確（哪些事件送 Telegram，哪些送 Discord）

**測試策略**
- 用 `FakeSink` 注入 Notifier（只記錄收到的訊息，不送網路）

### 8.2 整合測試（Integration）— 不需真實 Telegram/Discord
- WebServer
  - `/status.json` 回應 headers 包含 `Cache-Control: no-store`
  - 回傳 JSON schema 合規
- Polling（模擬）
  - 連續 fetch 10 次，`updated_at` 有變化
- Fake Webhook Server
  - 起本機 HTTP server 充當「假 Discord webhook」
  - 驗證 POST payload 格式、錯誤處理與重試（限次）

### 8.3 手動驗收（Manual E2E）— 需要真實 Telegram/Discord（僅此層需要）
- Win11 本機：
  - 開 `http://127.0.0.1:<port>/`，Execute 時每秒更新
- 手機（Tailscale）：
  - 開 `https://<node>.<tailnet>.ts.net/`，同樣每秒更新
- 人為阻塞（或模擬心跳停止）：
  - 超過 threshold → Telegram 收到 STALE
  - 恢復 → Telegram 收到 RECOVERED
- 完成：
  - Telegram/Discord 收到 DONE 摘要

---

## 9. 工作拆分（PR / Issue）

### PR1 — StatusCore（狀態引擎）
- 新增：
  - `StatusSnapshot`（模型）
  - `StatusStore`（事件聚合）
  - `StatusWriter`（節流 + 原子寫 status.json）
- 輸出：`REPORT/status.json`

### PR2 — Event Hooks（補齊即時性）
- 在耗時段落埋點：
  - phase start/end
  - file start/done
  - heartbeat（固定間隔）
  - error（含 file）
- counters 計數一致

### PR3 — WebStatus（本機站台 + Polling UI）
- 本機 Web server 綁 127.0.0.1
- index.html（手機 UI）
- `/status.json` no-store + 前端 polling

### PR4 — Tailscale Docs / Script
- docs：`tailscale serve` 啟用/停用/排錯
- 可選：`start_status_page.ps1`（啟動本機 server + 提示 serve 指令）

### PR5 — Notify Core（Policy + Notifier）
- NotificationPolicy（節流/去重/狀態遷移）
- Notifier（事件→通知）
- FakeSink 用於測試

### PR6 — Telegram Sink
- Bot API 發送（STALE/RECOVERED/ERROR/DONE）
- 失敗重試（限次）與錯誤記錄

### PR7 — Discord Sink
- Webhook 發送（RUN_START/PHASE/MILESTONE/DONE）
- 格式化訊息（含 counters、可附 status page URL）

### PR8 — Test Harness / E2E 驗收腳本
- unit + integration 測試補齊
- 假 webhook server 測試
- 手動驗收 checklist

---

## 10. 設定參數（建議預設）
- `SPT_STATUS_PORT=8765`
- `SPT_STATUS_WRITE_INTERVAL_MS=1000`
- `SPT_POLL_INTERVAL_MS=1000`
- `SPT_STALE_THRESHOLD_SEC=120`
- `SPT_NOTIFY_ENABLED=false`
- `SPT_NOTIFY_MILESTONE_MIN_SEC=1800`
- `SPT_NOTIFY_ERROR_DEDUP_SEC=600`

---

## 11. 交付物清單
- `REPORT/status.json`（每秒更新）
- `web_status/index.html`（狀態頁）
- Win11 本機 Web Server（可啟動/停止）
- docs：
  - `docs/v0.4-mobile-status.md`
  - `docs/notifications-setup.md`（Discord webhook / Telegram bot 的最小設定步驟）
- 測試：
  - unit tests（不需任何 token）
  - integration tests（本機假 webhook）
  - manual E2E checklist（需要真 token/webhook）

---

---

# 🔒 1.5 可靠性與卡死防護（v0.4 新增強化）

> 目標：避免 Visual hash dedupe 長時間卡住、取消無效、強制關閉導致狀態不一致等問題。

## 1.5.1 錯誤分類與錯誤碼

新增錯誤分類並統一寫入 manifest.jsonl / report.csv / status.json：

- E_NET_IO：網路 I/O 失敗（SMB 斷線、WinError、timeout）
- E_READ_TIMEOUT：單檔讀取超時
- E_DECODE_FAIL：影像解碼失敗（損壞檔）
- E_PHASH_TIMEOUT：pHash/visual hash 計算超時
- E_CANCELLED：使用者取消（正常流程）
- E_ABORTED：非正常退出（視窗 X 或強制終止）
- E_PARTIAL_OUTPUT：偵測到半成品檔案

---

## 1.5.2 單檔超時與跳過策略

Visual hash 必須加入單檔超時控制：

- SPT_PHASH_FILE_TIMEOUT_SEC（預設 120 秒）
- 超時時：記錄 E_PHASH_TIMEOUT 並 skip 該檔
- 不得卡住整體 pipeline

網路 I/O 必須配置 timeout + retry：

- SPT_IO_TIMEOUT_SEC（預設 60 秒）
- 使用 safe_op 配置化重試機制

---

## 1.5.3 取消與關閉行為

- 取消按鈕採 cooperative cancel（每檔案邊界檢查 cancel flag）
- 視窗 X 不可直接強制退出：
  - 觸發 graceful shutdown
  - 設定 SPT_GRACEFUL_SHUTDOWN_TIMEOUT_SEC（預設 30 秒）
  - 若仍未完成，記錄 E_ABORTED

---

## 1.5.4 Resume 強化

- 啟動時若偵測 E_ABORTED，提示使用 Resume
- validate_manifest() 檢查 jsonl 完整性
- 對於最後 STARTED 未收尾項目標記為 INCOMPLETE
- 支援安全重試或略過

---

## 1.5.5 StatusSnapshot 擴充

current 區塊新增：

- file_started_at
- file_elapsed_sec
- file_timeout_sec

用於即時顯示目前卡在哪個檔案與是否超時。

---

## 1.5.6 Stale/卡死判定

新增檔案層級卡死判定：

- 若 current.file 不變且 elapsed > timeout + buffer
- 自動記錄 E_PHASH_TIMEOUT 並 skip
- 發送通知（若啟用）

---

## 1.5.7 Telegram 錯誤通知新增

- ❌ ERROR E_PHASH_TIMEOUT | file=XXX | action=SKIP
- ❌ ERROR E_NET_IO | file=XXX | retrying
- ❌ ERROR E_ABORTED | 上次非正常退出

---

## 1.5.8 測試強化（v0.4 必須）

- 模擬 pHash timeout
- 模擬網路 I/O timeout
- 模擬強制中斷後 Resume
- 驗證取消按鈕 30 秒內必須安全停止

---

# 📌 UNC vs 磁碟機建議

- UNC（\\192.168.x.x\share）可直接使用
- 若遇到憑證或重連問題，建議使用 net use 掛載磁碟機
- 映射磁碟不一定更快，但在穩定性與認證管理上較清晰



---

# 🖥️ 1.6 各階段 UI 顯示強化（v0.4 補強，可觀測性/不再像當機）

> 目標：即使在 NAS/SMB（\\192.168.x.x\share）上處理「幾萬檔案」，也要讓使用者隨時看得出「正在做什麼、做到哪裡、是否卡住、多久會超時/跳過」。  
> 原則：**事件回報 + UI 節流更新 + 心跳**（不必高頻刷新，也不會吃資源）。

## 1.6.1 通用 UI 欄位（所有階段一致顯示）
在 Dry-run / Execute 視窗統一顯示以下欄位：

- 階段（phase）：Pre-scan / Metadata / Exact dedupe / Visual hash dedupe / Plan build / Moving / Renaming / Reporting
- 已處理（done_count）/總數（total_count）：以「檔案數」與「位元組數」雙指標顯示
- 目前檔案（current_file）：顯示相對路徑（過長時保留頭尾）
- 目前動作（current_op）：walk / stat / read-metadata / hash / phash / move / rename / write-report
- 速度（speed）：
  - 掃描階段：files/s
  - 搬移/雜湊階段：MB/s
- ETA：若 total 可估算就顯示，否則顯示「估算中」
- 最後心跳（last_heartbeat_age_sec）：顯示「Last update: Xs ago」
- 檔案耗時（file_elapsed_sec / file_timeout_sec）：v0.4 可靠性章節已新增，UI 必須顯示

> UI 更新頻率建議：250ms–1000ms（可配置），並採用節流（throttle）避免 UI 過度重繪。

## 1.6.2 Pre-scan 階段（最容易讓人覺得卡住）
Pre-scan 必須每固定數量回報進度（例如每 100 個檔案或每 1 秒）：

- scanned_files：已掃描檔案數（至少每秒更新）
- scanned_dirs：已掃描資料夾數
- current_dir：目前正在掃描的資料夾（顯示相對路徑）
- ext_breakdown：副檔名統計（可選，至少顯示照片/影片/其他）

UI 規則：
- 進度條可採「不確定模式（indeterminate）」直到取得 total_count，再切換為百分比
- elapsed 必須從階段開始起持續更新（不可一直顯示 0s）

## 1.6.3 Metadata/時間鎖定階段
每 N 筆更新：
- metadata_done / total
- timestamp_source 統計：EXIF / FS / fallback
- 失敗統計：decode_fail、missing_time

UI 顯示：
- 顯示目前檔案 + timestamp_locked + source（EXIF/FS）
- 若遇到檔案解碼失敗：立即在 log 追加一行（不必彈窗）

## 1.6.4 Exact dedupe（hash）階段
回報：
- hashing_done / total
- bytes_hashed / total_bytes
- speed MB/s（以 3–10 秒滑動平均）
- current_file + current_chunk（可選）

UI 顯示：
- 進度條以 bytes 為主（對大檔案才會平滑）
- 若 I/O timeout：顯示「retrying (k/n)」並寫入 log

## 1.6.5 Visual hash dedupe（pHash）階段（你目前卡住的點）
必做顯示：
- phash_done / total_images
- current_file（一定要顯示，讓使用者知道卡在哪個檔）
- file_elapsed_sec / file_timeout_sec
- 若超時跳過：即時顯示「超時已跳過」並列入錯誤統計

新增顯示：
- image_decode_ms（可選）
- phash_compute_ms（可選）

UI 規則：
- 任何「單檔處理 > 5 秒」必須仍然每秒更新心跳與 file_elapsed_sec
- 超時即自動 skip，不允許整體卡住

## 1.6.6 Plan build（規劃/決策）階段
回報：
- candidates_count（縮圖候選、exact duplicates、near duplicates）
- keep_count / quarantine_count
- rename_planned / move_planned

UI 顯示：
- 顯示「預計搬移 X、預計改名 Y」
- 若無動作：顯示 No changes needed

## 1.6.7 Execute（Moving/Renaming）階段
回報：
- ops_done / ops_total
- bytes_moved / total_bytes_moved
- current_op + current_file + dest_path（可只顯示最後一段）
- speed MB/s + ETA

UI 規則：
- move/rename 每完成一筆 op 就更新一次（或至少每秒心跳）
- cancel 時狀態列顯示：CANCELLING…（並顯示 graceful timeout 秒數）
- 視窗 X：顯示「正在安全結束，請稍候…」（不可無提示關閉）

## 1.6.8 Log 視窗與 log 檔（避免 UI 越跑越慢）
- UI log 採用 ring buffer（預設保留最後 200–500 行）
- 完整 log 寫入 REPORT/run.log（含每階段摘要）
- 提供「複製目前檔名」按鈕（可選，方便回報卡住檔）

## 1.6.9 新增設定（config）
- ui_update_interval_ms（預設 500）
- ui_log_max_lines（預設 300）
- progress_emit_every_files（預設 100）
- progress_emit_every_sec（預設 1）

## 1.6.10 驗收標準（v0.4 必過）
- Pre-scan：在 1Gb LAN + 幾萬檔案情境，UI 至少每 1 秒更新 scanned_files 與 current_dir
- Visual hash：必顯示 current_file；單檔超時（預設 120s）必跳過並記錄 E_PHASH_TIMEOUT
- Execute：ops_done 必穩定遞增；cancel 在 30 秒內完成安全停止或提示 E_ABORTED
- 長跑：UI 不得因 log 過多而逐漸卡頓（ring buffer 生效）
