# LinguaAgent — Implementation Guide

> Priority: Backend AI first (RAG, LangChain, Agents, n8n). Frontend and HTTPS are low priority.

---

## Phase 1 — Database & Schema (Supabase)

Everything else depends on the DB being set up first.

### Step 1.1 — Create a Supabase project
- Go to [supabase.com](https://supabase.com) and create a new project
- Save the credentials: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`

### Step 1.2 — Create the base tables
```sql
CREATE TABLE users (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  google_id TEXT UNIQUE,
  plan TEXT DEFAULT 'free',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE student_profiles (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  level TEXT DEFAULT 'beginner',
  total_sessions INT DEFAULT 0,
  streak_days INT DEFAULT 0
);

CREATE TABLE sessions (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id INT REFERENCES users(id),
  agent_type TEXT CHECK (agent_type IN ('chat', 'voice')),
  started_at TIMESTAMPTZ DEFAULT now(),
  ended_at TIMESTAMPTZ,
  summary TEXT
);

CREATE TABLE tasks (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id INT REFERENCES users(id),
  title TEXT NOT NULL,
  due_date DATE,
  completed_at TIMESTAMPTZ,
  assigned_by_agent TEXT
);

CREATE TABLE grammar_notes (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id INT REFERENCES sessions(id),
  error_type TEXT,
  original_text TEXT,
  correction TEXT,
  timestamp TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE payments (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id INT REFERENCES users(id),
  stripe_subscription_id TEXT,
  status TEXT DEFAULT 'active',
  next_billing_date DATE
);
```

### Step 1.3 — Enable pgvector and create documents table
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  content TEXT NOT NULL,
  embedding VECTOR(1536),
  metadata JSONB DEFAULT '{}',
  source_type TEXT CHECK (source_type IN ('course', 'profile', 'policy')),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON documents
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

### Step 1.4 — Create semantic search function
```sql
CREATE OR REPLACE FUNCTION match_documents(
  query_embedding VECTOR(1536),
  match_count INT DEFAULT 5,
  filter_source TEXT DEFAULT NULL,
  filter_level TEXT DEFAULT NULL
)
RETURNS TABLE (
  id INT,
  content TEXT,
  metadata JSONB,
  source_type TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id,
    d.content,
    d.metadata,
    d.source_type,
    1 - (d.embedding <=> query_embedding) AS similarity
  FROM documents d
  WHERE
    (filter_source IS NULL OR d.source_type = filter_source)
    AND (filter_level IS NULL OR d.metadata->>'level' = filter_level)
  ORDER BY d.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

**Checkpoint:** Tables created, pgvector enabled, search function ready.

---

## Phase 2 — RAG Pipeline

### Step 2.1 — Python project setup
```bash
mkdir backend && cd backend
python -m venv venv
source venv/bin/activate

pip install langchain langchain-anthropic langchain-community
pip install supabase openai
pip install python-dotenv redis
```

### Step 2.2 — Environment variables
Create `backend/.env`:
```env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # only for embeddings
REDIS_URL=redis://localhost:6379
```

### Step 2.3 — Course content ingestion script
Create `backend/rag/ingest.py`:
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from openai import OpenAI
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
openai_client = OpenAI()

# 1. Load documents
loader = DirectoryLoader(
    "data/courses/",
    glob="**/*.md",
    loader_cls=TextLoader
)
docs = loader.load()

# 2. Chunking
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n## ", "\n### ", "\n\n", "\n", " "]
)
chunks = splitter.split_documents(docs)

# 3. Generate embeddings and insert into Supabase
for chunk in chunks:
    embedding = openai_client.embeddings.create(
        input=chunk.page_content,
        model="text-embedding-3-small"
    ).data[0].embedding

    supabase.table("documents").insert({
        "content": chunk.page_content,
        "embedding": embedding,
        "metadata": {
            "source": chunk.metadata.get("source", ""),
            "level": chunk.metadata.get("level", "all")
        },
        "source_type": "course"
    }).execute()

print(f"Ingested {len(chunks)} chunks")
```

### Step 2.4 — Create sample course content
Create `backend/data/courses/beginner/greetings.md`:
```markdown
---
level: beginner
topic: greetings
---

# Greetings and Introductions

## Common Greetings
- Hello / Hi / Hey
- Good morning / Good afternoon / Good evening
- How are you? / How's it going?

## Introducing Yourself
- My name is... / I'm...
- Nice to meet you.
- I'm from...

## Common Mistakes
- Wrong: "I am agree" → Correct: "I agree"
- Wrong: "I have 25 years" → Correct: "I am 25 years old"
```

Create more similar files for other topics and levels.

### Step 2.5 — Retrieval module
Create `backend/rag/retriever.py`:
```python
from openai import OpenAI
from supabase import create_client
import os

openai_client = OpenAI()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

def retrieve_context(query: str, source_type: str = None, level: str = None, k: int = 5):
    """Search for the most relevant chunks in pgvector."""

    query_embedding = openai_client.embeddings.create(
        input=query,
        model="text-embedding-3-small"
    ).data[0].embedding

    result = supabase.rpc("match_documents", {
        "query_embedding": query_embedding,
        "match_count": k,
        "filter_source": source_type,
        "filter_level": level
    }).execute()

    return [
        {"content": doc["content"], "metadata": doc["metadata"], "similarity": doc["similarity"]}
        for doc in result.data
    ]
```

### Step 2.6 — Test the pipeline
Create `backend/rag/test_rag.py`:
```python
from dotenv import load_dotenv
load_dotenv()

from ingest import *   # runs the ingestion
from retriever import retrieve_context

results = retrieve_context(
    query="How do I introduce myself in English?",
    source_type="course",
    level="beginner",
    k=3
)

for r in results:
    print(f"[{r['similarity']:.3f}] {r['content'][:100]}...")
```

```bash
# Run
cd backend/rag
python test_rag.py
```

**Checkpoint:** You can run semantic queries against your course content.

---

## Phase 3 — LangChain + Agents

### Step 3.1 — Redis for conversational memory
```bash
# Install Redis locally
brew install redis
brew services start redis
```

### Step 3.2 — Chat Agent
Create `backend/agents/chat_agent.py`:
```python
from langchain_anthropic import ChatAnthropic
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from rag.retriever import retrieve_context
import redis
import json
import os

llm = ChatAnthropic(model="claude-sonnet-4-20250514", anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))
redis_client = redis.from_url(os.getenv("REDIS_URL"))

SYSTEM_PROMPT = """You are an English teacher. Have a natural conversation with the student.
After each student message, respond naturally first, then add a brief
grammar note if there are errors. Be encouraging.

Student level: {level}

## Student Context
{student_context}

## Relevant Course Material
{course_context}
"""

def get_chat_history(session_id: str, limit: int = 10):
    """Retrieve history from Redis."""
    history = redis_client.lrange(f"chat:{session_id}", -limit, -1)
    return [json.loads(msg) for msg in history]

def save_message(session_id: str, role: str, content: str):
    """Save message to Redis."""
    redis_client.rpush(f"chat:{session_id}", json.dumps({"role": role, "content": content}))
    redis_client.expire(f"chat:{session_id}", 86400)  # 24h TTL

def chat(user_id: str, session_id: str, message: str, level: str = "beginner"):
    # 1. RAG - get context
    student_context = retrieve_context(message, source_type="profile", k=3)
    course_context = retrieve_context(message, source_type="course", level=level, k=5)

    # 2. Build prompt with context
    system = SYSTEM_PROMPT.format(
        level=level,
        student_context="\n".join([c["content"] for c in student_context]),
        course_context="\n".join([c["content"] for c in course_context])
    )

    # 3. Conversation history
    history = get_chat_history(session_id)
    messages = [SystemMessage(content=system)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=message))

    # 4. Call Claude
    response = llm.invoke(messages)

    # 5. Save to Redis
    save_message(session_id, "user", message)
    save_message(session_id, "assistant", response.content)

    return response.content
```

### Step 3.3 — Voice Agent
Create `backend/agents/voice_agent.py`:
```python
from langchain_anthropic import ChatAnthropic
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from rag.retriever import retrieve_context
import redis
import json
import os

llm = ChatAnthropic(model="claude-sonnet-4-20250514", anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))
redis_client = redis.from_url(os.getenv("REDIS_URL"))

