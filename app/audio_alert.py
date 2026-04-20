# audio alert helper for posture warnings

def play_alert(audio_enabled=True):
    if not audio_enabled:
        return False

    # use a simple windows beep
    try:
        import winsound
        winsound.Beep(1500, 200)
        return True
    except Exception:
        return False


def test_alert(audio_enabled=True):
    return play_alert(audio_enabled)