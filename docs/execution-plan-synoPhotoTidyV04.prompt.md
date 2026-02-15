# syno-photo-tidy v0.4 Implementation Plan

**TL;DR** — v0.4 adds remote status monitoring (local web server + Tailscale HTTPS), Telegram/Discord notifications, pHash/I/O timeout & graceful shutdown, and richer UI progress. The codebase uses **tkinter** (not Qt), `queue.Queue` for thread communication, and `ProgressEvent` only in the Executor phase — the dry-run Pipeline uses simple int/string callbacks that must be upgraded. The plan is split into 7 incremental PRs, each independently testable.

---

## A) Files to Modify or Create

### New Files

| File | Purpose |
|------|---------|
| `src/syno_photo_tidy/models/status_snapshot.py` | `StatusSnapshot` dataclass matching the JSON schema in §4.1 of the plan |
| `src/syno_photo_tidy/core/status_store.py` | `StatusStore` — aggregates `ProgressEvent`s into `StatusSnapshot` (in-memory, single source of truth) |
| `src/syno_photo_tidy/core/status_writer.py` | `StatusWriter` — throttled atomic writer of `REPORT/status.json` (`.partial` → replace pattern from `ManifestWriter`) |
| `src/syno_photo_tidy/core/web_server.py` | Minimal `http.server.HTTPServer` on `127.0.0.1:<port>`, serves `/` → `index.html`, `/status.json` with `Cache-Control: no-store` |
| `src/syno_photo_tidy/web_status/index.html` | Mobile-friendly status page with JS polling (`fetch('/status.json?t=...')` at 1s intervals) |
| `src/syno_photo_tidy/notify/__init__.py` | Package init |
| `src/syno_photo_tidy/notify/policy.py` | `NotificationPolicy` — throttle (milestone ≥ 1800s), dedupe (same error signature ≤ 600s), state transition (STALE/RECOVERED once each) |
| `src/syno_photo_tidy/notify/notifier.py` | `Notifier` — consumes events from `StatusStore`, applies `NotificationPolicy`, dispatches to sinks |
| `src/syno_photo_tidy/notify/telegram_sink.py` | `TelegramSink` — HTTP POST to Bot API, retry with `safe_op` pattern |
| `src/syno_photo_tidy/notify/discord_sink.py` | `DiscordSink` — HTTP POST to webhook URL, retry |
| `src/syno_photo_tidy/notify/fake_sink.py` | `FakeSink` — records messages in-memory for unit tests |
| `docs/v0.4-mobile-status.md` | Tailscale serve setup/teardown docs |
| `docs/notifications-setup.md` | Telegram bot & Discord webhook setup guide |
| `tests/unit/test_status_store.py` | StatusStore unit tests |
| `tests/unit/test_status_writer.py` | StatusWriter unit tests |
| `tests/unit/test_notification_policy.py` | NotificationPolicy unit tests |
| `tests/unit/test_notifier.py` | Notifier unit tests |
| `tests/integration/test_web_server.py` | Web server integration tests |
| `tests/integration/test_notify_integration.py` | Fake webhook server integration tests |

### Modified Files

