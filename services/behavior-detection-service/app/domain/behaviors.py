#app/domain/behaviors.py
from enum import Enum

class BehaviorName(str, Enum):
    GREETING = "greeting"
    INTRODUCTION = "introduction"
    FORMAL_TONE = "formal_tone"
    SURVEY_INVITATION = "survey_invitation"