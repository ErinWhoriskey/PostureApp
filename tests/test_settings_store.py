import json
from pathlib import Path
from app import settings_store


def test_load_settings_returns_defaults_when_file_missing(monkeypatch):
    fake_path = Path("missing_settings.json")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: str(fake_path))

    settings = settings_store.load_settings()

    assert settings == {"audio_enabled": True}


def test_save_settings_writes_file_and_load_settings_reads_it(monkeypatch, tmp_path):
    fake_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_store, "_settings_path", lambda: str(fake_path))

    saved = settings_store.save_settings({"audio_enabled": False})
    loaded = settings_store.load_settings()

    assert saved is True
    assert loaded == {"audio_enabled": False}


def test_load_settings_returns_defaults_when_json_is_bad(monkeypatch, tmp_path):
    fake_path = tmp_path / "settings.json"
    fake_path.write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr(settings_store, "_settings_path", lambda: str(fake_path))

    settings = settings_store.load_settings()

    assert settings == {"audio_enabled": True}


def test_load_settings_ignores_unknown_keys(monkeypatch, tmp_path):
    fake_path = tmp_path / "settings.json"
    fake_path.write_text(
        json.dumps({"audio_enabled": False, "extra_key": 123}),
        encoding="utf-8"
    )
    monkeypatch.setattr(settings_store, "_settings_path", lambda: str(fake_path))

    settings = settings_store.load_settings()

    assert settings == {"audio_enabled": False}


def test_save_settings_returns_false_if_write_fails(monkeypatch):
    monkeypatch.setattr(settings_store, "_settings_path", lambda: "/bad/path/settings.json")

    def fake_open(*args, **kwargs):
        raise OSError("cannot write")

    monkeypatch.setattr("builtins.open", fake_open)

    saved = settings_store.save_settings({"audio_enabled": True})

    assert saved is False