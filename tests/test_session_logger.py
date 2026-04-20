from app.session_logger import SessionLogger



def test_reset_clears_records():
    logger = SessionLogger()
    logger.records = ["something"]
    logger.reset()
    assert logger.records == []


def test_add_creates_record():
    logger = SessionLogger()
    logger.add(state="good", angle=90, offset=10, lean_offset=0, nose_xy=(0.5, 0.2))

    assert len(logger.records) == 1
    record = logger.records[0]
    assert record.state == "good"
    assert record.angle == 90.0
    assert record.offset == 10.0
    assert record.lean_offset == 0.0
    assert record.nose_xy == (0.5, 0.2)


def test_has_records_false_for_zero_or_one_record():
    logger = SessionLogger()
    assert logger.has_records() is False

    logger.add(state="good")
    assert logger.has_records() is False


def test_has_records_true_for_more_than_one_record():
    logger = SessionLogger()
    logger.add(state="good")
    logger.add(state="bad_forward")
    assert logger.has_records() is True


def test_compute_state_times_empty_when_not_enough_records():
    logger = SessionLogger()
    times = logger.compute_state_times()

    assert times["good"] == 0.0
    assert times["bad_forward"] == 0.0
    assert times["bad_left"] == 0.0
    assert times["bad_right"] == 0.0
    assert times["not_at_desk"] == 0.0
    assert times["uncalibrated"] == 0.0


def test_compute_state_times_uses_record_differences():
    logger = SessionLogger()
    logger.add(state="good")
    logger.add(state="bad_forward")
    logger.add(state="bad_left")

    logger.records[0].t = 0.0
    logger.records[1].t = 2.0
    logger.records[2].t = 5.0

    times = logger.compute_state_times()

    assert times["good"] == 2.0
    assert times["bad_forward"] == 3.0
    assert times["bad_left"] == 0.0


def test_compute_state_times_ignores_negative_time_gap():
    logger = SessionLogger()
    logger.add(state="good")
    logger.add(state="bad_forward")

    logger.records[0].t = 5.0
    logger.records[1].t = 3.0

    times = logger.compute_state_times()
    assert times["good"] == 0.0


def test_summary_returns_expected_values():
    logger = SessionLogger()
    logger.add(state="good")
    logger.add(state="bad_forward")
    logger.add(state="bad_left")
    logger.add(state="not_at_desk")
    logger.add(state="uncalibrated")

    logger.records[0].t = 0.0
    logger.records[1].t = 2.0
    logger.records[2].t = 5.0
    logger.records[3].t = 9.0
    logger.records[4].t = 12.0

    summary = logger.summary()

    assert summary["frames"] == 5
    assert summary["good_s"] == 2.0
    assert summary["bad_forward_s"] == 3.0
    assert summary["bad_left_s"] == 4.0
    assert summary["bad_right_s"] == 0.0
    assert summary["not_at_desk_s"] == 3.0
    assert summary["uncalibrated_s"] == 0.0
    assert summary["bad_total_s"] == 7.0
    assert summary["tracked_duration_s"] == 9.0
    assert summary["duration_s"] == 12.0
    assert round(summary["bad_pct"], 2) == 77.78