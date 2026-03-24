#!/bin/bash
# Test script for the LinguaAgent API Gateway
# Requires: API running on localhost:8000

BASE_URL="http://localhost:8000"
GREEN='\033[92m'
CYAN='\033[96m'
YELLOW='\033[93m'
RED='\033[91m'
RESET='\033[0m'

echo -e "${CYAN}=== LinguaAgent API Tests ===${RESET}\n"

# 1. Health check
echo -e "${YELLOW}[1/5] Health check${RESET}"
curl -s $BASE_URL/health | python3 -m json.tool
echo ""

# 2. Generate test token
echo -e "${YELLOW}[2/5] Generating test token (user_id=1, level=beginner)${RESET}"
TOKEN_RESPONSE=$(curl -s $BASE_URL/dev/token/1?level=beginner)
echo $TOKEN_RESPONSE | python3 -m json.tool
TOKEN=$(echo $TOKEN_RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo -e "${GREEN}Token: $TOKEN${RESET}\n"

# 3. Chat endpoint
echo -e "${YELLOW}[3/5] POST /api/chat${RESET}"
echo -e "${CYAN}Sending: 'Hello! I have 25 years and I want to practice English.'${RESET}"
curl -s -X POST $BASE_URL/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "api-test-1", "message": "Hello! I have 25 years and I want to practice English."}' \
  | python3 -m json.tool
echo ""

# 4. Pending tasks
echo -e "${YELLOW}[4/5] GET /api/tasks${RESET}"
curl -s $BASE_URL/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
echo ""

# 5. Update level
echo -e "${YELLOW}[5/5] POST /api/level/1${RESET}"
curl -s -X POST $BASE_URL/api/level/1 \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
echo ""

echo -e "${GREEN}=== All tests complete ===${RESET}"
