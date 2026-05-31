from typing import Any, Optional


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: str = "app_error",
        status_code: int = 400,
        details: Optional[Any] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class InvalidJSONError(AppError):
    def __init__(self, message="Invalid JSON input", details=None):
        super().__init__(message=message, code="invalid_json", status_code=400, details=details)


class MissingFieldError(AppError):
    def __init__(self, message="Required field is missing", details=None):
        super().__init__(message=message, code="missing_field", status_code=400, details=details)


class InvalidSegmentError(AppError):
    def __init__(self, message="Invalid segment data", details=None):
        super().__init__(message=message, code="invalid_segment", status_code=400, details=details)


class AudioProcessingError(AppError):
    def __init__(self, message="Audio processing failed", details=None):
        super().__init__(message=message, code="audio_processing_error", status_code=500, details=details)


class ExternalAPIError(AppError):
    def __init__(self, message="External STT provider failed", details=None):
        super().__init__(message=message, code="external_api_error", status_code=502, details=details)
