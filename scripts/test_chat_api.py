import requests
import os
import sys
from dotenv import load_dotenv

# Determine environment (dev or prod) from command line argument
ENV = sys.argv[1] if len(sys.argv) > 1 else "dev"
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

for idx, question in enumerate(questions, 1):
    payload = {
        "message": question,  # Changed from 'mensaje' to 'message'
        "user_id": USER_ID    # Changed from 'usuario_id' to 'user_id'
    }
    response = requests.post(API_URL, json=payload, headers=headers)
    print(f"\nQuestion {idx}: {question}")
    print(f"Status: {response.status_code}")
    try:
        print("Response:", response.json())
    except Exception:
        print("Response is not JSON:", response.text)
