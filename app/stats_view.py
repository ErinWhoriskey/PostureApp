import tkinter as tk
from tkinter import ttk

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


def _compute_good_bad_time(records):
    # uses the per-frame timestamps (r.t) to estimate time spent in each state
    # adds dt between consecutive records to the state of the earlier record
    if not records or len(records) < 2:
        return 0.0, 0.0

    good_s = 0.0
    bad_s = 0.0

    for i in range(len(records) - 1):
        r = records[i]
        dt = records[i + 1].t - r.t
        if dt < 0:
            dt = 0.0

        if r.is_bad:
            bad_s += dt
        else:
            good_s += dt

    return good_s, bad_s


def show_stats(root, session_logger):
    win = tk.Toplevel(root)
    win.title("Session Stats")
    win.geometry("900x650")

    records = list(getattr(session_logger, "records", []))
    if not records:
        ttk.Label(win, text="No stats yet — run webcam/video first.").pack(padx=12, pady=12)
        return

    # good / bad time
    good_s, bad_s = _compute_good_bad_time(records)
    total_s = good_s + bad_s

    top = ttk.Frame(win)
    top.pack(fill="x", padx=12, pady=10)

    ttk.Label(
        top,
        text=f"Good posture time: {good_s:.1f} seconds",
        font=("Segoe UI", 12, "bold")
    ).pack(anchor="w")

    ttk.Label(
        top,
        text=f"Bad posture time:  {bad_s:.1f} seconds",
        font=("Segoe UI", 12, "bold")
    ).pack(anchor="w")

    if total_s > 0:
        ttk.Label(
            top,
            text=f"Bad posture % (time): {(bad_s / total_s) * 100.0:.1f}%",
            font=("Segoe UI", 10)
        ).pack(anchor="w", pady=(4, 0))

    # heatmap from nose_xy
    pts = []
    for r in records:
        if r.nose_xy is None:
            continue
        x, y = r.nose_xy
        if x is None or y is None:
            continue
        # keep only sensible normalised values
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            pts.append((float(x), float(y)))

    if len(pts) < 10:
        ttk.Label(win, text="Not enough nose points for a heatmap yet.").pack(padx=12, pady=12)
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=8)
        return

    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)

    bins = 45
    heat, xedges, yedges = np.histogram2d(xs, ys, bins=bins, range=[[0, 1], [0, 1]])

    fig = plt.Figure(figsize=(7.8, 5.0), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_title("Head position heatmap (nose)")
    ax.set_xlabel("X (normalised)")
    ax.set_ylabel("Y (normalised)")

    im = ax.imshow(
        heat.T,
        origin="lower",
        aspect="auto",
        extent=[0, 1, 0, 1],
    )
    fig.colorbar(im, ax=ax)

    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=10)

    ttk.Button(win, text="Close", command=win.destroy).pack(pady=8)
