# SaaS Security Monitor - Step 1

This repository contains Step 1 of the SaaS Security Monitor project, focusing on metadata collection and building the data foundation.

## What this Step Does
- Sets up a FastAPI backend with MongoDB integration.
- Configures Google Drive OAuth (local InstalledAppFlow) for read-only metadata access.
- Implements core models for Users, Files, and Events.
- Provides a Python script (`scripts/sync_drive.py`) to fetch Drive metadata and persist it in MongoDB.
- Provides REST APIs to retrieve files, users, and events.

## What this Step DOES NOT Do
- This step does not include the React frontend/dashboard.
- It does not include PII detection, sensitivity scoring, anomaly detection, risk engine, or blocking.
- It does not contain LLM or vector embeddings.
- It does not perform continuous real-time webhook-based monitoring. It uses a pull-based script to demonstrate API ingestion.

## Setup Instructions

### 1. Prerequisites
- Python 3.9+
- MongoDB installed locally or a MongoDB Atlas account.
- A Google Cloud Project with the Google Drive API enabled.

### 2. Google Cloud Setup
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Enable the **Google Drive API**.
4. Go to **Credentials** -> **Create Credentials** -> **OAuth client ID**.
5. Choose **Desktop app** as the application type.
6. Download the JSON credentials file.
7. Rename the file to `credentials.json` and place it in the `credentials/` folder:
   `saas-security-monitor/credentials/credentials.json`

### 3. Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Update the `.env` file if you are using MongoDB Atlas instead of local MongoDB.

### 4. Install Dependencies
Create a virtual environment and install dependencies:
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate

pip install -r backend/requirements.txt
```

### 5. Running the Backend (FastAPI)
Start the FastAPI server:
```bash
cd backend
uvicorn app.main:app --reload
```
Access the Swagger UI at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 6. Running the API Monitoring Proxy (Step 2)
The mitmproxy monitoring layer intercepts HTTP/HTTPS traffic to create Standardized Event Models and sends them to the backend API (`POST /api/events`). It does **NOT** log or store sensitive headers or payloads. 

Run the proxy in a separate terminal:
```bash
# Ensure venv is activated
set PYTHONPATH=backend  # Windows
# or export PYTHONPATH=backend # Linux/Mac
python scripts/run_proxy.py
```
This will start mitmdump locally on port 8080. You can point a test client to use this proxy to monitor events. Note: By default, it looks for API requests to known SaaS APIs (e.g., `googleapis.com`).

### 7. Synchronizing Google Drive Metadata (Step 1)
In a separate terminal, run the sync script (make sure you are at the project root and virtual environment is activated):
```bash
python scripts/sync_drive.py
```

### 8. PII Detection & Sensitivity Analysis (Step 3)
The system includes a privacy analysis module using Microsoft Presidio to detect structured PII without logging or storing the raw sensitive data by default.

**Supported PII Types:**
- EMAIL_ADDRESS (Moderate)
- PHONE_NUMBER (Moderate)
- PERSON (Low)
- IP_ADDRESS (Low)
- CREDIT_CARD (High)
- AADHAAR (High - via Custom Recognizer)
- PASSWORD (High - via Custom Recognizer)

**Sensitivity Classification & Scoring Formula:**
The sensitivity score ($S$) is calculated using weights (High=10, Moderate=5, Low=1):
$S = min(10H + 5M + 1L, 100)$

**Risk/Sensitivity Thresholds:**
- **Safe**: S < 20
- **Sensitive**: 20 <= S < 60
- **High-Risk**: S >= 60

*(Note: EWMA and behavioral anomaly detection belong to Step 4 and are not yet implemented).*

**API Endpoints:**
- `POST /api/privacy/analyze`: Analyzes text for PII and stores findings safely.
- `GET /api/privacy/findings`: Retrieves stored privacy analysis results.

**Privacy-Preserving Storage Approach:**
Raw PII is stripped out before saving to MongoDB. Only entity summaries, counts, scores, and categories are saved in the `pii_findings` collection.

**Example Synthetic Analysis Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/privacy/analyze" \
     -H "Content-Type: application/json" \
     -d '{
           "text": "My Aadhaar is 1234 5678 9012 and email is fake@example.com",
           "file_id": "test_file_01"
         }'
```