| File | Changes | Reason |
|------|---------|--------|
| `src/syno_photo_tidy/models/progress_event.py` | Add `ProgressEventType` values: `ERROR`, `RUN_START`, `RUN_DONE`, `MILESTONE`, `WARNING_STALE`, `RECOVERED`. Add fields: `file_started_at`, `file_elapsed_sec`, `file_timeout_sec`, `error_code`, `counters` dict | StatusStore and notifications need richer events |
| `src/syno_photo_tidy/models/error_record.py` | Add error codes: `E_NET_IO`, `E_READ_TIMEOUT`, `E_DECODE_FAIL`, `E_PHASH_TIMEOUT`, `E_CANCELLED`, `E_ABORTED`, `E_PARTIAL_OUTPUT` as constants or enum | Unified error taxonomy for manifest, status, and notifications |
| `src/syno_photo_tidy/core/pipeline.py` | Accept optional `event_callback: Callable[[ProgressEvent], None]`; emit structured `ProgressEvent`s for each phase (PHASE_START/END, FILE_START/DONE, HEARTBEAT). Pass `CancellationToken` to sub-components | Gap: dry-run has no structured events; sub-components (visual deduper, scanner) have no cancel propagation |
| `src/syno_photo_tidy/core/visual_deduper.py` | Add `cancel_token` parameter; wrap `compute_phash()` in `concurrent.futures.ThreadPoolExecutor` with `future.result(timeout=file_timeout_sec)`; emit per-file ProgressEvent; on timeout → record `E_PHASH_TIMEOUT` and skip | Critical gap: hangs indefinitely on corrupt/huge images over SMB |
| `src/syno_photo_tidy/core/scanner.py` | Add `cancel_token` + `event_callback`; emit `current_dir` and `scanned_files` count events; add heartbeat emission every `progress_emit_every_sec` | Gap: pre-scan appears frozen, no cancel support |
| `src/syno_photo_tidy/core/exact_deduper.py` | Add `cancel_token` propagation to hash workers; add per-file timeout via `future.result(timeout=...)` | Gap: no cancel/timeout in hash workers |
| `src/syno_photo_tidy/core/executor.py` | Register `StatusStore.on_event` alongside existing `progress_callback`; emit `RUN_START`/`RUN_DONE` events; add `file_started_at`/`file_elapsed_sec`/`file_timeout_sec` to `FILE_START`/`FILE_DONE` events | StatusStore integration point |
| `src/syno_photo_tidy/utils/image_utils.py` | Add optional `timeout_sec` parameter to `compute_phash()`; internal implementation can use a thread + `Event.wait(timeout)` fallback | Gap: no timeout on phash computation |
| `src/syno_photo_tidy/gui/main_window.py` | Create `StatusStore` + `StatusWriter` + optional `WebServer` + optional `Notifier` at startup; wire them into worker threads; handle graceful shutdown on window-X (`WM_DELETE_WINDOW` → grace period → `E_ABORTED`); start/stop web server lifecycle | Gap: no status/web/notify infrastructure; window-X kills immediately |
| `src/syno_photo_tidy/gui/progress_dialog.py` | Add `file_elapsed_sec`/`file_timeout_sec` labels; add indeterminate progress bar mode for pre-scan; add `current_dir` label for scan phase; display CANCELLING state with countdown | Gap: per-file timing and pre-scan indeterminate mode |
| `src/syno_photo_tidy/gui/widgets/progress_bar.py` | Add `set_indeterminate()` / `set_determinate()` mode methods | Pre-scan needs indeterminate mode |
| `src/syno_photo_tidy/config/defaults.py` | Add new config sections: `status`, `web_server`, `notify`, `phash.file_timeout_sec`, `io.timeout_sec`, `graceful_shutdown_timeout_sec` | New features need config defaults |
| `config/default_config.json` | Mirror changes from `defaults.py` | Must stay in sync |
| `src/syno_photo_tidy/config/schema.py` | Add validation rules for all new config sections | Config validation |
| `src/syno_photo_tidy/core/resume_manager.py` | Detect STARTED-but-not-completed entries → mark as `INCOMPLETE`; detect `E_ABORTED` in last run → prompt resume; add `validate_manifest()` integrity check for truncated JSONL | Gap: no E_ABORTED recovery |
| `src/syno_photo_tidy/core/manifest.py` | Write new error codes to manifest entries; add `E_ABORTED` sentinel record on ungraceful exit | New error taxonomy |
| `src/syno_photo_tidy/main.py` | Wire `StatusStore`/`StatusWriter`/`WebServer` into CLI `execute` command path; add `--status-port` CLI arg | CLI execute also needs status support |
| `requirements.txt` | No new external deps expected (stdlib `http.server`, `urllib.request` for Telegram/Discord) — confirm `aiohttp` or `requests` is NOT needed | Minimize dependencies |
| `setup.py` | Bump version to `0.4.0`; add `package_data` for `web_status/index.html` | New static asset |

---

## B) Data Flow Design: Worker → Event → StatusStore → UI / Web / Notification

