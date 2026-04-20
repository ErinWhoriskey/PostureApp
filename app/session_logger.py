# session logger

# stores posture states for the current run

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class FrameRecord:
    t: float
    state: str
    angle: Optional[float]
    offset: Optional[float]
    lean_offset: Optional[float]
    nose_xy: Optional[Tuple[float, float]] = None


@dataclass
class SessionLogger:
    started_at: float = field(default_factory=time.time)
    records: List[FrameRecord] = field(default_factory=list)

    def reset(self):
        # clear the current session
        self.started_at = time.time()
        self.records = []

    def add(self, state, angle=None, offset=None, lean_offset=None, nose_xy=None):
        # add one frame record to the session
        self.records.append(
            FrameRecord(
                t=time.time() - self.started_at,
                state=str(state),
                angle=float(angle) if angle is not None else None,
                offset=float(offset) if offset is not None else None,
                lean_offset=float(lean_offset) if lean_offset is not None else None,
                nose_xy=nose_xy,
            )
        )

    def has_records(self):
        # need more than one record to work out time gaps
        return len(self.records) > 1

    def compute_state_times(self):
        # work out how long was spent in each state
        times = {
            "good": 0.0,
            "bad_forward": 0.0,
            "bad_left": 0.0,
            "bad_right": 0.0,
            "not_at_desk": 0.0,
            "uncalibrated": 0.0,
        }

        if len(self.records) < 2:
            return times

        for i in range(len(self.records) - 1):
            current = self.records[i]
            nxt = self.records[i + 1]
            dt = nxt.t - current.t

            if dt < 0:
                dt = 0.0

            state = current.state
            if state not in times:
                times[state] = 0.0

            times[state] += dt

        return times

    def summary(self):
        # build the final session summary
        times = self.compute_state_times()

        good_s = times.get("good", 0.0)
        bad_forward_s = times.get("bad_forward", 0.0)
        bad_left_s = times.get("bad_left", 0.0)
        bad_right_s = times.get("bad_right", 0.0)
        not_at_desk_s = times.get("not_at_desk", 0.0)
        uncalibrated_s = times.get("uncalibrated", 0.0)

        bad_total_s = bad_forward_s + bad_left_s + bad_right_s
        tracked_total_s = good_s + bad_total_s
        all_total_s = tracked_total_s + not_at_desk_s + uncalibrated_s

        bad_pct = 0.0
        if tracked_total_s > 0:
            bad_pct = (bad_total_s / tracked_total_s) * 100.0

        return {
            "frames": len(self.records),
            "duration_s": all_total_s,
            "tracked_duration_s": tracked_total_s,
            "good_s": good_s,
            "bad_total_s": bad_total_s,
            "bad_forward_s": bad_forward_s,
            "bad_left_s": bad_left_s,
            "bad_right_s": bad_right_s,
            "not_at_desk_s": not_at_desk_s,
            "uncalibrated_s": uncalibrated_s,
            "bad_pct": bad_pct,
            "state_times": times,
        }