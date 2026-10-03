import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, List, Optional, Type, TypeVar

from pydantic import BaseModel

from tolmol.config import settings
from tolmol.errors import ProviderError
from tolmol.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


@lru_cache
def gemini_client():
    if not settings.GOOGLE_API_KEY:
        raise ProviderError("GOOGLE_API_KEY (or GEMINI_API_KEY) is not set.")
    from google import genai

    return genai.Client(api_key=settings.GOOGLE_API_KEY)


@lru_cache
def hf_client():
    if not settings.HUGGINGFACE_API_TOKEN:
        raise ProviderError("HUGGINGFACE_API_TOKEN (or HF_TOKEN) is not set.")
    from huggingface_hub import InferenceClient

    return InferenceClient(token=settings.HUGGINGFACE_API_TOKEN)


def _config(**kwargs):
    from google.genai import types

    return types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        **kwargs,
    )


def _call(model: str, contents: Any, config) -> Any:
    try:
        return gemini_client().models.generate_content(model=model, contents=contents, config=config)
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError(f"Gemini request failed: {exc}") from exc


def generate_text(prompt: str, system: Optional[str] = None, max_tokens: int = 700, temperature: float = 0.3) -> str:
    """Writes prose with the configured LLM_PROVIDER (Gemini, or LLaMA-3 on Hugging Face)."""
    if settings.LLM_PROVIDER.lower() == "huggingface":
        messages = [{"role": "user", "content": prompt}]
        if system:
            messages.insert(0, {"role": "system", "content": system})
        try:
            response = hf_client().chat_completion(
                messages=messages, model=settings.HF_CHAT_MODEL, max_tokens=max_tokens, temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Hugging Face request failed: {exc}") from exc

    response = _call(
        settings.GEMINI_CHAT_MODEL,
        prompt,
        _config(system_instruction=system, max_output_tokens=max_tokens, temperature=temperature),
    )
    if not response.text:
        raise ProviderError("Gemini returned an empty response.")
    return response.text.strip()


def generate_structured(prompt: str, schema: Type[T], contents: Any = None) -> T:
    """Gemini structured output: the response is validated against a Pydantic schema."""
    response = _call(
        settings.GEMINI_CHAT_MODEL,
        contents if contents is not None else prompt,
        _config(response_mime_type="application/json", response_schema=schema, temperature=0),
    )
    if isinstance(response.parsed, schema):
        return response.parsed
    try:
        return schema.model_validate_json(response.text or "")
    except Exception as exc:
        raise ProviderError(f"Gemini returned malformed JSON: {exc}") from exc


def generate_structured_from_image(prompt: str, image: bytes, mime_type: str, schema: Type[T]) -> T:
    from google.genai import types

    return generate_structured(prompt, schema, contents=[types.Part.from_bytes(data=image, mime_type=mime_type), prompt])


@dataclass
class GroundedResult:
    text: str
    sources: List[dict] = field(default_factory=list)  # [{"title": ..., "url": ...}]


def grounded_search(prompt: str, max_tokens: int = 4000) -> GroundedResult:
    """Gemini answering with Google Search grounding, so facts come from current web pages."""
    from google.genai import types

    response = _call(
        settings.GEMINI_SEARCH_MODEL,
        prompt,
        _config(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0, max_output_tokens=max_tokens),
    )
    sources = []
    candidate = (response.candidates or [None])[0]
    metadata = getattr(candidate, "grounding_metadata", None)
    for chunk in getattr(metadata, "grounding_chunks", None) or []:
        web = getattr(chunk, "web", None)
        if web and web.uri:
            sources.append({"title": web.title or "", "url": web.uri})
    return GroundedResult(text=response.text or "", sources=sources)


def extract_json(text: str) -> Any:
    """Pulls the first JSON object or array out of an LLM reply (tolerates ```json fences and prose)."""
    cleaned = re.sub(r"```(?:json)?", "", text)
    # Start from whichever bracket comes first, so an object containing an array isn't cut down to the array.
    pairs = sorted((("[", "]"), ("{", "}")), key=lambda pair: (cleaned.find(pair[0]) == -1, cleaned.find(pair[0])))
    for opener, closer in pairs:
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ProviderError("No JSON found in the model's reply.")
