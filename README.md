# SaaS Security Monitor

A working capstone implementation of **SaaS API monitoring for data leakage and
access anomalies**. It combines a FastAPI/MongoDB backend, a React SOC console,
a Windows endpoint agent, a metadata-only SaaS proxy, explainable risk scoring,
alert/incident workflows, and administrator-confirmed enforcement.

This README describes behavior that is implemented in this repository. It does
not claim production readiness, and it calls out the monitoring limits
explicitly. No dashboard value is fabricated: unavailable data is rendered as an
empty/error state rather than synthetic statistics.

---

## Contents

- [What it monitors](#what-it-monitors)
- [Explicit non-goals and limitations](#explicit-non-goals-and-limitations)
- [Architecture](#architecture)
- [Security model](#security-model)
- [Consent lifecycle](#consent-lifecycle)
- [Risk scoring](#risk-scoring)
- [SOC console routes](#soc-console-routes)
- [Windows endpoint agent](#windows-endpoint-agent)
- [SaaS proxy ingestion](#saas-proxy-ingestion)
- [Alerts, incidents and enforcement](#alerts-incidents-and-enforcement)
- [Investigation, health and audit](#investigation-health-and-audit)
- [Offline metadata analysis](#offline-metadata-analysis)
- [Optional integrations](#optional-integrations)
- [Repository layout](#repository-layout)
- [Local setup](#local-setup)
- [Enrolling a Windows device](#enrolling-a-windows-device)
- [Testing and verification](#testing-and-verification)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## What it monitors

### SaaS API traffic (metadata only)

The mitmproxy add-on observes requests to recognized SaaS hosts (currently
Google APIs/Drive) and forwards request/response **metadata** to the backend:
method, host, path, query, status code, content type, sizes, a sanitized header
map, and an opaque session fingerprint derived from the authorization token.

The proxy does **not** forward request/response bodies. `Authorization`,
`Cookie`, `Set-Cookie` and `X-API-Key` headers are redacted before the event is
created.

### Windows endpoint telemetry (metadata only)

The agent supports these event types:

| Area | Events | What is observed |
| --- | --- | --- |
| Process lifecycle | `process.started`, `process.stopped` | Process name, PID, create time, duration |
| Foreground app | `application.foreground_changed` | Application/process name and PID; **window titles are not read** |
| App usage | `application.usage` | Foreground app name and accumulated seconds per interval |
| Session | `session.locked`, `session.unlocked` | Workstation lock state |
| System lifecycle | `system.started`, `system.stopping`, `system.resumed`, `system.suspended` | Agent/system lifecycle metadata |
| Failed logons | `failed_login.observed` | Windows Security event 4625 metadata where accessible |
| File metadata | `file.created`, `file.modified`, `file.deleted` | File name, extension, parent directory name, size inside configured folders |
| Agent health | `agent.error` | Collector/error type only |

### Privacy and behavioral analysis

- PII detection through Microsoft Presidio when installed, with a deterministic
  regex fallback (`PII_ENGINE=auto|presidio|regex`). The active engine is shown
  in System Health.
- An authenticated user can explicitly submit an image or scanned PDF for
  local Tesseract OCR. The API stores entity types, counts, sensitivity scores
  and a linked risk assessment; it discards the upload and extracted text.
  Optional setup and size/page limits are described under Local setup.
- Only entity types, counts, scores, categories and scan metadata are persisted;
  raw PII text and matched values are not stored or logged.
- EWMA baselines are maintained per user over the configured time windows
  (30m, 1h, 2h, 8h, 1d, 7d, 30d, 90d) to detect activity-rate anomalies.
- Business roles (`GENERAL`, `DEVELOPER`, `HR`, `FINANCE`) add a transparent
  resource-category check to attributed endpoint behavior. Findings retain
  category labels and scores, not the resource name.

### Risk, alerts, incidents and response

- Explainable 0–100 risk score with privacy, behavior, endpoint and SaaS access
  signals.
- HIGH/CRITICAL assessments create deduplicated alerts; related alerts can be
  correlated into incidents.
- Administrators can restrict an account, revoke its device enrollments, and
  roll those actions back with an audit trail.
- Slack/Jira notifications are optional and only run when configured.

---

## Explicit non-goals and limitations

These are deliberate boundaries, not hidden behavior:

1. **No background content inspection or certified DLP.** The endpoint agent,
   SaaS proxy and offline analysis inspect **metadata only**. Content OCR runs
   only after a signed-in user selects a file in the privacy page; it is a
   prototype scan, not continuous DLP.
2. **No global file-access or upload visibility.** File events cover only the
   explicitly configured watch directories. Downloads/uploads performed inside
   an application are not observed by the endpoint agent.
3. **No keystrokes, screenshots, clipboard, browser history or window titles.**
   No endpoint collector reads document contents. User-selected OCR uploads are
   processed by the API for that request and are not retained.
4. **SaaS proxy events are unattributed.** The backend clears `user_id` from
   proxy events and marks them `identity_verified: false`. A raw proxy event
   therefore cannot be attributed to an employee, and it is not counted as a
   measured user access signal. User attribution requires a separate verified
   identity mapping that is not implemented.
5. **Role analytics are heuristic.** They classify known department terms in
   attributed endpoint metadata, do not understand document content, and skip
   unknown or shared categories. Unattributed proxy events are not assigned a
   business role.
6. **No automated blocking.** Enforcement is administrator-requested and, for
   account/device-changing actions, requires `confirm=true`. Nothing is labeled
   as a “simulated block”; an action is reported `EXECUTED` only after the
   database mutation succeeds.
7. **Enforcement is local to this application.** `RESTRICT_USER` disables the
   account in this system and revokes its agent enrollments. It does **not**
   suspend a Google Workspace account or block network traffic.
8. **Windows is the only endpoint platform with a collector implementation.**
   The agent package is importable elsewhere, but Windows collectors are what
   have been exercised.
9. **No public signup.** User creation is an administrative action; the initial
   administrator is provisioned with a local script.
10. **The vector search is lexical.** It is a local TF/cosine index for file-name
   similarity, not an embedding model or a hosted vector database.
11. **Optional integrations are not guaranteed delivery.** With no environment
    configuration they report `skipped_not_configured`; failures are reported
    as `failed`, never as delivered.
12. **The risk weights are documented policy values, not learned parameters.**
    They require calibration for any real environment.

---

## Architecture

```
┌──────────────────────┐        metadata only        ┌──────────────────────────┐
│ Windows endpoint     │  X-Device-Token (hashed)    │ FastAPI backend          │
│ agent                │ ──────────────────────────► │                          │
│ process / foreground │   heartbeat + event batches │ auth, RBAC, consent      │
│ session / failed     │                             │ event ingestion          │
│ login / file names   │ ◄────────────────────────── │ PII + EWMA + risk        │
└──────────────────────┘   consent / revoke status   │ alerts / incidents       │
                                                     │ enforcement / audit      │
┌──────────────────────┐        metadata only        │                          │
│ mitmproxy SaaS addon │  X-Ingestion-Key            │                          │
│ Google API metadata  │ ──────────────────────────► │                          │
└──────────────────────┘                             └────────────┬─────────────┘
                                                                  │
┌──────────────────────┐        HttpOnly cookie + CSRF           │
│ React SOC console    │ ────────────────────────────────────────┘
│ 11 protected routes  │                    MongoDB
└──────────────────────┘
```

Main components:

- `backend/` — FastAPI application, MongoDB models/services, detection,
  enforcement, tests.
- `frontend/` — React 19 + Vite SOC console.
- `agent/` — Windows endpoint agent, collectors, lifecycle scripts and tests.
- `scripts/run_proxy.py` — launches the mitmproxy add-on.
- `scripts/sync_drive.py` — optional Google Drive metadata sync.
- `backend/scripts/offline_analysis.py` — file-name-only offline baseline.
- `backend/scripts/create_admin.py` — secure initial administrator
  provisioning.

---

## Security model

### Browser authentication

- `POST /api/auth/login` returns a JWT **and** sets two cookies:
  - `access_token` — `HttpOnly`, used for authentication.
  - `csrf_token` — readable by the SPA, used only for the CSRF header.
- The SPA never persists the bearer token in `localStorage` or `sessionStorage`.
- Unsafe methods (`POST`, `PUT`, `PATCH`, `DELETE`) authenticated by cookie must
  send `X-CSRF-Token` matching the `csrf_token` cookie. The comparison is
  constant-time.
- The API also accepts `Authorization: Bearer ...` for programmatic clients.
  **If a bearer token is stored in a browser, it is exposed to XSS.** The
  supplied SPA does not do this; keep it that way.
- Logout clears both cookies. Sessions expire after
  `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480).
- Failed logins are rate-limited per IP + identifier.

### Authorization and tenant isolation

- Roles are `ADMIN` and `USER`.
- ADMIN-only operations include user administration, device administration,
  investigation, enforcement, system health, audit logs and consent history.
- USER requests are scoped server-side to their own `user_id` for dashboard,
  events, alerts, incidents, risk and privacy data. Supplying another user's ID
  does not widen the scope.
- Findings, events and risk records are ownership-checked before they are linked.
- Agent device credentials are scoped to one device and one user. The backend
  derives identity from the device token; an event payload cannot set its own
  `user_id`, `source` or trust level.

### Administrator provisioning

There is no public administrator registration route. Provision the first admin
on the server:

```powershell
# Run from the repository root with the virtual environment active.
python backend/scripts/create_admin.py --user-id admin --email admin@example.com
```

The script prompts for the password (or reads `ADMIN_PASSWORD`), enforces the
12-character minimum policy, stores a bcrypt hash, and refuses to overwrite an
existing user. Do not put the password in shell history or commit it.

After that, additional users are created by an ADMIN from the Users page or via
`POST /api/auth/register` (which itself requires an ADMIN session).

### Secrets and transport

- Generate `JWT_SECRET_KEY` with
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
  Production startup fails without a value of at least 32 characters.
- `INGESTION_API_KEY` is a server-to-server credential for the SaaS proxy. It
  must never be shipped to a browser. Empty disables proxy ingestion.
- Set `COOKIE_SECURE=true` and serve both frontend and API over HTTPS in
  production.
- Agent backend URLs must use HTTPS outside loopback. TLS certificates are
  always verified; there is no `verify=False` option.
- Never commit `.env`, credentials, enrollment tokens or generated passwords.
  These are ignored by `.gitignore`.

### Application hardening

- Exact-origin CORS (`FRONTEND_URL`, comma separated). Credentials are disabled
  if a wildcard origin is configured.
- Security headers: `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy`, `Permissions-Policy`, and HSTS when `COOKIE_SECURE=true`.
- Append-only audit log for authentication, consent changes, user/device
  administration, enforcement and rollback. Tokens and payload contents are not
  written to it.
- Risk signal values are always derived server-side; clients cannot submit
  endpoint/access scores.

---

## Consent lifecycle

Consent is enforced by the backend, not only by the UI:

```
NOT_ASKED ──► ALLOWED ──► REVOKED
    │            │
    └──► DECLINED└──► DECLINED
```

- New accounts start in `NOT_ASKED`.
- Users can choose `ALLOWED`, `DECLINED` or `REVOKED` on the consent page.
  `NOT_ASKED` is internal and cannot be selected.
- A one-time enrollment token can only be issued for a user whose consent is
  `ALLOWED` and whose account is active and not restricted.
- Agent heartbeats report `monitoring_enabled=false` when consent is not
  granted. The agent then stops collecting and clears buffered events.
- Event ingestion requires `ALLOWED`; otherwise the backend returns 403.
- Choosing `DECLINED` or `REVOKED` immediately revokes **all** active devices for
  that user. A revoked device receives 401/403 and the agent exits non-zero; it
  must be re-enrolled with a new token after consent is granted again.
- Every consent transition is written to `consent_history` and the audit log.

---

## Risk scoring

### Signals

| Signal | Source | Weight |
| --- | --- | --- |
| Privacy | PII sensitivity score (0–100) | 0.30 |
| Behavior | Maximum of EWMA deviation score and the role-policy mismatch score | 0.30 |
| Endpoint | Recent attributed endpoint events (process/file/session/failed logon) | 0.22 |
| Access | Recent attributed SaaS actions (share/delete/download/etc.) | 0.18 |

When a signal is **unavailable**, it is omitted and the remaining weights are
renormalized; `signal_confidence` reports the sum of available weights. This is
different from treating an absent signal as a measured zero.

If no endpoint/access telemetry exists at all, the engine uses the original
two-signal privacy/behavior combination (weights 0.5/0.5) and marks the result
`is_partial_assessment` when a signal is missing.

For a one-off OCR scan with no behavioral baseline, the available privacy
signal is renormalized to its full value; missing behavior is not treated as a
measured zero. The assessment remains marked partial.

**Access-signal limitation:** proxy events are stored unattributed
(`user_id=None`), so the access signal is currently unavailable for user risk
scoring. It is omitted rather than counted as zero. The endpoint signal comes
from authenticated agent events.

**Role-policy scoring:** administrators assign a business role separately from
the `ADMIN` / `USER` application permission. A mismatch on an attributed
endpoint event sets a rule-based score (65–90) that feeds the behavior signal
and adds `ROLE_POLICY_MISMATCH` to the explanation. The policy inspects
resource and application metadata transiently, then stores only the role,
category labels and score. It does not infer an employee's job or inspect file
contents. SaaS proxy events remain excluded until verified identity mapping is
implemented.

### Thresholds

| Category | Combined score |
| --- | --- |
| LOW | `< 20` |
| MEDIUM | `< 50` |
| HIGH | `< 80` |
| CRITICAL | `>= 80` |

### Automatic evaluation

When `AUTO_RISK_ENABLED=true`, each persisted endpoint event is evaluated
server-side. Evaluation is triggered for behavioral anomalies, endpoint signal
`>= 20`, access signal `>= 35`, or failed-logon events. Only server-generated
ingestion timestamps are used for baseline updates, so an endpoint cannot move
its own baseline. A risk-pipeline failure is logged and does not fail ingestion.

Each assessment persists its scores, weights used, signal confidence, factors,
explanation and linked finding IDs. HIGH/CRITICAL assessments create alerts with
deduplication keys; they do not automatically execute enforcement.

---

## SOC console routes

All routes below are protected. The first six are available to any authenticated
user (scoped to their own data); the last five are ADMIN-only.

| Route | Purpose |
| --- | --- |
| `/dashboard` | Role-scoped overview: events, alerts, incidents, devices, recent activity |
| `/risk-posture` | Risk distribution, recent assessments and explanations |
| `/live-activity` | Event stream with filters and event detail |
| `/sensitive-files` | File metadata, controlled text analysis and explicit image/PDF OCR scans |
| `/alerts` | Alert triage, status changes and notes |
| `/incidents` | Incident triage, assignment, status and notes |
| `/ueba` | EWMA behavior profiles, role mismatch findings and risk summaries |
| `/users` | User directory, consent, business roles, devices and enrollment tokens (ADMIN) |
| `/investigation` | Cross-entity user/event investigation (ADMIN) |
| `/enforcement` | Recommendations, confirmed actions and rollbacks (ADMIN) |
| `/system-health` | Live database/device/PII/OCR engine/retention status and audit logs (ADMIN) |

UEBA and Users are separate pages. Unknown routes render a 404; unauthenticated
access redirects to `/login`; users who have not granted consent are redirected
to `/consent`; non-admins see an explicit access-denied panel rather than a
blank or fabricated page.

The console also shows loading, empty, error and disconnected states. It does
not silently replace failed requests with fake numbers.

---

## Windows endpoint agent

Full installation and operations guide: [`agent/README.md`](agent/README.md).

Short version:

```powershell
# From the repository root, with the venv active and an enrollment token issued:
$env:AGENT_ENROLLMENT_TOKEN = "<one-time token>"
python -m agent enroll --backend-url https://monitor.example.com/api
python -m agent run
python -m agent status
python -m agent uninstall
```

Lifecycle scripts (explicit per-user logon task, no hidden persistence):

```powershell
powershell -File agent/scripts/install-agent.ps1 -BackendUrl https://monitor.example.com/api
powershell -File agent/scripts/start-agent.ps1
powershell -File agent/scripts/stop-agent.ps1
powershell -File agent/scripts/uninstall-agent.ps1 -PurgeState
```

Key properties:

- Device-scoped opaque token, stored hashed server-side; only the raw token is
  returned once at enrollment.
- Enrollment token is single-use and expires after 1 hour.
- Local credential file permissions are restricted to the current user and
  SYSTEM by the installer.
- Server heartbeat controls collection; revoked credentials are fatal.
- File monitoring is limited to configured directories (defaults: Documents,
  Desktop, Downloads) and observes names/sizes only.
- Failed-login monitoring requires an elevated agent to read Windows Security
  event 4625; otherwise that collector reports an explicit disabled state.
- No content, keystroke, screenshot, clipboard, browser-history or window-title
  collection.

---

## SaaS proxy ingestion

```powershell
# Terminal 1: backend running.
# Terminal 2 (repository root, venv active):
$env:PYTHONPATH = "backend"
$env:INGESTION_API_KEY = "<same value as the backend>"
$env:BACKEND_URL = "http://127.0.0.1:8000"
python scripts/run_proxy.py
```

The add-on listens on `127.0.0.1:8080` by default and forwards metadata for
recognized SaaS hosts to `POST /api/events` using `X-Ingestion-Key`.

The backend:

- rejects ingestion when `INGESTION_API_KEY` is unset or incorrect;
- forces `source="saas_proxy"`, clears `user_id`/`device_id`, and sets
  `metadata.identity_verified=false`;
- rejects timestamps more than 5 minutes in the future or older than 365 days.

To generate clearly-labelled test traffic through the proxy, see
`scripts/c1_e2e_test.py`. It requires the mitmproxy CA certificate to be trusted
by the client (`REQUESTS_CA_BUNDLE`); TLS verification is never disabled.

---

## Alerts, incidents and enforcement

### Alerts and incidents

- Alerts have `LOW`/`MEDIUM`/`HIGH`/`CRITICAL` severity, deterministic
  deduplication, evidence links and a status/notes history.
- Status transitions and notes are audited.
- Alerts can be correlated/attached to incidents; incidents support status,
  assignment and notes.
- APIs: `/api/alerts`, `/api/incidents` (ADMIN writes; scoped reads for USERs).

### Enforcement policy

| Risk category | Recommended action |
| --- | --- |
| LOW | `LOG` |
| MEDIUM | `ALERT` |
| HIGH | `WARN` |
| CRITICAL | `RESTRICT_USER` |

Recommendations are advisory. An administrator chooses the action and, for
`RESTRICT_USER` or `REVOKE_DEVICES`, must pass `confirm=true`.

Actual effects:

- `RESTRICT_USER`: sets `enforcement_status=RESTRICTED` and revokes all active
  device enrollments. The account cannot enroll new devices or ingest agent
  events while restricted.
- `REVOKE_DEVICES`: revokes active device enrollments without restricting the
  account.
- `ALERT` / `WARN`: create a deduplicated alert.
- `LOG`: records the response only.

Every response records the actor, confirmation, previous/resulting status,
revoked devices and targets. `RESTRICT_USER` and `REVOKE_DEVICES` can be rolled
back with a reason; the rollback is audited. Duplicate enforcement for the same
risk returns `ALREADY_HANDLED` instead of repeating the action.

---

## Investigation, health and audit

- **Investigation** (`ADMIN`) searches users and assembles a timeline across
  events, alerts, incidents, risk assessments, privacy findings, behavior
  profiles, devices and enforcement history. Event context includes related
  events for the same user/device.
- **System Health** (`ADMIN`) reports measured values: API version/uptime,
  database ping and collection counts, active/revoked/stale devices, active PII
  engine, auto-risk setting, retention settings, Slack/Jira configuration and
  runtime versions. Unavailable collections are returned as `null`, not
  invented.
- **Audit** (`ADMIN`) exposes the append-only `audit_logs` collection and
  `consent_history`, both filterable. Sensitive values are not stored.

---

## Offline metadata analysis

```powershell
python backend/scripts/offline_analysis.py
```

This script iterates over synced file metadata, indexes file **names** in the
local TF/cosine index, and stores a privacy baseline per file. It explicitly
labels results `analyzed_field="file_name_only"`. It does not download or read
document contents, so it must not be presented as a content DLP scan.

The optional Google Drive sync (`scripts/sync_drive.py`) also retrieves metadata
only, using read-only OAuth scopes. It requires `credentials/credentials.json`
and a local OAuth flow; no credentials are committed.

---

## Optional integrations

Configured entirely through environment variables:

| Variable | Purpose |
| --- | --- |
| `SLACK_WEBHOOK_URL` | HTTPS Slack incoming webhook |
| `JIRA_API_URL` | HTTPS Jira REST endpoint |
| `JIRA_AUTH_TOKEN` | Jira bearer token |
| `JIRA_PROJECT_KEY` | Jira project key (default `SEC`) |
| `JIRA_ISSUE_TYPE` | Jira issue type (default `Incident`) |

If they are unset, the result is `skipped_not_configured`. Non-HTTPS URLs are
rejected as `skipped_insecure_url`. HTTP failures are reported as `failed`.
Nothing is claimed as delivered unless the remote endpoint accepted it.

---

## Repository layout

```
backend/
  app/
    api/            FastAPI routers (auth, agent, alerts, incidents, risk, ...)
    core/           config, JWT/password security, RBAC dependencies
    enforcement/    policy, schemas, real execution and rollback
    models/         Pydantic models (user, device, event, alert, incident)
    privacy/        Presidio/regex PII engines and derived-only storage
    risk/           scoring, context signals, explanations, ownership checks
    services/       alerts, audit, devices, risk pipeline, monitoring
    proxy/          mitmproxy add-on and event mapper
    ...             behavior (EWMA), metadata vector index, database
  scripts/          create_admin.py, offline_analysis.py
  requirements*.txt
agent/
  collectors/       Windows metadata collectors
  scripts/          explicit install/start/stop/uninstall PowerShell scripts
  tests/            46 tests
frontend/
  src/pages/        SOC console pages
  src/context/      auth/session and consent state
  src/components/   shared UI primitives
tests/              backend API/security/risk/integration tests
scripts/            proxy launcher, Drive sync, labelled proxy traffic
```

---

## Local setup

### Prerequisites

- Python 3.11+ (tested with 3.12)
- Node.js 20+ and npm
- MongoDB running locally, or a MongoDB Atlas URI
- Windows 10/11 for the endpoint agent (not required for the web demo)

### 1. Python environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

Optional real Presidio engine:

```powershell
pip install -r backend/requirements-ml.txt
python -m spacy download en_core_web_sm
```

Without these, `PII_ENGINE=auto` uses the regex engine and reports that in
System Health.

### Optional OCR scan support

OCR runs only when an authenticated user selects an image or scanned PDF on the
Sensitive Files page. Install the Python packages and a local Tesseract OCR
executable, then ensure `tesseract` is available on the backend process `PATH`:

```powershell
pip install -r backend/requirements-ocr.txt
```

The default limits are 10 MiB per upload, 10 PDF pages and 100,000 extracted
characters. Override them with `OCR_MAX_FILE_BYTES`, `OCR_MAX_PAGES` and
`PII_MAX_TEXT_LENGTH`. System Health reports live OCR readiness. Hosted
deployments need both the optional Python packages and the Tesseract system
executable; installing the Python package alone is not sufficient.

### 2. Environment

```powershell
Copy-Item .env.example .env
```

Set at minimum:

```dotenv
MONGODB_URI=mongodb://localhost:27017
MONGO_DB_NAME=saas_monitor
JWT_SECRET_KEY=<random 48+ characters>
INGESTION_API_KEY=<random 32+ characters; or leave empty to disable proxy>
FRONTEND_URL=http://localhost:5173,http://127.0.0.1:5173
COOKIE_SECURE=false          # true behind HTTPS
COOKIE_SAMESITE=lax          # none + secure for cross-site deployment
```

Do not paste real values into documentation, screenshots, logs or reports.

### 3. Provision the administrator

```powershell
python backend/scripts/create_admin.py --user-id admin --email admin@example.com
```

You will be prompted for a password of at least 12 characters.

### 4. Start the backend

```powershell
cd backend
..\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- API docs: `http://127.0.0.1:8000/docs`
- Public health: `http://127.0.0.1:8000/health`

### 5. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and sign in with the administrator account.
Vite proxies `/api` and `/health` to `http://localhost:8000`, so the auth cookie
is same-origin during local development.

### 6. Run the isolated synthetic demo

Sign in as an administrator, then open **System Health → Synthetic demo**.
Select **Generate demo run**. The application creates clearly-labelled
synthetic users/devices and passes normal and suspicious endpoint events through
the same PII, UEBA, risk, alert and incident services used by monitored data.
Refresh Dashboard, Live Activity, Sensitive Files, UEBA, Alerts and Incidents
to view the generated records. Use **Reset synthetic data** to remove only
records created by the demo namespace; real users and monitoring data are not
selected by the reset query.

### 7. Create a user and grant consent

1. Sign in as ADMIN.
2. Go to **Users** and create a user (or use the API).
3. Sign in as that user, open `/consent`, and choose **Allow monitoring**.
4. Return to **Users**, select the user, and issue a one-time enrollment token.

The token is displayed once. Only its hash is stored.

---

## Enrolling a Windows device

On the endpoint, install the agent dependencies:

```powershell
pip install -r agent/requirements.txt
```

Enroll interactively (the installer prompts for the token without echoing it):

```powershell
powershell -File agent/scripts/install-agent.ps1 `
  -BackendUrl https://monitor.example.com/api
```

The installer:

- refuses non-HTTPS URLs outside loopback;
- restricts the state directory ACL to the current user and SYSTEM;
- enrolls the device once;
- registers an explicit per-user logon task named `SaaSMonitorAgent`;
- starts the task and prints the exact stop/remove commands.

Manual enrollment and diagnostics:

```powershell
python -m agent enroll --backend-url https://monitor.example.com/api
python -m agent run --once
python -m agent run
python -m agent status
python -m agent uninstall
```

Stop, start and remove:

```powershell
powershell -File agent/scripts/stop-agent.ps1
powershell -File agent/scripts/start-agent.ps1
powershell -File agent/scripts/uninstall-agent.ps1 -PurgeState
```

See [`agent/README.md`](agent/README.md) for configuration, telemetry scope,
consent behavior, troubleshooting and the security rationale.

---

## Testing and verification

All commands are run from the repository root on Windows unless noted.

The result counts below are historical records from the repository before the
OCR and role-aware behavior additions. They do not validate those new flows.

### Backend unit/integration suite

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

Current local verification: **113 passed** (the original 112-suite run plus the
isolated synthetic-demo integration test) against the test database
`saas_monitor_test`. The suite covers authentication, CSRF, RBAC,
tenant isolation, consent, agent enrollment/revocation, PII derived-only
storage, EWMA behavior, four-signal risk scoring, alerts/incidents, enforcement
effects and rollback, proxy ingestion authorization, integrations, offline
analysis, and safe synthetic-demo generation/reset.

### Agent suite

```powershell
.\venv\Scripts\python.exe -m pytest agent\tests -q
```

Last recorded result: **46 passed** (0.25 seconds). These are unit tests
with controlled providers; they do not by themselves prove live Windows
collection.

### Frontend build and lint

```powershell
cd frontend
cmd /c "npm run build"
npm run lint
```

Last recorded baseline results: production build succeeded (2,474 modules, JS 895.93 kB,
CSS 49.30 kB, 1.00 seconds) with a non-blocking chunk-size warning; lint passed
with warnings only. Use `cmd /c` on this machine because the PowerShell wrapper
can return a false non-zero exit code.

### End-to-end verification

The local stack was exercised with temporary harnesses (not committed) before
the OCR and role-aware behavior additions:

- **Real API + agent E2E: 106/106 checks passed.** The verifier used a real
  MongoDB, the running backend and the real agent collector lifecycle. It
  covered auth/RBAC/CSRF, consent gating, one-time enrollment, real Windows
  events, identity assignment, PII derived-only storage, a compound CRITICAL
  risk (privacy 100, behavior 100, endpoint 60; combined 89.28), alert/incident
  triage, auto-correlation, the `RESTRICT_USER` confirmation gate, device
  revocation, rollback, re-enrollment, consent revocation, revoked-agent exit
  code 2, dashboard scoping, investigation, system health and audit trail.
- **Browser E2E: 56/56 checks passed** using Playwright Core with system Chrome.
  It covered login, unauthenticated redirects, all 11 required routes, a real
  alert detail, executed enforcement history, connected health, admin-only
  navigation, sign-out, cleared-session redirect, consent decline, the
  monitoring-paused banner, the non-admin access-denied UI, and absence of page
  errors/failed requests/unexpected console errors.

These harnesses depend on a clean demo database and generated credentials. They
are intentionally not part of the repository, and their results are not a
substitute for the unit suites above.

### What is verified vs. not verified

- **Verified here:** backend logic and security controls, agent collector
  behavior with controlled and real Windows inputs, web UI routes and states,
  real enforcement mutations and rollback, and the full local E2E flow.
- **Not verified here:** deployment on Render/Netlify, Google OAuth against a
  real tenant, Slack/Jira delivery to real endpoints, elevated Security-log
  access on every Windows edition, long-duration soak behavior, or production
  scale/load.

---

## Deployment

### Backend on Render

`render.yaml` provisions a Python web service from `backend/`. It requires:

- `MONGODB_URI` — set in the Render dashboard (not committed).
- `MONGO_DB_NAME`.
- `JWT_SECRET_KEY` — auto-generated by Render or set explicitly (≥32 chars).
- `INGESTION_API_KEY` — auto-generated; set the same value on the proxy host.
- `FRONTEND_URL` — the exact HTTPS origin of the deployed console.
- `COOKIE_SECURE=true`.
- `COOKIE_SAMESITE` — `none` for a cross-site frontend/API deployment, `lax`
  when the frontend and API share a site.
- `APP_ENV=production`.

Use the health check `/health`. Serve only over HTTPS. If using Presidio,
install `requirements-ml.txt` and the spaCy model in the build or use the regex
engine explicitly.

### Frontend on Netlify

`frontend/netlify.toml` builds the SPA and rewrites unknown routes to
`index.html`. Choose one API topology:

**A. Same-origin proxy (recommended for cookies):**

- Add a Netlify redirect from `/api/*` to `https://<backend-host>/api/:splat`
  (status 200) and from `/health` to `https://<backend-host>/health`.
- Do not set `VITE_API_URL`; the SPA will call `/api`.
- Set backend `FRONTEND_URL` to the Netlify origin and use
  `COOKIE_SAMESITE=lax`.

**B. Cross-site API:**

- Set `VITE_API_URL=https://<backend-host>/api` in Netlify's build environment.
- Set backend `FRONTEND_URL` to the Netlify origin.
- Set `COOKIE_SECURE=true` and `COOKIE_SAMESITE=none`. CSRF protection still
  applies to cookie-authenticated writes.

Never put `INGESTION_API_KEY`, `JWT_SECRET_KEY`, agent tokens or database
credentials in frontend build variables. Anything prefixed `VITE_` is public.

### MongoDB

Use a dedicated database and a least-privilege user. Enable authentication and
TLS for Atlas. Back up the database before destructive demo resets. Retention is
configured by `EVENT_RETENTION_DAYS` and `AUDIT_RETENTION_DAYS`; `0` disables
automatic deletion.

---

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| `JWT_SECRET_KEY must be set...` at startup | Production requires a real secret; set it in `.env` or the host environment. |
| Login succeeds but writes return 403 `CSRF validation failed` | The SPA must send `X-CSRF-Token` from the `csrf_token` cookie. Do not block that cookie in a proxy. |
| Browser requests fail with CORS | `FRONTEND_URL` must list the exact scheme/host/port of the console. |
| Cookie not sent in production | Set `COOKIE_SECURE=true` under HTTPS; for cross-site use `COOKIE_SAMESITE=none`. |
| Agent exits with code 2 | Credential rejected/revoked, or consent/account no longer permits enrollment. Check `python -m agent status`, re-enroll with a new token if appropriate. |
| Agent says monitoring paused | Consent is not `ALLOWED` (or the device was revoked). The agent clears its buffer and stops collecting. |
| No failed-login events | Windows Security log is not readable; run elevated or accept the explicit disabled collector state. |
| No file events | Watch directories do not exist/are empty, or file monitoring is disabled. Check `AGENT_ENABLE_FILE_MONITORING` and `AGENT_WATCH_DIRS`. |
| Proxy events rejected | `INGESTION_API_KEY` is unset/mismatched, or the timestamp is outside the allowed window. |
| System Health shows `null` counts | That collection is unavailable/unreadable; the UI shows it as unavailable instead of inventing data. |
| Slack/Jira not delivered | Integration variables are unset, non-HTTPS, or the remote endpoint failed. Check the response `integration_results`. |

---

## License and use

This is an academic capstone prototype. It is not a certified DLP, EDR,
SIEM/SOAR or compliance product. Deploy it only on systems and accounts you are
authorized to monitor, and keep consent, retention and access-control policies
aligned with your jurisdiction and institution.
