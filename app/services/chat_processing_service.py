import re
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database_service import query_database
from app.services.openai_service import get_openai_response
from app.services.vector_store_service import get_rag_context  # Added import

async def process_chat_message(db: AsyncSession, message: str, user_id: str, project: str) -> str:
    """
    Decides whether to query the database, use RAG, or call OpenAI based on the message content.
    """
    # Priority 1: Specific database queries based on keywords
    if (re.search(r'\b(order|orders|órden|órdenes|orden|ordenes|pedido|pedidos)\b', message, re.IGNORECASE) or
        re.search(r'\b(status|estado|estados)\b', message, re.IGNORECASE) or
        (re.search(r'\bcuant[oa]s\b', message, re.IGNORECASE) and
         re.search(r'\b(pendiente|completada|cancelada|pending|completed|canceled)\b', message, re.IGNORECASE))):
        return await query_database(db=db, query_type="order_status", message=message, project_project_name=project, user_id=user_id)

    elif re.search(r'\b(cliente|clientes|customer|customers)\b', message, re.IGNORECASE):
        return await query_database(db=db, query_type="customer_info", message=message, project_project_name=project, user_id=user_id)

    elif re.search(r'\b(reporte|reportes|report|reports|datacardreport|data card|datacard|dashboard|estadísticas|estadistica|datos|data|resumen)\b', message, re.IGNORECASE):
        return await query_database(db=db, query_type="data_card_report", message=message, project_project_name=project, user_id=user_id)

    elif re.search(r'\b(tabla|tablas|table|tables|esquema|schema|columna|columnas|column|columns|estructura|structure)\b', message, re.IGNORECASE):
        return await query_database(db=db, query_type="schema_info", message=message, project_project_name=project, user_id=user_id)

    # Priority 2: Attempt RAG for other queries, especially if project-specific
    print(f"Attempting RAG for project: {project}, message: {message}")

    # --- RAG tabla controlada ---
    # Decide a qué tabla buscar según la pregunta
    table = None
    if re.search(r'\btest|testing\b', message, re.IGNORECASE):
        table = "data_testdata"
    elif re.search(r'\bdata ?card|datacard|dashboard|reporte|report|estadistica|section|day[1-7]_value\b', message, re.IGNORECASE):
        table = "data_datacardreport"
    
    if table:
        # Solo busca en el vector store los datos de esa tabla
        rag_context = await get_rag_context(query=message, project=None, k=3, filter={"source_table": table})
        if rag_context and "No relevant documents found" not in rag_context:
            rag_prompt = f"""Basado en el siguiente contexto de la tabla '{table}':\nNota: day1_value=Lunes, day2_value=Martes, ... day7_value=Domingo.\nContexto:\n{rag_context}\n---\nPregunta del usuario: {message}\n---\nResponde de forma concisa solo usando el contexto. Si el contexto no contiene la respuesta, dilo explícitamente."""
            return await get_openai_response(message=rag_prompt, project_context=f"rag_for_{table}")
        else:
            return "No hay información relevante en la base de datos permitida para tu consulta."

    rag_context = await get_rag_context(query=message, project=project)

    if rag_context and "No relevant documents found" not in rag_context:
        print(f"RAG context found for project {project}: {rag_context[:200]}...")  # Log first 200 chars
        # Construct a new prompt for OpenAI using the RAG context
        rag_prompt = f"""Based on the following context from project '{project}':
Context:
{rag_context}
---
User query: {message}
---
Provide a concise answer based *only* on the provided context. If the context does not contain the answer, say so.
"""
        # You might want a specific OpenAI call for RAG, perhaps with different parameters
        return await get_openai_response(message=rag_prompt, project_context=f"rag_for_{project}")
    else:
        print(f"No RAG context found for project {project} or context was empty. Falling back to general OpenAI.")
        # Priority 3: Fallback to general OpenAI if RAG doesn't provide context
        # or if it's a general knowledge query.
        return await get_openai_response(message=message, project_context=project)
