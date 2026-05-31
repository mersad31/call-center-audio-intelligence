import httpx
import asyncio
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin

from config import settings
from logger import get_logger
from exceptions import ServiceUnavailableError, ServiceProcessingError

logger = get_logger("clients")

DEFAULT_TIMEOUTS: Dict[str, httpx.Timeout] = {
    "Diarization": httpx.Timeout(connect=30.0, read=600.0, write=60.0, pool=60.0),
    "STT": httpx.Timeout(connect=30.0, read=900.0, write=60.0, pool=60.0),
    "RoleDetection": httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=30.0),
    "BehaviorDetection": httpx.Timeout(connect=10.0, read=120.0, write=60.0, pool=60.0),
    "SentimentAnalysis": httpx.Timeout(connect=10.0, read=300.0, write=60.0, pool=60.0),
    "OperatorScoring": httpx.Timeout(connect=10.0, read=180.0, write=60.0, pool=60.0),
    "SilenceFromSegments": httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=30.0),
}

RETRYABLE_EXCEPTIONS = (httpx.TimeoutException, httpx.TransportError)
MAX_RETRIES_BY_SERVICE: Dict[str, int] = {
    "STT": 1,
    "Diarization": 1,
    "RoleDetection": 1,
    "SentimentAnalysis": 1,
}


def _get_timeout(service_name: str, timeout: Optional[httpx.Timeout] = None) -> httpx.Timeout:
    if timeout is not None:
        return timeout
    return DEFAULT_TIMEOUTS.get(service_name, httpx.Timeout(60.0))


def _get_retries(service_name: str, retries: Optional[int] = None) -> int:
    if retries is not None:
        return retries
    return MAX_RETRIES_BY_SERVICE.get(service_name, 0)


async def _safe_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    service_name: str,
    timeout: Optional[httpx.Timeout] = None,
    retries: Optional[int] = None,
    retry_backoff_sec: float = 1.0,
    **kwargs
) -> Any:
    req_timeout = _get_timeout(service_name, timeout)
    max_retries = _get_retries(service_name, retries)

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            logger.info(
                "Sending request",
                extra={
                    "service": service_name,
                    "method": method,
                    "url": url,
                    "attempt": attempt + 1,
                    "timeout": str(req_timeout),
                },
            )

            response = await client.request(method, url, timeout=req_timeout, **kwargs)
            response.raise_for_status()

            try:
                return response.json()
            except Exception:
                raise ServiceProcessingError(
                    f"{service_name} returned non-JSON response.",
                    service_name=service_name,
                    details={"status": response.status_code, "body": response.text[:2000]},
                )

        except httpx.TimeoutException as e:
            last_exc = e
            if attempt < max_retries:
                logger.warning(
                    "Timeout, retrying request",
                    extra={
                        "service": service_name,
                        "url": url,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                    },
                )
                await asyncio.sleep(retry_backoff_sec * (attempt + 1))
                continue

            raise ServiceUnavailableError(
                f"{service_name} timed out.",
                service_name=service_name,
                details={"url": url, "timeout": str(req_timeout)},
            )

        except httpx.HTTPStatusError as e:
            raise ServiceProcessingError(
                f"{service_name} returned error.",
                service_name=service_name,
                details={
                    "status": e.response.status_code,
                    "body": e.response.text[:4000],
                    "url": str(e.request.url),
                },
            )

        except httpx.RequestError as e:
            last_exc = e
            if attempt < max_retries and isinstance(e, RETRYABLE_EXCEPTIONS):
                logger.warning(
                    "Request failed, retrying",
                    extra={
                        "service": service_name,
                        "url": url,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "error": str(e),
                    },
                )
                await asyncio.sleep(retry_backoff_sec * (attempt + 1))
                continue

            raise ServiceUnavailableError(
                f"Connection failed to {service_name}.",
                service_name=service_name,
                details={"url": url, "error": str(e)},
            )

    raise ServiceUnavailableError(
        f"{service_name} request failed.",
        service_name=service_name,
        details={"error": str(last_exc) if last_exc else "unknown"},
    )


async def fetch_diarization(
    file_bytes: bytes,
    filename: str,
    speaker_count: int = 2,
) -> dict:
    files = {"audio_file": (filename, file_bytes, "audio/wav")}
    data = {"speaker_count": str(speaker_count)}

    async with httpx.AsyncClient() as client:
        return await _safe_request(
            client,
            "POST",
            settings.diarize_url,
            "Diarization",
            files=files,
            data=data,
        )


def normalize_segments_for_role(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "speaker": str(seg.get("speaker", "")),
            "start": float(seg.get("start", 0)),
            "end": float(seg.get("end", 0)),
            "text": seg.get("text") or "",
        }
        for seg in segments
    ]


