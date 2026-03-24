# Phase 5 — n8n (Automation)

## Overview

n8n handles automated workflows that don't require real-time user interaction: reminders, payment failures, weekly reports, and admin escalations.

```
┌──────────────────────────────────────────────────────┐
│  n8n (localhost:5678)                                │
│                                                      │
│  Triggers:                     Actions:              │
│  • Cron (daily/weekly)    →    • HTTP to API Gateway │
│  • Webhook (Stripe/Agent) →    • Send Email/WhatsApp │
│  • Manual                 →    • Slack notification  │
│                                • Update DB           │
└──────────────────────────────────────────────────────┘
```

---

## Setup

### Step 1 — Start n8n with Docker
```bash
docker run -d \
  --name n8n \
  --network host \
  -v n8n_data:/home/node/.n8n \
  -e WEBHOOK_URL=http://localhost:5678 \
  -e N8N_SECURE_COOKIE=false \
  n8nio/n8n
```
> `--network host` allows n8n to reach the API at `localhost:8000` directly.
> `N8N_SECURE_COOKIE=false` is needed for local development without HTTPS. Remove in production.

### Step 2 — Verify it's running
```bash
docker ps | grep n8n
```

### Step 3 — Access the dashboard
Open `http://localhost:5678` in your browser. First time will ask you to create an account.

### Manage the container
```bash
# Stop
docker stop n8n

# Start again
docker start n8n

# View logs
docker logs n8n

# Remove (data persists in n8n_data volume)
docker rm n8n
```

---

## Workflows

### 1. Daily class reminder
| | |
|---|---|
| **Trigger** | Cron — every day at 8am |
| **What it does** | Queries API for pending tasks, sends email/WhatsApp to students with overdue tasks |
| **JSON file** | `backend/n8n_workflows/daily_reminder.json` |

```
[Cron: daily 8am]
       │
       ▼
[Get Service Token]
       │
       ▼
[HTTP GET localhost:8000/api/tasks]
       │
       ▼
[IF: has pending tasks]
       │
       ├── Yes → [Build Email: subject + body with task list]
       └── No  → [No action]
```

**Nodes in the workflow:**
| Node | Type | What it does |
|------|------|-------------|
| Every day at 8am | Schedule Trigger | Fires daily at 08:00 |
| Get Service Token | HTTP Request | Calls `/dev/token/service` to get a JWT |
| Get Pending Tasks | HTTP Request | Calls `/api/tasks` with the JWT |
| Has Pending Tasks? | IF | Checks if `tasks.length > 0` |
| Build Email | Set | Builds subject and body with the task list |
| No Pending Tasks | NoOp | Does nothing (end of flow) |

**How to import:**
1. Open `http://localhost:5678`
2. Click the **+** button to create a new workflow
3. Click the **...** menu (top right) → **Import from file**
4. Select `backend/n8n_workflows/daily_reminder.json`
5. The workflow loads with all nodes connected
6. Add a Send Email node after "Build Email" and configure your email provider
7. Activate the workflow

**Note:** Since n8n runs in Docker, use `host.docker.internal:8000` instead of `localhost:8000` to reach the API gateway.

- [x] Created

### 2. Failed payment
| | |
|---|---|
| **Trigger** | Webhook — receives POST from Stripe |
| **What it does** | Checks event type, notifies student, waits 7 days, suspends if still unpaid |
| **JSON file** | `backend/n8n_workflows/failed_payment.json` |

```
[Webhook: POST /stripe-payment-failed]
       │
       ▼
[IF: type == "invoice.payment_failed"]
       │
       ├── Yes → [Get Service Token]
       │              │
       │              ▼
       │         [Build Notification: email subject + body]
       │              │
       │              ▼
       │         [Wait 7 Days]
       │              │
       │              ▼
       │         [Check Still Unpaid]
       │              │
       │              ▼
       │         [Suspend Access]
       │
       └── No  → [No action]
```

**Nodes:**
| Node | Type | What it does |
|------|------|-------------|
| Stripe Webhook | Webhook | Receives POST from Stripe at `/webhook/stripe-payment-failed` |
| Is Payment Failed? | IF | Checks if `body.type == "invoice.payment_failed"` |
| Get Service Token | HTTP Request | Gets JWT from `/dev/token/service` |
| Build Notification | Set | Builds email subject, body, and extracts subscription_id |
| Wait 7 Days | Wait | Pauses execution for 7 days |
| Check Still Unpaid | HTTP Request | Checks payment status via API |
| Suspend Access | Set | Marks account for suspension |

**How to import:** Same as daily reminder — import from file in n8n dashboard.

**Stripe setup:** Point Stripe webhook to `http://<your-n8n-url>/webhook/stripe-payment-failed` for the `invoice.payment_failed` event.

- [x] Created

