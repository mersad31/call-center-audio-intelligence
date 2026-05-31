# errors.py
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Error:
    code: str
    message: str


ERRORS: Dict[str, Error] = {
    "E01": Error("E01", "Empty input."),
    "E02": Error("E02", "No customer message found."),
    "E03": Error("E03", "Input too short or meaningless."),
    "E04": Error("E04", "Non-Persian content detected."),
    "E06": Error("E06", "No valid emotional content detected."),
}


def error_response(code: str) -> Dict:
    err = ERRORS.get(code, Error(code, "Unknown error."))
    return {"error": {"code": err.code, "message": err.message}}
