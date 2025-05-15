import re
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.openai_service import get_openai_response
from app.services.vector_store_service import get_rag_context

async def process_chat_message(db: AsyncSession, message: str, user_id: str, project: str) -> str:
    """
    Usa RAG como primera y principal opción para responder preguntas.
    """
    # Detecta si la pregunta es sobre data_testdata o data_datacardreport
    table = None
    if re.search(r'\btest|testing\b', message, re.IGNORECASE):
        table = "data_testdata"
    elif re.search(r'\bdata ?card|datacard|dashboard|reporte|report|estadistica|section|day[1-7]_value\b', message, re.IGNORECASE):
        table = "data_datacardreport"

    # Si se detecta una tabla, filtra el RAG por esa tabla
    if table:
        rag_context = await get_rag_context(query=message, project=None, k=3, filter={"source_table": table})
        if rag_context and "No relevant documents found" not in rag_context:
            rag_prompt = f"""Basado en el siguiente contexto de la tabla '{table}':\nNota: day1_value=Lunes, day2_value=Martes, ... day7_value=Domingo.\nContexto:\n{rag_context}\n---\nPregunta del usuario: {message}\n---\nResponde de forma concisa solo usando el contexto. Si el contexto no contiene la respuesta, dilo explícitamente."""
            return await get_openai_response(message=rag_prompt, project_context=f"rag_for_{table}")
        else:
            return "No hay información relevante en la base de datos permitida para tu consulta."

    # Si no se detecta tabla, busca en todo el vector store (por proyecto si aplica)
    rag_context = await get_rag_context(query=message, project=project)
    if rag_context and "No relevant documents found" not in rag_context:
        # Solo menciona el proyecto si project no es None
        if project:
            rag_prompt = f"""Based on the following context from project '{project}':\nContext:\n{rag_context}\n---\nUser query: {message}\n---\nProvide a concise answer based *only* on the provided context. If the context does not contain the answer, say so.\n"""
        else:
            rag_prompt = f"""Based on the following context:\nContext:\n{rag_context}\n---\nUser query: {message}\n---\nProvide a concise answer based *only* on the provided context. If the context does not contain the answer, say so.\n"""
        return await get_openai_response(message=rag_prompt, project_context=f"rag_for_{project}" if project else None)
    else:
        return "No hay información relevante en la base de datos permitida para tu consulta."