### 3. Weekly report
| | |
|---|---|
| **Trigger** | Cron — Sundays at 10am |
| **What it does** | For each active user, generates a progress report via the API and emails it |
| **JSON file** | `backend/n8n_workflows/weekly_report.json` |

```
[Cron: Sunday 10am]
       │
       ▼
[Get Service Token]
       │
       ▼
[Active User IDs: ["1", "2", "3"]]
       │
       ▼
[Split Into Users: loops per user_id]
       │
       ▼
[HTTP GET /api/report/{user_id}] ← uses LLM + RAG (may take a few seconds)
       │
       ▼
[Build Email: subject + report body]
```

**Nodes:**
| Node | Type | What it does |
|------|------|-------------|
| Every Sunday at 10am | Schedule Trigger | Fires weekly on Sundays |
| Get Service Token | HTTP Request | Gets JWT from `/dev/token/service` |
| Active User IDs | Set | Hardcoded list of user IDs (replace with DB query in production) |
| Split Into Users | Split Out | Creates one execution per user_id |
| Generate Report | HTTP Request | Calls `/api/report/{user_id}` — timeout 120s because LLM generation takes time |
| Build Email | Set | Builds email with the report as body |

**Note:** The "Active User IDs" node has a hardcoded list `["1", "2", "3"]`. In production, replace this with an HTTP request to fetch all active users from the API.

- [x] Created

### 4. HITL escalation
| | |
|---|---|
| **Trigger** | Webhook — Inspector Agent detects anomaly |
| **What it does** | Builds alert, waits for admin decision, executes or rejects action |
| **JSON file** | `backend/n8n_workflows/hitl_escalation.json` |

```
[Webhook: POST /inspector-anomaly]
       │
       ▼
[Build Alert: message with anomaly_type, user_id, details]
       │
       ▼
[Wait for Admin Response: POST /admin-response]
       │
       ▼
[IF: decision == "approved"]
       │
       ├── Yes → [Get Service Token] → [Execute Action]
       └── No  → [Log Rejection]
```

**Nodes:**
| Node | Type | What it does |
|------|------|-------------|
| Inspector Anomaly Webhook | Webhook | Receives POST at `/webhook/inspector-anomaly` with `{ anomaly_type, user_id, details }` |
| Build Alert | Set | Formats alert message for Slack/email (add Slack node here) |
| Wait for Admin Response | Webhook | Pauses execution until admin POSTs to `/webhook/admin-response` with `{ decision: "approved" or "rejected" }` |
| Approved? | IF | Routes based on admin decision |
| Get Service Token | HTTP Request | Gets JWT for API call |
| Execute Action | Set | Logs the approved action (connect to API endpoint for actual execution) |
| Log Rejection | Set | Logs the rejection |

**How it works:**
1. Inspector Agent detects something unusual (e.g., student inactive 2 weeks, suspicious activity)
2. POSTs to `http://localhost:5678/webhook/inspector-anomaly`
3. n8n builds an alert (add Slack/email node after "Build Alert" to notify admin)
4. Workflow pauses and waits for admin to POST to `http://localhost:5678/webhook/admin-response`
5. If approved → executes the action via API. If rejected → logs and closes.

**To test manually:**
```bash
# 1. Trigger the anomaly
curl -X POST http://localhost:5678/webhook/inspector-anomaly \
  -H "Content-Type: application/json" \
  -d '{"anomaly_type": "inactive_student", "user_id": "2", "details": "No sessions in 14 days"}'

# 2. Approve the action
curl -X POST http://localhost:5678/webhook/admin-response \
  -H "Content-Type: application/json" \
  -d '{"decision": "approved"}'
```

- [x] Created

---

## Inspector Agent → n8n Connection

Two new functions were added to `backend/agents/inspector_agent.py`:

| Function | What it does |
|----------|-------------|
| `trigger_n8n_workflow(workflow, data)` | Generic function that POSTs to an n8n webhook |
| `check_and_remind(user_id)` | Checks for overdue tasks and triggers the HITL escalation workflow if any are found |

Example: when `check_and_remind("2")` finds overdue tasks, it POSTs to `http://localhost:5678/webhook/inspector-anomaly` with the task details, which triggers the HITL escalation workflow.

---

## Connection to API Gateway

n8n workflows call the LinguaAgent API at `http://localhost:8000`. They need a valid JWT token.

For automated workflows, generate a long-lived service token:
```bash
curl http://localhost:8000/dev/token/service?level=admin
```

Store this token in n8n as a credential and use it in the `Authorization: Bearer <token>` header of all HTTP Request nodes.

---

## Docker containers running

| Container | Port | Purpose |
|-----------|------|---------|
| `redis` | 6379 | Conversation memory (chat/voice sessions) |
| `n8n` | 5678 | Workflow automation |
| API (uvicorn) | 8000 | FastAPI gateway (not Docker, runs in venv) |