```
┌────────────────────────────────────────────────────────────────────┐
│  Worker Thread (Pipeline / PlanExecutor)                          │
│                                                                    │
│  phase loop:                                                       │
│    emit(PHASE_START) ──┐                                          │
│    for file in files:  │                                          │
│      emit(FILE_START)  ├── event_callback(ProgressEvent)          │
│      do_work(timeout)  │        │                                 │
│      emit(FILE_DONE)   │        │                                 │
│    emit(PHASE_END) ────┘        │                                 │
│                                 │                                 │
│  HeartbeatTicker ── emit(HEARTBEAT) every 2s                      │
└─────────────────────────────────┼─────────────────────────────────┘
                                  │
                    event_callback(event: ProgressEvent)
                                  │
                    ┌─────────────▼──────────────┐
                    │  StatusStore (thread-safe)  │
                    │                              │
                    │  • update_snapshot(event)    │
                    │  • counters += ...           │
                    │  • state = RUNNING/STALE/... │
                    │  • check stale (heartbeat)   │
                    │                              │
                    │  .snapshot → StatusSnapshot  │
                    └──┬──────────┬───────────┬───┘
                       │          │           │
          ┌────────────▼──┐  ┌───▼────┐  ┌───▼──────────────┐
          │ StatusWriter  │  │ Queue  │  │ Notifier          │
          │ (throttled    │  │ → GUI  │  │ (PolicyEngine)    │
          │  1s, atomic)  │  │ poll   │  │                   │
          │               │  │        │  │ STALE → Telegram  │
          │ status.json   │  │ tkinter│  │ DONE  → Telegram  │
          │  .partial →   │  │  after │  │        + Discord   │
          │  replace      │  │        │  │ MILESTONE→Discord  │
          └───────────────┘  └────────┘  └───────────────────┘
                 │                                │
        ┌────────▼─────────┐            Telegram Bot API
        │  Web Server      │            Discord Webhook
        │  127.0.0.1:8765  │
        │  / → index.html  │
        │  /status.json    │──── tailscale serve ──── Phone HTTPS
        └──────────────────┘
```

### Key Design Decisions

1. **Single `event_callback`** — both Pipeline (dry-run) and PlanExecutor (execute) call the same `event_callback(ProgressEvent)` function. This function is a thin wrapper that (a) puts the event on the GUI `queue.Queue`, and (b) calls `StatusStore.on_event(event)`.

2. **StatusStore is thread-safe** — uses `threading.Lock` for snapshot updates. The `StatusWriter` reads `StatusStore.snapshot` at a throttled interval (1s) from a background daemon thread, so it never blocks the worker.

3. **Web server reads `status.json` from disk** — it does NOT call StatusStore directly. This decouples the server from the pipeline process lifecycle and means the web page works even if the server starts before/after the pipeline.

4. **Notifier subscribes to StatusStore state transitions** — when `StatusStore` detects a transition (e.g., RUNNING→STALE), it calls `Notifier.on_transition(old_state, new_state, snapshot)`. The `NotificationPolicy` filters and the appropriate sink fires.

---

## C) Error Handling Strategy

### C.1 pHash Single-File Timeout
- In `VisualDeduper.dedupe()`, wrap each `compute_phash(path)` call in `concurrent.futures.ThreadPoolExecutor(max_workers=1)` with `future.result(timeout=config.get("phash.file_timeout_sec", 120))`
- On `TimeoutError`: record `E_PHASH_TIMEOUT` via `ProcessError`, emit `ProgressEvent(type=ERROR, error_code="E_PHASH_TIMEOUT")`, skip the file, continue to next
- The spawned compute thread will be abandoned (daemon thread) — acceptable since it's I/O-bound and will eventually finish or be killed at process exit
- `StatusSnapshot.current` will show `file_elapsed_sec` ticking up so the web page reflects the stall

### C.2 NAS/SMB I/O Timeout
- The existing `safe_op` decorator in `file_ops.py` already has retry+backoff, but **no per-call timeout**
- Add `SPT_IO_TIMEOUT_SEC` (default 60) — passed as `timeout` parameter to file read operations where applicable
- For `os.walk`/`os.stat`/EXIF reads (which are blocking C calls): wrap in a thread with timeout, same pattern as pHash
- On timeout after all retries exhausted: record `E_NET_IO` or `E_READ_TIMEOUT`, emit ERROR event, skip the file

