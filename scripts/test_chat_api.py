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

USUARIO_ID = "test_user"  # Cambia si es necesario

# Cargar variables de entorno desde .env
load_dotenv()
TOKEN = os.getenv("TEST_JWT_TOKEN", "AQUI_TU_TOKEN_JWT")

# Obtener la ruta absoluta del archivo test_questions.txt (siempre desde la raíz del proyecto)
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
        "mensaje": question,
        "usuario_id": USUARIO_ID
    }
    response = requests.post(API_URL, json=payload, headers=headers)
    print(f"\nPregunta {idx}: {question}")
    print(f"Status: {response.status_code}")
    try:
        print("Respuesta:", response.json())
    except Exception:
        print("Respuesta no es JSON:", response.text)
