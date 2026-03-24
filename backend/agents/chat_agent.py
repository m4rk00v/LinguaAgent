from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from rag.retriever import retrieve_context
import redis
import json
import os

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
DIM = "\033[2m"
RESET = "\033[0m"

llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "llama3"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)
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


def chat(user_id: str, session_id: str, message: str, level: str = "beginner", verbose: bool = True):
    if verbose:
        print(f"  {CYAN}[1/5]{RESET} Retrieving context from RAG...")
    student_context = retrieve_context(message, source_type="profile", k=3)
    course_context = retrieve_context(message, source_type="course", level=level, k=5)

    if verbose:
        print(f"  {CYAN}[2/5]{RESET} Building prompt (student chunks: {len(student_context)}, course chunks: {len(course_context)})...")
    system = SYSTEM_PROMPT.format(
        level=level,
        student_context="\n".join([c["content"] for c in student_context]),
        course_context="\n".join([c["content"] for c in course_context])
    )
    if verbose:
        print(f"\n  {GREEN}--- SYSTEM PROMPT ---{RESET}")
        for line in system.strip().split("\n"):
            print(f"  {DIM}{line}{RESET}")
        print(f"  {GREEN}--- END PROMPT ---{RESET}\n")

    if verbose:
        print(f"  {CYAN}[3/5]{RESET} Loading chat history from Redis...")
    history = get_chat_history(session_id)
    messages = [SystemMessage(content=system)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=message))
    if verbose:
        if history:
            print(f"\n  {YELLOW}--- CHAT HISTORY ({len(history)} messages) ---{RESET}")
            for msg in history:
                role_color = RED if msg["role"] == "user" else GREEN
                print(f"  {role_color}{msg['role']}:{RESET} {msg['content']}")
            print(f"  {YELLOW}--- END HISTORY ---{RESET}\n")
        else:
            print(f"        {DIM}No previous messages{RESET}")

    if verbose:
        print(f"  {CYAN}[4/5]{RESET} Calling LLM (llama3)... this may take a moment")
    response = llm.invoke(messages)

    if verbose:
        print(f"  {CYAN}[5/5]{RESET} Saving to Redis...")
    save_message(session_id, "user", message)
    save_message(session_id, "assistant", response.content)

    return response.content
