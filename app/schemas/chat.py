from pydantic import BaseModel
from typing import Optional, Any

class ChatRequest(BaseModel):
    message: str
    user_id: str

class ChatResponse(BaseModel):
    answer: str
    user_id: str
    json_data: Optional[Any] = None
