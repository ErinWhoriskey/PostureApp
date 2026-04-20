# stats window

# shows the latest session and saved progress over time

import json
import os
import tkinter as tk
from tkinter import ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


STATE_LABELS = {
    "good": "Good",
    "bad_forward": "Forward",
    "bad_left": "Left lean",
    "bad_right": "Right lean",
    "not_at_desk": "Not at desk",
    "uncalibrated": "Uncalibrated",
}


def _seconds_text(value):
    # turn seconds into simple text
    return str(round(float(value), 1)) + " s"


def _load_saved_sessions(store_path):
    # load saved session history from json
    if not store_path or not os.path.exists(store_path):
        return []

    try:
        with open(store_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []
    except Exception:
        return []


def _add_metric_card(parent, row, title, value):
    # make one small stats card
    card = ttk.Frame(parent, padding=10)
    card.grid(row=row[0], column=row[1], sticky="nsew", padx=6, pady=6)

    ttk.Label(card, text=title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(card, text=value, font=("Segoe UI", 14)).pack(anchor="w", pady=(4, 0))


def show_stats(root, session_logger, store_path=None):
    # open the stats window
    win = tk.Toplevel(root)
    win.title("Posture Statistics")
    win.geometry("1100x760")

    notebook = ttk.Notebook(win)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    current_tab = ttk.Frame(notebook)
    history_tab = ttk.Frame(notebook)

    notebook.add(current_tab, text="Current Session")
    notebook.add(history_tab, text="Progress")

    # current session tab
    records = list(getattr(session_logger, "records", []))

    if not records:
        ttk.Label(
            current_tab,
            text="No stats yet. Run a webcam or video session first."
        ).pack(padx=12, pady=12)
    else:
        summary = session_logger.summary()

        top = ttk.Frame(current_tab, padding=8)
        top.pack(fill="x")

        for i in range(3):
            top.columnconfigure(i, weight=1)

        _add_metric_card(top, (0, 0), "Tracked time", _seconds_text(summary.get("tracked_duration_s", 0.0)))
        _add_metric_card(top, (0, 1), "Good posture", _seconds_text(summary.get("good_s", 0.0)))
        _add_metric_card(top, (0, 2), "Bad posture", _seconds_text(summary.get("bad_total_s", 0.0)))
        _add_metric_card(top, (1, 0), "Forward posture", _seconds_text(summary.get("bad_forward_s", 0.0)))
        _add_metric_card(top, (1, 1), "Left lean", _seconds_text(summary.get("bad_left_s", 0.0)))
        _add_metric_card(top, (1, 2), "Right lean", _seconds_text(summary.get("bad_right_s", 0.0)))
        _add_metric_card(top, (2, 0), "Not at desk", _seconds_text(summary.get("not_at_desk_s", 0.0)))
        _add_metric_card(top, (2, 1), "Bad posture %", str(round(summary.get("bad_pct", 0.0), 1)) + "%")
        _add_metric_card(top, (2, 2), "Frames", str(summary.get("frames", 0)))
        
    # chart for the current session
        fig1 = plt.Figure(figsize=(9.5, 4.2), dpi=100)
        ax1 = fig1.add_subplot(111)

        states = ["good", "bad_forward", "bad_left", "bad_right", "not_at_desk"]
        values = [summary.get("state_times", {}).get(state, 0.0) for state in states]
        labels = [STATE_LABELS[state] for state in states]

        ax1.bar(labels, values)
        ax1.set_title("Time spent in each posture state")
        ax1.set_ylabel("Seconds")
        ax1.tick_params(axis="x", rotation=15)

        canvas1 = FigureCanvasTkAgg(fig1, master=current_tab)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=8)

    # history tab
    saved_sessions = _load_saved_sessions(store_path)

    if not saved_sessions:
        ttk.Label(history_tab, text="No saved sessions found yet.").pack(padx=12, pady=12)
    else:
        # chart for bad posture percentage over time
        fig2 = plt.Figure(figsize=(9.5, 4.0), dpi=100)
        ax2 = fig2.add_subplot(111)

        session_numbers = list(range(1, len(saved_sessions) + 1))
        bad_pcts = [float(item.get("bad_pct", 0.0)) for item in saved_sessions]

        ax2.plot(session_numbers, bad_pcts, marker="o")
        ax2.set_title("Bad posture percentage over time")
        ax2.set_xlabel("Session")
        ax2.set_ylabel("Bad posture %")
        ax2.set_xticks(session_numbers)

        canvas2 = FigureCanvasTkAgg(fig2, master=history_tab)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=(12, 8))

        latest = saved_sessions[-1]
        latest_frame = ttk.Frame(history_tab, padding=10)
        latest_frame.pack(fill="x")

        latest_text = (
            "Latest saved session  |  good: "
            + _seconds_text(latest.get("good_s", 0.0))
            + "  |  bad: "
            + _seconds_text(latest.get("bad_total_s", 0.0))
            + "  |  not at desk: "
            + _seconds_text(latest.get("not_at_desk_s", 0.0))
        )

        ttk.Label(
            latest_frame,
            text=latest_text,
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w")

    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))