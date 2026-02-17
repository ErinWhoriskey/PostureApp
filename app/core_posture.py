# Core posture calculations (keeps original logic)
import math

LEFT_EAR = 7
LEFT_SHOULDER = 11

def get_angle(ear, shoulder):
    dx = shoulder[0] - ear[0]
    dy = shoulder[1] - ear[1]
    # same simple angle logic (avoid divide by zero)
    if dx == 0:
        return 90
    angle = abs(math.degrees(math.atan2(dy, dx)))
    return int(angle)

def get_offset(ear, shoulder):
    # horizontal distance in pixels
    return abs(shoulder[0] - ear[0])
