import jwt
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Use the same secret and algorithm as in your .env file
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# Set expiration to 24 hours from now
exp = int(time.time()) + 24 * 3600
payload = {
    "token_type": "access",
    "exp": exp,
    "iat": int(time.time()),
    "jti": "test-jti-001",
    "user_id": 41
}

token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
print(token)
