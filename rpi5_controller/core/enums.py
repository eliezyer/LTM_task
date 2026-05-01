from __future__ import annotations

from enum import Enum, IntEnum, IntFlag


class SessionType(str, Enum):
    TRAINING = "training"
    RETRIEVAL = "retrieval"
    RETRAINING = "retraining"


class BehaviorState(IntEnum):
    IDLE = 0
    OPENING_CORRIDOR = 1
    CONTEXT_ZONE = 2
    REWARD_DELIVERY = 3
    AIRPUFF_DELIVERY = 4
    ITI = 5
    OUTCOME_ZONE = 6


class Segment(str, Enum):
    OPENING = "opening"
    CONTEXT = "context"


class UdpFlags(IntFlag):
    NONE = 0
    TELEPORT = 1 << 0
    ITI_ACTIVE = 1 << 1
    FREEZE = 1 << 2
    OUTCOME_ACTIVE = 1 << 3


SCENE_OPENING = 0
SCENE_BLACK = 0
SCENE_OUTCOME = 4
