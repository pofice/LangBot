from __future__ import annotations

import dataclasses
import datetime


@dataclasses.dataclass
class ZaloEvent:
    type: str  # 'im'
    user_id: str
    text: str
    message_id: str
    timestamp: float
    receiver_id: str | None = None
    pic_url: str | None = None

    @staticmethod
    def now_ts() -> float:
        return float(datetime.datetime.utcnow().timestamp())


