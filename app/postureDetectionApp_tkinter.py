# Erin's Posture Detector (Tkinter GUI)
# Keeps the same posture logic 
# Added: Tkinter GUI + Settings (bottom-right) to enable/disable audio + adjust alert "volume".

import cv2
import mediapipe as mp

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
import math
import threading
import time
import json
import os
import io
import wave
import struct
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except Exception:
    PIL_OK = False

from core_posture import LEFT_EAR, LEFT_SHOULDER, get_angle, get_offset
from settings_store import load_settings, save_settings
from audio_alert import play_alert, test_alert
from session_logger import SessionLogger
from stats_view import show_stats


# Core posture logic (same as my original code)


LEFT_EAR = 7
LEFT_SHOULDER = 11

def get_angle(ear, shoulder):
    dx = ear[0] - shoulder[0]
    dy = shoulder[1] - ear[1]
    angle_value = math.degrees(math.atan2(dy, dx))
    return abs(angle_value)

def get_offset(ear, shoulder):
    return abs(ear[0] - shoulder[0])


# Audio helper 


def _make_tone_wav_bytes(freq_hz=1500, duration_s=0.20, sample_rate=44100, amplitude=0.6):
    
    n_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  
        wf.setframerate(sample_rate)
        max_amp = int(32767 * max(0.0, min(1.0, amplitude)))
        for i in range(n_samples):
            t = i / sample_rate
            sample = int(max_amp * math.sin(2.0 * math.pi * freq_hz * t))
            wf.writeframes(struct.pack('<h', sample))
    return buf.getvalue()

class AudioAlert:
    def __init__(self):
        self.enabled = True
        self.volume = 70  # 0-100
        self._tone_bytes = None

        self._is_windows = (os.name == 'nt')
        if self._is_windows:
            import winsound  # only available on Windows
            import ctypes
            self._winsound = winsound
            self._ctypes = ctypes

    def _get_system_wave_volume(self):
        
        try:
            vol = self._ctypes.c_uint()
            self._ctypes.windll.winmm.waveOutGetVolume(0, self._ctypes.byref(vol))
            left = vol.value & 0xFFFF
            right = (vol.value >> 16) & 0xFFFF
            return left, right
        except Exception:
            return None

    def _set_system_wave_volume(self, left, right):
        try:
            vol = (int(right) << 16) | int(left)
            self._ctypes.windll.winmm.waveOutSetVolume(0, vol)
            return True
        except Exception:
            return False

    def play(self):
        if not self.enabled:
            return

        # Run in thread so GUI never freezes
        threading.Thread(target=self._play_thread, daemon=True).start()

    def _play_thread(self):
        
        if self._is_windows:
            try:
                if self._tone_bytes is None:
                    #
                    self._tone_bytes = _make_tone_wav_bytes(freq_hz=1500, duration_s=0.20, amplitude=0.9)

                old = self._get_system_wave_volume()

               
                v = int(max(0, min(100, self.volume)) * 65535 / 100)
                if old is not None:
                    self._set_system_wave_volume(v, v)

                
                flags = 0x0001 | 0x0004 | 0x0002
                self._winsound.PlaySound(self._tone_bytes, flags)

                # let the sound finish (keeps volume change short)
                time.sleep(0.22)

                if old is not None:
                    self._set_system_wave_volume(old[0], old[1])

                return
            except Exception:
                try:
                    # fallback: plain Beep (no volume control, but audible on most systems)
                    self._winsound.Beep(1500, 200)
                    return
                except Exception:
                    # fall through to no-op
                    pass

        
        return



def _settings_path():
    # saves beside this script
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "settings.json")

def load_settings():
    default = {"audio_enabled": True, "audio_volume": 70}
    p = _settings_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # keep defaults if keys missing
        for k in default:
            if k not in data:
                data[k] = default[k]
        return data
    except Exception:
        return default

def save_settings(data):
    p = _settings_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


# Tkinter GUI app


class PostureTkApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Erin's Posture Detector (Tkinter)")
        self.root.geometry("980x640")
        self.root.minsize(900, 600)

        if not PIL_OK:
            messagebox.showerror(
                "Missing Pillow (PIL)",
                "This GUI needs Pillow installed (pip install pillow) to show the webcam inside Tkinter.\n\n"
                "Your detection logic is fine, it just can't render frames into the Tk window without Pillow."
            )
            self.root.destroy()
            return

        # mediapipe
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose()

        # state (same as original)
        self.ANGLE_LIMIT = None
        self.OFFSET_LIMIT = None
        self.calibrated = False
        self.alert_played = False
        self.last_angle = None
        self.last_offset = None
        self.last_has_landmarks = False

        # camera
        self.cap = None
        self.running = False

        # capture mode
        self.source_mode = None  # 'webcam' or 'video'
        self.source_path = None

        # session logger for Stats
        self.logger = SessionLogger()
        self.has_session_data = False

        # fps
        self._prev_time = time.time()
        self._fps = 0.0

        # settings / audio
        s = load_settings()
        self.audio = AudioAlert()
        self.audio.enabled = bool(s.get("audio_enabled", True))
        self.audio.volume = int(s.get("audio_volume", 70))

        # UI
        self._build_ui()

        # close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        # main layout: left video, right panel
        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)

        # video area
        video_frame = ttk.Frame(self.root, padding=10)
        video_frame.grid(row=0, column=0, sticky="nsew")

        self.video_label = ttk.Label(video_frame)
        self.video_label.pack(fill="both", expand=True)

        # right panel
        side = ttk.Frame(self.root, padding=10)
        side.grid(row=0, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)

        self.status_title = ttk.Label(side, text="Status", font=("Segoe UI", 14, "bold"))
        self.status_title.grid(row=0, column=0, sticky="w")

        self.status_text = tk.StringVar(value="Camera stopped.")
        self.status_label = tk.Label(side, textvariable=self.status_text, wraplength=260, justify="left")
        self.status_label.grid(row=1, column=0, sticky="w", pady=(6, 12))

        self.metrics_title = ttk.Label(side, text="Live Metrics", font=("Segoe UI", 12, "bold"))
        self.metrics_title.grid(row=2, column=0, sticky="w")

        self.metrics_text = tk.StringVar(value="Angle: -\nOffset: -\nLimits: -")
        ttk.Label(side, textvariable=self.metrics_text, justify="left").grid(row=3, column=0, sticky="w", pady=(6, 12))

        self.help_title = ttk.Label(side, text="How to use", font=("Segoe UI", 12, "bold"))
        self.help_title.grid(row=4, column=0, sticky="w")

        help_msg = (
            "1) Click Start\n"
            "2) Sit upright (good posture)\n"
            "3) Click Calibrate\n"
            "4) Poor posture, it shows BAD POSTURE+alert\n"
        )
        ttk.Label(side, text=help_msg, justify="left", wraplength=260).grid(row=5, column=0, sticky="w")

        # bottom bar
        bottom = ttk.Frame(self.root, padding=(10, 8))
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=0)

        # left button group
        left_btns = ttk.Frame(bottom)
        left_btns.grid(row=0, column=0, sticky="w")

        self.start_btn = ttk.Button(left_btns, text="Start", command=self.toggle_start)
        self.start_btn.grid(row=0, column=0, padx=(0, 8))

        self.cal_btn = ttk.Button(left_btns, text="Calibrate", command=self.calibrate, state="disabled")
        self.cal_btn.grid(row=0, column=1, padx=(0, 8))

        self.video_btn = ttk.Button(left_btns, text="Upload Video", command=self.upload_video)
        self.video_btn.grid(row=0, column=2, padx=(0, 8))

        self.stats_btn = ttk.Button(left_btns, text="Stats", command=self.open_stats)
        self.stats_btn.grid(row=0, column=3, padx=(0, 8))

        self.quit_btn = ttk.Button(left_btns, text="Quit", command=self.on_close)
        self.quit_btn.grid(row=0, column=4)

        # bottom-right settings
        self.settings_btn = ttk.Button(bottom, text="Settings", command=self.open_settings)
        self.settings_btn.grid(row=0, column=1, sticky="e")


   
    # Video file + Stats
   

    def upload_video(self):
        path = filedialog.askopenfilename(
            title="Select a video file",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.avi *.mkv *.m4v"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return

        # stop current capture if needed
        if self.running:
            self.stop_camera()

        self.start_video(path)

    def start_video(self, path):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            messagebox.showerror("Video error", "Could not open that video file.")
            self.cap = None
            return

        self.source_mode = "video"
        self.source_path = path

        self.source_mode = "webcam"
        self.source_path = None

        self.running = True
        self.start_btn.configure(text="Stop")
        self.cal_btn.configure(state="normal")
        self.status_text.set("Video running. Scrub posture: sit upright in first seconds, then click Calibrate.")
        self.logger.reset()
        self.has_session_data = False
        self._prev_time = time.time()
        self._fps = 0.0
        self._update_loop()

    def open_stats(self):
        if not self.has_session_data:
            # still allow, but will show "no data"
            show_stats(self.root, self.logger)
            return
        show_stats(self.root, self.logger)

    
    # Camera / processing
 

    def toggle_start(self):
        if not self.running:
            self.start_camera()
        else:
            self.stop_camera()

    def start_camera(self):
        if self.running:
            return
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Camera error", "Could not open webcam (index 0).")
            self.cap = None
            return

        self.source_mode = "webcam"
        self.source_path = None

        self.running = True
        self.start_btn.configure(text="Stop")
        self.cal_btn.configure(state="normal")
        self.status_text.set("Camera running. Sit upright, then click Calibrate.")
        self.logger.reset()
        self.has_session_data = False
        self._update_loop()

    def stop_camera(self):
        self.running = False

        # capture mode
        self.source_mode = None  # 'webcam' or 'video'
        self.source_path = None

        # session logger for Stats
        self.logger = SessionLogger()
        self.has_session_data = False
        self.start_btn.configure(text="Start")
        self.cal_btn.configure(state="disabled")
        self.status_text.set("Camera stopped.")
        self.metrics_text.set("Angle: -\nOffset: -\nLimits: -")

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        # mark session data
        try:
            self.has_session_data = bool(getattr(self.logger, 'records', []))
        except Exception:
            self.has_session_data = False

        # clear video
        self.video_label.configure(image="")
        self.video_label.image = None

    def _set_status(self, msg, colour="black"):
        self.status_text.set(msg)
        try:
            if hasattr(self, "status_label") and self.status_label is not None:
                self.status_label.configure(fg=colour)
        except Exception:
            pass

    def _update_loop(self):
        if not self.running or self.cap is None:
            return

        ok, frame = self.cap.read()
        if not ok:
            # If it's a video file, we've likely reached the end
            if self.source_mode == "video":
                self._set_status("Video finished.", "black")
            else:
                self._set_status("Could not read from camera.", "black")
            self.stop_camera()
            return

        # fps (smoothed)
        now = time.time()
        dt = now - self._prev_time
        self._prev_time = now
        if dt > 0:
            inst = 1.0 / dt
            self._fps = (0.90 * self._fps) + (0.10 * inst)

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)

        self.last_has_landmarks = bool(results.pose_landmarks)

        if results.pose_landmarks:
            # draw MediaPipe pose skeleton (tracking points)
            try:
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=3, circle_radius=3),
                    connection_drawing_spec=mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=3),
                )
            except Exception:
                pass
            lm = results.pose_landmarks.landmark

            # flip x values because camera flipped (same as original)
            ear_x = 1 - lm[LEFT_EAR].x
            shoulder_x = 1 - lm[LEFT_SHOULDER].x

            ear = (int(ear_x * w), int(lm[LEFT_EAR].y * h))
            shoulder = (int(shoulder_x * w), int(lm[LEFT_SHOULDER].y * h))

            angle = get_angle(ear, shoulder)
            offset = get_offset(ear, shoulder)

            self.last_angle = angle
            self.last_offset = offset

            # nose point for heatmap (normalised)
            try:
                nose_x = 1 - lm[0].x
                nose_y = lm[0].y
                nose_xy = (float(nose_x), float(nose_y))
            except Exception:
                nose_xy = None

            # posture check (same logic)
            if self.calibrated:
                bad = False
                if angle < self.ANGLE_LIMIT:
                    bad = True
                if offset > self.OFFSET_LIMIT:
                    bad = True

                # log per-frame
                try:
                    self.logger.add(is_bad=bad, angle=angle, offset=offset, nose_xy=nose_xy)
                except Exception:
                    pass

                if bad:
                    # draw warning
                    txt = "BAD POSTURE"
                    cv2.putText(frame, txt, (int(w*0.20), int(h*0.55)),
                                cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 255), 5)

                    if self.alert_played == False:
                        self.audio.play()
                        self.alert_played = True
                    self._set_status("BAD POSTURE detected.", "red")
                else:
                    self.alert_played = False
                    self._set_status("Good posture.", "green")
            else:
                try:
                    self.logger.add(is_bad=False, angle=angle, offset=offset, nose_xy=nose_xy)
                except Exception:
                    pass
                self._set_status("Not calibrated yet. Sit upright and click Calibrate.", "black")

            # draw points
            cv2.circle(frame, ear, 5, (0, 255, 0), -1)
            cv2.circle(frame, shoulder, 5, (255, 0, 0), -1)

            # update metrics panel
            if self.calibrated:
                limits = f"AngleLimit: {int(self.ANGLE_LIMIT)} | OffsetLimit: {int(self.OFFSET_LIMIT)}"
            else:
                limits = "-"
            self.metrics_text.set(f"FPS: {self._fps:.1f}\nAngle: {int(angle)}\nOffset: {int(offset)}\nLimits: {limits}")

        else:
            self.metrics_text.set(f"FPS: {self._fps:.1f}\nAngle: -\nOffset: -\nLimits: -")
            self._set_status("No person detected. Move into view.", "black")
            self.alert_played = False

        # FPS overlay
        try:
            cv2.putText(frame, f"FPS: {self._fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
        except Exception:
            pass

        # show frame in Tkinter (convert AFTER drawing overlays)
        rgb_show = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_show)
        # keep aspect ratio to fit label
        label_w = max(1, self.video_label.winfo_width())
        label_h = max(1, self.video_label.winfo_height())
        img = img.resize((label_w, label_h))
        imgtk = ImageTk.PhotoImage(image=img)
        self.video_label.configure(image=imgtk)
        self.video_label.image = imgtk

        # schedule next frame
        self.root.after(10, self._update_loop)

   
    # Calibration (same as original)


    def calibrate(self):
        if not self.running:
            return
        if not self.last_has_landmarks or self.last_angle is None or self.last_offset is None:
            messagebox.showwarning("Calibration", "I can't see your pose yet. Move into view and try again.")
            return

        upright_angle = self.last_angle
        upright_offset = self.last_offset

        self.ANGLE_LIMIT = upright_angle - 10     # small tolerance (same)
        self.OFFSET_LIMIT = upright_offset + 20   # small tolerance (same)

        self.calibrated = True
        self.alert_played = False

        self.status_text.set("Calibrated! Now it will warn you if posture goes bad.")
        # update metrics immediately
        self.metrics_text.set(
            f"Angle: {int(upright_angle)}\nOffset: {int(upright_offset)}\n"
            f"Limits: AngleLimit: {int(self.ANGLE_LIMIT)} | OffsetLimit: {int(self.OFFSET_LIMIT)}"
        )

  
    # Settings window
 

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        pad = 12
        frm = ttk.Frame(win, padding=pad)
        frm.pack(fill="both", expand=True)

        audio_enabled_var = tk.BooleanVar(value=self.audio.enabled)
        volume_var = tk.IntVar(value=self.audio.volume)

        ttk.Label(frm, text="Audio Alerts", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        chk = ttk.Checkbutton(frm, text="Enable alert sound", variable=audio_enabled_var)
        chk.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(frm, text="Volume").grid(row=2, column=0, sticky="w")
        vol = ttk.Scale(frm, from_=0, to=100, orient="horizontal", variable=volume_var)
        vol.grid(row=2, column=1, sticky="ew", padx=(10, 0))
        frm.columnconfigure(1, weight=1)

        vol_label = ttk.Label(frm, text=str(volume_var.get()) + "%")
        vol_label.grid(row=3, column=1, sticky="e", pady=(2, 0))

        def on_vol_change(*_):
            vol_label.configure(text=str(int(volume_var.get())) + "%")
        volume_var.trace_add("write", on_vol_change)


        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(14, 0))

        def test_sound():
            # Preview using the current slider value
            vol_now = int(volume_var.get())
            prev_enabled = self.audio.enabled
            prev_vol = self.audio.volume
            try:
                self.audio.enabled = True
                self.audio.volume = vol_now
                self.audio.play()
            finally:
                self.audio.enabled = prev_enabled
                self.audio.volume = prev_vol

        def apply_settings(close_after=False):
            self.audio.enabled = bool(audio_enabled_var.get())
            self.audio.volume = int(volume_var.get())

            data = {"audio_enabled": self.audio.enabled, "audio_volume": self.audio.volume}
            save_settings(data)

            if close_after:
                win.destroy()

        ttk.Button(btns, text="Test", command=test_sound).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Apply", command=lambda: apply_settings(close_after=False)).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(btns, text="OK", command=lambda: apply_settings(close_after=True)).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(btns, text="Cancel", command=win.destroy).grid(row=0, column=3)
  

    def on_close(self):
        try:
            self.stop_camera()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

def main():
    root = tk.Tk()

    style = ttk.Style()
    style.theme_use("clam")  

    PostureTkApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()