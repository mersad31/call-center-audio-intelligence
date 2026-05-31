# preprocessing.py
import re
from typing import List, Tuple

PERSIAN_CHARS_RE = re.compile(r"[\u0600-\u06FF]")

ARABIC_TO_PERSIAN = {
    "ي": "ی",
    "ك": "ک",
    "ة": "ه",
    "ؤ": "و",
    "إ": "ا",
    "أ": "ا",
    "ۀ": "ه",
    "ئ": "ی",
}

DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0610-\u061A\u06D6-\u06ED]")
URL_RE = re.compile(r"(https?://\S+|www\.\S+)")
HTML_RE = re.compile(r"<[^>]+>")
MULTISPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[!?.]{2,}")

OPERATOR_TAGS = [
    "اپراتور", "پشتیبان", "کارشناس", "agent", "operator", "support",
    "نماینده", "ادمین", "مدیر"
]

CUSTOMER_TAGS = ["مشتری", "کاربر", "user", "customer"]


def normalize_persian(text: str) -> str:
    if not text:
        return ""
    for a, p in ARABIC_TO_PERSIAN.items():
        text = text.replace(a, p)
    text = DIACRITICS_RE.sub("", text)
    text = URL_RE.sub(" ", text)
    text = HTML_RE.sub(" ", text)
    text = text.replace("\u200c", " ")
    text = PUNCT_RE.sub(".", text)
    text = MULTISPACE_RE.sub(" ", text).strip()
    return text


def remove_noise(text: str) -> str:
    text = re.sub(r"[^\w\s\u0600-\u06FF.!?،٬؛:_\-]", " ", text)
    text = MULTISPACE_RE.sub(" ", text).strip()
    return text


def is_persian(text: str, threshold: float = 0.4) -> bool:
    if not text:
        return False
    total = len(text)
    if total == 0:
        return False
    persian_count = len(PERSIAN_CHARS_RE.findall(text))
    return (persian_count / total) >= threshold


def split_messages(text: str) -> List[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines if lines else [text]


def detect_speaker(line: str) -> Tuple[str, str]:
    lower = line.lower()
    for tag in CUSTOMER_TAGS:
        if lower.startswith(f"{tag}:") or lower.startswith(f"{tag} -"):
            return "customer", line.split(":", 1)[-1].strip()
    for tag in OPERATOR_TAGS:
        if lower.startswith(f"{tag}:") or lower.startswith(f"{tag} -"):
            return "operator", line.split(":", 1)[-1].strip()
    return "unknown", line


def extract_customer_messages(text: str) -> List[str]:
    messages = split_messages(text)
    tagged = [detect_speaker(m) for m in messages]
    has_tags = any(s in ("customer", "operator") for s, _ in tagged)
    if not has_tags:
        return [m for _, m in tagged if m]
    return [m for s, m in tagged if s == "customer" and m]


def preprocess_conversation(text: str) -> List[str]:
    text = normalize_persian(text)
    text = remove_noise(text)
    messages = extract_customer_messages(text)

    cleaned = []
    for msg in messages:
        m = normalize_persian(msg)
        m = remove_noise(m)
        if m:
            cleaned.append(m)
    return cleaned
