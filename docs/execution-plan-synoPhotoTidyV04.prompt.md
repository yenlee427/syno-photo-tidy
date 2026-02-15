# syno-photo-tidy v0.4.1 Implementation Plan (Decision-Complete)

## 0) Summary

v0.4.1 delivers five capabilities for both GUI and CLI execution paths:
1. Unified structured progress events across dry-run and execute.
2. Durable runtime status (`REPORT/status.json`) + local web status page.
3. Notification pipeline (Telegram/Discord) with deterministic policy.
4. Reliability upgrades: bounded timeout handling, cooperative cancel, graceful shutdown, resume safety.
5. UI progress improvements for pre-scan and per-file timing.

This plan is **decision-complete**: implementation details, interfaces, compatibility, testing, rollout, and failure handling are fully specified.

## 1) Scope

### In Scope
- Status engine (`StatusStore`, `StatusWriter`, `StatusSnapshot`).
- Event model extension (`ProgressEvent`, `ProgressEventType`) with backward compatibility.
- Web status server and static status page.
- Notification policy, notifier, sinks.
- Timeout/cancel/shutdown/resume reliability upgrades.
- GUI + CLI parity for status and notifications.

### Out of Scope
- New third-party dependencies.
- Major pipeline algorithm changes.
- Authentication layer for local web server (Tailscale provides transport access control).

## 2) Non-Negotiable Constraints

- Python stdlib only for web and HTTP notifications (`http.server`, `urllib.request`).
- No breaking API change for existing callback users.
- No unbounded worker/thread growth under timeout conditions.
- No token/secret leakage in logs, status JSON, or UI.

## 3) Public Interfaces and Type Changes

## 3.1 `ProgressEventType` additions

Add enum values:
- `RUN_START`
- `RUN_DONE`
- `MILESTONE`
- `ERROR`
- `WARNING_STALE`
- `RECOVERED`

Existing values remain unchanged.

## 3.2 `ProgressEvent` compatibility contract

Add optional fields with defaults (must not break existing call sites):
- `file_started_at: Optional[float] = None`
- `file_elapsed_sec: Optional[float] = None`
- `file_timeout_sec: Optional[float] = None`
- `error_code: Optional[str] = None`
- `counters: Optional[dict[str, int]] = None`
- `current_dir: Optional[str] = None`

Rule: all new fields are optional and ignored safely by old consumers.

## 3.3 Error code taxonomy

Define stable constants in `models/error_record.py`:
- `E_NET_IO`
- `E_READ_TIMEOUT`
- `E_DECODE_FAIL`
- `E_PHASH_TIMEOUT`
- `E_CANCELLED`
- `E_ABORTED`
- `E_PARTIAL_OUTPUT`

Rule: manifest, status JSON, notifications all use this exact set.

## 3.4 `StatusSnapshot` JSON schema (v1)

Add `schema_version = 1` at root. Required fields:

```json
{
  "schema_version": 1,
  "app": {"name": "syno-photo-tidy", "version": "0.4.1"},
  "run": {
    "run_id": "string",
    "mode": "dry_run|execute",
    "started_at": "ISO-8601",
    "updated_at": "ISO-8601"
  },
  "state": "INIT|RUNNING|STALE|CANCELLING|CANCELLED|ABORTED|DONE|FAILED",
  "heartbeat": {"last_event_at": "ISO-8601", "age_sec": 0},
  "phase": {"name": "string", "index": 0, "total": 0},
  "current": {
    "file": null,
    "dir": null,
    "file_started_at": null,
    "file_elapsed_sec": null,
    "file_timeout_sec": null
  },
  "counters": {
    "total": 0,
    "processed": 0,
    "success": 0,
    "skipped": 0,
    "failed": 0,
    "scanned_files": 0
  },
  "errors": [
    {
      "ts": "ISO-8601",
      "code": "E_*",
      "message": "string",
      "path": null
    }
  ],
  "log_tail": ["string"]
}
```

Limits:
- `errors` max 50 items (drop oldest).
- `log_tail` max `progress.ui_log_max_lines`.

Compatibility:
- New fields in future versions must be additive.
- Consumers must ignore unknown keys.

## 4) Runtime State Machine (authoritative)

