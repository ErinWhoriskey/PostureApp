import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

@dataclass
class FrameRecord:
    t: float
    is_bad: bool
    angle: float
    offset: float
    nose_xy: Optional[Tuple[float, float]] = None  # normalised (0..1, 0..1)

@dataclass
class SessionLogger:
    started_at: float = field(default_factory=time.time)
    records: List[FrameRecord] = field(default_factory=list)

    def reset(self):
        self.started_at = time.time()
        self.records = []

    def add(self, is_bad: bool, angle: float, offset: float, nose_xy=None):
        self.records.append(FrameRecord(
            t=time.time() - self.started_at,
            is_bad=bool(is_bad),
            angle=float(angle) if angle is not None else float("nan"),
            offset=float(offset) if offset is not None else float("nan"),
            nose_xy=nose_xy
        ))

    def summary(self):
        if not self.records:
            return {
                "frames": 0,
                "bad_frames": 0,
                "good_frames": 0,
                "bad_pct": 0.0,
                "duration_s": 0.0
            }
        frames = len(self.records)
        bad_frames = sum(1 for r in self.records if r.is_bad)
        good_frames = frames - bad_frames
        duration_s = self.records[-1].t
        bad_pct = (bad_frames / frames) * 100.0 if frames else 0.0
        return {
            "frames": frames,
            "bad_frames": bad_frames,
            "good_frames": good_frames,
            "bad_pct": bad_pct,
            "duration_s": duration_s
        }
