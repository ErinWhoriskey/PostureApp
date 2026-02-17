# Erin's Posture Detector CA3 (Final)
# This is my final posture detection app for CA3.
# It uses two points: my ear and my shoulder.
# I calculate the angle between them and how far forward my head is.
# I compare these with my calibrated upright posture.
# If either goes outside the limits, it shows BAD POSTURE and plays a beep.


import cv2
import mediapipe as mp
import math
import winsound
import threading

# use pose model to get points
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

# point indexes I use (ear + shoulder)
LEFT_EAR = 7
LEFT_SHOULDER = 11

# limits set during calibration
ANGLE_LIMIT = None
OFFSET_LIMIT = None

calibrated = False
alert_played = False

# work out the angle between ear and shoulder
def get_angle(ear, shoulder):
    dx = ear[0] - shoulder[0]
    dy = shoulder[1] - ear[1]
    angle_value = math.degrees(math.atan2(dy, dx))
    return abs(angle_value)

# how far forward my head is 
def get_offset(ear, shoulder):
    return abs(ear[0] - shoulder[0])

cap = cv2.VideoCapture(0)

while True:
    ok, frame = cap.read()
    if not ok:
        break

    frame = cv2.flip(frame, 1)  # flip webcam so it looks normal
    h, w, _ = frame.shape

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb)

    if results.pose_landmarks:

        # get the points from mediapipe
        lm = results.pose_landmarks.landmark

        # flip the x values because the camera is flipped
        ear_x = 1 - lm[LEFT_EAR].x
        shoulder_x = 1 - lm[LEFT_SHOULDER].x

        # turn normalised points into screen positions
        ear = (int(ear_x * w), int(lm[LEFT_EAR].y * h))
        shoulder = (int(shoulder_x * w), int(lm[LEFT_SHOULDER].y * h))

        # calculate angle + offset like I said in CA2
        angle = get_angle(ear, shoulder)
        offset = get_offset(ear, shoulder)

        # text row at top (simple)
        top_text = "Angle: " + str(int(angle))
        if calibrated:
            top_text = top_text + " | Limit: " + str(int(ANGLE_LIMIT)) + " | Offset: " + str(int(offset)) + " | OffsetLimit: " + str(int(OFFSET_LIMIT))
        else:
            top_text = top_text + " | Offset: " + str(int(offset))

        cv2.putText(frame, top_text, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 1)

        # if not calibrated tell user to press C
        if not calibrated:
            cv2.putText(frame, "Press C to set your upright posture", (15, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)

        # posture check
        if calibrated:

            bad = False

            # angle too low = leaning neck
            if angle < ANGLE_LIMIT:
                bad = True

            # head too far forward
            if offset > OFFSET_LIMIT:
                bad = True

            if bad:
                # show warning in the middle
                txt = "BAD POSTURE"
                size = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 2.2, 5)[0]
                x = (w - size[0]) // 2
                y = h // 2

                cv2.putText(frame, txt, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (0,0,255), 5)

                # sound only once per posture event (threading so no freeze)
                if alert_played == False:
                    threading.Thread(target=winsound.Beep, args=(1500, 200)).start()
                    alert_played = True
            else:
                alert_played = False

        # draw the two points
        cv2.circle(frame, ear, 5, (0,255,0), -1)
        cv2.circle(frame, shoulder, 5, (255,0,0), -1)

    cv2.imshow("Erin's Posture Detector CA3", frame)

    key = cv2.waitKey(1) & 0xFF

    # calibration
    if key == ord('c') and results.pose_landmarks:
        upright_angle = angle
        upright_offset = offset

        ANGLE_LIMIT = upright_angle - 10     # small tolerance
        OFFSET_LIMIT = upright_offset + 20   # small tolerance

        calibrated = True
        print("Calibrated")
        print("Angle limit:", ANGLE_LIMIT)
        print("Offset limit:", OFFSET_LIMIT)

    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
