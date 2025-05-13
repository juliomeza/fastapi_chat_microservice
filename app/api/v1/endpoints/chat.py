from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_processing_service import process_chat_message
from app.core.security import get_current_user
from app.db.session import get_db

router = APIRouter()

@router.post("/", response_model=ChatResponse)
async def handle_chat_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    # current_user_payload will contain the decoded JWT payload (e.g., user_id, username, exp)
    current_user_payload: dict = Depends(get_current_user) 
):
    """
    Processes a chat message.
    The message can be a query for the database or a general question for an AI model.
    """
    # Example: Accessing user_id from token (adjust key based on your Django JWT payload)
    # token_user_id = current_user_payload.get("user_id") or current_user_payload.get("sub")
    # if not token_user_id:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User identifier not found in token")
    #
    # if request.usuario_id != str(token_user_id):
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User ID in request does not match token")

    response_text = await process_chat_message(
        db=db,
        message=request.mensaje,
        user_id=request.usuario_id, # Using usuario_id from request body
        project=request.proyecto
    )
    return ChatResponse(respuesta=response_text, usuario_id=request.usuario_id, proyecto=request.proyecto)