Allowed transitions:
- `INIT -> RUNNING`
- `RUNNING -> STALE`
- `STALE -> RUNNING` (emit `RECOVERED` once per stale episode)
- `RUNNING -> CANCELLING`
- `STALE -> CANCELLING`
- `CANCELLING -> CANCELLED`
- `RUNNING -> DONE`
- `RUNNING -> FAILED`
- `CANCELLING -> ABORTED` (forced close after grace timeout)

Forbidden transitions are ignored and logged at debug level.

Transition-triggered notifications:
- `RUNNING -> STALE`: send STALE once.
- `STALE -> RUNNING`: send RECOVERED once.
- `* -> DONE`: send DONE once.
- `* -> FAILED`: send FAILED once.

## 5) Architecture and Data Flow

Single event ingress:
- Worker emits `ProgressEvent` to `event_callback(event)`.
- `event_callback` fan-out:
1. GUI queue (`queue.Queue`).
2. `StatusStore.on_event(event)`.

`StatusStore` responsibilities:
- Thread-safe snapshot aggregation under `threading.Lock`.
- Heartbeat age tracking and stale detection.
- Transition emission for notifier.

`StatusWriter` responsibilities:
- Poll snapshot at `status.write_interval_ms`.
- Atomic write: `status.json.partial` then `os.replace()` to `status.json`.
- Never block worker threads.

Web server:
- `ThreadingHTTPServer` on `127.0.0.1:<port>`.
- `GET /` serves `web_status/index.html`.
- `GET /status.json` serves file from disk with `Cache-Control: no-store`.

Notifier:
- Subscribes to `StatusStore` transitions + selected events.
- Policy gates events before sink dispatch.

## 6) Reliability Design

## 6.1 Timeout strategy (bounded resources)

Do **not** create one detached thread per timeout event.

Implement bounded executors:
- pHash executor: max workers = `min(4, os.cpu_count() or 2)`.
- IO timeout executor: max workers = 8.

Per-file timeout handling:
- `future.result(timeout=...)` for timed operations.
- On timeout: mark file failure with `E_PHASH_TIMEOUT` or `E_READ_TIMEOUT`, continue pipeline.

Backpressure rule:
- If executor queue length exceeds 2x workers, skip additional timed tasks with `E_PARTIAL_OUTPUT` and log warning.

Circuit-breaker rule (NAS instability):
- If `E_NET_IO` or `E_READ_TIMEOUT` occurs >= 20 times within 120s, enter degraded mode for 300s:
- reduce parallelism by 50%
- emit one warning notification
- keep pipeline running unless user cancels

## 6.2 Cancel behavior

- Cancel button and WM close both call `cancel_token.cancel()`.
- Components (`Scanner`, `ExactDeduper`, `VisualDeduper`) must check token between items and before dispatching new futures.
- `RUN_DONE` emitted with `state=CANCELLED` for cooperative cancel completion.

## 6.3 Graceful shutdown contract (strict order)

When WM close occurs during active run:
1. Set state `CANCELLING`, emit event.
2. Stop accepting new file tasks.
3. Wait worker join up to `graceful_shutdown_timeout_sec`.
4. If joined: emit `RUN_DONE(CANCELLED)`.
5. If timeout: append manifest sentinel `E_ABORTED`, emit `RUN_DONE(ABORTED)`.
6. Force final `StatusWriter.flush_now()`.
7. Stop notifier (flush pending send queue with max wait 3s).
8. Stop web server.
9. Destroy GUI root.

Guarantee: final `status.json` and manifest reflect terminal state before process exit.

## 6.4 Manifest repair and resume safety

`ResumeManager.validate_manifest()` behavior:
- Always create backup `manifest.jsonl.bak.<timestamp>` before repair.
- Truncated last line: drop only the malformed tail line.
- `STARTED` without terminal record: mark as `INCOMPLETE`.
- Presence of `E_ABORTED` sentinel marks run as interrupted.

Modes:
- default: auto-repair + report summary.
- strict: no auto-repair; raise actionable error.

## 7) Security and Secrets Policy

- Config file may contain placeholders only; real secrets should come from env vars.
- Env precedence over config for all notify secrets.
- Mandatory redaction in logs/status/UI: tokens, chat IDs, webhook URLs partially masked.
- Never serialize raw secrets into `status.json`, manifest, or test fixtures.

Env keys:
- `SPT_NOTIFY_ENABLED`
- `SPT_TELEGRAM_BOT_TOKEN`
- `SPT_TELEGRAM_CHAT_ID`
- `SPT_DISCORD_WEBHOOK_URL`

