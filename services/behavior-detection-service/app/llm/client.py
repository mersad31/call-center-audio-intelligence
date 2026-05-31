# app/llm/client.py
import json
import logging
from typing import Any, Dict, Optional

import httpx
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.errors import ErrorCode
from app.domain.enums import BehaviorLabel

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM client using GAPGPT OpenAI-compatible API.
    Backend model can be Gemini or any other compatible model.
    """

    def __init__(self) -> None:
        self.base_url = settings.GAPGPT_BASE_URL.rstrip("/")
        self.primary_model = settings.LLM_PRIMARY_MODEL
        self.fallback_model = settings.LLM_FALLBACK_MODEL

        self._http_client = httpx.AsyncClient(
            timeout=settings.LLM_TIMEOUT_SECONDS,
            event_hooks={
                "request": [self._log_request],
                "response": [self._log_response],
            },
        )

        self.client = AsyncOpenAI(
            api_key=settings.GAPGPT_API_KEY,
            base_url=self.base_url,
            http_client=self._http_client,
        )

        logger.info(
            "LLMClient initialized",
            extra={
                "base_url": self.base_url,
                "primary_model": self.primary_model,
                "fallback_model": self.fallback_model,
            },
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def detect(
        self,
        prompt: str,
        request_id: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if model_name:
            return await self._call_llm(
                prompt=prompt,
                model=model_name,
                request_id=request_id,
            )

        last_exc: Optional[Exception] = None

        for model in [self.primary_model, self.fallback_model]:
            if not model:
                continue
            try:
                return await self._call_llm(
                    prompt=prompt,
                    model=model,
                    request_id=request_id,
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "LLM call failed, trying next model if available",
                    extra={
                        "request_id": request_id,
                        "model": model,
                        "error": str(exc),
                    },
                )

        raise RuntimeError(
            f"{ErrorCode.LLM_CALL_FAILED}: all configured models failed"
        ) from last_exc

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    async def _call_llm(
        self,
        prompt: str,
        model: str,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info(
            "Sending request to LLM",
            extra={
                "request_id": request_id,
                "model": model,
            },
        )

        response = await self.client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a behavior detection assistant. "
                        "Always return a valid JSON object."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError(f"{ErrorCode.INVALID_LLM_RESPONSE}: empty content")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{ErrorCode.INVALID_LLM_RESPONSE}: response is not valid JSON"
            ) from exc

        label_value = data.get("label")
        if label_value is None:
            raise RuntimeError(
                f"{ErrorCode.INVALID_LLM_RESPONSE}: missing label in response"
            )

        try:
            label = BehaviorLabel(label_value)
        except ValueError as exc:
            raise RuntimeError(
                f"{ErrorCode.INVALID_LLM_RESPONSE}: invalid label '{label_value}'"
            ) from exc

        result: Dict[str, Any] = {
            "label": label,
            "raw_response": data,
            "model": model,
        }

        logger.info(
            "LLM response parsed successfully",
            extra={
                "request_id": request_id,
                "model": model,
                "label": label.value,
            },
        )

        return result

    async def _log_request(self, request: httpx.Request) -> None:
        logger.debug(
            "HTTP request sent to LLM provider",
            extra={
                "method": request.method,
                "url": str(request.url),
            },
        )

    async def _log_response(self, response: httpx.Response) -> None:
        logger.debug(
            "HTTP response received from LLM provider",
            extra={
                "status_code": response.status_code,
                "url": str(response.request.url),
            },
        )
