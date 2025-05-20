import re
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.openai_service import get_openai_response
from app.services.vector_store_service import get_rag_context
# Import the new LangChain Text-to-SQL function
from app.services.database_service import get_answer_from_table_via_langchain
from typing import Optional, Any  # Add Optional and Any imports

async def process_chat_message(db: AsyncSession, message: str, user_id: str) -> tuple[str, Optional[Any]]:
    """
    Uses RAG as the first and main option to answer questions.
    Preprocesses the question to map warehouse aliases, days, and weeks.
    If the question appears to be for the 'data_orders' table, uses LangChain Text-to-SQL.
    Returns the answer in natural language and, optionally, JSON data.
    """
    # Known warehouse aliases (must match those used in ingestion)
    warehouse_aliases = {
        "(WH: 10) - Boca Raton (951)  - FL": ["warehouse 10", "boca", "boca raton", "951", "florida", "boca warehouse", "boca raton warehouse", "warehouse boca", "warehouse 951", "warehouse de boca", "warehouse del 951", "warehouse de florida"],
        # Add other warehouses here if they exist
    }
    # Reverse mapping alias -> warehouse
    alias_to_warehouse = {}
    for wh, aliases in warehouse_aliases.items():
        for alias in aliases:
            alias_to_warehouse[alias.lower()] = wh
    # Mapping of column synonyms for more flexible queries
    column_synonyms = {
        "order type": "order or shipment class type",
        "type": "order or shipment class type",
        "class": "order or shipment class type",
        "order class": "order or shipment class type",
        "shipment class": "order or shipment class type",
        # Add more synonyms here if needed
    }

    # Normalize the question by replacing synonyms with the real column name
    normalized_message = message
    for synonym, real_col in column_synonyms.items():
        # Only replace if the synonym appears as a whole word
        normalized_message = re.sub(rf"\\b{re.escape(synonym)}\\b", real_col, normalized_message, flags=re.IGNORECASE)

    # Detect warehouse by alias in the question
    warehouse_detected = None
    for alias, wh in alias_to_warehouse.items():
        if re.search(rf"\\b{re.escape(alias)}\\b", normalized_message, re.IGNORECASE):
            warehouse_detected = wh
            break
    # Detect week of the year (e.g., week 20)
    week_detected = None
    year_detected = None
    week_match = re.search(r"semana[\\s:-]*(\\d{1,2})", normalized_message, re.IGNORECASE) or re.search(r"week[\\s:-]*(\\d{1,2})", normalized_message, re.IGNORECASE)
    if week_match:
        week_detected = int(week_match.group(1))
        # Look for year if present
        year_match = re.search(r"(\\d{4})", normalized_message)
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

    # If a table is detected, filter the RAG by that table
    table = None
    if re.search(r'\btest|testing\b', normalized_message, re.IGNORECASE):
        table = "data_testdata"
    elif re.search(r'\bdata ?card|datacard|dashboard|reporte|report|estadistica|section|day[1-7]_value\b', normalized_message, re.IGNORECASE):
        table = "data_datacardreport"
    # If a table is detected, filter the RAG by that table and apply additional filters
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
            extra_note = "Note: day1_value=Monday, day2_value=Tuesday, ... day7_value=Sunday. You can ask using warehouse aliases like 'Boca', '951', 'Florida', etc. Example: 'ORDERS SHIPPED from warehouse 10 for week 15 of 2025'."
            rag_prompt = f"Based on the following context from table '{table}':\n{extra_note}\nContext:\n{rag_context}\n---\nUser question: {normalized_message}\n---\nRespond concisely using only the context. If the context does not contain the answer, say so explicitly."
            return await get_openai_response(message=rag_prompt, project_context=f"rag_for_{table}"), None
        else:
            return "No relevant information found in the allowed database for your query.", None
    
    rag_context = await get_rag_context(query=normalized_message)
    if rag_context and "No relevant documents found" not in rag_context:
        rag_prompt = f"Based on the following context:\nContext:\n{rag_context}\n---\nUser query: {normalized_message}\n---\nProvide a concise answer based *only* on the provided context. If the context does not contain the answer, say so.\n"
        return await get_openai_response(message=rag_prompt), None
    else:
        return "No relevant information found in the allowed database for your query.", None
