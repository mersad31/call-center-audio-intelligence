from typing import List, Tuple, Optional, Dict, Any
import re
import os

# =========================
# Normalization / Regex
# =========================
TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)

DEBUG_ENV = os.getenv("DEBUG_SENTIMENT", "0").lower() in ("1", "true", "yes")
DEBUG_ENV = DEBUG_ENV or (os.getenv("SENTIMENT_DEBUG", "0").lower() in ("1", "true", "yes"))

PERSIAN_CHAR_FIXES = str.maketrans({
    "ك": "ک",
    "ي": "ی",
})

# =========================
# Calibrated Lexicons
# =========================
POS_TOKENS = {
    "خوب", "عالی", "بهترین", "راضی", "رضایت", "دوست",
    "محشر", "عالیه", "خوبه", "خوشحال", "خوشحالیم",
    "سریع", "دقیق", "حرفه‌ای", "حرفه", "محترمانه",
    "بهتر", "حل", "درست", "بینظیره", "بی‌نظیره", "بینظیر",
    "قابل", "قبول", "راضی‌ام", "راضیم", "بهتره",
    "راه", "می‌ارزید", "می ارزید", "اوکی", "اوکِی",
}

NEG_TOKENS = {
    "بد", "ضعیف", "افتضاح", "ناراضی", "شاکی", "مشکل", "خراب", "کند", "نامناسب",
    "تاخیر", "ناامید", "غلط", "اشتباه", "مزخرف", "فاجعه", "داغون", "آشغال",
    "مزخرفه", "ناراحت", "ناراحتم", "ناراحتیم", "ناراضیم", "ناراضی‌ام",
    "ناراضیام", "دیر", "نرسید", "اذیت", "کلافه", "خسته", "معطل",
    "جوابگو", "ضعیفه", "بی‌کیفیت", "بیکیفیت", "بی‌مسئولیتی",
    "بی‌توجهی", "اعصاب‌خردکن", "اعصاب", "قطع", "خرابی", "ضعف",
    "نشد", "نیست", "نبود",
}

NEUTRAL_TOKENS = {
    "معمولی", "متوسط", "بدک", "قابل", "قبول",
}

PHRASE_WEIGHTS: Dict[str, float] = {
    # strong positive
    "فوق العاده بود": 2.3,
    "فوق‌العاده بود": 2.3,
    "بی‌نظیر بود": 2.2,
    "بینظیر بود": 2.2,
    "عالی بود": 1.85,
    "محشر بود": 2.0,

    # medium positive
    "خیلی خوب بود": 1.45,
    "بسیار خوب بود": 1.55,
    "خوب بود": 0.9,
    "راضی بودم": 0.9,
    "رضایت دارم": 1.0,
    "راضی‌ام": 0.95,
    "راضیم": 0.95,
    "الان راضی‌ام": 1.1,
    "الان راضیم": 1.1,
    "الان راضی هستم": 1.1,
    "دوستش داشتم": 1.1,
    "خیلی دوستش داشتم": 1.5,
    "مشکل حل شد": 1.55,
    "حل شد": 1.05,
    "درست شد": 1.0,
    "خوب شد": 0.9,
    "بهتر شد": 0.9,
    "بهتر شده": 0.85,
    "به موقع": 0.65,
    "به‌موقع": 0.65,
    "سریع بود": 0.7,
    "محترمانه بود": 0.7,
    "حرفه‌ای بود": 0.85,
    "دقیق بود": 0.75,
    "در کل راضی‌کننده است": 0.95,
    "در کل راضی کننده است": 0.95,
    "راضی‌کننده": 0.85,
    "راضی کننده": 0.85,
    "بد نبود": 0.7,
    "بد نیست": 0.55,
    "خوب شده": 0.85,
    "ارزش داشت": 0.9,
    "می‌ارزید": 0.8,
    "می ارزید": 0.8,
    "کار راه افتاد": 0.85,
    "اوکی شد": 0.5,
    "اوکیه": 0.4,
    "اوکی است": 0.4,

    # strong negative
    "افتضاح بود": -2.2,
    "فاجعه بود": -2.45,
    "مزخرف بود": -2.3,
    "حیف پول": -2.3,
    "اصلا راضی نیستم": -2.35,
    "اصلاً راضی نیستم": -2.35,
    "کاملا ناراضی": -2.2,
    "کاملاً ناراضی": -2.2,

    # medium negative
    "خیلی بد": -1.7,
    "بسیار بد": -1.7,
    "بد بود": -1.15,
    "راضی نبودم": -1.05,
    "خوب نبود": -1.0,
    "اصلا خوب نبود": -1.55,
    "اصلاً خوب نبود": -1.55,
    "اصلا راضی نبودم": -1.8,
    "اصلاً راضی نبودم": -1.8,
    "تعریفی نداشت": -0.9,
    "انتظار بیشتری داشتم": -0.85,
    "دیر رسید": -1.0,
    "حل نشد": -1.45,
    "مشکل من حل نشد": -1.7,
    "به موقع نرسید": -1.35,
    "بی کیفیت": -1.15,
    "بی‌کیفیت": -1.15,
    "کیفیت بد": -1.1,
    "اذیت شدم": -1.25,
    "کلافه شدم": -1.3,
    "خسته شدم": -1.0,
    "معطل شدم": -1.2,
    "جوابگو نیست": -1.2,
    "پاسخگو نیست": -1.2,
    "پاسخگو نبود": -1.2,
    "پاسخ نداد": -1.4,
    "جواب نداد": -1.4,
    "جواب نمی‌داد": -1.45,
    "جواب نمی داد": -1.45,
    "جواب نمی‌دین": -1.55,
    "جواب نمی دین": -1.55,
    "جواب نمیده": -1.45,
    "جواب نمی‌دهد": -1.45,
    "افت کرده": -1.0,
    "ضعیفه": -1.0,
    "بی مسئولیتی": -1.25,
    "بی‌مسئولیتی": -1.25,
    "بی توجهی": -1.1,
    "بی‌توجهی": -1.1,
    "اعصاب خردکن": -1.4,
    "اعصاب‌خردکن": -1.4,
    "کار نکرد": -1.5,
    "قطع شد": -1.5,
    "دیر شد": -0.95,
    "سه روزه": -1.25,
    "هنوز درست نشده": -1.6,
    "هنوز حل نشده": -1.6,
    "هنوز ضعف داره": -1.0,
    "هنوز ضعف دارد": -1.0,
    "مشکل داشت": -0.9,
    "دیگه نمی‌ارزه": -1.2,
    "دیگه نمی ارزه": -1.2,

    # neutral / mixed
    "بدک نبود": 0.3,
    "قابل قبول بود": 0.2,
    "کار راه‌انداز بود": 0.15,
    "کار راه انداز بود": 0.15,
    "معمولی بود": 0.0,
    "متوسط بود": 0.0,
    "نه خوب نه بد": 0.0,
    "نظری ندارم": 0.0,
    "ثبت شد": 0.0,
    "پیام دریافت شد": 0.0,
    "نمی دانم": 0.0,
    "نمیدانم": 0.0,
    "نمی‌دانم": 0.0,
    "اطلاعی ندارم": 0.0,
    "دریافت شد": 0.0,
    "بد هم نبود": 0.45,
    "نه بد بود نه خوب": 0.0,
    "نه خوب بود نه بد": 0.0,
}

