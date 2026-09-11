"""
TACTICAL LOGGING SYSTEM FOR MORTAR CALC
Supports dynamic file logging (disabled by default to save disk space),
automatic size retention via RotatingFileHandler, log clearing,
and real-time in-memory streaming to UI subscribers.
"""

import glob
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from collections import deque
from datetime import datetime

LOG_FILE = os.path.abspath("mortar_calc.log")
DEFAULT_MAX_BYTES = 256 * 1024  # 256 KB max per log file
DEFAULT_BACKUP_COUNT = 1        # Max 1 backup (mortar_calc.log.1) -> max ~512 KB total disk space

# In-memory log buffer for GUI display (last 200 entries)
_gui_log_buffer = deque(maxlen=200)
_gui_subscribers = []

_file_handler = None
_file_logging_enabled = False


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


# Configure Base Logger
_logger = logging.getLogger("MortarCalc")
_logger.setLevel(logging.INFO)

# Initial handlers: GUI buffer + Console (NO FileHandler by default)
if not _logger.handlers:
    # GUI Handler
    gh = GUILogHandler()
    gh.setLevel(logging.INFO)
    gh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(gh)

    # Console Handler (safe for terminal output)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    _logger.addHandler(ch)


def _enforce_retention(max_bytes: int = DEFAULT_MAX_BYTES, backup_count: int = DEFAULT_BACKUP_COUNT):
    """Ensures existing log files do not exceed the retention limit."""
    try:
        base_dir = os.path.dirname(LOG_FILE)
        pattern = os.path.join(base_dir, "mortar_calc.log.*")
        backups = sorted(glob.glob(pattern))
        if len(backups) > backup_count:
            for b in backups[:-backup_count]:
                try:
                    os.remove(b)
                except Exception:
                    pass

        if os.path.exists(LOG_FILE):
            size = os.path.getsize(LOG_FILE)
            if size > max_bytes:
                # Truncate if already over limit before rotating handler starts
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Log truncated by retention policy.\n")
    except Exception:
        pass


def set_file_logging(enabled: bool, max_bytes: int = DEFAULT_MAX_BYTES, backup_count: int = DEFAULT_BACKUP_COUNT):
    """Enables or disables logging to mortar_calc.log with automatic size retention."""
    global _file_handler, _file_logging_enabled
    _file_logging_enabled = bool(enabled)

    # Remove existing file handler if present
    if _file_handler is not None:
        try:
            _logger.removeHandler(_file_handler)
            _file_handler.flush()
            _file_handler.close()
        except Exception:
            pass
        _file_handler = None

    if _file_logging_enabled:
        try:
            _enforce_retention(max_bytes, backup_count)
            _file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8"
            )
            _file_handler.setLevel(logging.INFO)
            _file_handler.setFormatter(
                logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
            )
            _logger.addHandler(_file_handler)
        except Exception as e:
            print(f"Warning: Could not enable file logging: {e}")


def is_file_logging_enabled() -> bool:
    """Returns whether file logging is currently active."""
    return _file_logging_enabled


def get_log_file_size_kb() -> float:
    """Returns total size of log file and rotated backups in KB."""
    total_bytes = 0
    try:
        if os.path.exists(LOG_FILE):
            total_bytes += os.path.getsize(LOG_FILE)
        base_dir = os.path.dirname(LOG_FILE)
        for b in glob.glob(os.path.join(base_dir, "mortar_calc.log.*")):
            try:
                total_bytes += os.path.getsize(b)
            except Exception:
                pass
    except Exception:
        pass
    return round(total_bytes / 1024, 1)


def clear_log_file() -> bool:
    """Truncates the log file, removes all backups, and clears the UI buffer."""
    global _file_handler
    try:
        reopen = False
        if _file_handler is not None:
            try:
                _logger.removeHandler(_file_handler)
                _file_handler.flush()
                _file_handler.close()
                _file_handler = None
                reopen = True
            except Exception:
                pass

        # Truncate main file to 0 bytes
        if os.path.exists(LOG_FILE):
            try:
                os.remove(LOG_FILE)
            except Exception:
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    pass

        # Remove rotated backup files
        base_dir = os.path.dirname(LOG_FILE)
        for b in glob.glob(os.path.join(base_dir, "mortar_calc.log.*")):
            try:
                os.remove(b)
            except Exception:
                pass

        _gui_log_buffer.clear()

        if reopen and _file_logging_enabled:
            set_file_logging(True)

        return True
    except Exception as e:
        _logger.error(f"Failed to clear log file: {e}")
        return False


def get_logger():
    return _logger

def log_info(msg: str):
    _logger.info(msg)

def log_warning(msg: str):
    _logger.warning(msg)

def log_error(msg: str):
    _logger.error(msg)

def get_recent_logs():
    """Returns recent log messages from the in-memory buffer."""
    return list(_gui_log_buffer)

def subscribe_to_logs(callback):
    """Subscribes a callback(msg) to receive new log messages in real-time."""
    if callback not in _gui_subscribers:
        _gui_subscribers.append(callback)

def unsubscribe_from_logs(callback):
    """Removes a log subscriber."""
    if callback in _gui_subscribers:
        _gui_subscribers.remove(callback)
