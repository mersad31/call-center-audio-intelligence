from openai import AsyncOpenAI
import json
from app.config import settings


class LLMError(Exception):
    pass


client = AsyncOpenAI(
    base_url=settings.gapgpt_base_url,
    api_key=settings.gapgpt_api_key,
    timeout=settings.llm_timeout,
    max_retries=settings.llm_max_retries,
)


def clean_json_text(text: str) -> str:
    text = text.strip()

    if text.startswith("```json"):
            text = text.removeprefix("```json").strip()
    elif text.startswith("```"):
            text = text.removeprefix("```").strip()

    if text.endswith("```"):
            text = text.removesuffix("```").strip()

    return text


async def call_gemini(prompt: str) -> dict:
    try:
        response = await client.chat.completions.create(
        model=settings.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=settings.temperature,
        )

        content = response.choices[0].message.content or ""
        content = clean_json_text(content)

        try:
            return json.loads(content)

        except json.JSONDecodeError as e:
            raise LLMError(f"MODEL_RETURNED_INVALID_JSON: {content}") from e

    except Exception as e:
        raise LLMError(str(e))