STRONG_NEG_TOKENS = {"مزخرف", "افتضاح", "فاجعه", "آشغال"}
STRONG_POS_TOKENS = {"عالی", "محشر", "بینظیر", "بی‌نظیر"}

NEGATION_WORDS = {
    "نه", "نیست", "نبود", "نمی", "نشد", "هرگز",
    "هیچوقت", "هیچ‌وقت", "هیچ", "هیچ وقت", "بی",
    "ندارم", "نداشتم", "نخواهد", "نمیشه", "نمیشه",
    "نمی‌شود", "نمیشود",
}

COURTESY_PHRASES = {
    "باشه", "باشه مرسی", "باشه ممنون", "اوکی", "اوکی مرسی", "اوکی ممنون",
    "ممنون", "مرسی", "خیلی ممنون", "سپاس", "متشکرم",
    "ممنون از اطلاع‌رسانی", "ممنون از اطلاع رسانی", "فعلاً", "فعلا"
}

CONTRADICTIONS = ["با این حال", "بااین‌حال", "اما", "ولی", "ولی بعد", "ولی آخرش"]
TEMPORAL_CUES = [
    "در نهایت", "آخرش", "نهایتاً", "نهایتا", "در آخر",
    "اوایل", "اول", "اولش", "در ابتدا", "ابتدا", "قبلا", "قبلاً",
    "بعدش", "بعد", "بعدا", "بعداً", "وسطش",
    "الان", "اکنون", "حالا", "فعلاً", "فعلا", "این بار",
]
FINAL_STATE_CUES = {
    "الان", "اکنون", "حالا", "فعلاً", "فعلا", "در نهایت", "آخرش",
    "نهایتاً", "نهایتا", "در آخر", "در کل", "این بار", "آخر کار"
}
EARLY_STATE_CUES = {
    "اوایل", "اول", "اولش", "در ابتدا", "ابتدا", "قبلا", "قبلاً", "اول کار"
}
LATE_STATE_CUES = {
    "بعد", "بعدش", "بعدا", "بعداً", "الان", "اکنون", "حالا", "در نهایت", "آخرش", "در آخر", "بعدتر"
}

SARCASM_CUE_PHRASES = {
    "آره عالی", "خیلی هم که خوب", "مخصوصاً اونجایی که",
    "مرسی واقعا", "مرسی واقعاً", "چه خوب", "دمتون گرم", "به‌به", "به به",
    "عجب", "واقعاً عالی بود", "واقعا عالی بود", "چه عالی", "شاهکار کردید",
    "دستتون درد نکنه", "خیلی خوبه که", "عالیه که",
}