SYSTEM_PROMPT = """You are a friendly English conversation partner. Focus on keeping
the conversation flowing naturally. Note grammar issues internally but do NOT
correct mid-conversation. Keep responses short (1-3 sentences) for natural voice pacing.

Student level: {level}

## Topic Context
{course_context}
"""

SUMMARY_PROMPT = """Based on this conversation, provide a brief grammar feedback summary.
List the main errors the student made and how to correct them.

Conversation:
{conversation}
"""

def voice_chat(user_id: str, session_id: str, transcribed_text: str, level: str = "beginner"):
    """Process transcribed text and return text response (for TTS afterwards)."""

    # Lightweight RAG - topic context only, no profile (lower latency)
    course_context = retrieve_context(transcribed_text, source_type="course", level=level, k=3)

    system = SYSTEM_PROMPT.format(
        level=level,
        course_context="\n".join([c["content"] for c in course_context])
    )

    # Short history for voice
    history = redis_client.lrange(f"voice:{session_id}", -6, -1)
    messages = [SystemMessage(content=system)]
    for msg_raw in history:
        msg = json.loads(msg_raw)
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=transcribed_text))

    response = llm.invoke(messages)

    # Save to Redis
    redis_client.rpush(f"voice:{session_id}", json.dumps({"role": "user", "content": transcribed_text}))
    redis_client.rpush(f"voice:{session_id}", json.dumps({"role": "assistant", "content": response.content}))
    redis_client.expire(f"voice:{session_id}", 3600)  # 1h TTL

    return response.content

