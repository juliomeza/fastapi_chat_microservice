from pydantic import BaseModel
from typing import Optional, Any # Import Any

class ChatRequest(BaseModel):
    mensaje: str
    usuario_id: str 

class ChatResponse(BaseModel):
    respuesta: str
    usuario_id: str
    json_data: Optional[Any] = None # Add json_data field