POSITIVE_OPENERS = {
    "خیلی خوب", "عالی بود", "خوب بود", "آره عالی", "خیلی هم که خوب", "چه خوب", "چه عالی",
    "خیلی خوبه", "عالیه"
}

COMPLAINT_CUES = {
    "جواب نداد", "جواب نمی‌داد", "جواب نمی داد", "جواب نمی‌دین", "جواب نمی دین",
    "حل نشد", "خراب شد", "دیر شد", "سه روزه", "هنوز", "معطل", "تاخیر",
    "نرسید", "کار نکرد", "قطع شد", "اذیت شدم", "مشکل داشت",
    "آشغال", "اشغال", "درست نشد", "حیف پول", "افتضاح", "رسیدگی نمی", "پاسخ نمی"
}

INTENSIFIER_WEAK = {
    "خیلی": 1.14,
    "واقعا": 1.12,
    "واقعاً": 1.12,
    "بسیار": 1.16,
    "کلاً": 1.06,
    "کلا": 1.06,
    "نسبتاً": 0.92,
    "نسبتا": 0.92,
}

INTENSIFIER_STRONG = {
    "اصلا": 1.28,
    "اصلاً": 1.28,
    "کاملا": 1.24,
    "کاملاً": 1.24,
    "شدیدا": 1.28,
    "شدیداً": 1.28,
}

# backward-compat alias for older imports
INTENSIFIER_FACTORS = {
    **INTENSIFIER_WEAK,
    **INTENSIFIER_STRONG,
}

NEUTRAL_PHRASES = {
    "نظری ندارم", "ثبت شد", "پیام دریافت شد", "نمی دانم", "نمیدانم",
    "نمی‌دانم", "اطلاعی ندارم", "دریافت شد", "معمولی بود", "نه خوب نه بد",
    "نه بد بود نه خوب", "نه خوب بود نه بد"
}

NEGATION_IDIOM_PATTERNS = [
    (re.compile(r"\bبد\s+نبود\b"), 0.8, "negation_idiom:بد نبود"),
    (re.compile(r"\bبدک\s+نبود\b"), 0.3, "negation_idiom:بدک نبود"),
    (re.compile(r"\bبد\s+نیست\b"), 0.5, "negation_idiom:بد نیست"),
    (re.compile(r"\bبد\s+هم\s+نبود\b"), 0.45, "negation_idiom:بد هم نبود"),
    (re.compile(r"\bچندان\s+بد\s+نیست\b"), 0.35, "negation_idiom:چندان بد نیست"),
    (re.compile(r"\bخوب\s+نبود\b"), -1.0, "negation_idiom:خوب نبود"),
    (re.compile(r"\bچندان\s+خوب\s+نیست\b"), -0.6, "negation_idiom:چندان خوب نیست"),
    (re.compile(r"\bعالی\s+نبود\b"), -0.75, "negation_idiom:عالی نبود"),
    (re.compile(r"\bافتضاح\s+نبود\b"), 0.15, "negation_idiom:افتضاح نبود"),
    (re.compile(r"\bناراضی\s+نیستم\b"), 0.85, "negation_idiom:ناراضی نیستم"),
    (re.compile(r"\bراضی\s+نیستم\b"), -1.35, "negation_idiom:راضی نیستم"),
    (re.compile(r"\bراضی\s+نبودم\b"), -1.05, "negation_idiom:راضی نبودم"),
    (re.compile(r"\bنه\s+خوب\s+نه\s+بد\b"), 0.0, "negation_idiom:نه خوب نه بد"),
    (re.compile(r"\bنه\s+بد\s+بود\s+نه\s+خوب\b"), 0.0, "negation_idiom:نه بد بود نه خوب"),
    (re.compile(r"\bنه\s+خوب\s+بود\s+نه\s+بد\b"), 0.0, "negation_idiom:نه خوب بود نه بد"),
]

SARCASM_REGEX_PATTERNS = [
    (
        re.compile(
            r"(خیلی\s+خوبه\s+که|عالیه\s+که|چه\s+خوب\s+که|مرسی\s+که).*(جواب\s+نمی|پاسخ\s+نمی|رسیدگی\s+نمی|خراب|بده|قطع\s+شد|نشد|نرسید|معطل|تاخیر)",
            re.UNICODE,
        ),
        -1.85,
        "sarcasm:positive_opener_plus_negative_outcome"
    ),
]

