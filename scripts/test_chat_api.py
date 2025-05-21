import requests
import os
import sys
import argparse
from dotenv import load_dotenv

# Argument parser for --show-all
parser = argparse.ArgumentParser(description="Test chat API and summarize results.")
parser.add_argument('env', nargs='?', default='dev', help='Environment: dev or prod')
parser.add_argument('--show-all', action='store_true', help='Show all questions and responses, not just failures')
args = parser.parse_args()

ENV = args.env
if ENV == "prod":
    API_URL = "https://fastapi-chat-microservice.onrender.com/api/v1/chat/"
else:
    API_URL = "http://localhost:8080/api/v1/chat/"

USER_ID = "test_user"  # Change if necessary

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv("TEST_JWT_TOKEN", "YOUR_JWT_TOKEN_HERE")

# Get the absolute path of the test_questions.txt file (always from the project root)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
QUESTIONS_FILE = os.path.join(BASE_DIR, "test_questions.txt")

with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
    questions = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

results = []
total = len(questions)

for idx, question in enumerate(questions, 1):
    payload = {
        "message": question,  # Changed from 'mensaje' to 'message'
        "user_id": USER_ID    # Changed from 'usuario_id' to 'user_id'
    }
    response = requests.post(API_URL, json=payload, headers=headers)
    try:
        resp_json = response.json()
    except Exception:
        resp_json = {"answer": "Response is not JSON", "json_data": None}
    failed = resp_json.get('json_data') is None
    results.append({
        'idx': idx,
        'question': question,
        'status': response.status_code,
        'response': resp_json,
        'failed': failed
    })
    # Show progress and result immediately
    print(f"Question {idx}/{total}: {question}")
    print(f"Result: {'FAIL' if failed else 'PASS'}\n")

# Print summary
passed = sum(1 for r in results if not r['failed'])
total = len(results)
print(f"\nPassed: {passed}/{total}")

if any(r['failed'] for r in results):
    print("\nFailed questions:")
    for r in results:
        if r['failed']:
            print(f"\nQuestion {r['idx']}: {r['question']}")
            print(f"Status: {r['status']}")
            print(f"Response: {r['response']}")

if args.show_all:
    print("\nAll questions and responses:")
    for r in results:
        print(f"\nQuestion {r['idx']}: {r['question']}")
        print(f"Status: {r['status']}")
        print(f"Response: {r['response']}")
        print(f"Result: {'FAIL' if r['failed'] else 'PASS'}")
