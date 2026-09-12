"""
SETTINGS MANAGER FOR MORTAR CALC
Persists user preferences such as selected microphone, language,
overlay opacity, scale, and window preferences to settings.json.
"""

import json
import os
from logger import log_error

SETTINGS_FILE = os.path.abspath("settings.json")

DEFAULT_SETTINGS = {
    "device_idx": None,
    "device_name": None,
    "engine": "google",          # "google", "whisper", or "vosk"
    "language": "uk",
    "scale_mode": "100m",
    "scale_multiplier": 100.0,
    "always_on_top": True,
    "opacity": 0.95,
    "compact_mode": True,       # Very small window by default
    "ptt_general_key": "f2",    # General PTT hotkey
    "ptt_start_key": "b",       # Dedicated Start PTT hotkey
    "ptt_target_key": "v",      # Dedicated Target PTT hotkey
    "toggle_hide_key": "f4",    # Global hotkey to toggle hide/show overlay
    "enable_logging": False,    # Disabled by default to save disk space
    "log_max_size_kb": 256      # Maximum log file size retention
}


def load_settings():
    """Loads settings from settings.json, returning defaults if not found."""
    if not os.path.exists(SETTINGS_FILE):
        return dict(DEFAULT_SETTINGS)

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Merge with defaults in case of missing keys
            settings = dict(DEFAULT_SETTINGS)
            settings.update(data)
            return settings
    except Exception as e:
        log_error(f"Failed to read settings.json: {e}")
        return dict(DEFAULT_SETTINGS)


def save_settings(settings_dict):
    """Saves settings dictionary to settings.json."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        log_error(f"Failed to save settings.json: {e}")
        return False
