#app/domain/enums.py
from enum import Enum

class BehaviorLabel(int, Enum):
    Done = 1
    Not_Done = 0
    UNKNOWN = -1