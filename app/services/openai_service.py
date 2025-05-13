from openai import AsyncOpenAI
from app.core.config import settings
from typing import Optional

async def get_openai_response(message: str, project_context: Optional[str] = None) -> str:
    """
    Gets a response from OpenAI API.
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_api_key":
        return "OpenAI API Key no configurada. No se puede procesar la pregunta genérica."

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        prompt_message = f"Proyecto: {project_context}\n\nUsuario: {message}\n\nRespuesta:" if project_context else message
        
        completion = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un asistente útil que responde preguntas. Si la pregunta es sobre un proyecto específico, considera ese contexto."},
                {"role": "user", "content": prompt_message}
            ]
        )
        if completion.choices and len(completion.choices) > 0 and completion.choices[0].message:
            return completion.choices[0].message.content.strip()
        else:
            return "No se recibió una respuesta válida de OpenAI."
            
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return f"Error al contactar OpenAI: {e}"
