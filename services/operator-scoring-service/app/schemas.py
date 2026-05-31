from pydantic import BaseModel, Field
from typing import List, Literal


class Utterance(BaseModel):
    speaker: Literal["operator", "customer"]
    start_time: float
    end_time: float
    text: str = Field(min_length=1)


class ConversationRequest(BaseModel):
    conversation_id: str
    utterances: List[Utterance]


class ScoreResponse(BaseModel):
    politeness_score: int = Field(ge=0, le=100)
    anger_control_score: int = Field(ge=0, le=100)
    problem_solving_score: int = Field(ge=0, le=100)