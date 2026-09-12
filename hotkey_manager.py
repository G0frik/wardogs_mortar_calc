"""
GLOBAL HOTKEY & PUSH-TO-TALK MANAGER (WINDOWS)
Uses lightweight GetAsyncKeyState queries (0% CPU, no DLL injection, no hooks).
Supports configurable Push-To-Talk for General, Start-only, and Target-only.
Provides interactive keybinding detection, key name formatting, and unbinding.
"""

import ctypes
import threading
import time
from logger import log_info, log_warning

user32 = ctypes.windll.user32

# Comprehensive Virtual-Key mapping (canonical lowercase name -> VK code)
VK_TABLE = {
    "none": 0,
    # Mouse buttons
    "mouse4": 0x05,         # Mouse XBUTTON1 (side button back)
    "mouse5": 0x06,         # Mouse XBUTTON2 (side button forward)
    "middle_mouse": 0x04,   # Mouse scroll wheel click
    "right_mouse": 0x02,    # Right mouse button
    # Modifiers & navigation
    "capslock": 0x14,
    "space": 0x20,
    "tab": 0x09,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "tilde": 0xC0,
    "enter": 0x0D,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "escape": 0x1B,
    "backspace": 0x08,
    "delete": 0x2E,
}

# F1 - F12
for i in range(1, 13):
    VK_TABLE[f"f{i}"] = 0x70 + (i - 1)

# Letters A - Z
for i in range(26):
    VK_TABLE[chr(ord('a') + i)] = 0x41 + i

# Digits 0 - 9
for i in range(10):
    VK_TABLE[str(i)] = 0x30 + i
    VK_TABLE[f"numpad{i}"] = 0x60 + i

# Common punctuation
VK_TABLE.update({
    "semicolon": 0xBA,
    "equal": 0xBB,
    "comma": 0xBC,
    "minus": 0xBD,
    "period": 0xBE,
    "slash": 0xBF,
    "bracket_left": 0xDB,
    "backslash": 0xDC,
    "bracket_right": 0xDD,
    "quote": 0xDE
})

# Reverse lookup for known VKs
REVERSE_VK_TABLE = {v: k for k, v in VK_TABLE.items() if v != 0}

DISPLAY_NAMES = {
    "none": "UNBOUND",
    "mouse4": "MOUSE 4",
    "mouse5": "MOUSE 5",
    "middle_mouse": "MIDDLE CLICK",
    "right_mouse": "RIGHT CLICK",
    "capslock": "CAPS LOCK",
    "space": "SPACE",
    "tab": "TAB",
    "shift": "SHIFT",
    "ctrl": "CTRL",
    "alt": "ALT",
    "tilde": "~ (TILDE)",
    "escape": "ESC",
    "backspace": "BACKSPACE",
    "delete": "DELETE",
    "enter": "ENTER",
}

# Pre-compiled list of VK codes to check during keybind capture
CHECKED_VKS = [
    0x04,  # Middle mouse
    0x05,  # Mouse 4
    0x06,  # Mouse 5
    0x02,  # Right mouse
    0x1B,  # Escape (unbind)
    0x08,  # Backspace (unbind)
    0x2E,  # Delete (unbind)
    0x14,  # CapsLock
    0x20,  # Space
    0x09,  # Tab
    0x10,  # Shift
    0x11,  # Ctrl
    0x12,  # Alt
    0xC0,  # Tilde
    0x0D,  # Enter
]
CHECKED_VKS += list(range(0x70, 0x7C))  # F1 - F12
CHECKED_VKS += list(range(0x41, 0x5B))  # A - Z
CHECKED_VKS += list(range(0x30, 0x3A))  # 0 - 9
CHECKED_VKS += list(range(0x60, 0x6A))  # Numpad 0 - 9
CHECKED_VKS += [0x21, 0x22, 0x23, 0x24, 0x2D]  # PageUp, PageDown, End, Home, Insert


def vk_to_storage_name(vk: int) -> str:
    """Converts a VK code to internal lowercase key string (e.g. 'mouse4', 'v', 'f2')."""
    if vk == 0:
        return "none"
    if vk in REVERSE_VK_TABLE:
        return REVERSE_VK_TABLE[vk]
    # Fallback to Windows scan code
    scan = user32.MapVirtualKeyW(vk, 0)
    buf = ctypes.create_unicode_buffer(32)
    if user32.GetKeyNameTextW(scan << 16, buf, 32) > 0:
        name = buf.value.lower().replace(" ", "_")
        VK_TABLE[name] = vk
        REVERSE_VK_TABLE[vk] = name
        return name
    return f"vk_{hex(vk)}"


def storage_name_to_vk(name: str) -> int:
    """Converts a storage string name to VK code."""
    if not name:
        return 0
    return VK_TABLE.get(str(name).strip().lower(), 0)


def format_key_display(name_or_vk) -> str:
    """Returns a user-friendly display string for keybind buttons (e.g. 'MOUSE 4', 'V', 'UNBOUND')."""
    if isinstance(name_or_vk, int):
        name = vk_to_storage_name(name_or_vk)
    else:
        name = str(name_or_vk or "").strip().lower()
    if not name or name in ("none", "0", ""):
        return "UNBOUND"
    if name in DISPLAY_NAMES:
        return DISPLAY_NAMES[name]
    return name.upper().replace("_", " ")


class GlobalHotkeyManager:
    def __init__(self, on_ptt_press=None, on_ptt_release=None, on_toggle_hide=None):
        """
        on_ptt_press(role): role is 'general', 'start', or 'target'
        on_ptt_release(role)
        on_toggle_hide(): called when toggle hide/show hotkey is pressed
        """
        self.on_ptt_press = on_ptt_press
        self.on_ptt_release = on_ptt_release
        self.on_toggle_hide = on_toggle_hide

        # Configured bindings: role -> vk_code
        self.bindings = {
            "general": storage_name_to_vk("f2"),
            "start": storage_name_to_vk("b"),
            "target": storage_name_to_vk("v"),
            "hide": storage_name_to_vk("f4")
        }

        # Key state tracking: role -> is_down
        self.key_states = {
            "general": False,
            "start": False,
            "target": False,
            "hide": False
        }

        self.running = False
        self.thread = None

    def configure(self, general_key="f2", start_key="b", target_key="v", toggle_hide_key="f4"):
        """Configures hotkeys by name."""
        self.bindings["general"] = storage_name_to_vk(general_key)
        self.bindings["start"] = storage_name_to_vk(start_key)
        self.bindings["target"] = storage_name_to_vk(target_key)
        self.bindings["hide"] = storage_name_to_vk(toggle_hide_key)
        log_info(f"Hotkeys configured: General={general_key}, Start={start_key}, Target={target_key}, Hide={toggle_hide_key}")

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
                    if role == "hide":
                        if self.on_toggle_hide:
                            try:
                                self.on_toggle_hide()
                            except Exception:
                                pass
                    elif self.on_ptt_press:
                        try:
                            self.on_ptt_press(role)
                        except Exception:
                            pass
                elif not is_down and was_down:
                    self.key_states[role] = False
                    if role != "hide" and self.on_ptt_release:
                        try:
                            self.on_ptt_release(role)
                        except Exception:
                            pass

            # Sleep 25ms (40 polls/sec is instant for human speech and costs 0% CPU)
            time.sleep(0.025)