PHRASE_SEMANTIC_PATTERNS = [
    (re.compile(r"خیلی\s+دوستش\s+داشتم"), 1.5, "pattern:خیلی دوستش داشتم"),
    (re.compile(r"دوستش\s+داشتم"), 1.1, "pattern:دوستش داشتم"),
    (re.compile(r"بی[‌\s]?نظیر(?:ه| بود)?"), 2.0, "pattern:بی‌نظیر"),
    (re.compile(r"مشکل\s+حل\s+شد"), 1.55, "pattern:مشکل حل شد"),
    (re.compile(r"حل\s+شد"), 1.05, "pattern:حل شد"),
    (re.compile(r"در\s+کل\s+راضی"), 1.0, "pattern:در کل راضی"),
    (re.compile(r"خیلی\s+خوب(?:\s+بود)?"), 1.35, "pattern:خیلی خوب"),
    (re.compile(r"بسیار\s+خوب(?:\s+بود)?"), 1.45, "pattern:بسیار خوب"),
    (re.compile(r"خوب\s+بود"), 0.9, "pattern:خوب بود"),
    (re.compile(r"خوب\s+شده"), 0.85, "pattern:خوب شده"),
    (re.compile(r"بهتر\s+شد(?:ه)?"), 0.85, "pattern:بهتر شد"),
    (re.compile(r"بد\s+نیست"), 0.5, "pattern:بد نیست"),
    (re.compile(r"بد\s+هم\s+نبود"), 0.45, "pattern:بد هم نبود"),
    (re.compile(r"قابل\s+قبول(?:\s+بود)?"), 0.2, "pattern:قابل قبول"),
    (re.compile(r"کار\s+راه[‌\s]?افتاد"), 0.85, "pattern:کار راه افتاد"),
    (re.compile(r"ارزش\s+داشت"), 0.9, "pattern:ارزش داشت"),
    (re.compile(r"محترمانه\s+بود"), 0.7, "pattern:محترمانه بود"),
    (re.compile(r"حرفه[‌\s]?ای\s+بود"), 0.85, "pattern:حرفه‌ای بود"),
    (re.compile(r"دقیق\s+بود"), 0.75, "pattern:دقیق بود"),
    (re.compile(r"به[‌\s]?موقع"), 0.65, "pattern:به‌موقع"),
    (re.compile(r"راضی(?:‌ام|ام| بودم)?"), 0.85, "pattern:راضی"),
    (re.compile(r"ناراضی\s+نیستم"), 0.85, "pattern:ناراضی نیستم"),
    (re.compile(r"افتضاح\s+بود"), -2.2, "pattern:افتضاح بود"),
    (re.compile(r"فاجعه\s+بود"), -2.45, "pattern:فاجعه بود"),
    (re.compile(r"مزخرف\s+بود"), -2.3, "pattern:مزخرف بود"),
    (re.compile(r"حیف\s+پول"), -2.3, "pattern:حیف پول"),
    (re.compile(r"خیلی\s+بد"), -1.7, "pattern:خیلی بد"),
    (re.compile(r"بسیار\s+بد"), -1.7, "pattern:بسیار بد"),
    (re.compile(r"بد\s+بود"), -1.15, "pattern:بد بود"),
    (re.compile(r"خوب\s+نبود"), -1.0, "pattern:خوب نبود"),
    (re.compile(r"اصلا\s+خوب\s+نبود|اصلاً\s+خوب\s+نبود"), -1.55, "pattern:اصلاً خوب نبود"),
    (re.compile(r"راضی\s+نبودم"), -1.05, "pattern:راضی نبودم"),
    (re.compile(r"راضی\s+نیستم"), -1.35, "pattern:راضی نیستم"),
    (re.compile(r"اصلا\s+راضی\s+نبودم|اصلاً\s+راضی\s+نبودم"), -1.8, "pattern:اصلاً راضی نبودم"),
    (re.compile(r"اصلا\s+راضی\s+نیستم|اصلاً\s+راضی\s+نیستم"), -2.35, "pattern:اصلاً راضی نیستم"),
    (re.compile(r"تعریفی\s+نداشت"), -0.9, "pattern:تعریفی نداشت"),
    (re.compile(r"انتظار\s+بیشتری\s+داشتم"), -0.85, "pattern:انتظار بیشتری داشتم"),
    (re.compile(r"دیر\s+رسید"), -1.0, "pattern:دیر رسید"),
    (re.compile(r"حل\s+نشد"), -1.45, "pattern:حل نشد"),
    (re.compile(r"مشکل(?:\s+من)?\s+حل\s+نشد"), -1.7, "pattern:مشکل حل نشد"),
    (re.compile(r"به\s+موقع\s+نرسید|به[‌\s]?موقع\s+نرسید"), -1.35, "pattern:به‌موقع نرسید"),
    (re.compile(r"بی[‌\s]?کیفیت"), -1.15, "pattern:بی‌کیفیت"),
    (re.compile(r"کیفیت\s+بد"), -1.1, "pattern:کیفیت بد"),
    (re.compile(r"اذیت\s+شدم"), -1.25, "pattern:اذیت شدم"),
    (re.compile(r"کلافه\s+شدم"), -1.3, "pattern:کلافه شدم"),
    (re.compile(r"خسته\s+شدم"), -1.0, "pattern:خسته شدم"),
    (re.compile(r"معطل\s+شدم"), -1.2, "pattern:معطل شدم"),
    (re.compile(r"جوابگو\s+نیست"), -1.2, "pattern:جوابگو نیست"),
    (re.compile(r"پاسخگو\s+نیست|پاسخگو\s+نبود"), -1.2, "pattern:پاسخگو نیست/نبود"),
    (re.compile(r"پاسخ\s+نداد"), -1.4, "pattern:پاسخ نداد"),
    (re.compile(r"جواب\s+نداد"), -1.4, "pattern:جواب نداد"),
    (re.compile(r"جواب\s+نمی[‌\s]?داد"), -1.45, "pattern:جواب نمی‌داد"),
    (re.compile(r"جواب\s+نمی[‌\s]?دین"), -1.55, "pattern:جواب نمی‌دین"),
    (re.compile(r"افت\s+کرده"), -1.0, "pattern:افت کرده"),
    (re.compile(r"ضعیفه"), -1.0, "pattern:ضعیفه"),
    (re.compile(r"بی[‌\s]?مسئولیتی"), -1.25, "pattern:بی‌مسئولیتی"),
    (re.compile(r"بی[‌\s]?توجهی"), -1.1, "pattern:بی‌توجهی"),
    (re.compile(r"اعصاب[‌\s]?خردکن"), -1.4, "pattern:اعصاب‌خردکن"),
    (re.compile(r"کار\s+نکرد"), -1.5, "pattern:کار نکرد"),
    (re.compile(r"قطع\s+شد"), -1.5, "pattern:قطع شد"),
    (re.compile(r"دیر\s+شد"), -0.95, "pattern:دیر شد"),
    (re.compile(r"سه\s+روزه"), -1.25, "pattern:سه روزه"),
    (re.compile(r"هنوز\s+درست\s+نشده"), -1.6, "pattern:هنوز درست نشده"),
    (re.compile(r"هنوز\s+حل\s+نشده"), -1.6, "pattern:هنوز حل نشده"),
    (re.compile(r"هنوز\s+ضعف\s+دار(?:ه|د)"), -1.0, "pattern:هنوز ضعف دارد"),
    (re.compile(r"مشکل\s+داشت"), -0.9, "pattern:مشکل داشت"),
    (re.compile(r"بد\s+نبود"), 0.7, "pattern:بد نبود"),
    (re.compile(r"بدک\s+نبود"), 0.3, "pattern:بدک نبود"),
    (re.compile(r"قابل\s+قبول\s+بود"), 0.2, "pattern:قابل قبول بود"),
    (re.compile(r"کار\s+راه[‌\s]?انداز\s+بود"), 0.15, "pattern:کار راه‌انداز بود"),
    (re.compile(r"معمولی\s+بود"), 0.0, "pattern:معمولی بود"),
    (re.compile(r"متوسط\s+بود"), 0.0, "pattern:متوسط بود"),
    (re.compile(r"نه\s+خوب\s+نه\s+بد"), 0.0, "pattern:نه خوب نه بد"),
    (re.compile(r"نه\s+بد\s+بود\s+نه\s+خوب"), 0.0, "pattern:نه بد بود نه خوب"),
    (re.compile(r"نه\s+خوب\s+بود\s+نه\s+بد"), 0.0, "pattern:نه خوب بود نه بد"),
    (re.compile(r"نظری\s+ندارم"), 0.0, "pattern:نظری ندارم"),
    (re.compile(r"ثبت\s+شد"), 0.0, "pattern:ثبت شد"),
    (re.compile(r"پیام\s+دریافت\s+شد"), 0.0, "pattern:پیام دریافت شد"),
    (re.compile(r"نمی[‌\s]?دانم|نمیدانم"), 0.0, "pattern:نمی‌دانم"),
    (re.compile(r"اطلاعی\s+ندارم"), 0.0, "pattern:اطلاعی ندارم"),
    (re.compile(r"دریافت\s+شد"), 0.0, "pattern:دریافت شد"),
]

