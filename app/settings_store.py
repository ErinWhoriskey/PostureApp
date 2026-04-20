# settings storage

import json
import os


DEFAULTS = {
    "audio_enabled": True
}


def _settings_path():
    # get the path to settings.json inside the app folder
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "settings.json")


def load_settings():
    # load saved settings or fall back to defaults
    path = _settings_path()

    if not os.path.exists(path):
        return DEFAULTS.copy()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return DEFAULTS.copy()

    settings = DEFAULTS.copy()

    for key in settings:
        if key in data:
            settings[key] = data[key]

    return settings


def save_settings(settings_dict):
    # save settings to the json file
    path = _settings_path()

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, indent=2)
        return True
    except Exception:
        return False