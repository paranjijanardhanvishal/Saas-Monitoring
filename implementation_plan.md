# Capstone implementation notes

The authoritative setup guide, route list and limitations live in
[`README.md`](README.md). This file summarizes how the implementation maps to
the capstone abstract.

## Implemented

- FastAPI/MongoDB service with cookie and CSRF authentication, RBAC, consent
  enforcement, audit records and tenant-scoped reads.
- React SOC console with live API-backed overview, risk, activity, privacy,
  alert, incident, user, investigation, enforcement and health screens.
- Windows metadata-only endpoint agent and metadata-only SaaS proxy ingestion.
- Presidio/regex PII analysis with derived-only persisted findings.
- Optional, user-initiated local OCR for image and scanned-PDF uploads. OCR
  output and source files are not persisted; findings link to a scan event and
  a risk assessment. When no behavioral baseline exists, the privacy score is
  renormalized to its full value and the assessment is marked partial.
- EWMA activity baselines and rule-based business-role checks for attributed
  endpoint events. `GENERAL`, `DEVELOPER`, `HR` and `FINANCE` profiles use
  transparent resource-category terms; findings keep categories and scores,
  not filenames.
- Explainable risk scoring, alerts, incident workflows and administrator-
  confirmed enforcement with rollback and audit history.
- Live OCR readiness in System Health, configurable upload/page limits, and
  user-directory controls for assigning and filtering business roles.

## Deliberate limits

- OCR requires the optional packages in `backend/requirements-ocr.txt` and a
  local Tesseract executable. It is a one-request scan, not continuous DLP.
- Role checks are heuristic. They use known terms in attributed endpoint
  metadata and skip unknown/shared categories. SaaS proxy events are still
  unattributed and cannot be assigned a business role.
- The endpoint agent and offline analysis remain metadata-only; they do not
  inspect file contents. The proxy does not forward request or response bodies.
- Vector search is a local lexical TF/cosine index over names, not an embedding
  service.
- No automatic account or network blocking is performed. Administrative
  enforcement is confirmed and local to this application.
- Risk weights are prototype policy values, not learned or calibrated
  parameters.

## Verification status

The repository README records earlier baseline suite and browser-E2E results.
Those records predate the OCR and role-aware changes above and do not validate
the new flows. Current setup commands and feature limits are in the README.