LABELS = ["خیلی ناراضی", "ناراضی", "خنثی", "خوب", "عالی"]


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = str(text).translate(PERSIAN_CHAR_FIXES)
    text = text.replace("\u200c", " ")
    text = re.sub(r"[ـ]+", "", text)
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(normalize_text(text))


def has_emotion_words(text: str) -> bool:
    t = normalize_text(text)
    toks = tokenize(t)
    if any(p in t for p in PHRASE_WEIGHTS.keys()):
        return True
    if any(p.search(t) for p, _, _ in PHRASE_SEMANTIC_PATTERNS):
        return True
    if any(p.search(t) for p, _, _ in NEGATION_IDIOM_PATTERNS):
        return True
    return any(tok in POS_TOKENS or tok in NEG_TOKENS for tok in toks)


def _apply_negation_window(tokens: List[str], idx: int, val: float) -> float:
    left = max(0, idx - 3)
    right = min(len(tokens), idx + 2)
    left_window = tokens[left:idx]
    right_window = tokens[idx + 1:right]

    if any(tok in {"نه"} for tok in left_window) and idx + 1 < len(tokens):
        return -val * 0.85

    if any(tok in NEGATION_WORDS for tok in left_window):
        return -val * 0.85

    if val > 0 and any(tok in {"نیست", "نبود", "نشد", "ندارم", "نداشتم"} for tok in right_window):
        return -val * 0.9

    return val


