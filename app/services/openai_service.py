from openai import AsyncOpenAI
from app.core.config import settings
from typing import Optional

async def get_openai_response(message: str, project_context: Optional[str] = None) -> str:
    """
    Gets a response from the OpenAI API.
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_api_key":
        return "OpenAI API Key not configured. Cannot process the generic question."

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        prompt_message = message  # No longer using project_context
        
        completion = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions."},
                {"role": "user", "content": prompt_message}
            ]
        )
        if completion.choices and len(completion.choices) > 0 and completion.choices[0].message:
            return completion.choices[0].message.content.strip()
        else:
            return "No valid response received from OpenAI."
            
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return f"Error contacting OpenAI: {e}"
