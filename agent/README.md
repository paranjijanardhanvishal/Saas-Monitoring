# SaaS Security Monitor — Windows endpoint agent

The endpoint agent collects **metadata-only** endpoint telemetry, sends it to the
SaaS Security Monitor backend with a revocable device credential, and obeys
server-side monitoring consent.

It is not an EDR, keylogger, screen recorder, clipboard monitor, browser-history
collector or content scanner. Read [What it does not collect](#what-it-does-not-collect)
before deploying it.

---

## Security properties

- **Device-scoped credential.** Enrollment consumes a single-use token issued by
  an administrator for a user whose consent is `ALLOWED`. The backend returns a
  raw device token once; only its SHA-256 hash is stored server-side.
- **No user-supplied identity.** Event payloads cannot set `user_id`, `source`
  or device identity. The backend derives them from the device token.
- **TLS verification always on.** `requests` uses `verify=True`; there is no
  `verify=False` switch. Non-loopback HTTP backends are rejected.
- **Explicit lifecycle.** Install, start, stop and uninstall are separate
  commands/scripts. The installer creates a visible per-user logon task named
  `SaaSMonitorAgent` and prints how to remove it. No hidden watchdog,
  auto-updater or persistence mechanism is installed.
- **Token handling.** The device token is never logged or printed by `status`,
  `enroll` or `run`. Enrollment tokens are read from `AGENT_ENROLLMENT_TOKEN` or
  an interactive prompt, consumed once, and not saved.
- **Consent enforced server-side.** The agent cannot enable collection by
  itself. A heartbeat that reports monitoring disabled stops collectors and
  clears the buffer. Revoked credentials are fatal (exit code 2).
- **No elevation at install.** The scheduled task runs with
  `-RunLevel Limited`. Elevated execution is only needed if you want
  failed-logon monitoring (Security event 4625).

**Local storage limitation:** the device credential is a JSON file in a
user-only ACL directory. It is not sealed with Windows DPAPI. Use BitLocker or
another full-disk encryption mechanism and restrict the state directory.

---

## What it collects

| Event type | Metadata observed |
| --- | --- |
| `process.started` | Process name, PID, create time |
| `process.stopped` | Process name, PID, duration |
| `application.foreground_changed` | Foreground process/application name, PID, previous app and duration |
| `application.usage` | Foreground application name and accumulated seconds |
| `session.locked` / `session.unlocked` | Workstation lock state |
| `failed_login.observed` | Windows Security event 4625 fields: account, logon type, source IP, status/sub-status |
| `file.created` / `file.modified` / `file.deleted` | File name, extension, parent directory name, size inside configured folders |
| `system.started` / `system.stopping` | Agent lifecycle markers |
| `system.suspended` / `system.resumed` | Reserved lifecycle event types |
| `agent.error` | Collector name and error class |

Window titles are **not** read. File contents are never opened or uploaded.
The file collector watches only configured directories (default: Documents,
Desktop and Downloads) and is not global file-access visibility.

---

## What it does not collect

- File contents, document text, or uploads/downloads inside applications
- Keystrokes, clipboard contents, screenshots, or screen recordings
- Browser history, URLs, page contents, or passwords
- Window titles
- Microphone, camera, or location data
- Email or chat contents
- Any data outside the configured watch directories

It also does not block, quarantine, delete, or modify files.

---

## Requirements

- Windows 10/11 (collectors are Windows-specific)
- Python 3.11+ on the endpoint
- Network access to the backend over HTTPS
- For failed-login monitoring: an elevated agent context that can read the
  Windows Security log

Install dependencies:

```powershell
pip install -r agent/requirements.txt
```

`psutil` is required for process/foreground/session collection. `watchdog` is
optional: without it, file monitoring falls back to bounded polling.

---

## Configuration

Configuration comes from environment variables and an optional `agent/.env`
file. The repository-level `.env` is also read by `python-dotenv`, but agent
variables are usually kept in `agent/.env`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `BACKEND_URL` | `http://127.0.0.1:8000/api` | Backend API base URL. HTTPS required outside loopback. |
| `AGENT_ENROLLMENT_TOKEN` | unset | One-time enrollment token. Prefer this over `--token` to avoid shell history. |
| `AGENT_STATE_DIR` | `%LOCALAPPDATA%\SaaSMonitorAgent` | Directory for `device.json` and local state. |
| `HEARTBEAT_INTERVAL` | `60` | Seconds between heartbeats (minimum 10). |
| `POLL_INTERVAL` | `5` | Seconds between collector polls (minimum 1). |
| `USAGE_REPORT_INTERVAL` | `300` | Seconds between aggregated usage events (minimum 60). |
| `EVENT_BATCH_SIZE` | `100` | Events per upload batch (maximum 200). |
| `AGENT_ENABLE_FILE_MONITORING` | `true` | Enable/disable file metadata collection. |
| `AGENT_WATCH_DIRS` | Documents; Desktop; Downloads | Semicolon-separated directories to observe. |
| `AGENT_ENABLE_FAILED_LOGIN_MONITORING` | `true` | Enable/disable Security 4625 collection. |
| `AGENT_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

Copy `agent/.env.example` to `agent/.env` if you prefer a file. Never commit
`agent/.env`.

---

## Enrollment

### 1. Grant consent and issue a token

The user must sign in, open `/consent`, and choose **Allow monitoring**.
An administrator then opens **Users**, selects the user, and issues a one-time
enrollment token. Tokens expire after one hour and can be used once.

### 2. Enroll the device

Interactive, preferred for a workstation:

```powershell
powershell -File agent/scripts/install-agent.ps1 `
  -BackendUrl https://monitor.example.com/api
```

The installer prompts for the token without echoing it, enrolls the device,
restricts the state-directory ACL, registers the logon task and starts it.

Manual enrollment (for diagnostics or custom deployment):

```powershell
$env:AGENT_ENROLLMENT_TOKEN = "<one-time token>"
python -m agent enroll --backend-url https://monitor.example.com/api
Remove-Item Env:\AGENT_ENROLLMENT_TOKEN
```

Use `--force` only when you intentionally want to replace an existing device
credential.

### 3. Verify

```powershell
python -m agent status
```

`status` prints sanitized state: device ID, user ID, hostname, OS/agent version,
backend URL, monitoring state, queue depth, counters and collector status. It
never prints the device token.

---

## Running and lifecycle

### Foreground diagnostics

```powershell
# One heartbeat, one collection pass, one upload, then exit.
python -m agent run --once

# Run for 60 seconds (useful for testing).
python -m agent run --duration 60

# Normal loop; Ctrl+C stops it.
python -m agent run
```

### Scheduled task scripts

```powershell
# Install and start (prompts for token if not already enrolled).
powershell -File agent/scripts/install-agent.ps1 -BackendUrl https://monitor.example.com/api

# Start / stop the installed task.
powershell -File agent/scripts/start-agent.ps1
powershell -File agent/scripts/stop-agent.ps1

# Remove the task. Add -PurgeState to delete the local device credential.
powershell -File agent/scripts/uninstall-agent.ps1 -PurgeState
```

The task:

- runs at logon for the current user;
- uses `-RunLevel Limited` (no elevation);
- restarts up to 3 times at 1-minute intervals if it fails;
- has no execution time limit;
- can be inspected with `Get-ScheduledTask -TaskName SaaSMonitorAgent`.

Uninstalling removes the local task and, with `-PurgeState`, the local
credential. The device remains enrolled server-side until an administrator
revokes it from **Users**.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Clean exit / command succeeded |
| `2` | Enrollment, credential, consent/account, or state failure; re-enroll or fix consent |

A revoked device credential (HTTP 401) or revoked enrollment (HTTP 403) causes
the running agent to stop with code 2. It does not silently continue collecting.

---

## Consent and revocation behavior

1. The backend heartbeat returns `monitoring_enabled`.
2. If `true`, collectors start and events are queued/uploaded.
3. If `false`, collectors stop and any buffered events are cleared.
4. If the user chooses `DECLINED` or `REVOKED`, the backend revokes all active
   devices. The next heartbeat/send fails and the agent exits with code 2.
5. Re-enrollment requires a new token after consent is `ALLOWED` again.

The server, not the endpoint, decides whether monitoring is permitted.

---

## Event delivery

- Events are queued in memory (bounded at 5,000) and uploaded in batches.
- Each event has a stable ID so retries are deduplicated server-side.
- The backend rejects unsupported event types, future timestamps, old
  timestamps, oversized batches, revoked devices, restricted accounts and users
  without `ALLOWED` consent.
- Transport failures are retried with the batch preserved; queue overflow drops
  the oldest events and increments a counter. Check `status` counters if events
  appear missing.
- The server's ingestion timestamp is used for behavioral baselines; an
  endpoint cannot move its own baseline.

---

## Telemetry scope details

### Process and foreground

The first process poll establishes a baseline and emits nothing, so starting the
agent does not replay every running process. Foreground changes emit an event
only after the foreground application actually changes. Window titles are not
read.

### Usage

Foreground application time is sampled and flushed as an `application.usage`
event per interval. Sampling is capped per poll so long sleeps do not inflate
attributed time. Locked/no-foreground periods are not attributed to the last
application.

### Failed logons

The collector probes the Security log at startup. If access is denied, it
disables itself and reports the reason instead of fabricating events. Run the
agent elevated to enable this capability. Availability varies by Windows
edition and audit policy.

### Files

`watchdog` is used when installed; otherwise a bounded polling snapshot is
used. The collector ignores temporary/partial files, its own state directory,
and limits the number of scanned files. A move produces a delete/modify plus a
create event. Paths are hashed for resource IDs; only the file name, extension,
parent directory name and size are sent.

---

## Limitations

- Windows only for collectors.
- No DPAPI sealing of the local credential; rely on ACLs and disk encryption.
- No automatic update mechanism.
- No offline buffering across process restarts; the queue is in-memory.
- Failed-login collection depends on elevation and audit policy.
- File monitoring is directory-scoped, not a global file-access audit.
- No content inspection or DLP.
- Usage attribution is foreground-only and interval-based, not per-window.
- The agent does not enforce policy locally; it obeys server consent and
  revocation.

---

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `Device is not enrolled` | Issue a token for an `ALLOWED` user, then enroll with `AGENT_ENROLLMENT_TOKEN`. |
| `already_enrolled` | Run `python -m agent status`; use `enroll --force` only to replace the credential intentionally. |
| `enroll` returns 409/401 | Token expired/used, consent not `ALLOWED`, account restricted, or the device is already active or owned by another user. |
| `status` shows `enrolled: false` | Use the same `--state-dir` as the installer, or set `AGENT_STATE_DIR`. The installer defaults to `%LOCALAPPDATA%\SaaSMonitorAgent`. |
| Backend unreachable | Verify `BACKEND_URL`, DNS, certificate trust and firewall. Non-loopback HTTP is rejected by design. |
| Monitoring paused | Consent is not `ALLOWED`, or the device was revoked. Check the Users page. |
| No failed-login events | Run elevated; check Windows audit policy for logon failure events. |
| No file events | Confirm watch directories exist and `AGENT_ENABLE_FILE_MONITORING=true`; install `watchdog` for event-driven monitoring. |
| Task does not start | Check `Get-ScheduledTask -TaskName SaaSMonitorAgent` and the Python path used at install time. Re-run the installer with `-PythonExe`. |
| Exit code 2 | Credential rejected or account/consent no longer permits monitoring. Re-enroll after fixing consent/account state. |

Logs go to stderr with timestamps. They include error classes and event types,
not tokens, passwords, file contents or window titles.

---

## Tests

```powershell
# From the repository root:
.\venv\Scripts\python.exe -m pytest agent\tests -q
```

Last recorded result: **46 passed**. The agent suite uses controlled providers
for collectors and a fake HTTP client; it verifies enrollment, consent pause,
credential revocation, batching, queue behavior, telemetry mapping and CLI
commands. It does not replace a live Windows deployment test.

A separate real end-to-end run exercised the actual agent lifecycle against the
local backend and MongoDB, including real Windows events, device revocation and
the revoked-agent exit code.