### C.3 Cancel Button (Cooperative Cancel)
- Current mechanism is correct: checks `cancel_token.is_cancelled()` between files
- **Enhancement:** propagate `cancel_token` into `VisualDeduper`, `Scanner`, `ExactDeduper` — currently missing from these components
- On cancel: record `E_CANCELLED` as the run status, emit `RUN_DONE` with state=CANCELLED

### C.4 Window-X / Graceful Shutdown
- Override `WM_DELETE_WINDOW` in `MainWindow`:
  1. Set `cancel_token.cancel()` (same as cancel button)
  2. Show "Safely stopping... (30s)" in the UI
  3. Wait up to `SPT_GRACEFUL_SHUTDOWN_TIMEOUT_SEC` (default 30) for worker thread to finish
  4. If worker finishes in time: normal cleanup
  5. If timeout: write `E_ABORTED` sentinel record to manifest, then `root.destroy()`
- `StatusStore` emits `RUN_DONE` with `state=ABORTED`

### C.5 Resume after E_ABORTED
- On startup, `ResumeManager.find_latest_manifest()` already locates the last manifest
- **Enhancement:** `validate_manifest()` checks for:
  - Truncated JSONL (incomplete last line) → repair by dropping the bad line
  - Entries with `status=STARTED` but no subsequent SUCCESS/FAILED → mark as `INCOMPLETE`
  - `E_ABORTED` sentinel present → prompt user with "Last run was interrupted. Resume?"
- `build_actions_from_manifest()` includes INCOMPLETE entries in the resume plan

---

## D) Test Plan & Acceptance Criteria

### D.1 Unit Tests (no network, no tokens)

| Test File | Coverage | Key Assertions |
|-----------|----------|----------------|
| `test_status_store.py` | `StatusStore` | 1. Event aggregation: counters accumulate correctly across PHASE/FILE events. 2. Stale detection: heartbeat age > threshold → state=STALE. 3. Recovery: heartbeat resumes → state=RUNNING, RECOVERED event emitted once. 4. Phase tracking: PHASE_START updates `snapshot.phase`. 5. Error collection: ERROR events append to `snapshot.errors` (capped at 50). 6. Thread safety: concurrent `on_event()` calls don't corrupt snapshot. |
| `test_status_writer.py` | `StatusWriter` | 1. Atomic write: `.partial` file created, then replaced to `status.json`. 2. Throttling: rapid calls produce at most 1 write per interval. 3. Valid JSON: output is parseable and matches `StatusSnapshot` schema. 4. Crash safety: if write fails, previous `status.json` remains intact. |
| `test_notification_policy.py` | `NotificationPolicy` | 1. Throttle: MILESTONE events within 1800s window → suppressed. 2. Dedupe: same `error_signature` within 600s → suppressed. 3. Transition: RUNNING→STALE sends once; repeated STALE → suppressed. 4. Transition: STALE→RUNNING sends RECOVERED once. 5. DONE always passes through. |
| `test_notifier.py` | `Notifier` + `FakeSink` | 1. Event routing: STALE/ERROR/DONE → Telegram sink; RUN_START/PHASE/MILESTONE/DONE → Discord sink. 2. Sink failure: HTTP error doesn't crash notifier; error is logged. 3. Disabled: `notify.enabled=false` → no sink calls. |
| `test_visual_deduper.py` (extend) | pHash timeout | 1. Corrupt image → `E_PHASH_TIMEOUT` after configured timeout; file skipped; processing continues. 2. Cancel token set → raises `CancelledError` between files. |
| `test_scanner.py` (extend) | Scanner events | 1. Emits `ProgressEvent(PHASE_START)` at scan begin. 2. Emits periodic events with `scanned_files` count. 3. Cancel token set → scan aborts early. |
| `test_resume_manager.py` (extend) | E_ABORTED resume | 1. Truncated JSONL → `validate_manifest()` repairs and reports. 2. STARTED entries → marked INCOMPLETE. 3. E_ABORTED sentinel → `needs_resume()` returns True. |

### D.2 Integration Tests (no real Telegram/Discord)

