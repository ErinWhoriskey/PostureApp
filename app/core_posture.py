# core posture calculations

# keeps the maths in one place so the gui file stays cleaner

import math


# mediapipe pose indexes
NOSE = 0
LEFT_EAR = 7
RIGHT_EAR = 8
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12


def get_point(landmarks, index, w, h, flip_x=False):
    # turn a mediapipe landmark into pixel x and y
    x = landmarks[index].x
    y = landmarks[index].y

    if flip_x:
        x = 1 - x

    return (int(x * w), int(y * h))


def get_visibility(landmarks, index):
    # get landmark visibility safely
    try:
        return float(landmarks[index].visibility)
    except Exception:
        return 0.0


def get_best_side(landmarks):
    # pick the side with the best visibility
    left_score = get_visibility(landmarks, LEFT_EAR) + get_visibility(
        landmarks, LEFT_SHOULDER
    )
    right_score = get_visibility(landmarks, RIGHT_EAR) + get_visibility(
        landmarks, RIGHT_SHOULDER
    )

    if right_score > left_score:
        return "right"

    return "left"


def get_side_points(landmarks, w, h, flip_x=False, side="left"):
    # get ear and shoulder for the chosen side
    if side == "right":
        ear = get_point(landmarks, RIGHT_EAR, w, h, flip_x)
        shoulder = get_point(landmarks, RIGHT_SHOULDER, w, h, flip_x)
    else:
        ear = get_point(landmarks, LEFT_EAR, w, h, flip_x)
        shoulder = get_point(landmarks, LEFT_SHOULDER, w, h, flip_x)

    return ear, shoulder


def get_angle(ear, shoulder):
    # work out the neck angle
    dx = ear[0] - shoulder[0]
    dy = shoulder[1] - ear[1]

    if dx == 0:
        return 90.0

    angle_value = math.degrees(math.atan2(dy, dx))
    return abs(float(angle_value))


def get_offset(ear, shoulder):
    # forward posture check using horizontal distance
    return abs(float(ear[0] - shoulder[0]))


def get_shoulder_midpoint(landmarks, w, h, flip_x=False):
    # get the middle point between both shoulders
    left_shoulder = get_point(landmarks, LEFT_SHOULDER, w, h, flip_x)
    right_shoulder = get_point(landmarks, RIGHT_SHOULDER, w, h, flip_x)

    mid_x = int((left_shoulder[0] + right_shoulder[0]) / 2)
    mid_y = int((left_shoulder[1] + right_shoulder[1]) / 2)

    return (mid_x, mid_y)


def get_nose_point(landmarks, w, h, flip_x=False):
    # get the nose point in pixels
    return get_point(landmarks, NOSE, w, h, flip_x)


def get_nose_xy_normalised(landmarks, flip_x=False):
    # get the nose point in normalised values
    x = float(landmarks[NOSE].x)
    y = float(landmarks[NOSE].y)

    if flip_x:
        x = 1 - x

    return (x, y)


def get_lean_offset(nose_point, shoulder_midpoint):
    # negative means left and positive means right on the displayed frame
    return float(nose_point[0] - shoulder_midpoint[0])