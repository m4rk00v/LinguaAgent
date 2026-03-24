from dotenv import load_dotenv
load_dotenv()

import sys
sys.path.insert(0, "..")

from agents.inspector_agent import generate_weekly_report

print("=== Inspector Agent — Weekly Report (uses LLM) ===\n")

report = generate_weekly_report("1")
print(report)
