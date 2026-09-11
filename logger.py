"""
TACTICAL LOGGING SYSTEM FOR MORTAR CALC
Logs application events, microphone status, Vosk speech recognition,
and calculation actions to both file (mortar_calc.log) and in-memory buffer for UI.
"""

import logging
import os
import sys
from collections import deque
from datetime import datetime

LOG_FILE = os.path.abspath("mortar_calc.log")

# In-memory log buffer for GUI display (last 300 entries)
_gui_log_buffer = deque(maxlen=300)
_gui_subscribers = []


class GUILogHandler(logging.Handler):
    """Custom logging handler that forwards log records to GUI callbacks."""
    def emit(self, record):
        try:
            msg = self.format(record)
            _gui_log_buffer.append(msg)
            for sub in _gui_subscribers:
                try:
                    sub(msg)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)


# Configure Logger
_logger = logging.getLogger("MortarCalc")
_logger.setLevel(logging.INFO)

# Prevent duplicate handlers if re-imported
if not _logger.handlers:
    # File Handler
    try:
        fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        _logger.addHandler(fh)
    except Exception as e:
        print(f"Warning: Could not create log file: {e}")

    # GUI Handler
    gh = GUILogHandler()
    gh.setLevel(logging.INFO)
    gh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(gh)

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(ch)


def get_logger():
    return _logger

def log_info(msg: str):
    _logger.info(msg)

def log_warning(msg: str):
    _logger.warning(msg)

def log_error(msg: str):
    _logger.error(msg)

def get_recent_logs():
    """Returns a list of recent log messages."""
    return list(_gui_log_buffer)

def subscribe_to_logs(callback):
    """Subscribes a callback(msg) to receive new log messages in real-time."""
    if callback not in _gui_subscribers:
        _gui_subscribers.append(callback)

def unsubscribe_from_logs(callback):
    """Removes a log subscriber."""
    if callback in _gui_subscribers:
        _gui_subscribers.remove(callback)

def clear_log_file():
    """Truncates the log file."""
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Log cleared by user.\n")
        _gui_log_buffer.clear()
        return True
    except Exception as e:
        _logger.error(f"Failed to clear log file: {e}")
        return False
