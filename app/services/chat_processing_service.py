import re
from typing import Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database_service import get_answer_from_table_via_langchain
from app.services.vector_store_service import get_rag_context # Assuming this is still needed for specific cases

async def process_chat_message(db: AsyncSession, message: str, user_id: str) -> Tuple[str, Optional[Any]]:
    """
    Processes a user's chat message.
    1. Checks if the question is about a specific order or shipment number.
       If so, uses RAG to fetch details for that specific entity.
    2. Otherwise, attempts to answer the question using LangChain Text-to-SQL against the 'data_orders' table.
    3. If LangChain cannot answer or an error occurs, a fallback message is provided.
    Returns a natural language answer and optional JSON data.
    """
    normalized_message = message.lower() # Normalize for easier matching

    # Regex to find order_number or shipment_number patterns
    # This pattern looks for common prefixes like "order", "shipment", "orden", "pedido"
    # followed by a colon or space, and then the number/code itself (alphanumeric, hyphens, underscores).
    # It also tries to capture numbers/codes that might be mentioned without explicit prefixes if they look like typical IDs.
    order_shipment_pattern = re.compile(
        r"(?:order number\b|order\b|shipment number\b|shipment\b|orden\b|pedido\b|embarque\b)[\s:]*([a-z0-9-_/]+)|\b([a-z0-9-_/]{5,})\b", 
        re.IGNORECASE
    )
    
    match = order_shipment_pattern.search(normalized_message)
    specific_identifier_found = None

    if match:
        # Prioritize the explicitly prefixed group if found
        # Only consider group 1 (explicitly prefixed identifiers) for the RAG path.
        # Group 2 (standalone alphanumeric sequences) was too general and incorrectly captured common words.
        specific_identifier_found = match.group(1)

    if specific_identifier_found:
        # If a specific order/shipment ID is found, use RAG to get its details.
        # The RAG context should be filtered for the specific order/shipment number.
        # We assume `get_rag_context` can handle a filter for `order_number` or `shipment_number`.
        # This part needs to be adapted based on how your vector store is structured and how `get_rag_context` works.
        
        # Construct a query that is specific to the identifier found.
        rag_query = f"Details for order or shipment: {specific_identifier_found}"
        
        # Example filter: (This needs to match the metadata fields in your vector store)
        # We will try to match the identifier against both order_number and shipment_number fields.
        # This assumes your vector store documents have fields like 'order_number' and 'shipment_number'.
        rag_filter = {
            "$or": [
                {"order_number": specific_identifier_found},
                {"shipment_number": specific_identifier_found}
            ]
        }
        
        try:
            # Using k=1 because we are looking for a very specific document.
            rag_context_str = await get_rag_context(query=rag_query, k=1, filter=rag_filter)

            if rag_context_str and "No relevant documents found" not in rag_context_str:
                # If RAG provides context, format it as an answer.
                # For now, we return the direct RAG context. You might want to process this further.
                # Also, RAG typically returns text; creating structured JSON from it might require additional parsing or LLM calls.
                # For simplicity, we'll return the text and no specific JSON for RAG results here.
                return f"Details for {specific_identifier_found}:\n{rag_context_str}", None
            else:
                # If RAG doesn't find it, we can still try Langchain or inform the user.
                # For now, let's inform the user and not proceed to Langchain for this specific ID case.
                return f"I couldn't find specific details for order/shipment '{specific_identifier_found}'. If this is not an ID, please ask your question more generally.", None
        except Exception as e:
            print(f"Error during RAG lookup for {specific_identifier_found}: {e}")
            return "I encountered an error while looking up the specific order/shipment details. Please try again.", None

    # If no specific order/shipment ID is detected, or RAG failed to find it and we decide to proceed:
    # Use LangChain Text-to-SQL for the 'data_orders' table.
    try:
        nl_answer, json_data = await get_answer_from_table_via_langchain(
            db_session=db, 
            question=message,  # Use original message for Langchain for better context
            table_name="data_orders"
        )
        
        # If nl_answer is empty or indicates no data, provide a helpful response.
        if not nl_answer or "could not find" in nl_answer.lower() or "don't know" in nl_answer.lower():
            return "I couldn't find the information in the 'data_orders' table. We are still under development for accessing other data sources.", json_data
            
        return nl_answer, json_data
    
    except Exception as e:
        print(f"Error in LangChain processing: {e}")
        # Fallback message if LangChain fails
        return "I am having trouble accessing the database at the moment. We are still under development for some information requests. Please try again later or ask a different question.", None