### 9. EWMA-Based Behavioral Anomaly Detection (Step 4)
The system maintains an adaptive behavioral baseline for each user to detect abnormal temporal deviations in SaaS activity using Exponentially Weighted Moving Average (EWMA). 

**Activity Rate Equation:**
The current activity rate (activities per hour) is calculated as:
`r_t = 3600 / (t_current - t_last)`
*(Note: A minimum elapsed time of 1 second is enforced to prevent division-by-zero errors).*

**EWMA Equation:**
The dynamic baseline is updated using:
`EWMA_(t,w) = λ_w * r_t + (1 - λ_w) * EWMA_(t-1,w)`

**Time Windows & Lambda Configuration:**
The system maintains independent baselines for each user across all 8 time windows specified in the paper: `30m, 1h, 2h, 8h, 1d, 7d, 30d, 90d`.
Since the paper does not specify the exact `λ` (lambda) values for each window, the following implementation defaults are used:
- 30m: 0.5
- 1h: 0.4
- 2h: 0.3
- 8h: 0.2
- 1d: 0.1
- 7d: 0.05
- 30d: 0.02
- 90d: 0.01

**Adaptive Anomaly Detection:**
Rather than a static threshold, anomalies are flagged when the deviation ratio between the `current_activity_rate` and the `EWMA_baseline` exceeds an configurable implementation default threshold. This successfully detects bursts of activity while adapting to normal user activity. 

**Cold-Start Behavior:**
For a new user, there is no previous timestamp or EWMA baseline. The system initializes the EWMA baselines using the initial activity rate (e.g. 1.0) and records the first event's timestamp, creating the `behavior_profiles` state in MongoDB without generating false alarms.

**API Endpoints:**
- `POST /api/v1/behavior/analyze`: Analyzes an event against EWMA baselines and persists findings.
- `GET /api/v1/behavior/users/{user_id}`: Retrieves the current behavioral baseline for a user.
- `GET /api/v1/behavior/anomalies`: Retrieves stored anomaly findings.

**Example Synthetic Anomaly Scenario:**
```bash
# Scenario A (Stable) vs Scenario B (Burst)
# Stable activity (e.g., 1 action per hour) sets a low baseline.
# A sudden burst of actions in 1 second creates an activity rate of 3600/hr, triggering a deviation anomaly.
curl -X POST "http://localhost:8000/api/v1/behavior/analyze" \
     -H "Content-Type: application/json" \
     -d '{
           "user_id": "userB",
           "event_id": "event_burst_1"
         }'
```

**Limitations & Future Steps:**
- The current deviation threshold is an implementation default and can be tuned per environment.
- Atomic concurrent updates for `behavior_profiles` are currently limited by standard MongoDB update semantics. 
- **Explicit Statement:** Step 4 produces behavioral/anomaly results only. The combined privacy + behavioral risk scoring belongs to **Step 5** and is not yet implemented.

### 10. Combined Risk Scoring Engine (Step 5)
The system features a final risk-scoring layer that integrates the **Privacy/Sensitivity information (Step 3)** and **Behavioral anomaly information (Step 4)** to produce a single interpretable risk score (0-100) and an overall risk category.

**Architecture:**
```
[Step 3 Privacy Score] & [Step 4 Behavioral Signal] --> Risk Engine --> Combined Risk Score --> Overall Risk Category
```

**Scoring Methodology:**
The engine uses the following scoring components:
- **Privacy Score Input:** Uses the normalized 0-100 sensitivity score directly from Step 3 ($S = min(10H + 5M + 1L, 100)$ as defined in the paper).
- **Behavioral Score Input:** Converts the Step 4 deviation ratio ($current\_rate / EWMA\_baseline$) into a normalized 0-100 score. *Note: Since the paper does not specify a numerical behavioral score conversion, a prototype mapping (linear scaling from deviation 1.0 to 10.0) is used.*
- **Combined Scoring Formula:** `combined_score = (privacy_weight * privacy_score) + (behavioral_weight * behavioral_score)`. 
- **Weight Configuration:** Since the paper emphasizes combined analysis but does not prescribe numeric weights, prototype defaults are used (`privacy_weight = 0.5`, `behavioral_weight = 0.5`).

