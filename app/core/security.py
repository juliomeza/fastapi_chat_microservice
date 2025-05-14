from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

api_key_scheme = APIKeyHeader(name="Authorization", auto_error=True)

class TokenData(BaseModel):
    username: Optional[str] = None

async def get_current_user(token_header: str = Depends(api_key_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token_header or not token_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header. Must be 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = token_header.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        username: Optional[str] = payload.get("user_id")
        if username is None:
            username = payload.get("sub")
            if username is None:
                raise credentials_exception
        
        exp = payload.get("exp")
        if exp is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has no expiration date",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if datetime.fromtimestamp(exp, timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
    except JWTError as e:
        print(f"JWTError: {e}")
        raise credentials_exception
    except Exception as e:
        print(f"Generic decoding/validation error: {e}")
        raise credentials_exception
