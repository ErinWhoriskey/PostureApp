# Settings storage (json file next to scripts)
import json, os

DEFAULTS = {
    "audio_enabled": True,
    "volume": 100
}

def _settings_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "settings.json")

def load_settings():
    path = _settings_path()
    if not os.path.exists(path):
        return DEFAULTS.copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        s = DEFAULTS.copy()
        s.update({k: data.get(k, s[k]) for k in s})
        return s
    except Exception:
        return DEFAULTS.copy()

def save_settings(settings_dict):
    path = _settings_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, indent=2)
        return True
    except Exception:
        return False