**Risk Categories & Thresholds:**
The combined score is mapped to the following overall risk categories (using prototype default thresholds as none were explicitly defined in the paper):
- **LOW:** `< 20`
- **MEDIUM:** `< 50`
- **HIGH:** `< 80`
- **CRITICAL:** `>= 80`

**Missing Data & Cold-Start Behavior:**
- If one signal is missing (e.g. no privacy findings or missing behavioral history due to a cold start), the missing signal contributes `0.0` to the score, and the assessment is marked as `is_partial_assessment: true`. This prevents a new user's cold start from being artificially escalated to HIGH/CRITICAL simply because history is unavailable.

**Risk-Factor Explanation:**
The engine generates human-readable explanations based on the findings (e.g., `HIGH_SENSITIVITY_PII`, `BEHAVIORAL_ANOMALY`, `ACTIVITY_SPIKE`) explaining exactly why the score was generated.

**MongoDB Collection:**
Risk assessments are persisted in the `risk_assessments` collection. Raw PII is never stored in this collection.

**API Endpoints:**
- `POST /api/risk/analyze`: Generates a combined risk assessment.
- `GET /api/risk/assessments`: Retrieves paginated risk assessments.
- `GET /api/risk/users/{user_id}`: Retrieves risk assessments for a specific user.

**Example Synthetic Combined Risk Scenario:**
```bash
curl -X POST "http://localhost:8000/api/risk/analyze" \
     -H "Content-Type: application/json" \
     -d '{
           "user_id": "test_user",
           "event_id": "test_event",
           "privacy_finding_id": "existing_privacy_id_here",
           "anomaly_id": "existing_anomaly_id_here"
         }'
```

**Limitations & Future Steps:**
- Normalization curves and weights are prototype implementation choices that require fine-tuning for production.
- **Explicit Statement:** Step 5 only produces the combined risk assessment. Automatic blocking, access denial, and firewall enforcement belong to **Step 6** and are not yet implemented.

### 11. Enforcement and Response (Step 6)
The enforcement layer acts upon the combined risk score generated by Step 5 to automatically deploy security responses.

**Architecture Flow:**
```
[Step 5 Combined Risk Assessment] --> Enforcement Engine --> Action Policy --> Executed/Simulated Response
```

**Risk Category Mapping (Prototype Defaults):**
The research paper describes the necessity of mitigating identified risk but does not strictly specify the technical execution parameters of a response system. The following policy mapping is a **configurable prototype implementation decision**:
- **LOW** $\rightarrow$ `LOG`: The event is recorded silently. No active enforcement is required.
- **MEDIUM** $\rightarrow$ `ALERT`: A security alert is generated for the event. The user is not blocked.
- **HIGH** $\rightarrow$ `WARN`: A high-risk warning is issued to the administrator.
- **CRITICAL** $\rightarrow$ `SIMULATED_BLOCK`: A simulated blocking action is applied.

**Safe Prototype Enforcement:**
Because this project is a local security monitor prototype, active interference (such as actually suspending a Google Workspace account) is intentionally **simulated** (using the `SIMULATED` response status). Passive actions (logging and alerting) are logged as `EXECUTED`. This provides verifiable proof of the decision engine without destructive real-world side effects.

**Duplicate Response Protection (Idempotency):**
The system prevents duplicate enforcement actions. If a `CRITICAL` event is submitted for enforcement multiple times, the service returns the existing response with an `ALREADY_HANDLED` status rather than spamming alerts or blocks.

**API Endpoints:**
- `POST /api/enforcement/respond`: Triggers an enforcement response given a `risk_id`.
- `GET /api/enforcement/responses`: Retrieves the history of enforcement actions.
- `GET /api/enforcement/users/{user_id}`: Retrieves enforcement history for a specific user.

**Example Synthetic Test Command:**
```bash
curl -X POST "http://localhost:8000/api/enforcement/respond" \
     -H "Content-Type: application/json" \
     -d '{
           "risk_id": "your_existing_risk_id_here"
         }'
```

