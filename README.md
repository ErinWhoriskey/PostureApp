# PostureApp

A webcam-based posture detection application built in Python using OpenCV, MediaPipe and Tkinter

## Features
- Live webcam posture monitoring
- Manual calibration using the user’s upright sitting position
- Detection of:
  - good posture
  - forward posture
  - left lean
  - right lean
- Audio alert on bad posture
- Uploaded video analysis
- Session logging and stats view
- Automated pytest tests

## Project Structure
- `app/` - main application code
- `tests/` - automated pytest test files

## Requirements
Install the required packages:

```bash
pip install -r requirements.txt