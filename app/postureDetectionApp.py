# posture detection app
# webcam stays live
# uploaded videos are analysed offline and then stats are shown
# first 3 seconds of uploaded video are used for calibration

import cv2
import mediapipe as mp
import os
import json
import time
import threading
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except Exception:
    PIL_OK = False

from core_posture import (
    get_angle,
    get_offset,
    get_best_side,
    get_side_points,
    get_shoulder_midpoint,
    get_nose_point,
    get_nose_xy_normalised,
    get_lean_offset,
)
from settings_store import load_settings, save_settings
from session_logger import SessionLogger
from stats_view import show_stats
from audio_alert import play_alert


class AudioAlert:
    def __init__(self):
        self.enabled = True

    def play(self):
        # play the alert in a separate thread
        if not self.enabled:
            return

        threading.Thread(
            target=play_alert,
            kwargs={"audio_enabled": True},
            daemon=True,
        ).start()


class PostureTkApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Erin's Posture Detector")
        self.root.geometry("1120x720")
        self.root.minsize(980, 640)

        if not PIL_OK:
            messagebox.showerror(
                "Missing Pillow",
                "Install Pillow first so the webcam/video can show in Tkinter.\n\npip install pillow",
            )
            self.root.destroy()
            return

        # mediapipe setup
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # posture limits from calibration
        self.ANGLE_LIMIT = None
        self.OFFSET_LIMIT = None
        self.LEAN_LEFT_LIMIT = None
        self.LEAN_RIGHT_LIMIT = None
        self.HEAD_DISTANCE_LIMIT = None
        self.calibrated = False

        # runtime posture state
        self.alert_played = False
        self.bad_started_at = None
        self.bad_candidate_started_at = None
        self.pending_bad_type = None
        self.reentry_grace_until = 0.0
        self.last_angle = None
        self.last_offset = None
        self.last_lean_offset = None
        self.last_head_distance = None
        self.last_has_landmarks = False
        self.current_state = "uncalibrated"
        self.current_bad_type = None

        # capture state
        self.cap = None
        self.running = False
        self.source_mode = None
        self.source_path = None

        # fps tracking
        self._prev_time = time.time()
        self._fps = 0.0

        # session logging
        self.logger = SessionLogger()
        self.last_session_logger = None
        self.session_store_path = self._get_session_store_path()

        # audio settings
        settings = load_settings()
        self.audio = AudioAlert()
        self.audio.enabled = bool(settings.get("audio_enabled", True))

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _get_session_store_path(self):
        # save session history beside this file
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, "posture_sessions.json")

    def _build_ui(self):
        # main layout
        self.root.columnconfigure(0, weight=4)
        self.root.columnconfigure(1, weight=2)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)

        # video area
        video_frame = ttk.Frame(self.root, padding=10)
        video_frame.grid(row=0, column=0, sticky="nsew")
        video_frame.rowconfigure(0, weight=1)
        video_frame.columnconfigure(0, weight=1)

        self.video_label = ttk.Label(video_frame)
        self.video_label.grid(row=0, column=0, sticky="nsew")

        # right side info panel
        side = ttk.Frame(self.root, padding=12)
        side.grid(row=0, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)

        ttk.Label(
            side,
            text="Live Status",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.status_text = tk.StringVar(value="Camera stopped.")
        self.status_label = tk.Label(
            side,
            textvariable=self.status_text,
            wraplength=320,
            justify="left",
        )
        self.status_label.grid(row=1, column=0, sticky="w", pady=(6, 14))

        ttk.Label(
            side,
            text="Live Metrics",
            font=("Segoe UI", 12, "bold"),
        ).grid(row=2, column=0, sticky="w")

        self.metrics_text = tk.StringVar(
            value="FPS: -\nAngle: -\nForward offset: -\nLean offset: -\nHead distance: -\nLimits: -"
        )
        ttk.Label(
            side,
            textvariable=self.metrics_text,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(6, 14))

        ttk.Label(
            side,
            text="How to use",
            font=("Segoe UI", 12, "bold"),
        ).grid(row=4, column=0, sticky="w")

        help_msg = (
            "1) Click Start for webcam mode\n"
            "2) Sit upright facing forward\n"
            "3) Click Calibrate\n"
            "4) Upload Video will analyse the file and shows stats only\n"
            "5) If you leave the desk it pauses tracking and shows no body detected\n"
        )
        ttk.Label(
            side,
            text=help_msg,
            justify="left",
            wraplength=320,
        ).grid(row=5, column=0, sticky="w")

        ttk.Label(
            side,
            text="Detected posture type",
            font=("Segoe UI", 12, "bold"),
        ).grid(row=6, column=0, sticky="w", pady=(16, 0))

        self.type_text = tk.StringVar(value="-")
        ttk.Label(
            side,
            textvariable=self.type_text,
            justify="left",
            font=("Segoe UI", 11),
        ).grid(row=7, column=0, sticky="w", pady=(6, 0))

        # bottom buttons
        bottom = ttk.Frame(self.root, padding=(10, 8))
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=0)

        left_btns = ttk.Frame(bottom)
        left_btns.grid(row=0, column=0, sticky="w")

        self.start_btn = ttk.Button(left_btns, text="Start", command=self.toggle_start)
        self.start_btn.grid(row=0, column=0, padx=(0, 8))

        self.cal_btn = ttk.Button(
            left_btns,
            text="Calibrate",
            command=self.calibrate,
            state="disabled",
        )
        self.cal_btn.grid(row=0, column=1, padx=(0, 8))

        self.video_btn = ttk.Button(
            left_btns,
            text="Upload Video",
            command=self.upload_video,
        )
        self.video_btn.grid(row=0, column=2, padx=(0, 8))

        self.stats_btn = ttk.Button(left_btns, text="Stats", command=self.open_stats)
        self.stats_btn.grid(row=0, column=3, padx=(0, 8))

        self.quit_btn = ttk.Button(left_btns, text="Quit", command=self.on_close)
        self.quit_btn.grid(row=0, column=4)

        self.settings_btn = ttk.Button(
            bottom,
            text="Settings",
            command=self.open_settings,
        )
        self.settings_btn.grid(row=0, column=1, sticky="e")

    def _set_status(self, msg, colour="black"):
        # update the status text
        self.status_text.set(msg)
        try:
            self.status_label.configure(fg=colour)
        except Exception:
            pass

    def _set_type_text(self, text):
        # update the posture type text
        self.type_text.set(text)

    def _reset_runtime_state(self):
        # clear runtime values for a fresh session
        self.alert_played = False
        self.bad_started_at = None
        self.bad_candidate_started_at = None
        self.pending_bad_type = None
        self.reentry_grace_until = 0.0
        self.last_angle = None
        self.last_offset = None
        self.last_lean_offset = None
        self.last_head_distance = None
        self.last_has_landmarks = False
        self.current_state = "uncalibrated"
        self.current_bad_type = None
        self._prev_time = time.time()
        self._fps = 0.0

    def _get_point_distance(self, p1, p2):
        # get the distance between two points
        if p1 is None or p2 is None:
            return None

        return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

    def toggle_start(self):
        # start or stop webcam mode
        if self.running:
            self.stop_capture()
        else:
            self.start_camera()

    def start_camera(self):
        # start live webcam capture
        if self.running:
            return

        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Camera error", "Could not open webcam.")
            self.cap = None
            return

        self.source_mode = "webcam"
        self.source_path = None
        self.running = True
        self.start_btn.configure(text="Stop")
        self.cal_btn.configure(state="normal")
        self.logger = SessionLogger()
        self._reset_runtime_state()
        self._set_status("Camera running. Sit upright and click Calibrate.")
        self._set_type_text("Waiting for posture...")
        self._update_loop()

    def upload_video(self):
        # choose and analyse a video file
        path = filedialog.askopenfilename(
            title="Select a video file",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.avi *.mkv *.m4v"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        if self.running:
            self.stop_capture()

        self._analyse_uploaded_video(path)

    def _get_frame_metrics(self, frame, flip_x=False):
        # get posture numbers from a single frame
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)

        if not results.pose_landmarks:
            return None

        lm = results.pose_landmarks.landmark
        side = get_best_side(lm)

        ear, shoulder = get_side_points(lm, w, h, flip_x=flip_x, side=side)
        nose_point = get_nose_point(lm, w, h, flip_x=flip_x)
        shoulder_mid = get_shoulder_midpoint(lm, w, h, flip_x=flip_x)
        nose_xy = get_nose_xy_normalised(lm, flip_x=flip_x)

        angle = get_angle(ear, shoulder)
        offset = get_offset(ear, shoulder)
        lean_offset = get_lean_offset(nose_point, shoulder_mid)
        head_distance = self._get_point_distance(nose_point, shoulder_mid)

        left_shoulder = (
            int(lm[self.mp_pose.PoseLandmark.LEFT_SHOULDER].x * w),
            int(lm[self.mp_pose.PoseLandmark.LEFT_SHOULDER].y * h),
        )
        right_shoulder = (
            int(lm[self.mp_pose.PoseLandmark.RIGHT_SHOULDER].x * w),
            int(lm[self.mp_pose.PoseLandmark.RIGHT_SHOULDER].y * h),
        )
        shoulder_tilt = left_shoulder[1] - right_shoulder[1]

        return {
            "angle": angle,
            "offset": offset,
            "lean_offset": lean_offset,
            "head_distance": head_distance,
            "nose_xy": nose_xy,
            "shoulder_tilt": shoulder_tilt,
        }

    def _detect_posture_state(
        self,
        angle,
        offset,
        lean_offset,
        head_distance,
        shoulder_tilt=None,
    ):
        # decide which posture state the frame is in
        if not self.calibrated:
            return "uncalibrated", None

        if (
            head_distance is not None
            and self.HEAD_DISTANCE_LIMIT is not None
            and head_distance < self.HEAD_DISTANCE_LIMIT
        ):
            return "bad_forward", "Forward posture"

        if offset is not None and offset > self.OFFSET_LIMIT:
            return "bad_forward", "Forward posture"

        if lean_offset is not None and lean_offset < self.LEAN_LEFT_LIMIT:
            return "bad_left", "Left lean"

        if lean_offset is not None and lean_offset > self.LEAN_RIGHT_LIMIT:
            return "bad_right", "Right lean"

        if shoulder_tilt is not None:
            if shoulder_tilt < -22:
                return "bad_left", "Left lean"
            if shoulder_tilt > 22:
                return "bad_right", "Right lean"

        if angle is not None and angle < self.ANGLE_LIMIT:
            return "bad_forward", "Forward posture"

        return "good", "Good posture"

    def _analyse_uploaded_video(self, path):
        # analyse an uploaded file offline
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            messagebox.showerror("Video error", "Could not open that video file.")
            return

        self.source_mode = "video"
        self.source_path = path
        self.logger = SessionLogger()
        self._reset_runtime_state()
        self._set_status("Analysing uploaded video...")
        self._set_type_text("Analysing...")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 1 or fps > 240:
            fps = 30.0

        calibration_seconds = 3.0
        reentry_seconds = 2.5
        confirm_seconds = 2.0

        calibration_frames = int(fps * calibration_seconds)
        reentry_frames = int(fps * reentry_seconds)
        confirm_frames = int(fps * confirm_seconds)

        frame_index = 0
        no_body_until_frame = -1
        bad_candidate_start_frame = None
        pending_bad_type = None

        calib_angles = []
        calib_offsets = []
        calib_leans = []
        calib_head_dists = []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            total_frames = None

        progress_win = tk.Toplevel(self.root)
        progress_win.title("Analysing video")
        progress_win.resizable(False, False)
        progress_win.transient(self.root)

        progress_label = ttk.Label(progress_win, text="Analysing uploaded video...")
        progress_label.pack(padx=14, pady=(14, 8))

        progress_var = tk.DoubleVar(value=0)
        progress = ttk.Progressbar(
            progress_win,
            variable=progress_var,
            maximum=100,
            length=320,
        )
        progress.pack(padx=14, pady=(0, 14))

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                metrics = self._get_frame_metrics(frame, flip_x=False)

                if metrics is None:
                    self.logger.add(
                        state="not_at_desk",
                        angle=None,
                        offset=None,
                        lean_offset=None,
                        nose_xy=None,
                    )
                    no_body_until_frame = frame_index + reentry_frames
                    bad_candidate_start_frame = None
                    pending_bad_type = None
                    frame_index += 1

                    if total_frames:
                        progress_var.set((frame_index / total_frames) * 100.0)
                        progress_label.configure(
                            text="Analysing uploaded video... "
                            + str(int(progress_var.get()))
                            + "%"
                        )
                        progress_win.update()

                    continue

                angle = metrics["angle"]
                offset = metrics["offset"]
                lean_offset = metrics["lean_offset"]
                head_distance = metrics["head_distance"]
                nose_xy = metrics["nose_xy"]
                shoulder_tilt = metrics["shoulder_tilt"]

                # use the first few seconds to calibrate
                if frame_index < calibration_frames:
                    calib_angles.append(angle)
                    calib_offsets.append(offset)
                    calib_leans.append(lean_offset)
                    calib_head_dists.append(head_distance)

                    self.logger.add(
                        state="uncalibrated",
                        angle=angle,
                        offset=offset,
                        lean_offset=lean_offset,
                        nose_xy=nose_xy,
                    )
                    frame_index += 1

                    if total_frames:
                        progress_var.set((frame_index / total_frames) * 100.0)
                        progress_label.configure(
                            text="Analysing uploaded video... "
                            + str(int(progress_var.get()))
                            + "%"
                        )
                        progress_win.update()

                    continue

                if not self.calibrated:
                    valid_angles = [v for v in calib_angles if v is not None]
                    valid_offsets = [v for v in calib_offsets if v is not None]
                    valid_leans = [v for v in calib_leans if v is not None]
                    valid_heads = [v for v in calib_head_dists if v is not None]

                    if (
                        not valid_angles
                        or not valid_offsets
                        or not valid_leans
                        or not valid_heads
                    ):
                        messagebox.showerror(
                            "Calibration failed",
                            "Could not calibrate from the first 3 seconds of the uploaded video.",
                        )
                        cap.release()
                        progress_win.destroy()
                        return

                    upright_angle = sum(valid_angles) / len(valid_angles)
                    upright_offset = sum(valid_offsets) / len(valid_offsets)
                    upright_lean = sum(valid_leans) / len(valid_leans)
                    upright_head_distance = sum(valid_heads) / len(valid_heads)

                    self.ANGLE_LIMIT = upright_angle - 15
                    self.OFFSET_LIMIT = upright_offset + 28
                    self.LEAN_LEFT_LIMIT = upright_lean - 40
                    self.LEAN_RIGHT_LIMIT = upright_lean + 40
                    self.HEAD_DISTANCE_LIMIT = upright_head_distance - 50
                    self.calibrated = True

                # if the user leaves the frame wait a bit before checking again
                if frame_index <= no_body_until_frame:
                    self.logger.add(
                        state="not_at_desk",
                        angle=angle,
                        offset=offset,
                        lean_offset=lean_offset,
                        nose_xy=nose_xy,
                    )
                    bad_candidate_start_frame = None
                    pending_bad_type = None
                    frame_index += 1

                    if total_frames:
                        progress_var.set((frame_index / total_frames) * 100.0)
                        progress_label.configure(
                            text="Analysing uploaded video... "
                            + str(int(progress_var.get()))
                            + "%"
                        )
                        progress_win.update()

                    continue

                posture_state, _ = self._detect_posture_state(
                    angle,
                    offset,
                    lean_offset,
                    head_distance,
                    shoulder_tilt,
                )

                if posture_state == "good":
                    self.logger.add(
                        state="good",
                        angle=angle,
                        offset=offset,
                        lean_offset=lean_offset,
                        nose_xy=nose_xy,
                    )
                    bad_candidate_start_frame = None
                    pending_bad_type = None
                else:
                    if pending_bad_type != posture_state:
                        pending_bad_type = posture_state
                        bad_candidate_start_frame = frame_index

                    if (
                        bad_candidate_start_frame is not None
                        and (frame_index - bad_candidate_start_frame) >= confirm_frames
                    ):
                        self.logger.add(
                            state=posture_state,
                            angle=angle,
                            offset=offset,
                            lean_offset=lean_offset,
                            nose_xy=nose_xy,
                        )
                    else:
                        self.logger.add(
                            state="good",
                            angle=angle,
                            offset=offset,
                            lean_offset=lean_offset,
                            nose_xy=nose_xy,
                        )

                frame_index += 1

                if total_frames:
                    progress_var.set((frame_index / total_frames) * 100.0)
                    progress_label.configure(
                        text="Analysing uploaded video... "
                        + str(int(progress_var.get()))
                        + "%"
                    )
                    progress_win.update()

        finally:
            cap.release()
            try:
                progress_win.destroy()
            except Exception:
                pass

        self.last_session_logger = self.logger
        self._save_session_to_json(self.logger)
        self._set_status("Uploaded video analysed. Stats are ready.", "green")
        self._set_type_text("Analysis complete")
        self.metrics_text.set(
            "FPS: source "
            + str(round(fps, 2))
            + "\nAngle: -\nForward offset: -\nLean offset: -\nHead distance: -\nLimits: video analysis used"
        )
        self.open_stats()

    def _save_session_to_json(self, logger_to_save):
        # save a session summary to the json history file
        if logger_to_save is None or not logger_to_save.has_records():
            return

        summary = logger_to_save.summary()
        session_entry = {
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source_mode": self.source_mode,
            "source_path": self.source_path,
            "frames": summary.get("frames", 0),
            "duration_s": summary.get("duration_s", 0.0),
            "tracked_duration_s": summary.get("tracked_duration_s", 0.0),
            "good_s": summary.get("good_s", 0.0),
            "bad_total_s": summary.get("bad_total_s", 0.0),
            "bad_forward_s": summary.get("bad_forward_s", 0.0),
            "bad_left_s": summary.get("bad_left_s", 0.0),
            "bad_right_s": summary.get("bad_right_s", 0.0),
            "not_at_desk_s": summary.get("not_at_desk_s", 0.0),
            "uncalibrated_s": summary.get("uncalibrated_s", 0.0),
            "bad_pct": summary.get("bad_pct", 0.0),
        }

        data = []
        if os.path.exists(self.session_store_path):
            try:
                with open(self.session_store_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    data = loaded
            except Exception:
                data = []

        data.append(session_entry)

        try:
            with open(self.session_store_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def stop_capture(self):
        # stop webcam capture and save the session
        if not self.running:
            return

        saved_logger = self.logger
        saved_source_mode = self.source_mode
        saved_source_path = self.source_path

        self.running = False
        self.start_btn.configure(text="Start")
        self.cal_btn.configure(state="disabled")

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        self.last_session_logger = saved_logger
        self.source_mode = saved_source_mode
        self.source_path = saved_source_path
        self._save_session_to_json(saved_logger)

        self.source_mode = None
        self.source_path = None
        self._reset_runtime_state()
        self._set_status("Camera/video stopped.")
        self._set_type_text("-")
        self.metrics_text.set(
            "FPS: -\nAngle: -\nForward offset: -\nLean offset: -\nHead distance: -\nLimits: -"
        )
        self.video_label.configure(image="")
        self.video_label.image = None

    def open_stats(self):
        # open the stats window
        logger_to_show = self.logger if self.running else self.last_session_logger
        if logger_to_show is None:
            logger_to_show = SessionLogger()

        show_stats(self.root, logger_to_show, self.session_store_path)

    def calibrate(self):
        # save the current upright posture as the baseline
        if not self.running:
            return

        if (
            not self.last_has_landmarks
            or self.last_angle is None
            or self.last_offset is None
            or self.last_lean_offset is None
            or self.last_head_distance is None
        ):
            messagebox.showwarning(
                "Calibration",
                "No body is detected yet. Move into view and try again.",
            )
            return

        upright_angle = self.last_angle
        upright_offset = self.last_offset
        upright_lean = self.last_lean_offset
        upright_head_distance = self.last_head_distance

        self.ANGLE_LIMIT = upright_angle - 15
        self.OFFSET_LIMIT = upright_offset + 28
        self.LEAN_LEFT_LIMIT = upright_lean - 40
        self.LEAN_RIGHT_LIMIT = upright_lean + 40
        self.HEAD_DISTANCE_LIMIT = upright_head_distance - 50
        self.calibrated = True
        self.alert_played = False
        self.bad_started_at = None

        self._set_status(
            "Calibrated. It will now track good posture, forward posture, left lean, and right lean.",
            "green",
        )
        self._set_type_text("Good posture")
        self._update_metrics_text()

    def _update_metrics_text(self):
        # refresh the live metrics text
        limits = "-"
        if self.calibrated:
            limits = (
                "Angle<"
                + str(int(self.ANGLE_LIMIT))
                + " | Forward>"
                + str(int(self.OFFSET_LIMIT))
                + " | Left<"
                + str(int(self.LEAN_LEFT_LIMIT))
                + " | Right>"
                + str(int(self.LEAN_RIGHT_LIMIT))
                + " | Head<"
                + str(int(self.HEAD_DISTANCE_LIMIT))
            )

        angle_text = "-" if self.last_angle is None else str(int(self.last_angle))
        offset_text = "-" if self.last_offset is None else str(int(self.last_offset))
        lean_text = "-" if self.last_lean_offset is None else str(int(self.last_lean_offset))
        head_text = "-" if self.last_head_distance is None else str(int(self.last_head_distance))

        self.metrics_text.set(
            "FPS: "
            + str(round(self._fps, 1))
            + "\nAngle: "
            + angle_text
            + "\nForward offset: "
            + offset_text
            + "\nLean offset: "
            + lean_text
            + "\nHead distance: "
            + head_text
            + "\nLimits: "
            + limits
        )

    def _draw_overlay_box(self, frame, title_text, subtitle_text=None):
       
        h, w, _ = frame.shape

        x = w - 320
        y = 40

        cv2.putText(
            frame,
            title_text,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (255, 255, 255),
            2,
        )

        if subtitle_text:
            cv2.putText(
                frame,
                subtitle_text,
                (x, y + 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

    def _handle_bad_posture(self, frame, state, bad_label):
        # confirm bad posture before counting it fully
        now = time.time()

        if self.pending_bad_type != state:
            self.pending_bad_type = state
            self.bad_candidate_started_at = now
            self.bad_started_at = None
            self.alert_played = False

        confirm_seconds = 2.0
        candidate_elapsed = 0.0
        if self.bad_candidate_started_at is not None:
            candidate_elapsed = now - self.bad_candidate_started_at

        if candidate_elapsed < confirm_seconds:
            self.current_bad_type = None
            self._draw_overlay_box(frame, "CHECKING POSTURE", bad_label)
            self._set_status("Posture changed. Waiting to confirm...", "orange")
            self._set_type_text("Checking " + bad_label)
            return False

        if self.bad_started_at is None:
            self.bad_started_at = now

        elapsed = now - self.bad_started_at
        self.current_bad_type = bad_label

        if elapsed >= 6 and not self.alert_played:
            self.audio.play()
            self.alert_played = True

        title = "BAD POSTURE"
        subtitle = bad_label
        if elapsed >= 10:
            subtitle = bad_label + " - please sit upright"

        self._draw_overlay_box(frame, title, subtitle)
        self._set_status(bad_label + " detected.", "red")
        self._set_type_text(bad_label)
        return True

    def _handle_good_posture(self):
        # clear bad posture timers and state
        self.bad_started_at = None
        self.bad_candidate_started_at = None
        self.pending_bad_type = None
        self.alert_played = False
        self.current_bad_type = None
        self._set_status("Good posture.", "green")
        self._set_type_text("Good posture")

    def _handle_no_person(self, frame):
        # pause tracking if no person is visible
        self.last_angle = None
        self.last_offset = None
        self.last_lean_offset = None
        self.last_head_distance = None
        self.current_state = "not_at_desk"
        self.alert_played = False
        self.bad_started_at = None
        self.bad_candidate_started_at = None
        self.pending_bad_type = None
        self.reentry_grace_until = time.time() + 2.5

        self.logger.add(
            state="not_at_desk",
            angle=None,
            offset=None,
            lean_offset=None,
            nose_xy=None,
        )
        self._draw_overlay_box(
            frame,
            "NO BODY DETECTED",
            "Tracking paused until a person returns",
        )
        self._set_status("No body detected in the frame. Tracking is paused.")
        self._set_type_text("Not at desk")
        self._update_metrics_text()

    def _update_loop(self):
        # main live webcam loop
        if not self.running or self.cap is None:
            return

        ok, frame = self.cap.read()
        if not ok:
            self._set_status("Could not read from camera.")
            self.stop_capture()
            return

        if self.source_mode == "webcam":
            frame = cv2.flip(frame, 1)

        now = time.time()
        dt = now - self._prev_time
        self._prev_time = now
        if dt > 0:
            inst = 1.0 / dt
            self._fps = (0.90 * self._fps) + (0.10 * inst)

        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)
        self.last_has_landmarks = bool(results.pose_landmarks)

        if results.pose_landmarks:
            try:
                self.mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing.DrawingSpec(
                        color=(0, 255, 0),
                        thickness=3,
                        circle_radius=3,
                    ),
                    connection_drawing_spec=self.mp_drawing.DrawingSpec(
                        color=(255, 255, 255),
                        thickness=2,
                    ),
                )
            except Exception:
                pass

            lm = results.pose_landmarks.landmark
            side = get_best_side(lm)

            ear, shoulder = get_side_points(lm, w, h, flip_x=False, side=side)
            nose_point = get_nose_point(lm, w, h, flip_x=False)
            shoulder_mid = get_shoulder_midpoint(lm, w, h, flip_x=False)
            nose_xy = get_nose_xy_normalised(lm, flip_x=False)

            left_shoulder_point = (
                int(lm[self.mp_pose.PoseLandmark.LEFT_SHOULDER].x * w),
                int(lm[self.mp_pose.PoseLandmark.LEFT_SHOULDER].y * h),
            )
            right_shoulder_point = (
                int(lm[self.mp_pose.PoseLandmark.RIGHT_SHOULDER].x * w),
                int(lm[self.mp_pose.PoseLandmark.RIGHT_SHOULDER].y * h),
            )
            shoulder_tilt = left_shoulder_point[1] - right_shoulder_point[1]

            angle = get_angle(ear, shoulder)
            offset = get_offset(ear, shoulder)
            lean_offset = get_lean_offset(nose_point, shoulder_mid)
            head_distance = self._get_point_distance(nose_point, shoulder_mid)

            self.last_angle = angle
            self.last_offset = offset
            self.last_lean_offset = lean_offset
            self.last_head_distance = head_distance
            self._update_metrics_text()

            cv2.circle(frame, ear, 5, (0, 255, 0), -1)
            cv2.circle(frame, shoulder, 5, (255, 0, 0), -1)
            cv2.circle(frame, nose_point, 5, (0, 255, 255), -1)
            cv2.circle(frame, shoulder_mid, 5, (255, 255, 0), -1)
            cv2.line(frame, nose_point, shoulder_mid, (0, 255, 255), 2)

            posture_state, label_text = self._detect_posture_state(
                angle,
                offset,
                lean_offset,
                head_distance,
                shoulder_tilt,
            )

            now = time.time()
            if now < self.reentry_grace_until:
                self.current_state = "not_at_desk"
                self.logger.add(
                    state="not_at_desk",
                    angle=angle,
                    offset=offset,
                    lean_offset=lean_offset,
                    nose_xy=nose_xy,
                )
                self.bad_started_at = None
                self.bad_candidate_started_at = None
                self.pending_bad_type = None
                self.alert_played = False
                self._draw_overlay_box(frame, "BODY DETECTED", "Stabilising tracking...")
                self._set_status("Body detected. Waiting a moment before posture checks.")
                self._set_type_text("Stabilising")
            elif posture_state == "good":
                self.current_state = "good"
                self.logger.add(
                    state="good",
                    angle=angle,
                    offset=offset,
                    lean_offset=lean_offset,
                    nose_xy=nose_xy,
                )
                self._handle_good_posture()
                self._draw_overlay_box(frame, "GOOD POSTURE")
            elif posture_state == "uncalibrated":
                self.current_state = "uncalibrated"
                self.logger.add(
                    state="uncalibrated",
                    angle=angle,
                    offset=offset,
                    lean_offset=lean_offset,
                    nose_xy=nose_xy,
                )
                self.alert_played = False
                self.bad_started_at = None
                self.bad_candidate_started_at = None
                self.pending_bad_type = None
                self._set_status("Not calibrated yet. Sit upright and click Calibrate.")
                self._set_type_text("Waiting for calibration")
                self._draw_overlay_box(frame, "WAITING", "FOR CALIBRATION")
            else:
                confirmed = self._handle_bad_posture(frame, posture_state, label_text)
                if confirmed:
                    self.current_state = posture_state
                    self.logger.add(
                        state=posture_state,
                        angle=angle,
                        offset=offset,
                        lean_offset=lean_offset,
                        nose_xy=nose_xy,
                    )
                else:
                    self.current_state = "good"
                    self.logger.add(
                        state="good",
                        angle=angle,
                        offset=offset,
                        lean_offset=lean_offset,
                        nose_xy=nose_xy,
                    )
        else:
            self._handle_no_person(frame)

        cv2.putText(
            frame,
            "FPS: " + str(round(self._fps, 1)),
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
        )

        rgb_show = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_show)
        label_w = max(1, self.video_label.winfo_width())
        label_h = max(1, self.video_label.winfo_height())
        img = img.resize((label_w, label_h))
        imgtk = ImageTk.PhotoImage(image=img)

        self.video_label.configure(image=imgtk)
        self.video_label.image = imgtk

        self.root.after(15, self._update_loop)

    def open_settings(self):
        # simple settings window for audio on or off
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)

        audio_enabled_var = tk.BooleanVar(value=self.audio.enabled)

        ttk.Label(
            frm,
            text="Audio alerts",
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        ttk.Checkbutton(
            frm,
            text="Enable posture beep",
            variable=audio_enabled_var,
        ).grid(row=1, column=0, sticky="w", pady=(0, 10))

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, sticky="e", pady=(14, 0))

        def apply_settings(close_after=False):
            self.audio.enabled = bool(audio_enabled_var.get())
            save_settings({"audio_enabled": self.audio.enabled})
            if close_after:
                win.destroy()

        def test_sound():
            if audio_enabled_var.get():
                self.audio.play()

        ttk.Button(btns, text="Test", command=test_sound).grid(
            row=0,
            column=0,
            padx=(0, 8),
        )
        ttk.Button(
            btns,
            text="Apply",
            command=lambda: apply_settings(False),
        ).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(
            btns,
            text="OK",
            command=lambda: apply_settings(True),
        ).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=win.destroy).grid(row=0, column=3)

    def on_close(self):
        # close the app safely
        try:
            if self.running:
                self.stop_capture()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass


def main():
    root = tk.Tk()
    style = ttk.Style()

    try:
        style.theme_use("clam")
    except Exception:
        pass

    PostureTkApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()