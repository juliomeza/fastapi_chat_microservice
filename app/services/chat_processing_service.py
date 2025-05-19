import re
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.openai_service import get_openai_response
from app.services.vector_store_service import get_rag_context
# Import the new LangChain Text-to-SQL function
from app.services.database_service import get_answer_from_table_via_langchain
from typing import Optional, Any  # Add Optional and Any imports

async def process_chat_message(db: AsyncSession, message: str, user_id: str) -> tuple[str, Optional[Any]]:
    """
    Usa RAG como primera y principal opción para responder preguntas.
    Preprocesa la pregunta para mapear alias de warehouse, días y semanas.
    Si la pregunta parece ser para la tabla 'data_orders', usa LangChain Text-to-SQL.
    Devuelve la respuesta en lenguaje natural y, opcionalmente, datos JSON.
    """
    # Alias de warehouse conocidos (debe coincidir con los usados en la ingestión)
    warehouse_aliases = {
        "(WH: 10) - Boca Raton (951)  - FL": ["warehouse 10", "boca", "boca raton", "951", "florida", "boca warehouse", "boca raton warehouse", "warehouse boca", "warehouse 951", "warehouse de boca", "warehouse del 951", "warehouse de florida"],
        # Agrega aquí otros warehouses si existen
    }
    # Mapeo inverso alias -> warehouse
    alias_to_warehouse = {}
    for wh, aliases in warehouse_aliases.items():
        for alias in aliases:
            alias_to_warehouse[alias.lower()] = wh
    # Días de la semana
    day_map = {
        "lunes": "day1_value", "monday": "day1_value",
        "martes": "day2_value", "tuesday": "day2_value",
        "miércoles": "day3_value", "wednesday": "day3_value",
        "jueves": "day4_value", "thursday": "day4_value",
        "viernes": "day5_value", "friday": "day5_value",
        "sábado": "day6_value", "saturday": "day6_value",
        "domingo": "day7_value", "sunday": "day7_value",
    }
    # Mapeo de sinónimos de columnas para queries más flexibles
    column_synonyms = {
        "order type": "order or shipment class type",
        "type": "order or shipment class type",
        "class": "order or shipment class type",
        "order class": "order or shipment class type",
        "shipment class": "order or shipment class type",
        # Puedes agregar más sinónimos aquí
    }

    # Normaliza la pregunta reemplazando sinónimos por el nombre real de la columna
    normalized_message = message
    for synonym, real_col in column_synonyms.items():
        # Solo reemplaza si el sinónimo aparece como palabra completa
        normalized_message = re.sub(rf"\\b{re.escape(synonym)}\\b", real_col, normalized_message, flags=re.IGNORECASE)

    # Detectar warehouse por alias en la pregunta
    warehouse_detected = None
    for alias, wh in alias_to_warehouse.items():
        if re.search(rf"\\b{re.escape(alias)}\\b", normalized_message, re.IGNORECASE):
            warehouse_detected = wh
            break
    # Detectar día de la semana
    day_detected = None
    for day_word, day_col in day_map.items():
        if re.search(rf"\\b{day_word}\\b", normalized_message, re.IGNORECASE):
            day_detected = day_col
            break
    # Detectar semana del año (ej: semana 20, week 20)
    week_detected = None
    year_detected = None
    week_match = re.search(r"semana[\s:-]*(\d{1,2})", normalized_message, re.IGNORECASE) or re.search(r"week[\s:-]*(\d{1,2})", normalized_message, re.IGNORECASE)
    if week_match:
        week_detected = int(week_match.group(1))
        # Buscar año si está presente
        year_match = re.search(r"(\d{4})", normalized_message)
        if year_match:
            year_detected = int(year_match.group(1))

    # Check if the question is likely for data_orders table
    # Keywords that might indicate a query for data_orders
    data_orders_keywords = [
        "order", "órdenes", "pedido", "pedidos", "inbound", "outbound", 
        "total de órdenes", "número de órdenes", "cuántas órdenes"
    ]
    is_for_data_orders = any(keyword in normalized_message.lower() for keyword in data_orders_keywords)

    if is_for_data_orders:
        # Use LangChain Text-to-SQL for data_orders
        # We pass the db session and the message
        # Returns natural language answer and json_data
        nl_answer, json_data = await get_answer_from_table_via_langchain(db_session=db, question=normalized_message, table_name="data_orders")
        return nl_answer, json_data

    # Si se detecta una tabla, filtra el RAG por esa tabla
    table = None
    if re.search(r'\btest|testing\b', normalized_message, re.IGNORECASE):
        table = "data_testdata"
    elif re.search(r'\bdata ?card|datacard|dashboard|reporte|report|estadistica|section|day[1-7]_value\b', normalized_message, re.IGNORECASE):
        table = "data_datacardreport"
    # Si se detecta una tabla, filtra el RAG por esa tabla y aplica filtros adicionales
    if table == "data_datacardreport":
        rag_filter = {"source_table": table}
        if warehouse_detected:
            rag_filter["warehouse_order"] = warehouse_detected
        if week_detected:
            rag_filter["week"] = week_detected
        if year_detected:
            rag_filter["year"] = year_detected
        rag_context = await get_rag_context(query=normalized_message, k=3, filter=rag_filter)
        if rag_context and "No relevant documents found" not in rag_context:
            extra_note = "Nota: day1_value=Lunes/Monday, day2_value=Martes/Tuesday, ... day7_value=Domingo/Sunday. Puedes preguntar usando alias de warehouse como 'Boca', '951', 'Florida', etc. Ejemplo: 'ORDERS SHIPPED del warehouse 10 de la semana 15 del 2025'."
            rag_prompt = f"Basado en el siguiente contexto de la tabla '{table}':\n{extra_note}\nContexto:\n{rag_context}\n---\nPregunta del usuario: {normalized_message}\n---\nResponde de forma concisa solo usando el contexto. Si el contexto no contiene la respuesta, dilo explícitamente."
            return await get_openai_response(message=rag_prompt, project_context=f"rag_for_{table}"), None
        else:
            return "No hay información relevante en la base de datos permitida para tu consulta.", None
    
    rag_context = await get_rag_context(query=normalized_message)
    if rag_context and "No relevant documents found" not in rag_context:
        rag_prompt = f"Based on the following context:\nContext:\n{rag_context}\n---\nUser query: {normalized_message}\n---\nProvide a concise answer based *only* on the provided context. If the context does not contain the answer, say so.\n"
        return await get_openai_response(message=rag_prompt), None
    else:
        return "No hay información relevante en la base de datos permitida para tu consulta.", None
