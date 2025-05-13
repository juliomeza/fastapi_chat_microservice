from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # Dummy tokenUrl

class TokenData(BaseModel):
    username: Optional[str] = None

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        username: Optional[str] = payload.get("user_id") # Adjust if Django uses a different key e.g. "sub"
        if username is None:
            username = payload.get("sub")
            if username is None:
                raise credentials_exception
        
        if "exp" in payload:
            expiration_timestamp = payload.get("exp")
            if datetime.fromtimestamp(expiration_timestamp, timezone.utc) < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        # token_data = TokenData(username=str(username)) # Not strictly needed if returning payload
    except JWTError as e:
        print(f"JWTError: {e}")
        raise credentials_exception
    
    return payload # Return the whole payload for flexibility
