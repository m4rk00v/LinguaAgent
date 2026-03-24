from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
from dotenv import load_dotenv
import os

load_dotenv()

# Import agents
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.chat_agent import chat
from agents.inspector_agent import generate_weekly_report, get_pending_tasks, update_student_level

app = FastAPI(title="LinguaAgent API")
security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"


# --- Auth ---

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate JWT and return the payload."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def create_token(user_id: str, level: str = "beginner"):
    """Helper to generate a JWT for testing."""
    return jwt.encode({"sub": user_id, "level": level}, JWT_SECRET, algorithm=JWT_ALGORITHM)


# --- Request models ---

class ChatRequest(BaseModel):
    session_id: str
    message: str


# --- Chat Agent ---

@app.post("/api/chat")
def api_chat(req: ChatRequest, user=Depends(verify_token)):
    response = chat(
        user_id=user["sub"],
        session_id=req.session_id,
        message=req.message,
        level=user.get("level", "beginner"),
        verbose=False
    )
    return {"response": response}


# --- Inspector Agent ---

@app.get("/api/report/{user_id}")
def api_report(user_id: str, user=Depends(verify_token)):
    report = generate_weekly_report(user_id, verbose=False)
    return {"report": report}


@app.get("/api/tasks")
def api_tasks(user=Depends(verify_token)):
    tasks = get_pending_tasks(user["sub"])
    return {"tasks": tasks}


@app.post("/api/level/{user_id}")
def api_update_level(user_id: str, user=Depends(verify_token)):
    level = update_student_level(user_id)
    return {"user_id": user_id, "level": level}


# --- Health ---

@app.get("/health")
def health():
    return {"status": "ok"}


# --- Dev: generate test token ---

@app.get("/dev/token/{user_id}")
def dev_token(user_id: str, level: str = "beginner"):
    """DEV ONLY — generates a JWT for testing. Remove in production."""
    token = create_token(user_id, level)
    return {"token": token, "user_id": user_id, "level": level}