**MongoDB Collection:**
Enforcement records are stored in the `enforcement_responses` collection.

### 12. Security Monitoring Dashboard (Step 7)
The project includes a simple web-based security monitoring dashboard to visually monitor the data produced by Steps 1–6. It retrieves data safely via the existing backend REST APIs without exposing raw sensitive payloads.

**Technology Stack:**
- React (Vite)
- Tailwind CSS for styling
- Recharts for data visualization
- Axios for API communication

**Features:**
- **Summary Metrics**: High-level counts of events, anomalies, privacy findings, and risks.
- **Risk Distribution Chart**: Visual breakdown of Risk Categories (LOW, MEDIUM, HIGH, CRITICAL).
- **Recent Risk Assessments**: Table of recent unified risk scores and categories.
- **Privacy Findings**: Safe overview of privacy events (metadata and scores only).
- **Behavior Anomalies**: Details on temporal activity anomalies (EWMA deviations).
- **Enforcement Responses**: Log of automated responses (e.g., SIMULATED blocks, WARN).

**How to start the Frontend:**
1. Ensure the FastAPI backend is running on `http://localhost:8000`.
2. Open a new terminal and navigate to the frontend directory:
```bash
cd frontend
```
3. Install dependencies (only needed once):
```bash
npm install
```
4. Start the Vite development server:
```bash
npm run dev
```
5. Open your browser to the local URL provided (usually `http://localhost:5173`).

*(Note: The dashboard auto-refreshes every 10 seconds to display new events.)*

### 13. Running Tests
Run tests using pytest from the virtual environment:
```bash
# Ensure PYTHONPATH is set so modules resolve
set PYTHONPATH=backend
venv\Scripts\pytest tests/
```
## Final Demo Quick Start (Step 8)

To quickly run the complete end-to-end demonstration on Windows PowerShell, follow these steps:

### 1. Start the Backend
Open **Terminal 1** from the project root:
```powershell
cd backend
..\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```
You can view the interactive Swagger API documentation at: http://127.0.0.1:8000/docs

### 2. Start the Frontend Dashboard
Open **Terminal 2** from the project root:
```powershell
cd frontend
npm run dev
```
Open your browser to the URL provided (e.g., http://localhost:5173). Keep this window open. The dashboard auto-refreshes every 10 seconds.

### 3. Generate a Complete Synthetic Event Pipeline
Open **Terminal 3** from the project root. You can execute this synthetic Python script to simulate a complete data pipeline (Event -> Privacy -> Behavior -> Risk -> Enforcement) which will immediately populate the React dashboard:

```powershell
cd backend
..\venv\Scripts\Activate.ps1
python demo.py
```

**What this script does:**
1. Generates a synthetic Event (`POST /api/events`).
2. Runs Privacy Analysis on a sensitive text payload (`POST /api/privacy/analyze`).
3. Runs Behavioral Anomaly Detection which triggers a high activity rate (`POST /api/behavior/analyze`).
4. Computes the Combined Risk Score (`POST /api/risk/analyze`).
5. Triggers an automated Enforcement Response (`POST /api/enforcement/respond`).

Once the script completes, check your browser where the React Dashboard will instantly reflect the new total events, privacy findings, behavior anomalies, High/Critical risks, and the automated enforcement response log!

## Step 8 (Final PDF Alignment) Integrations
The project includes the final advanced integrations outlined in the research paper:
- **Slack & Jira Alerting:** Configurable via .env (SLACK_WEBHOOK_URL, JIRA_API_URL, JIRA_AUTH_TOKEN). If not configured, alerts operate in safe mock/simulation mode (logged to console) and do not crash the application.
- **Vector / Semantic Similarity Search:** A lightweight local vector database prototype is implemented (using pure mathematical TF & cosine similarity) for finding similar file behavior contexts without requiring a paid Pinecone API key.
- **Offline Cloud Content Analysis:** The script ackend/scripts/offline_analysis.py can be executed manually to run a batch analysis of all currently synced MongoDB files, generating semantic embeddings and pre-computing privacy risk baselines, as required by Section V-B of the research paper.
