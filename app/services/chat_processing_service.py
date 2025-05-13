import re
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database_service import query_database
from app.services.openai_service import get_openai_response

async def process_chat_message(db: AsyncSession, message: str, user_id: str, project: str) -> str:
    """
    Decides whether to query the database or call OpenAI based on the message content.
    """
    if re.search(r'\b(order|orders|órden|órdenes)\b', message, re.IGNORECASE):
        return await query_database(db=db, query_type="order_status", message=message, project_project_name=project, user_id=user_id)
    elif re.search(r'\b(cliente|clientes)\b', message, re.IGNORECASE):
        return await query_database(db=db, query_type="customer_info", message=message, project_project_name=project, user_id=user_id)
    else:
        return await get_openai_response(message=message, project_context=project)
