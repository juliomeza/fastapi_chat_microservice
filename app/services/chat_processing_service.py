import re
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database_service import query_database
from app.services.openai_service import get_openai_response

async def process_chat_message(db: AsyncSession, message: str, user_id: str, project: str) -> str:
    """
    Decides whether to query the database or call OpenAI based on the message content.
    """
    # Detectar consultas relacionadas con órdenes y su estado
    if (re.search(r'\b(order|orders|órden|órdenes|orden|ordenes|pedido|pedidos)\b', message, re.IGNORECASE) or 
        re.search(r'\b(status|estado|estados)\b', message, re.IGNORECASE) or
        (re.search(r'\bcuant[oa]s\b', message, re.IGNORECASE) and 
         re.search(r'\b(pendiente|completada|cancelada|pending|completed|canceled)\b', message, re.IGNORECASE))):
        return await query_database(db=db, query_type="order_status", message=message, project_project_name=project, user_id=user_id)
    
    # Detectar consultas sobre clientes
    elif re.search(r'\b(cliente|clientes|customer|customers)\b', message, re.IGNORECASE):
        return await query_database(db=db, query_type="customer_info", message=message, project_project_name=project, user_id=user_id)
    
    # Detectar consultas sobre reportes, dashboards, estadísticas
    elif re.search(r'\b(reporte|reportes|report|reports|datacardreport|data card|datacard|dashboard|estadísticas|estadistica|datos|data|resumen)\b', message, re.IGNORECASE):
        return await query_database(db=db, query_type="data_card_report", message=message, project_project_name=project, user_id=user_id)
    
    # Detectar consultas sobre el esquema de la base de datos o estructura de tablas
    elif re.search(r'\b(tabla|tablas|table|tables|esquema|schema|columna|columnas|column|columns|estructura|structure)\b', message, re.IGNORECASE):
        return await query_database(db=db, query_type="schema_info", message=message, project_project_name=project, user_id=user_id)
    
    # Si la consulta no coincide con ninguna de las anteriores, enviarla a OpenAI
    else:
        return await get_openai_response(message=message, project_context=project)
