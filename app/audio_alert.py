# Audio alert helper (Windows winsound + fallback)
import sys

def play_alert(audio_enabled=True, volume=100):
    if not audio_enabled:
        return False

    # Try a WAV then fall back to Beep.
    try:
        import winsound
        # Simple beep (reliable)
        winsound.Beep(1500, 200)
        return True
    except Exception:
        return False

def test_alert(audio_enabled=True, volume=100):
    return play_alert(audio_enabled, volume)