async def fetch_roles(payload: Dict[str, Any]) -> dict:
    normalized_payload = {
        "segments": normalize_segments_for_role(payload.get("segments", []))
    }

    logger.info(
        "Preparing RoleDetection request",
        extra={
            "url": settings.role_url,
            "segment_count": len(normalized_payload["segments"]),
        },
    )

    async with httpx.AsyncClient() as client:
        return await _safe_request(
            client=client,
            method="POST",
            url=settings.role_url,
            service_name="RoleDetection",
            json=normalized_payload,
        )


def seconds_to_time_str(seconds: float) -> str:
    if seconds is None:
        seconds = 0.0
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds < 0:
        seconds = 0.0

    total_ms = int(round(seconds * 1000))
    hh = total_ms // (3600 * 1000)
    rem = total_ms % (3600 * 1000)
    mm = rem // (60 * 1000)
    rem = rem % (60 * 1000)
    ss = rem // 1000
    ms = rem % 1000

    sec_part = f"{ss:02d}.{ms:03d}" if ms else f"{ss:02d}"
    return f"{hh:02d}:{mm:02d}:{sec_part}" if hh > 0 else f"{mm:02d}:{sec_part}"


async def fetch_stt(
    audio_path: str,
    segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    stt_segments_payload: List[Dict[str, Any]] = []
    for seg in segments:
        start_sec = float(seg.get("start", 0.0))
        end_sec = float(seg.get("end", 0.0))
        if end_sec < start_sec:
            start_sec, end_sec = end_sec, start_sec

        stt_segments_payload.append(
            {
                "speaker": str(seg.get("speaker", "")),
                "start": seconds_to_time_str(start_sec),
                "end": seconds_to_time_str(end_sec),
            }
        )

    payload = {
        "audio_path": audio_path,
        "segments": stt_segments_payload,
    }

    logger.info(
        "Calling STT service",
        extra={
            "audio_path": audio_path,
            "segment_count": len(stt_segments_payload),
        },
    )

    async with httpx.AsyncClient() as client:
        data = await _safe_request(
            client,
            "POST",
            settings.stt_url,
            "STT",
            json=payload,
        )

    if not isinstance(data, dict) or not data.get("success"):
        raise ServiceProcessingError(
            "STT response unsuccessful",
            service_name="STT",
            details=data if isinstance(data, dict) else {"raw": str(data)[:2000]},
        )

    returned_segments = data.get("segments", []) or []
    if len(returned_segments) != len(segments):
        logger.warning(
            "STT segment count mismatch",
            extra={"expected": len(segments), "got": len(returned_segments)},
        )

    for i, original in enumerate(segments):
        original["text"] = returned_segments[i].get("text", "") if i < len(returned_segments) else ""

    return segments


def _ensure_behavior_endpoint(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return u

    if u.rstrip("/").endswith("/detect"):
        return u

    base = u if u.endswith("/") else (u + "/")
    return urljoin(base, "detect")


async def fetch_behaviors(
    client: httpx.AsyncClient,
    transcript: List[Dict[str, Any]],
    model: Optional[str] = None,
) -> dict:
    payload = {"transcript": transcript}
    if model:
        payload["model"] = model

    behavior_url = _ensure_behavior_endpoint(settings.behavior_url)

    return await _safe_request(
        client,
        "POST",
        behavior_url,
        "BehaviorDetection",
        json=payload,
    )


async def fetch_sentiment(
    client: httpx.AsyncClient,
    conversation: str,
) -> dict:
    return await _safe_request(
        client,
        "POST",
        settings.sentiment_url,
        "SentimentAnalysis",
        json={"conversation": conversation},
    )


async def fetch_operator_score(
    client: httpx.AsyncClient,
    conversation_id: str,
    utterances: List[Dict[str, Any]],
) -> dict:
    payload = {"conversation_id": conversation_id, "utterances": utterances}
    return await _safe_request(
        client,
        "POST",
        settings.operator_score_url,
        "OperatorScoring",
        json=payload,
    )


async def fetch_silence_from_segments(
    client: httpx.AsyncClient,
    call_id: str,
    segments: List[Dict[str, Any]],
    total_duration: Optional[float] = None,
    silence_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "call_id": call_id,
        "segments": [
            {
                "speaker": str(s.get("speaker", "")),
                "start": float(s.get("start", 0.0)),
                "end": float(s.get("end", 0.0)),
                "text": s.get("text"),
                "role": s.get("role"),
            }
            for s in (segments or [])
        ],
    }
    if total_duration is not None:
        payload["total_duration"] = float(total_duration)
    if silence_threshold is not None:
        payload["silence_threshold"] = float(silence_threshold)

    return await _safe_request(
        client=client,
        method="POST",
        url=settings.silence_from_segments_url,
        service_name="SilenceFromSegments",
        json=payload,
    )
