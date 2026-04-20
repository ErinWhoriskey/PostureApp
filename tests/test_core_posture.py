from app.core_posture import (
    get_point,
    get_visibility,
    get_best_side,
    get_side_points,
    get_angle,
    get_offset,
    get_shoulder_midpoint,
    get_nose_point,
    get_nose_xy_normalised,
    get_lean_offset,
    NOSE,
    LEFT_EAR,
    RIGHT_EAR,
    LEFT_SHOULDER,
    RIGHT_SHOULDER,
)


class FakeLandmark:
    def __init__(self, x, y, visibility=1.0):
        self.x = x
        self.y = y
        self.visibility = visibility


def make_landmarks():
    landmarks = [FakeLandmark(0, 0, 0.0) for _ in range(33)]
    landmarks[NOSE] = FakeLandmark(0.50, 0.20, 1.0)
    landmarks[LEFT_EAR] = FakeLandmark(0.40, 0.30, 0.9)
    landmarks[RIGHT_EAR] = FakeLandmark(0.60, 0.30, 0.4)
    landmarks[LEFT_SHOULDER] = FakeLandmark(0.40, 0.60, 0.9)
    landmarks[RIGHT_SHOULDER] = FakeLandmark(0.60, 0.60, 0.4)
    return landmarks


def test_get_point_returns_pixel_coordinates():
    landmarks = make_landmarks()
    point = get_point(landmarks, NOSE, 100, 200)
    assert point == (50, 40)


def test_get_point_flips_x_when_requested():
    landmarks = make_landmarks()
    point = get_point(landmarks, NOSE, 100, 200, flip_x=True)
    assert point == (50, 40)


def test_get_visibility_returns_value():
    landmarks = make_landmarks()
    assert get_visibility(landmarks, LEFT_EAR) == 0.9


def test_get_best_side_returns_left_when_left_more_visible():
    landmarks = make_landmarks()
    assert get_best_side(landmarks) == "left"


def test_get_best_side_returns_right_when_right_more_visible():
    landmarks = make_landmarks()
    landmarks[RIGHT_EAR].visibility = 1.0
    landmarks[RIGHT_SHOULDER].visibility = 1.0
    landmarks[LEFT_EAR].visibility = 0.2
    landmarks[LEFT_SHOULDER].visibility = 0.2
    assert get_best_side(landmarks) == "right"


def test_get_side_points_left():
    landmarks = make_landmarks()
    ear, shoulder = get_side_points(landmarks, 100, 100, side="left")
    assert ear == (40, 30)
    assert shoulder == (40, 60)


def test_get_side_points_right():
    landmarks = make_landmarks()
    ear, shoulder = get_side_points(landmarks, 100, 100, side="right")
    assert ear == (60, 30)
    assert shoulder == (60, 60)


def test_get_angle_returns_90_when_dx_is_zero():
    ear = (40, 30)
    shoulder = (40, 60)
    assert get_angle(ear, shoulder) == 90.0


def test_get_angle_returns_expected_value():
    ear = (50, 30)
    shoulder = (40, 60)
    angle = get_angle(ear, shoulder)
    assert round(angle, 2) == 71.57


def test_get_offset_returns_horizontal_difference():
    ear = (50, 30)
    shoulder = (40, 60)
    assert get_offset(ear, shoulder) == 10.0


def test_get_shoulder_midpoint_returns_middle_point():
    landmarks = make_landmarks()
    midpoint = get_shoulder_midpoint(landmarks, 100, 100)
    assert midpoint == (50, 60)


def test_get_nose_point_returns_nose_pixel_point():
    landmarks = make_landmarks()
    nose = get_nose_point(landmarks, 100, 100)
    assert nose == (50, 20)


def test_get_nose_xy_normalised_returns_normalised_values():
    landmarks = make_landmarks()
    nose_xy = get_nose_xy_normalised(landmarks)
    assert nose_xy == (0.5, 0.2)


def test_get_nose_xy_normalised_flips_x():
    landmarks = make_landmarks()
    nose_xy = get_nose_xy_normalised(landmarks, flip_x=True)
    assert nose_xy == (0.5, 0.2)


def test_get_lean_offset_returns_difference_from_midpoint():
    nose_point = (60, 20)
    shoulder_midpoint = (50, 60)
    assert get_lean_offset(nose_point, shoulder_midpoint) == 10.0