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
```

## Testing
This project includes automated pytest unit tests for key helper modules.

Test files:
- `tests/test_core_posture.py`
- `tests/test_session_logger.py`
- `tests/test_settings_store.py`

To run the tests:

```bash
python -m pytest tests -v
```

## Screenshots

### Good posture
![Good posture](docs/images/good-posture.png)

### Checking posture
![Checking posture](docs/images/checking-posture.png)

### Bad posture forward
![Bad posture forward](docs/images/bad-posture-forward.png)

### Bad posture left
![Bad posture left](docs/images/bad-posture-left.png)

### Bad posture right
![Bad posture right](docs/images/bad-posture-right.png)

### Statistics view
![Statistics view](docs/images/stats-view.png)

### Progress graph
![Progress graph](docs/images/progress-graph.png)

### Upload video analysis
![Upload video analysis](docs/images/upload-video.png)

### Audio settings
![Audio settings](docs/images/audio-settings.png)

### No body detected
![No body detected](docs/images/no-body-detected.png)