def _token_score(tokens: List[str]) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []

    for i, tok in enumerate(tokens):
        val = 0.0

        if tok in POS_TOKENS:
            val = 0.52
            if tok in STRONG_POS_TOKENS:
                val = 0.95

        elif tok in NEG_TOKENS:
            val = -0.62
            if tok in STRONG_NEG_TOKENS:
                val = -1.12

        elif tok in NEUTRAL_TOKENS:
            val = 0.0

        if val != 0.0:
            adj = _apply_negation_window(tokens, i, val)
            if adj != val:
                reasons.append(f"negation:{tok}:{val:.2f}->{adj:.2f}")
            score += adj
            reasons.append(f"token:{tok}:{adj:.2f}")

    return score, reasons


def _phrase_score(text: str) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []

    for phrase, weight in PHRASE_WEIGHTS.items():
        if phrase in text:
            score += weight
            reasons.append(f"phrase:{phrase}:{weight:.2f}")

    for pattern, weight, name in PHRASE_SEMANTIC_PATTERNS:
        if pattern.search(text):
            score += weight
            reasons.append(f"{name}:{weight:.2f}")

    return score, reasons


def _intensifier_multiplier(text: str) -> Tuple[float, List[str]]:
    mult = 1.0
    reasons: List[str] = []
    words = text.split()

    for k, v in INTENSIFIER_WEAK.items():
        if k in words:
            mult *= v
            reasons.append(f"intensifier_weak:{k}:{v:.2f}")

    for k, v in INTENSIFIER_STRONG.items():
        if k in words:
            mult *= v
            reasons.append(f"intensifier_strong:{k}:{v:.2f}")

    return mult, reasons


def _contains_any(text: str, items) -> bool:
    return any(x in text for x in items)


def _contains_token(text: str, token_set: set) -> bool:
    words = set(text.split())
    return any(tok in words for tok in token_set)


def _negation_idiom_override(text: str) -> Tuple[Optional[float], List[str]]:
    for pattern, mapped_score, reason in NEGATION_IDIOM_PATTERNS:
        if pattern.search(text):
            return mapped_score, [f"{reason}:{mapped_score:.2f}"]
    return None, []


def _sarcasm_adjustment(text: str) -> Tuple[float, List[str]]:
    reasons: List[str] = []

    for pattern, delta, reason in SARCASM_REGEX_PATTERNS:
        if pattern.search(text):
            reasons.append(f"{reason}:{delta:.2f}")
            return delta, reasons

    if _contains_any(text, SARCASM_CUE_PHRASES) and _contains_any(text, COMPLAINT_CUES):
        reasons.append("sarcasm_detected:-1.40")
        return -1.4, reasons

    if _contains_any(text, POSITIVE_OPENERS) and _contains_any(text, COMPLAINT_CUES):
        reasons.append("sarcasm_positive_opener_with_complaint:-1.10")
        return -1.1, reasons

    return 0.0, reasons


def _score_segment(text: str) -> Dict[str, Any]:
    norm = normalize_text(text)
    toks = tokenize(norm)
    token_score, token_reasons = _token_score(toks)
    phrase_score, phrase_reasons = _phrase_score(norm)
    base_score = token_score + phrase_score
    return {
        "normalized_text": norm,
        "tokens": toks,
        "token_score": token_score,
        "phrase_score": phrase_score,
        "base_score": base_score,
        "reasons": token_reasons + phrase_reasons if (token_reasons or phrase_reasons) else ["fallback: score_text"],
    }


def _split_by_contrast(text: str) -> Optional[Tuple[str, str, str]]:
    for marker in sorted(CONTRADICTIONS, key=len, reverse=True):
        if marker in text:
            left, right = text.split(marker, 1)
            return left.strip(), marker, right.strip()
    return None


def _temporal_adjustment(text: str) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    score = 0.0

    has_final = _contains_any(text, FINAL_STATE_CUES)
    has_early = _contains_any(text, EARLY_STATE_CUES)
    has_late = _contains_any(text, LATE_STATE_CUES)

    positive_endings = [
        "حل شد", "درست شد", "راضی", "خوب شد", "بهتر شد", "بهتر شده",
        "عالی شد", "عالی شده", "الان راضی", "آخرش درست شد", "در نهایت حل شد"
    ]
    negative_endings = [
        "حل نشد", "خراب", "نرسید", "اذیت شدم", "کلافه شدم", "هنوز",
        "مشکل داشت", "افتضاح شد", "آخرش خراب شد", "در نهایت خراب شد", "الان ناراضی"
    ]

    has_positive = any(p in text for p in positive_endings)
    has_negative = any(p in text for p in negative_endings)

    if has_final and has_positive and has_negative:
        if any(p in text for p in ["آخرش درست شد", "در نهایت حل شد", "الان راضی", "حالا راضی"]):
            score += 0.9
            reasons.append("temporal_final_positive_override:+0.90")
        else:
            score += 0.55
            reasons.append("temporal_final_positive_override:+0.55")

    elif has_early and has_late and has_positive and has_negative:
        if any(p in text for p in ["آخرش خراب شد", "در نهایت خراب شد", "الان ناراضی"]):
            score -= 0.75
            reasons.append("temporal_final_negative_override:-0.75")
        else:
            reasons.append("temporal_shift_detected:+0.20")
            score += 0.20

    if re.search(r"(اول|اولش|اوایل).*(خوب|عالی|راضی).*(بعد|بعدش|آخرش).*(بد|خراب|ناراضی|افتضاح)", text):
        score -= 0.95
        reasons.append("temporal_pattern_positive_to_negative:-0.95")

    if re.search(r"(اول|اولش|اوایل).*(بد|خراب|ناراضی|مشکل).*(بعد|بعدش|آخرش|الان).*(خوب|بهتر|حل شد|درست شد|راضی)", text):
        score += 0.95
        reasons.append("temporal_pattern_negative_to_positive:+0.95")

    return score, reasons


