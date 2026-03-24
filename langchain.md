# Phase 3 — LangChain Agents

## What LangChain Does Here

LangChain is the framework that connects all the pieces inside each agent. Without it, you'd have to wire everything manually.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LangChain (the glue)                        │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     CHAT AGENT FLOW                          │   │
│  │                                                              │   │
│  │  Student message                                             │   │
│  │       │                                                      │   │
│  │       ▼                                                      │   │
│  │  ┌─────────────────────┐    ┌─────────────────────────────┐  │   │
│  │  │ OllamaEmbeddings    │    │ DirectoryLoader             │  │   │
│  │  │ (langchain_ollama)  │    │ (langchain_community)       │  │   │
│  │  │                     │    │                             │  │   │
│  │  │ Converts query to   │    │ Loads .md course files      │  │   │
│  │  │ 768-dim vector for  │    │ at ingestion time           │  │   │
│  │  │ RAG search          │    │         │                   │  │   │
│  │  └────────┬────────────┘    │         ▼                   │  │   │
│  │           │                 │ RecursiveCharacterText-     │  │   │
│  │           │                 │ Splitter (langchain_text)   │  │   │
│  │           │                 │ Cuts docs into ~500 token   │  │   │
│  │           │                 │ chunks for pgvector         │  │   │
│  │           │                 └─────────────────────────────┘  │   │
│  │           │                                                  │   │
│  │           ▼                                                  │   │
│  │  ┌─────────────────────┐                                     │   │
│  │  │ pgvector (Supabase) │                                     │   │
│  │  │ Returns top-K       │                                     │   │
│  │  │ similar chunks      │                                     │   │
│  │  └────────┬────────────┘                                     │   │
│  │           │ relevant chunks                                  │   │
│  │           ▼                                                  │   │
│  │  ┌─────────────────────────────────────────────────────┐     │   │
│  │  │ Build messages array (langchain_core.messages)      │     │   │
│  │  │                                                     │     │   │
│  │  │  SystemMessage:  system prompt + RAG chunks         │     │   │
│  │  │       +                                             │     │   │
│  │  │  HumanMessage / AIMessage:  history from Redis      │     │   │
│  │  │       +                                             │     │   │
│  │  │  HumanMessage:  current student message             │     │   │
│  │  └────────────────────┬────────────────────────────────┘     │   │
│  │                       │                                      │   │
│  │                       ▼                                      │   │
│  │  ┌─────────────────────────────────────────────────────┐     │   │
│  │  │ ChatOllama (langchain_ollama)                       │     │   │
│  │  │                                                     │     │   │
│  │  │ Sends the full messages array to llama3 via Ollama  │     │   │
│  │  │ Returns the agent response                          │     │   │
│  │  └────────────────────┬────────────────────────────────┘     │   │
│  │                       │                                      │   │
│  │                       ▼                                      │   │
│  │              Save to Redis (user + assistant)                │   │
│  │              Return response to student                      │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  LangChain components used:                                         │
│  ┌────────────────────────┬────────────────────────────────────┐    │
│  │ Package                │ What it provides                   │    │
│  ├────────────────────────┼────────────────────────────────────┤    │
│  │ langchain_ollama       │ ChatOllama, OllamaEmbeddings       │    │
│  │ langchain_core         │ SystemMessage, HumanMessage,       │    │
│  │                        │ AIMessage                          │    │
│  │ langchain_text_splitters│ RecursiveCharacterTextSplitter    │    │
│  │ langchain_community    │ DirectoryLoader, TextLoader        │    │
│  └────────────────────────┴────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Redis Setup

Redis is used for short-term conversation memory (chat history per session).

### How to start Redis
```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### Verify Redis is running
```bash
docker exec redis redis-cli ping
# Expected output: PONG
```

### Connection
- URL: `redis://localhost:6379`
- Configured in `backend/.env` as `REDIS_URL`

### What Redis stores
| Key pattern | TTL | Purpose |
|-------------|-----|---------|
| `chat:{session_id}` | 24h | Chat Agent conversation history (last N messages) |
| `voice:{session_id}` | 1h | Voice Agent conversation history (shorter, for low latency) |

---

## Agents (pending)

### Chat Agent (`backend/agents/chat_agent.py`)
- [x] Created

**Purpose:** Text-based conversational English practice. Corrects grammar in real time.

**Flow:**
1. Student sends a message
2. RAG retrieves student profile context (errors, level) + relevant course material
3. Redis loads the last 10 messages of conversation history
4. LLM (llama3) receives: system prompt + RAG context + history + student message
5. LLM responds naturally and adds a grammar note if there are errors
6. Message pair (user + assistant) saved to Redis with 24h TTL

**Key functions:**
| Function | Purpose |
|----------|---------|
| `chat(user_id, session_id, message, level)` | Main entry point — orchestrates RAG + history + LLM call |
| `get_chat_history(session_id, limit)` | Loads last N messages from Redis |
| `save_message(session_id, role, content)` | Saves a message to Redis with 24h TTL |

### Voice Agent (`backend/agents/voice_agent.py`)
- [ ] Create file

### Inspector Agent (`backend/agents/inspector_agent.py`)
- [x] Created

**Purpose:** Backend supervisor. Does not interact with the student directly. Monitors progress, calculates levels, and generates reports.

**Key difference:** Most logic is deterministic (DB queries + rules). The LLM is only used to generate the weekly progress report in natural language.

**Functions:**
| Function | Uses LLM? | Purpose |
|----------|-----------|---------|
| `update_student_level(user_id)` | No | Calculates level based on sessions count + error rate. Rules: ≥20 sessions & <0.3 errors → advanced, ≥10 & <0.5 → intermediate, else → beginner |
| `get_pending_tasks(user_id)` | No | Returns incomplete tasks (where `completed_at` is NULL) |
| `generate_weekly_report(user_id)` | Yes | Fetches profile + recent sessions + errors from DB, retrieves context via RAG, then asks LLM to generate a friendly email report |

---

## How to Test

Test scripts are in `backend/local_test/`. Always run from that directory:

```bash
cd /data/users/engineer/projects/LinguaAgent/backend/local_test
source ../venv/bin/activate
```

### Test Chat Agent
```bash
python3 test_chat_agent.py
```
- Sends 2 messages with the same `session_id`
- First message: should correct "I have 25 years" → "I am 25 years old"
- Second message: should correct "I go" → "I went" and remember the previous conversation (Redis memory)

### Test Inspector Agent — Levels & Tasks (no LLM)
```bash
python3 test_inspector_level.py
```
- Calculates and updates level for all 3 seed users based on sessions + error rate
- Lists pending tasks per user (where `completed_at` is NULL)

### Test Inspector Agent — Weekly Report (uses LLM)
```bash
python3 test_inspector_report.py
```
- Fetches profile, recent sessions, and grammar notes from Supabase
- Retrieves context via RAG
- LLM generates a friendly progress report formatted as an email body
