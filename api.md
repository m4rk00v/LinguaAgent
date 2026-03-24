# Phase 4 — API Gateway (FastAPI)

## Overview

The API Gateway is the single entry point for all client requests. It validates JWT tokens, routes to the correct agent, and returns responses.

```
Client (browser/app)
       │
       ▼
┌─────────────────────────┐
│  FastAPI Gateway         │
│  localhost:8000          │
│                          │
│  1. Validates JWT        │
│  2. Routes to agent      │
│  3. Returns JSON         │
└──────┬──────────────────┘
       │
       ├──── /api/chat ──────── Chat Agent
       ├──── /api/tasks ─────── Inspector Agent (deterministic)
       ├──── /api/level/{id} ── Inspector Agent (deterministic)
       └──── /api/report/{id} ─ Inspector Agent (LLM)
```

---

## Setup

### Step 1 — Install dependencies
```bash
cd /data/users/engineer/projects/LinguaAgent/backend
source venv/bin/activate
pip install fastapi uvicorn "python-jose[cryptography]"
```

### Step 2 — JWT Secret
A secret key was generated and added to `backend/.env`:
```env
JWT_SECRET=4c8de66c780794c15aaeb829e90d17954d4966f48106ee832a0f105abd8a30c6
```
This key signs and verifies all JWT tokens. Change it in production.

### Step 3 — Start the server
```bash
cd /data/users/engineer/projects/LinguaAgent/backend
source venv/bin/activate
uvicorn api.main:app --reload --port 8000
```
The server runs at `http://localhost:8000`.

---

## Endpoints

### Health Check
```
GET /health
```
No auth required. Returns `{"status": "ok"}`.

### Generate Test Token (dev only)
```
GET /dev/token/{user_id}?level=beginner
```
No auth required. Returns a JWT for testing. **Remove in production.**

Response:
```json
{
  "token": "eyJ...",
  "user_id": "1",
  "level": "beginner"
}
```

### Chat Agent
```
POST /api/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "session_id": "session-123",
  "message": "Hello! I have 25 years."
}
```
The `user_id` and `level` are extracted from the JWT. The agent responds with grammar corrections.

Response:
```json
{
  "response": "Hi there! Great to meet you! ... Note: We say 'I am 25 years old' instead of 'I have 25 years'."
}
```

### Pending Tasks
```
GET /api/tasks
Authorization: Bearer <token>
```
Returns incomplete tasks for the user in the JWT.

### Update Student Level
```
POST /api/level/{user_id}
Authorization: Bearer <token>
```
Recalculates the student level based on sessions and error rate.

### Weekly Report
```
GET /api/report/{user_id}
Authorization: Bearer <token>
```
Generates a weekly progress report using RAG + LLM. May take a few seconds.

---

## JWT Authentication

All `/api/*` endpoints require a Bearer token in the `Authorization` header.

The token is a standard JWT (HS256) with this payload:
```json
{
  "sub": "1",       // user_id
  "level": "beginner" // student level
}
```

Flow:
1. Client sends request with `Authorization: Bearer <token>`
2. Gateway decodes and validates the JWT using `JWT_SECRET`
3. If valid, extracts `sub` (user_id) and `level` from the payload
4. Passes them to the agent
5. If invalid or expired, returns `401 Unauthorized`

---

## How to Test

### Option A — Run the test script
```bash
# Terminal 1: start the server
cd /data/users/engineer/projects/LinguaAgent/backend
source venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Terminal 2: run tests
cd /data/users/engineer/projects/LinguaAgent/backend/local_test
bash test_api.sh
```

The script runs 5 tests in order:
1. Health check
2. Generate test JWT token
3. Chat endpoint (sends a message with grammar errors)
4. Get pending tasks
5. Update student level

### Option B — Manual curl
```bash
# Get a test token
curl http://localhost:8000/dev/token/1?level=beginner

# Use the token (replace <TOKEN> with the actual token)
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-1", "message": "I have 25 years"}'
```
