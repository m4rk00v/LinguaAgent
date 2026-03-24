from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from rag.retriever import retrieve_context
from supabase import create_client
import httpx
import os
from datetime import datetime

llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "llama3"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def update_student_level(user_id: str):
    """Deterministic logic — does not use LLM."""
    sessions = supabase.table("sessions").select("*").eq("user_id", user_id).execute()
    notes = supabase.table("grammar_notes").select("*").execute()

    total = len(sessions.data)
    error_rate = len(notes.data) / max(total, 1)

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


def generate_weekly_report(user_id: str, verbose: bool = True):
    """Uses LLM + RAG to generate a report in natural language."""
    if verbose:
        print("  [1/4] Retrieving student context from RAG...")
    context = retrieve_context(
        f"weekly progress report for student {user_id}",
        source_type="profile",
        k=10
    )

    if verbose:
        print("  [2/4] Fetching data from Supabase (profile, sessions, errors)...")
    profile = supabase.table("student_profiles").select("*").eq("user_id", user_id).single().execute()
    recent_sessions = supabase.table("sessions").select("*").eq("user_id", user_id).order("started_at", desc=True).limit(7).execute()
    recent_errors = supabase.table("grammar_notes").select("*").order("timestamp", desc=True).limit(20).execute()

    if verbose:
        print(f"        Sessions: {len(recent_sessions.data)}, Errors: {len(recent_errors.data)}")

    if verbose:
        print("  [3/4] Building prompt...")
    prompt = f"""Generate a weekly English learning progress report for this student.
Be encouraging but honest. Include specific areas to improve.

Student Profile: {profile.data}
Sessions this week: {len(recent_sessions.data)}
Recent errors: {[n['error_type'] for n in recent_errors.data]}
RAG Context: {[c['content'] for c in context]}

Format as a friendly email body.
"""

    if verbose:
        print("  [4/4] Calling LLM (llama3)... this may take a moment")
    response = llm.invoke([SystemMessage(content=prompt)])
    return response.content


# --- n8n Integration ---

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook")


def trigger_n8n_workflow(workflow: str, data: dict):
    """Trigger an n8n workflow via webhook."""
    with httpx.Client() as client:
        client.post(f"{N8N_WEBHOOK_URL}/{workflow}", json=data)


def check_and_remind(user_id: str):
    """Check for overdue tasks and trigger n8n reminder."""
    pending = get_pending_tasks(user_id)
    overdue = [t for t in pending if t["due_date"] and t["due_date"] < str(datetime.now().date())]

    if overdue:
        trigger_n8n_workflow("inspector-anomaly", {
            "anomaly_type": "overdue_tasks",
            "user_id": user_id,
            "details": f"{len(overdue)} overdue task(s): {[t['title'] for t in overdue]}"
        })
    return overdue
