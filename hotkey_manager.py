"""
GLOBAL HOTKEY & PUSH-TO-TALK MANAGER (WINDOWS)
Uses lightweight GetAsyncKeyState queries (0% CPU, no DLL injection, no hooks).
Supports configurable Push-To-Talk for General, Start-only, and Target-only.
"""

import ctypes
import threading
import time
from logger import log_info, log_warning

user32 = ctypes.windll.user32

# Friendly name to Windows Virtual-Key code mapping
VK_TABLE = {
    "none": 0,
    "capslock": 0x14,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "v": 0x56,
    "b": 0x42,
    "c": 0x43,
    "t": 0x54,
    "g": 0x47,
    "x": 0x58,
    "z": 0x5A,
    "q": 0x51,
    "e": 0x45,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "numpad0": 0x60,
    "numpad1": 0x61,
    "numpad2": 0x62,
    "numpad3": 0x63,
    "mouse4": 0x05,         # Mouse XBUTTON1 (side button back)
    "mouse5": 0x06,         # Mouse XBUTTON2 (side button forward)
    "middle_mouse": 0x04,   # Mouse scroll wheel click
    "alt": 0x12,
    "ctrl": 0x11,
    "shift": 0x10,
    "tab": 0x09
}

REVERSE_VK_TABLE = {v: k for k, v in VK_TABLE.items()}


class GlobalHotkeyManager:
    def __init__(self, on_ptt_press=None, on_ptt_release=None):
        """
        on_ptt_press(role): role is 'general', 'start', or 'target'
        on_ptt_release(role)
        """
        self.on_ptt_press = on_ptt_press
        self.on_ptt_release = on_ptt_release

        # Configured bindings: role -> vk_code
        self.bindings = {
            "general": VK_TABLE.get("f2", 0x71),
            "start": VK_TABLE.get("none", 0),
            "target": VK_TABLE.get("none", 0)
        }

        # Key state tracking: role -> is_down
        self.key_states = {
            "general": False,
            "start": False,
            "target": False
        }

        self.running = False
        self.thread = None

    def configure(self, general_key="f2", start_key="none", target_key="none"):
        """Configures hotkeys by name."""
        self.bindings["general"] = VK_TABLE.get(str(general_key).lower(), 0)
        self.bindings["start"] = VK_TABLE.get(str(start_key).lower(), 0)
        self.bindings["target"] = VK_TABLE.get(str(target_key).lower(), 0)
        log_info(f"Hotkeys configured: General={general_key}, Start={start_key}, Target={target_key}")

    def start(self):
        """Starts the background polling loop."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops the background polling loop."""
        self.running = False

    def _poll_loop(self):
        """Low-overhead polling loop (25ms sleep = 40Hz check, 0.00% CPU)."""
        while self.running:
            for role, vk in self.bindings.items():
                if vk == 0:
                    continue

                # 0x8000 bit is set if key is currently down
                is_down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
                was_down = self.key_states[role]

                if is_down and not was_down:
                    self.key_states[role] = True
                    if self.on_ptt_press:
                        try:
                            self.on_ptt_press(role)
                        except Exception:
                            pass
                elif not is_down and was_down:
                    self.key_states[role] = False
                    if self.on_ptt_release:
                        try:
                            self.on_ptt_release(role)
                        except Exception:
                            pass

            # Sleep 25ms (40 polls/sec is instant for human speech and costs 0% CPU)
            time.sleep(0.025)