| Test File | Coverage | Key Assertions |
|-----------|----------|----------------|
| `test_web_server.py` | Web server | 1. `GET /status.json` returns valid JSON with `Content-Type: application/json` and `Cache-Control: no-store`. 2. `GET /` returns HTML with `Content-Type: text/html`. 3. Server starts/stops cleanly on a random port. 4. Concurrent requests don't crash. |
| `test_notify_integration.py` | Fake webhook | 1. Start a local HTTP server as fake Discord webhook. 2. `DiscordSink` POSTs correct payload format. 3. Fake server returns 500 → sink retries up to max. 4. `TelegramSink` payload format matches Bot API spec. |
| `test_basic_workflow.py` (extend) | End-to-end with status | 1. Full dry-run+execute produces `REPORT/status.json`. 2. Status file updates during execution. 3. Final state is DONE with correct counters. |

### D.3 Manual E2E Acceptance (requires real tokens + Tailscale)

| # | Scenario | Pass Criteria |
|---|----------|---------------|
| 1 | Open `http://127.0.0.1:8765/` during Execute | Page loads; updates every 1s; shows phase, counters, current_file, heartbeat age |
| 2 | Open `https://<node>.<tailnet>.ts.net/` on phone | Same as above, over Tailscale HTTPS |
| 3 | Pre-scan on NAS (\\\\192.168.x.x\share) with 10k+ files | `scanned_files` increments at least every 1s; `current_dir` changes; UI not frozen |
| 4 | Visual hash on corrupt image | `file_elapsed_sec` ticks up; at 120s → SKIP with `E_PHASH_TIMEOUT`; next file proceeds |
| 5 | Simulate stale (pause worker thread via debugger) | After 120s → Telegram receives STALE; resume → RECOVERED |
| 6 | Run completes normally | Telegram + Discord receive DONE with counters summary |
| 7 | Click Cancel during Execute | UI shows "CANCELLING…"; stops within 30s; manifest records `E_CANCELLED` |
| 8 | Close window-X during Execute | "Safely stopping…" dialog; stops within 30s or records `E_ABORTED` |
| 9 | Resume after E_ABORTED | "Last run interrupted" prompt; resumes from last incomplete item; already-done items skipped |
| 10 | Long run (1h+) | UI log doesn't slow down (ring buffer); `status.json` size stays constant |

---

## E) Implementation Checklist (PR Order)

### PR1 — StatusCore (Status Engine)
- [ ] Create `StatusSnapshot` dataclass in `src/syno_photo_tidy/models/status_snapshot.py` — fields per §4.1 schema (`app`, `run`, `state`, `heartbeat`, `phase`, `current`, `counters`, `errors`, `log_tail`)
- [ ] Extend `ProgressEventType` in `src/syno_photo_tidy/models/progress_event.py` — add `ERROR`, `RUN_START`, `RUN_DONE`, `MILESTONE`, `WARNING_STALE`, `RECOVERED`
- [ ] Extend `ProgressEvent` fields — add `file_started_at`, `file_elapsed_sec`, `file_timeout_sec`, `error_code`, `counters`
- [ ] Create `StatusStore` in `src/syno_photo_tidy/core/status_store.py` — `on_event(event)` method, `threading.Lock` for thread safety, stale detection logic
- [ ] Create `StatusWriter` in `src/syno_photo_tidy/core/status_writer.py` — daemon thread, throttled (1s), atomic write (`.partial` → replace)
- [ ] Add new config keys to `src/syno_photo_tidy/config/defaults.py` and `config/default_config.json`: `status.write_interval_ms` (1000), `status.stale_threshold_sec` (120)
- [ ] Add schema validation in `src/syno_photo_tidy/config/schema.py`
- [ ] Write `test_status_store.py` and `test_status_writer.py`

