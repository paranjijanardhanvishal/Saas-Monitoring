# Final Project Completion Plan (PDF Alignment)

Based on a thorough review of the provided research paper, the current SaaS Security Monitor implementation successfully fulfills the core architecture (API proxy, Presidio-based PII detection, EWMA behavioral anomaly detection, risk scoring, and dashboarding). 

However, there are a few advanced features explicitly described in the PDF that are currently missing from the codebase. In previous steps, these were explicitly marked as "out of scope" or "Step 9+", but since your latest request asks to *complete the whole project according to that pdf and implement anything missed*, I have identified them for implementation.

## User Review Required

> [!WARNING]
> **Constraint Override:** In the previous step, you strictly commanded: `"DO NOT implement: Slack integration, Jira integration, Pinecone, embeddings, machine-learning models."`
> However, the PDF requires these exact features to match the paper's full architecture. 
> **Please approve this plan to explicitly override the previous constraints and allow me to implement these missing modules.**

## Open Questions

1. **Slack & Jira Credentials:** To implement the Slack/Jira integrations, I will need to set up mock integrations or you will need to provide Webhook URLs/API keys in the `.env` file. Should I implement these using simulated mock logs, or do you want real integrations?
2. **Pinecone & Embeddings:** The paper mentions vectorizing metadata and storing it in a vector database (Pinecone) to find semantic similarities between files. Should I implement a lightweight local vector store (e.g., ChromaDB/FAISS) to avoid requiring a paid Pinecone API key, or do you strictly want Pinecone?

## Proposed Changes

If approved, I will implement the following missing modules to fully align with the PDF:

### 1. Vector Database / Semantic Metadata Indexing (Section III-C)
* **Description:** The paper states that metadata is "converted into high-dimensional vector forms and is indexed in the vector database" to identify files with similar characteristics or exposure patterns.
* **Implementation:** I will integrate an embedding model (e.g., `SentenceTransformers`) to vectorize file metadata and store it in a vector database (Pinecone or a local alternative like FAISS) to support semantic similarity searches.

### 2. Slack & Jira Automated Alerting (Section III-F & IV-E)
* **Description:** The paper describes an automated alerting system that provides notifications of critical events to security teams via Slack and generates Jira tickets for incident tracking.
* **Implementation:** I will create an `app/integrations/` module that listens for `HIGH` or `CRITICAL` risk assessments and automatically dispatches a formatted alert to a Slack Webhook and creates an issue via the Jira API.

### 3. Offline Cloud Content Analysis Pipeline (Section V-B)
* **Description:** The paper describes an "offline analysis pipeline that periodically reviews files stored in the cloud... based on pre-computed baseline and policies."
* **Implementation:** I will implement a background worker (using `apscheduler` or `Celery`) that periodically scans cloud files (via the Google Drive API), processes them through the PII engine offline, and pre-computes sensitivity baselines without blocking live traffic.

## Verification Plan

### Automated Tests
- I will write unit tests for the new Slack/Jira integration functions.
- I will write unit tests for the vector embedding generation and similarity search functions.
- I will ensure the offline analysis pipeline can run headlessly and update MongoDB records.

### Manual Verification
- You will be able to trigger a high-risk event and observe the simulated/real Slack alert and Jira ticket generation in the console logs.
