from dotenv import load_dotenv
load_dotenv()

import sys
sys.path.insert(0, "..")

from agents.inspector_agent import update_student_level, get_pending_tasks

print("=== Inspector Agent — Deterministic Tests (no LLM) ===\n")

# Update levels for all 3 users
for user_id in ["1", "2", "3"]:
    level = update_student_level(user_id)
    print(f"User {user_id} → level: {level}")

print()

# Check pending tasks for each user
for user_id in ["1", "2", "3"]:
    tasks = get_pending_tasks(user_id)
    if tasks:
        for t in tasks:
            print(f"User {user_id} → pending: \"{t['title']}\" (due: {t['due_date']})")
    else:
        print(f"User {user_id} → no pending tasks")