### PR2 — Event Hooks (Unified Event Emission)
- [ ] Refactor `src/syno_photo_tidy/core/pipeline.py` — accept `event_callback`; emit `ProgressEvent` for each phase and sub-step; wrap existing simple callbacks to also emit structured events
- [ ] Update `src/syno_photo_tidy/core/scanner.py` — accept `cancel_token` + `event_callback`; emit `scanned_files`/`current_dir` events at `progress_emit_every_sec` (1s) or `progress_emit_every_files` (100) intervals
- [ ] Update `src/syno_photo_tidy/core/exact_deduper.py` — propagate `cancel_token` to worker futures
- [ ] Update `src/syno_photo_tidy/core/executor.py` — register `StatusStore.on_event` as secondary listener; emit `RUN_START`/`RUN_DONE`; populate `file_started_at`/`file_elapsed_sec` in FILE events
- [ ] Wire in `src/syno_photo_tidy/gui/main_window.py` — create `StatusStore` + `StatusWriter`, pass them to worker thread; update `_start_worker` to bridge old callbacks + new event flow
- [ ] Extend scanner and executor tests to verify structured events

### PR3 — Reliability (Timeouts + Graceful Shutdown + Resume)
- [ ] Add error code constants to `src/syno_photo_tidy/models/error_record.py`: `E_NET_IO`, `E_READ_TIMEOUT`, `E_DECODE_FAIL`, `E_PHASH_TIMEOUT`, `E_CANCELLED`, `E_ABORTED`, `E_PARTIAL_OUTPUT`
- [ ] Add pHash timeout in `src/syno_photo_tidy/core/visual_deduper.py` — `ThreadPoolExecutor(1)` + `future.result(timeout=file_timeout_sec)`; on `TimeoutError` → skip + emit `ERROR` event
- [ ] Add `cancel_token` to `VisualDeduper.dedupe()` — check between files
- [ ] Add I/O timeout wrapper in `src/syno_photo_tidy/utils/image_utils.py` `compute_phash()`
- [ ] Add config keys: `phash.file_timeout_sec` (120), `io.timeout_sec` (60), `graceful_shutdown_timeout_sec` (30)
- [ ] Implement graceful shutdown in `src/syno_photo_tidy/gui/main_window.py` — `WM_DELETE_WINDOW` handler: cancel → wait(30s) → `E_ABORTED` sentinel → destroy
- [ ] Enhance `src/syno_photo_tidy/core/resume_manager.py` — STARTED→INCOMPLETE detection; truncated JSONL repair; E_ABORTED prompt
- [ ] Update `src/syno_photo_tidy/core/manifest.py` — write `E_ABORTED` sentinel record on ungraceful exit
- [ ] Write/extend tests: pHash timeout simulation, cancel propagation, E_ABORTED resume, truncated manifest repair

### PR4 — WebStatus (Local Server + Polling UI)
- [ ] Create `src/syno_photo_tidy/core/web_server.py` — `http.server.HTTPServer` on `127.0.0.1:<port>` in daemon thread; route `/` → `index.html`, `/status.json` → read `REPORT/status.json` from disk; response headers `Cache-Control: no-store`
- [ ] Create `src/syno_photo_tidy/web_status/index.html` — single-file HTML+CSS+JS; responsive/mobile-friendly; `fetch('/status.json?t=...')` polling at `SPT_POLL_INTERVAL_MS`; display all §5.2 fields; STALE badge (red) when `age_sec > threshold`; error list (last 5); collapsible log tail (50 lines)
- [ ] Add config key: `web_server.port` (8765), `web_server.enabled` (true)
- [ ] Wire in `MainWindow` — start/stop web server with pipeline lifecycle
- [ ] Wire in CLI `execute` in `src/syno_photo_tidy/main.py` — `--status-port` arg
- [ ] Add `package_data` for `index.html` in `setup.py`
- [ ] Write `test_web_server.py` — start/stop, response headers, JSON schema, concurrent requests