def _contrast_adjustment(text: str) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    split = _split_by_contrast(text)
    if not split:
        return 0.0, reasons

    left, marker, right = split
    left_detail = _score_segment(left)
    right_detail = _score_segment(right)

    left_score = float(left_detail["base_score"])
    right_score = float(right_detail["base_score"])

    left_weight = 0.72
    right_weight = 1.42
    weighted_score = (left_score * left_weight) + (right_score * right_weight)
    original_sum = left_score + right_score
    delta = weighted_score - original_sum

    reasons.append(f"contrast_marker:{marker}")
    reasons.append(f"contrast_left_score:{left_score:.2f}")
    reasons.append(f"contrast_right_score:{right_score:.2f}")

    if _contains_any(left, EARLY_STATE_CUES) or _contains_any(right, LATE_STATE_CUES):
        left_weight = 0.55
        right_weight = 1.70
        weighted_score = (left_score * left_weight) + (right_score * right_weight)
        delta = weighted_score - original_sum
        reasons.append("contrast_temporal_tail_emphasis")

    if abs(left_score) < 0.45 and abs(right_score) < 0.45:
        delta *= 0.5
        reasons.append("contrast_mild_segments_smoothing")

    reasons.append(f"contrast_delta:{delta:.2f}")
    return delta, reasons


def _courtesy_neutral_override(text: str, raw_score: float) -> Tuple[float, List[str]]:
    reasons: List[str] = []

    if text in COURTESY_PHRASES:
        reasons.append("courtesy_override_to_neutral")
        return 0.0, reasons

    if raw_score == 0.0 and any(p in text for p in COURTESY_PHRASES):
        reasons.append("courtesy_soft_neutral")
        return 0.0, reasons

    return raw_score, reasons


def _length_adjustment(tokens: List[str], score: float) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    n = len(tokens)

    if n <= 2 and abs(score) >= 1.8:
        score *= 1.03
        reasons.append("short_text_boost")
    elif n >= 25 and abs(score) > 0:
        score *= 0.95
        reasons.append("long_text_smooth")
    elif n <= 4 and abs(score) < 0.65:
        score *= 0.92
        reasons.append("short_edge_case_smooth")

    return score, reasons


def _normalize_score_to_label(score: float) -> str:
    if score <= -2.0:
        return "خیلی ناراضی"
    if score < -0.52:
        return "ناراضی"
    if score < 0.45:
        return "خنثی"
    if score < 1.7:
        return "خوب"
    return "عالی"


def score_message_with_reasons(text: str) -> Dict[str, Any]:
    label, detail = score_text(text, debug=True)
    return {
        "score": detail["final_score"],
        "base_score": detail["base_score"],
        "token_score": detail["token_score"],
        "phrase_score": detail["phrase_score"],
        "normalized_text": detail["normalized_text"],
        "label": label,
        "reasons": detail["reasons"],
        "raw_detail": detail,
    }


