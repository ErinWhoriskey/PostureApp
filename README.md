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

## Testing
This project includes automated pytest unit tests for key helper modules.

Test files:
- `tests/test_core_posture.py`
- `tests/test_session_logger.py`
- `tests/test_settings_store.py`

To run the tests:

```bash
python -m pytest tests -v