### PR5 — Notify Core (Policy + Notifier + Sinks)
- [ ] Create `NotificationPolicy` in `src/syno_photo_tidy/notify/policy.py` — throttle, dedupe (error signature hashing), state transition tracking
- [ ] Create `Notifier` in `src/syno_photo_tidy/notify/notifier.py` — subscribes to `StatusStore` transitions; dispatches to registered sinks per event-type→channel mapping
- [ ] Create `TelegramSink` in `src/syno_photo_tidy/notify/telegram_sink.py` — `urllib.request.urlopen` POST to `https://api.telegram.org/bot<token>/sendMessage`; retry 3x; message templates from §7.4
- [ ] Create `DiscordSink` in `src/syno_photo_tidy/notify/discord_sink.py` — `urllib.request.urlopen` POST to webhook URL; retry 3x; embed-format messages from §7.4
- [ ] Create `FakeSink` in `src/syno_photo_tidy/notify/fake_sink.py` — in-memory message recorder
- [ ] Add config keys: `notify.enabled` (false), `notify.telegram.bot_token`, `notify.telegram.chat_id`, `notify.discord.webhook_url`, `notify.milestone_min_sec` (1800), `notify.error_dedup_sec` (600); support env-var overrides (`SPT_TELEGRAM_BOT_TOKEN` etc.)
- [ ] Wire in `MainWindow` / CLI — create `Notifier` if `notify.enabled`; register sinks based on which tokens are configured
- [ ] Write `test_notification_policy.py`, `test_notifier.py`, `test_notify_integration.py` (fake webhook server)

### PR6 — UI Enhancement (Progress Display)
- [ ] Update `src/syno_photo_tidy/gui/progress_dialog.py` — add `file_elapsed_sec` / `file_timeout_sec` display; add `current_dir` label for scan phase; add CANCELLING state with countdown timer
- [ ] Update `src/syno_photo_tidy/gui/widgets/progress_bar.py` — add `set_indeterminate()` / `set_determinate()` mode toggle
- [ ] Pre-scan phase: indeterminate progress bar until total is known, then switch to determinate
- [ ] Visual hash phase: show `file_elapsed_sec` / `file_timeout_sec` prominently; highlight when `elapsed > 5s`
- [ ] Add config keys: `progress.ui_log_max_lines` (300), `progress.emit_every_files` (100), `progress.emit_every_sec` (1)
- [ ] Verify ring buffer in `LogViewer` already uses config `log_max_lines`

### PR7 — Tailscale Docs
- [ ] Create `docs/v0.4-mobile-status.md` — `tailscale serve` setup/teardown/troubleshooting; phone-side Tailscale app instructions
- [ ] Create `docs/notifications-setup.md` — Telegram BotFather minimal steps; Discord webhook creation steps; env-var configuration
- [ ] Optional: create `scripts/start_status_page.ps1` — PowerShell script to start web server + prompt tailscale serve command

---

## F) Verification Summary

| Check | Command / Method |
|-------|-----------------|
| Unit tests pass | `pytest tests/unit/ -v` |
| Integration tests pass | `pytest tests/integration/ -v` |
| No new deps needed | Verify `requirements.txt` unchanged (stdlib only for web/notify) |
| `status.json` valid | `python -m json.tool REPORT/status.json` during run |
| Web page loads | `curl http://127.0.0.1:8765/` returns HTML |
| Status endpoint works | `curl -I http://127.0.0.1:8765/status.json` shows `Cache-Control: no-store` |
| pHash timeout fires | Create a 0-byte `.jpg`, run visual dedupe, confirm `E_PHASH_TIMEOUT` in manifest |
| Cancel within 30s | Click Cancel during Execute, measure time to safe stop |
| Window-X graceful | Close window during Execute, confirm `E_ABORTED` in manifest, resume works |
| Telegram notification | Set `SPT_NOTIFY_ENABLED=true` + bot token, trigger STALE, confirm message received |
| Mobile status page | Phone on Tailscale, open HTTPS URL, confirm auto-refresh |

---

## G) Key Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| HTTP library | `http.server` (stdlib) | Zero new dependencies |
| Notification HTTP | `urllib.request` (stdlib) | Zero new dependencies |
| pHash timeout mechanism | `ThreadPoolExecutor(1)` + `future.result(timeout)` | Works on Windows (no `signal.alarm`); simple |
| Web server data source | Reads `status.json` from disk | Decoupled from pipeline lifecycle; survives server restart |
| GUI communication | Keep existing `queue.Queue` + `root.after()` | Add `StatusStore.on_event` as parallel listener, not replacement |
| Existing callback compat | Wrap old int/string callbacks to also emit `ProgressEvent`s | Non-breaking; existing tests remain valid |