def score_text(text: str, debug: bool = False) -> Tuple[str, Dict[str, Any]]:
    norm = normalize_text(text)
    tokens = tokenize(norm)

    if not norm:
        label = "خنثی"
        detail = {
            "text": text,
            "normalized_text": norm,
            "tokens": [],
            "token_score": 0.0,
            "phrase_score": 0.0,
            "base_score": 0.0,
            "intensifier_multiplier": 1.0,
            "score_after_intensifier": 0.0,
            "sarcasm_delta": 0.0,
            "temporal_delta": 0.0,
            "contrast_delta": 0.0,
            "negation_override": None,
            "raw_score": 0.0,
            "final_score": 0.0,
            "label": label,
            "reasons": ["empty_text"],
        }
        return label, detail

    neg_override, neg_override_reasons = _negation_idiom_override(norm)

    token_score, token_reasons = _token_score(tokens)
    phrase_score, phrase_reasons = _phrase_score(norm)
    base_score = token_score + phrase_score

    if neg_override is not None:
        base_score = neg_override
        token_score = 0.0
        phrase_score = neg_override

    mult, intensifier_reasons = _intensifier_multiplier(norm)
    score_after_intensifier = base_score * mult

    sarcasm_delta, sarcasm_reasons = _sarcasm_adjustment(norm)
    temporal_delta, temporal_reasons = _temporal_adjustment(norm)
    contrast_delta, contrast_reasons = _contrast_adjustment(norm)

    raw_score = score_after_intensifier + sarcasm_delta + temporal_delta + contrast_delta
    raw_score, courtesy_reasons = _courtesy_neutral_override(norm, raw_score)
    final_score, length_reasons = _length_adjustment(tokens, raw_score)

    label = _normalize_score_to_label(final_score)

    reasons = (
        neg_override_reasons
        + token_reasons
        + phrase_reasons
        + intensifier_reasons
        + sarcasm_reasons
        + temporal_reasons
        + contrast_reasons
        + courtesy_reasons
        + length_reasons
    )
    if not reasons:
        reasons = ["fallback: score_text"]

    detail = {
        "text": text,
        "normalized_text": norm,
        "tokens": tokens,
        "token_score": round(token_score, 4),
        "phrase_score": round(phrase_score, 4),
        "base_score": round(base_score, 4),
        "intensifier_multiplier": round(mult, 4),
        "score_after_intensifier": round(score_after_intensifier, 4),
        "sarcasm_delta": round(sarcasm_delta, 4),
        "temporal_delta": round(temporal_delta, 4),
        "contrast_delta": round(contrast_delta, 4),
        "negation_override": neg_override,
        "raw_score": round(raw_score, 4),
        "final_score": round(final_score, 4),
        "label": label,
        "reasons": reasons,
    }

    if debug or DEBUG_ENV:
        return label, detail
    return label, detail


def score_messages(messages: List[str], debug: bool = False) -> Tuple[str, Dict[str, Any]]:
    if not messages:
        detail = {
            "messages": [],
            "message_labels": [],
            "message_scores": [],
            "aggregate_score": 0.0,
            "label": "خنثی",
            "last_message_detail": None,
            "raw_detail": None,
        }
        return "خنثی", detail

    message_labels: List[str] = []
    message_scores: List[float] = []
    message_details: List[Dict[str, Any]] = []

    for msg in messages:
        label, detail = score_text(msg, debug=True)
        message_labels.append(label)
        message_scores.append(detail["final_score"])
        message_details.append(detail)

    last_detail = message_details[-1]
    agg = sum(message_scores) / len(message_scores)

    if len(message_scores) >= 2:
        prev_avg = sum(message_scores[:-1]) / max(1, len(message_scores) - 1)
        agg = 0.30 * prev_avg + 0.70 * message_scores[-1]

    final_label = _normalize_score_to_label(agg)

    detail = {
        "messages": messages,
        "message_labels": message_labels,
        "message_scores": [round(x, 4) for x in message_scores],
        "aggregate_score": round(agg, 4),
        "label": final_label,
        "last_message_detail": last_detail,
        "raw_detail": {
            "all_message_details": message_details,
            "aggregation": {
                "method": "last_weighted_mean",
                "last_weight": 0.70 if len(message_scores) >= 2 else 1.0,
            },
        },
    }

    if debug or DEBUG_ENV:
        return final_label, detail
    return final_label, detail


def classify_sentiment(text_or_messages, debug: bool = False):
    if isinstance(text_or_messages, list):
        return score_messages(text_or_messages, debug=debug)
    return score_text(str(text_or_messages), debug=debug)


def sentiment_label(text_or_messages, debug: bool = False) -> str:
    label, _ = classify_sentiment(text_or_messages, debug=debug)
    return label

def map_final_sentiment(score):
    if isinstance(score, tuple):
        label, _ = score
        return label
    if isinstance(score, (int, float)):
        return _normalize_score_to_label(score)
    if isinstance(score, str):
        return score
    return "خنثی"


__all__ = [
    "LABELS",
    "POS_TOKENS",
    "NEG_TOKENS",
    "NEUTRAL_TOKENS",
    "PHRASE_WEIGHTS",
    "STRONG_NEG_TOKENS",
    "STRONG_POS_TOKENS",
    "NEGATION_WORDS",
    "COURTESY_PHRASES",
    "CONTRADICTIONS",
    "TEMPORAL_CUES",
    "FINAL_STATE_CUES",
    "SARCASM_CUE_PHRASES",
    "POSITIVE_OPENERS",
    "COMPLAINT_CUES",
    "INTENSIFIER_WEAK",
    "INTENSIFIER_STRONG",
    "INTENSIFIER_FACTORS",
    "NEUTRAL_PHRASES",
    "NEGATION_IDIOM_PATTERNS",
    "PHRASE_SEMANTIC_PATTERNS",
    "normalize_text",
    "tokenize",
    "has_emotion_words",
    "score_message_with_reasons",
    "score_text",
    "score_messages",
    "classify_sentiment",
    "sentiment_label",
]
