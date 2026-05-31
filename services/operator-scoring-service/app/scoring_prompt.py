def build_prompt(conversation: list[dict]) -> str:
    return f"""
شما یک سیستم ارزیابی کیفیت مکالمه مرکز تماس هستید.

بر اساس مکالمه زیر، فقط عملکرد اپراتور را ارزیابی کن.

شاخص‌ها:
1. رعایت ادب
2. کنترل خشم
3. حل مسئله

قوانین:
- هر شاخص عددی بین 0 تا 100 باشد
- فقط خروجی JSON بده
- هیچ توضیح اضافه ننویس
- اگر مکالمه برای ارزیابی کافی نیست، فقط این JSON را بده:
{{"error": "INSUFFICIENT_DATA"}}

فرمت خروجی:
{{
  "politeness_score": number,
  "anger_control_score": number,
  "problem_solving_score": number
}}

مکالمه:
{conversation}
"""
