from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    mensaje: str
    usuario_id: str 
    proyecto: str

class ChatResponse(BaseModel):
    respuesta: str
    usuario_id: str
    proyecto: str