## 8) Config Contract (new keys)

Add to `defaults.py`, `default_config.json`, and schema:
- `status.write_interval_ms: 1000`
- `status.stale_threshold_sec: 120`
- `web_server.enabled: true`
- `web_server.port: 8765`
- `notify.enabled: false`
- `notify.milestone_min_sec: 1800`
- `notify.error_dedup_sec: 600`
- `phash.file_timeout_sec: 120`
- `io.timeout_sec: 60`
- `graceful_shutdown_timeout_sec: 30`
- `progress.ui_log_max_lines: 300`
- `progress.emit_every_files: 100`
- `progress.emit_every_sec: 1`

Validation:
- Timeouts: `1..3600`
- Port: `1024..65535`
- Thresholds: positive integers only

## 9) PR Plan (incremental, testable)

### PR1: Status Core
- Add `StatusSnapshot`, `StatusStore`, `StatusWriter`.
- Add config+schema for status settings.
- Add unit tests for aggregation/thread safety/atomic write.

### PR2: Unified Event Emission
- Extend `ProgressEventType` and `ProgressEvent` (defaulted fields).
- Wire event callback in pipeline/scanner/executor.
- Preserve old callback compatibility.

### PR3a: Timeout + Cancel (bounded)
- Implement bounded timeout executors.
- Add error code mapping.
- Propagate cancel token through scanner/dedupers.
- Add targeted tests for timeout and cancel.

### PR3b: Graceful Shutdown + Resume Repair
- WM close flow with strict shutdown order.
- Manifest sentinel + validation backup/strict mode.
- Resume logic for `INCOMPLETE` and `E_ABORTED`.

### PR4: Web Status
- Add `ThreadingHTTPServer`, static page, status endpoint.
- Wire GUI and CLI execute paths.
- Package static asset.

### PR5: Notify Core
- Add policy, notifier, Telegram/Discord/Fake sinks.
- Add retry + dedupe + transition rules.
- Add fake webhook integration tests.

### PR6: UI Progress Improvements
- Add pre-scan indeterminate mode.
- Add `current_dir`, `file_elapsed_sec`, `file_timeout_sec` display.
- Add cancelling countdown state.

### PR7: Docs and Ops
- `docs/v0.4-mobile-status.md`
- `docs/notifications-setup.md`
- troubleshooting and safe defaults.

## 10) Test Plan and Acceptance Criteria

## 10.1 Unit tests

- `test_status_store.py`
- `test_status_writer.py`
- `test_notification_policy.py`
- `test_notifier.py`
- extended `test_visual_deduper.py`, `test_scanner.py`, `test_resume_manager.py`

Requirements:
- Use injectable clock or monkeypatched time for stale/throttle tests.
- CI timeout/stale windows must use short test overrides (1-2 sec), not production defaults.

## 10.2 Integration tests

- `test_web_server.py`
- `test_notify_integration.py` (local fake webhook server)
- extend `test_basic_workflow.py` for status file generation and final terminal state.

## 10.3 Manual E2E

GUI scenarios:
- pre-scan progress remains responsive.
- corrupt file yields `E_DECODE_FAIL`.
- simulated stuck hash yields `E_PHASH_TIMEOUT`.
- cancel completes within configured window.
- WM close writes terminal ABORTED/CANCELLED status correctly.

CLI scenarios:
- `execute` writes and updates `REPORT/status.json`.
- `--status-port` works and serves web status.
- notify enabled via env only.

## 11) Verification Commands

- `pytest tests/unit -v`
- `pytest tests/integration -v`
- `python -m json.tool REPORT/status.json`
- `curl -I http://127.0.0.1:8765/status.json` (expect `Cache-Control: no-store`)
- `curl http://127.0.0.1:8765/` (expect HTML)

## 12) Rollout and Defaults

- Keep notify disabled by default.
- Keep web server enabled by default on localhost only.
- If status writer fails, continue run and surface warning in UI/log.
- Feature considered complete when:
1. all listed tests pass,
2. GUI and CLI acceptance both pass,
3. no secret leakage found in logs/status/manifest.

## 13) Assumptions (explicit)

- Tailscale is managed outside application code.
- Existing manifest format allows additive fields.
- Current packaging can include `web_status/index.html` via `setup.py package_data`.
- Python version supports `dataclasses`, `ThreadingHTTPServer`, and type hints used in codebase.