def end_voice_session(session_id: str):
    """Generate error summary at the end of the voice session."""
    history = redis_client.lrange(f"voice:{session_id}", 0, -1)
    conversation = "\n".join([
        f"{json.loads(m)['role']}: {json.loads(m)['content']}" for m in history
    ])

    messages = [
        SystemMessage(content=SUMMARY_PROMPT.format(conversation=conversation))
    ]
    summary = llm.invoke(messages)

    # Clean up Redis
    redis_client.delete(f"voice:{session_id}")

    return summary.content
```

### Step 3.4 — Inspector Agent
Create `backend/agents/inspector_agent.py`:
```python
from langchain_anthropic import ChatAnthropic
from langchain.schema import SystemMessage
from rag.retriever import retrieve_context
from supabase import create_client
import os

llm = ChatAnthropic(model="claude-sonnet-4-20250514", anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

def update_student_level(user_id: str):
    """Deterministic logic — does not use LLM."""
    # Get sessions and errors
    sessions = supabase.table("sessions").select("*").eq("user_id", user_id).execute()
    notes = supabase.table("grammar_notes").select("*").execute()

    total = len(sessions.data)
    error_rate = len(notes.data) / max(total, 1)

    # Simple level rules
    if total >= 20 and error_rate < 0.3:
        level = "advanced"
    elif total >= 10 and error_rate < 0.5:
        level = "intermediate"
    else:
        level = "beginner"

    supabase.table("student_profiles").update(
        {"level": level, "total_sessions": total}
    ).eq("user_id", user_id).execute()

    return level

def get_pending_tasks(user_id: str):
    """Incomplete tasks."""
    result = supabase.table("tasks").select("*").eq("user_id", user_id).is_("completed_at", "null").execute()
    return result.data

def generate_weekly_report(user_id: str):
    """Uses LLM + RAG to generate a report in natural language."""
    # Student context via RAG
    context = retrieve_context(
        f"weekly progress report for student {user_id}",
        source_type="profile",
        k=10
    )

    # Hard data from the DB
    profile = supabase.table("student_profiles").select("*").eq("user_id", user_id).single().execute()
    recent_sessions = supabase.table("sessions").select("*").eq("user_id", user_id).order("started_at", desc=True).limit(7).execute()
    recent_errors = supabase.table("grammar_notes").select("*").order("timestamp", desc=True).limit(20).execute()

    prompt = f"""Generate a weekly English learning progress report for this student.
Be encouraging but honest. Include specific areas to improve.

Student Profile: {profile.data}
Sessions this week: {len(recent_sessions.data)}
Recent errors: {[n['error_type'] for n in recent_errors.data]}
RAG Context: {[c['content'] for c in context]}

Format as a friendly email body.
"""

    response = llm.invoke([SystemMessage(content=prompt)])
    return response.content
```

### Step 3.5 — Test the agents
Create `backend/test_agents.py`:
```python
from dotenv import load_dotenv
load_dotenv()

from agents.chat_agent import chat
from agents.voice_agent import voice_chat, end_voice_session

# Test Chat Agent
print("=== Chat Agent ===")
resp = chat(
    user_id="test-user-1",
    session_id="test-session-1",
    message="Hello! I want to practice my English. I have 25 years.",
    level="beginner"
)
print(resp)

# Test Voice Agent
print("\n=== Voice Agent ===")
resp = voice_chat(
    user_id="test-user-1",
    session_id="test-voice-1",
    transcribed_text="I go to the store yesterday and I buy many things",
    level="intermediate"
)
print(resp)

summary = end_voice_session("test-voice-1")
print(f"\nSession Summary:\n{summary}")
```

**Checkpoint:** All 3 agents work with RAG + Redis + Claude.

---

## Phase 4 — API Gateway (FastAPI)

### Step 4.1 — Install FastAPI
```bash
pip install fastapi uvicorn python-jose[cryptography]
```

### Step 4.2 — Create the gateway
Create `backend/api/main.py`:
```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt
import os

from agents.chat_agent import chat
from agents.voice_agent import voice_chat, end_voice_session
from agents.inspector_agent import generate_weekly_report, get_pending_tasks

app = FastAPI(title="LinguaAgent API")
security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

class ChatRequest(BaseModel):
    session_id: str
    message: str

class VoiceRequest(BaseModel):
    session_id: str
    transcribed_text: str

# --- Chat Agent ---
@app.post("/api/chat")
def api_chat(req: ChatRequest, user=Depends(verify_token)):
    response = chat(
        user_id=user["sub"],
        session_id=req.session_id,
        message=req.message,
        level=user.get("level", "beginner")
    )
    return {"response": response}

# --- Voice Agent ---
@app.post("/api/voice")
def api_voice(req: VoiceRequest, user=Depends(verify_token)):
    response = voice_chat(
        user_id=user["sub"],
        session_id=req.session_id,
        transcribed_text=req.transcribed_text,
        level=user.get("level", "beginner")
    )
    return {"response": response}

@app.post("/api/voice/end")
def api_voice_end(req: VoiceRequest, user=Depends(verify_token)):
    summary = end_voice_session(req.session_id)
    return {"summary": summary}

# --- Inspector Agent ---
@app.get("/api/report/{user_id}")
def api_report(user_id: str, user=Depends(verify_token)):
    report = generate_weekly_report(user_id)
    return {"report": report}

@app.get("/api/tasks")
def api_tasks(user=Depends(verify_token)):
    tasks = get_pending_tasks(user["sub"])
    return {"tasks": tasks}

# --- Health ---
@app.get("/health")
def health():
    return {"status": "ok"}
```

### Step 4.3 — Run it
```bash
cd backend
uvicorn api.main:app --reload --port 8000
```

**Checkpoint:** API running on `localhost:8000`. Test with curl or Postman.

---

## Phase 5 — n8n (Automation)

### Step 5.1 — Install n8n locally (development)
```bash
# Option A: Docker
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n

# Option B: npm
npm install -g n8n
n8n start
```
Access at `http://localhost:5678`

### Step 5.2 — Workflow: Daily class reminder
Create in n8n:
```
[Cron Trigger: every day at 8am]
       │
       ▼
[HTTP Request: GET localhost:8000/api/tasks?pending=true]
       │
       ▼
[IF: has pending tasks]
       │
       ├── Yes ──▶ [Send Email / WhatsApp]
       │           "You have pending English tasks"
       │
       └── No ──▶ [No action]
```

### Step 5.3 — Workflow: Failed payment
```
[Webhook: receives POST from Stripe]
       │
       ▼
[IF: event.type == "invoice.payment_failed"]
       │
       ▼
[HTTP Request: update payment status via API]
       │
       ▼
[Send Email: "Your payment has failed"]
       │
       ▼
[Wait: 7 days]
       │
       ▼
[IF: still unpaid]
       │
       ├── Yes ──▶ [HTTP Request: suspend access]
       │
       └── No ──▶ [No action]
```

### Step 5.4 — Workflow: Weekly report
```
[Cron Trigger: Sundays at 10am]
       │
       ▼
[HTTP Request: GET all active user_ids]
       │
       ▼
[Loop: for each user_id]
       │
       ▼
[HTTP Request: GET localhost:8000/api/report/{user_id}]
       │
       ▼
[Send Email: send report to student]
```

### Step 5.5 — Workflow: HITL escalation
```
[Webhook: Inspector Agent detects anomaly]
       │
       ▼
[Slack: notify #admin-alerts]
       │
       ▼
[Wait for Webhook: wait for admin response]
       │
       ├── Approved ──▶ [HTTP Request: execute action]
       │
       └── Rejected ──▶ [Log and close]
```

### Step 5.6 — Connect Inspector Agent to n8n
Add to `backend/agents/inspector_agent.py`:
```python
import httpx

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook")

async def trigger_n8n_workflow(workflow: str, data: dict):
    """Trigger an n8n workflow via webhook."""
    async with httpx.AsyncClient() as client:
        await client.post(f"{N8N_WEBHOOK_URL}/{workflow}", json=data)

# Example: after detecting pending tasks
async def check_and_remind(user_id: str):
    pending = get_pending_tasks(user_id)
    overdue = [t for t in pending if t["due_date"] < str(datetime.now().date())]

    if overdue:
        await trigger_n8n_workflow("overdue-task", {
            "user_id": user_id,
            "tasks": overdue
        })
```

**Checkpoint:** n8n running with reminder, failed payment, report, and HITL workflows.

---

## Phase 6 — Voice Pipeline (Whisper + ElevenLabs)

### Step 6.1 — Install dependencies
```bash
pip install openai-whisper elevenlabs httpx
```

### Step 6.2 — Voice service
Create `backend/services/voice_service.py`:
```python
import whisper
from elevenlabs import ElevenLabs
import os

whisper_model = whisper.load_model("base")  # "small" or "medium" for better quality
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

def transcribe_audio(audio_path: str) -> str:
    """Audio → Text using Whisper."""
    result = whisper_model.transcribe(audio_path)
    return result["text"]

def text_to_speech(text: str, voice_id: str = "Rachel") -> bytes:
    """Text → Audio using ElevenLabs."""
    audio = elevenlabs_client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_turbo_v2"  # optimized for low latency
    )
    return b"".join(audio)
```

### Step 6.3 — Full voice endpoint
Add to `backend/api/main.py`:
```python
from fastapi import UploadFile, File
from fastapi.responses import Response
from services.voice_service import transcribe_audio, text_to_speech
import tempfile

@app.post("/api/voice/full")
async def api_voice_full(
    session_id: str,
    audio: UploadFile = File(...),
    user=Depends(verify_token)
):
    # 1. Save audio temporarily
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    # 2. STT: Audio → Text
    transcription = transcribe_audio(tmp_path)
    os.unlink(tmp_path)

    # 3. Agent: Text → Response
    response_text = voice_chat(
        user_id=user["sub"],
        session_id=session_id,
        transcribed_text=transcription,
        level=user.get("level", "beginner")
    )

    # 4. TTS: Response → Audio
    audio_bytes = text_to_speech(response_text)

    return Response(content=audio_bytes, media_type="audio/mpeg")
```

**Checkpoint:** Full pipeline: student voice → text → agent → text → response voice.

---

## Phase 7 — Stripe (Payments)

### Step 7.1 — Setup
```bash
pip install stripe
```

### Step 7.2 — Stripe webhook
Create `backend/api/stripe_webhook.py`:
```python
import stripe
from fastapi import Request, HTTPException
from supabase import create_client
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        supabase.table("payments").insert({
            "user_id": session["client_reference_id"],
            "stripe_subscription_id": session["subscription"],
            "status": "active"
        }).execute()

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        supabase.table("payments").update(
            {"status": "past_due"}
        ).eq("stripe_subscription_id", invoice["subscription"]).execute()
        # n8n handles the collection flow

    return {"received": True}
```

**Checkpoint:** Stripe processes payments and n8n handles failures.

---

## Phase 8 — Deploy (AWS)

### Step 8.1 — Dockerize the backend
Create `backend/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 8.2 — Docker Compose for development
Create `docker-compose.yml` in the root:
```yaml
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  n8n:
    image: n8nio/n8n
    ports:
      - "5678:5678"
    volumes:
      - n8n_data:/home/node/.n8n
    environment:
      - WEBHOOK_URL=http://localhost:5678

volumes:
  n8n_data:
```

### Step 8.3 — Start everything
```bash
docker compose up -d
```

### Step 8.4 — AWS (production)
```
1. ECS Fargate for the backend API
2. ElastiCache (Redis) for sessions
3. EC2 for n8n (self-hosted, sensitive data)
4. Supabase Cloud for DB + pgvector
5. Route 53 + ALB for routing
```

**Checkpoint:** Everything running in containers, ready for deploy.

---

## Phase 9 (Low Priority) — Frontend Next.js

Basic setup once the backend is solid:
```bash
npx create-next-app@latest frontend --typescript --tailwind
cd frontend
npm install next-auth @supabase/supabase-js
```

Connect to the API at `localhost:8000`. Auth with NextAuth + Google OAuth.

---

## Phase 10 (Low Priority) — HTTPS & Domain

- SSL certificate via AWS Certificate Manager or Let's Encrypt
- Domain on Route 53
- HTTPS on the ALB

---

## Implementation Order Summary

```
 1. ██████████ Supabase + pgvector (schema + search function)
 2. ██████████ RAG pipeline (ingestion + retrieval)
 3. ██████████ LangChain agents (Chat + Voice + Inspector)
 4. ████████── FastAPI gateway
 5. ████████── n8n workflows
 6. ██████──── Voice pipeline (Whisper + ElevenLabs)
 7. ██████──── Stripe payments
 8. ████────── Docker + deploy
 9. ██──────── Frontend (Next.js)
10. █───────── HTTPS + domain
```
