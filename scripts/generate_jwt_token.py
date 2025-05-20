import jwt
import time

# Use the same secret and algorithm as in your .env file
SECRET_KEY = "-4n-21b4lk%kqol1grj-=@rvm)$r$c5uobgyh^_!5vn5fedy1h # Generate a strong key!"
ALGORITHM = "HS256"

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
