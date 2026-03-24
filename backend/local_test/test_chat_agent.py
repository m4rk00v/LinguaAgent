from dotenv import load_dotenv
load_dotenv()

import sys
sys.path.insert(0, "..")

from agents.chat_agent import chat

print("=== Chat Agent Test ===\n")

# First message — should correct "I have 25 years"
print("Student: Hello! I have 25 years and I want to practice my English.\n")
response = chat(
    user_id="1",
    session_id="test-chat-1",
    message="Hello! I have 25 years and I want to practice my English.",
    level="beginner"
)
print(f"Agent: {response}\n")

# Second message — same session_id, agent should remember context
print("---\nStudent: Yesterday I go to the park with my friends.\n")
response = chat(
    user_id="1",
    session_id="test-chat-1",
    message="Yesterday I go to the park with my friends.",
    level="beginner"
)
print(f"Agent: {response}")
