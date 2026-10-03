from functools import lru_cache
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from core.config import settings
from core.exceptions import LLMGenerationError
from core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


@lru_cache
def gemini_client():
    if not settings.GOOGLE_API_KEY:
        raise LLMGenerationError("GOOGLE_API_KEY (or GEMINI_API_KEY) is not set.")
    from google import genai

    return genai.Client(api_key=settings.GOOGLE_API_KEY)


@lru_cache
def hf_client():
    if not settings.HUGGINGFACE_API_TOKEN:
        raise LLMGenerationError("HUGGINGFACE_API_TOKEN (or HF_TOKEN) is not set.")
    from huggingface_hub import InferenceClient

    return InferenceClient(token=settings.HUGGINGFACE_API_TOKEN)


def gemini_available() -> bool:
    return bool(settings.GOOGLE_API_KEY)


def generate_text(prompt: str, system: Optional[str] = None, max_tokens: int = 600, temperature: float = 0.2) -> str:
    """Generates text with the configured LLM_PROVIDER (Gemini or LLaMA-3 on Hugging Face)."""
    provider = settings.LLM_PROVIDER.lower()
    try:
        if provider == "huggingface":
            messages = [{"role": "user", "content": prompt}]
            if system:
                messages.insert(0, {"role": "system", "content": system})
            response = hf_client().chat_completion(
                messages=messages, model=settings.HF_CHAT_MODEL, max_tokens=max_tokens, temperature=temperature
            )
            return response.choices[0].message.content.strip()

        from google.genai import types

        response = gemini_client().models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        if not response.text:
            raise LLMGenerationError("Gemini returned an empty response.")
        return response.text.strip()
    except LLMGenerationError:
        raise
    except Exception as exc:
        raise LLMGenerationError(f"{provider} generation failed: {exc}") from exc


def generate_structured(prompt: str, schema: Type[T]) -> T:
    """Asks Gemini for JSON that matches a Pydantic schema (structured output)."""
    from google.genai import types

    try:
        response = gemini_client().models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        if isinstance(response.parsed, schema):
            return response.parsed
        return schema.model_validate_json(response.text or "")
    except LLMGenerationError:
        raise
    except Exception as exc:
        raise LLMGenerationError(f"Structured generation failed: {exc}") from exc
