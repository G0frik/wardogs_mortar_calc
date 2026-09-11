"""
WAR DOGS // MORTAR DISTANCE CALCULATOR & VOICE FIRE CONTROL
Ultra-compact, frameless in-game HUD overlay with draggable borderless window,
mousewheel opacity control, bottom-right manual corner resize handle,
expand/collapse toggle, global Push-to-Talk (PTT) with role routing (Start / Target),
and multi-engine speech recognition (Google / Whisper / Vosk).
"""

import math
import os
import re
import sys
import threading
import tkinter as tk
from tkinter import messagebox

from voice_service import VoiceRecognitionService
from hotkey_manager import GlobalHotkeyManager, VK_TABLE
from settings_manager import load_settings, save_settings
from settings_window import SettingsWindow
from logger import log_info, log_error, log_warning


def parse_coordinate_string(text: str):
    """Parses coordinate string into (x, y) float tuple."""
    if not text:
        return None
    s = text.strip().replace(';', ' ')

    parts_by_comma = [p.strip() for p in s.split(',') if p.strip()]
    if len(parts_by_comma) == 4:
        try:
            x = float(f"{parts_by_comma[0]}.{parts_by_comma[1]}")
            y = float(f"{parts_by_comma[2]}.{parts_by_comma[3]}")
            return (x, y)
        except ValueError:
            pass

    parts = re.split(r'\s+', s)
    if len(parts) == 2:
        try:
            x = float(parts[0].replace(',', '.'))
            y = float(parts[1].replace(',', '.'))
            return (x, y)
        except ValueError:
            pass

    if len(parts_by_comma) == 2:
        try:
            x = float(parts_by_comma[0])
            y = float(parts_by_comma[1])
            return (x, y)
        except ValueError:
            pass

    nums = re.findall(r'\d+(?:[.,]\d+)?', s)
    if len(nums) == 2:
        try:
            x = float(nums[0].replace(',', '.'))
            y = float(nums[1].replace(',', '.'))
            return (x, y)
        except ValueError:
            pass
    elif len(nums) == 4:
        try:
            x = float(f"{nums[0]}.{nums[1]}")
            y = float(f"{nums[2]}.{nums[3]}")
            return (x, y)
        except ValueError:
            pass

    return None


def detect_full_quad(text: str):
    """Detects if user pasted both Start and Target into a single field."""
    s = text.strip()
    s = re.sub(r'[-–—>to]+', ' ', s)
    tokens = [t for t in re.split(r'[\s;,]+', s) if t]
    
    if len(tokens) == 4:
        try:
            x1 = float(tokens[0].replace(',', '.'))
            y1 = float(tokens[1].replace(',', '.'))
            x2 = float(tokens[2].replace(',', '.'))
            y2 = float(tokens[3].replace(',', '.'))
            return ((x1, y1), (x2, y2))
        except ValueError:
            pass
            
    if len(tokens) == 8:
        try:
            x1 = float(f"{tokens[0]}.{tokens[1]}")
            y1 = float(f"{tokens[2]}.{tokens[3]}")
            x2 = float(f"{tokens[4]}.{tokens[5]}")
            y2 = float(f"{tokens[6]}.{tokens[7]}")
            return ((x1, y1), (x2, y2))
        except ValueError:
            pass

    return None


class MortarCalcWidget(tk.Tk):
    def __init__(self):
        super().__init__()

        self.settings = load_settings()
        log_info("Starting Wardogs Mortar Calculator (Resizable Mini-HUD)...")

        # Tactical Palette
        self.COLOR_BG = "#121418"
        self.COLOR_HEADER = "#181c24"
        self.COLOR_CARD = "#1a1d24"
        self.COLOR_BORDER = "#2b3240"
        self.COLOR_TEXT = "#e2e8f0"
        self.COLOR_MUTED = "#8290a4"
        self.COLOR_ACCENT = "#00ffcc"
        self.COLOR_AMBER = "#ffb703"
        self.COLOR_RED = "#ff5555"
        self.COLOR_INPUT_BG = "#0c0e12"

        # Frameless Window
        self.overrideredirect(True)
        self.configure(bg=self.COLOR_BG, highlightbackground=self.COLOR_BORDER, highlightthickness=1)

        # Window State
        self.always_on_top = self.settings.get("always_on_top", True)
        self.attributes("-topmost", self.always_on_top)
        self.current_alpha = self.settings.get("opacity", 0.95)
        self.attributes("-alpha", self.current_alpha)

        # Window Size & Mode: Compact by default
        self.is_compact = self.settings.get("compact_mode", True)
        self.COMPACT_SIZE = (
            self.settings.get("compact_w", 270),
            self.settings.get("compact_h", 130)
        )
        self.EXPANDED_SIZE = (
            self.settings.get("expanded_w", 340),
            self.settings.get("expanded_h", 480)
        )

        win_x = self.settings.get("win_x", 100)
        win_y = self.settings.get("win_y", 100)
        w, h = self.COMPACT_SIZE if self.is_compact else self.EXPANDED_SIZE
        self.geometry(f"{w}x{h}+{win_x}+{win_y}")

        # Dragging & Resizing state
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_orig_w = w
        self._resize_orig_h = h
        self._opacity_timer = None

        # Scale options
        self.scale_multiplier = tk.DoubleVar(value=self.settings.get("scale_multiplier", 100.0))
        self.scale_mode = tk.StringVar(value=self.settings.get("scale_mode", "100m"))

        # Voice & PTT Service
        self.voice_lang = self.settings.get("language", "uk")
        self.voice_service = VoiceRecognitionService(
            models_dir="models",
            on_action=self._on_voice_action_async,
            on_partial=self._on_voice_partial_async,
            on_status=self._on_voice_status_async
        )

        # Global Hotkey Manager
        self.hotkey_mgr = GlobalHotkeyManager(
            on_ptt_press=self._on_global_ptt_down,
            on_ptt_release=self._on_global_ptt_up
        )
        self._sync_hotkeys_config()

        self.settings_window = None

        self._build_ui()
        self._setup_bindings()

        # Initialize voice in background
        threading.Thread(target=self._init_services_bg, daemon=True).start()

    def _init_services_bg(self):
        pref_dev = self.settings.get("device_idx")
        pref_engine = self.settings.get("engine", "google")
        self.voice_service.initialize(self.voice_lang, preferred_device_idx=pref_dev, engine=pref_engine)
        self.hotkey_mgr.start()

    def _sync_hotkeys_config(self):
        gen_key = self.settings.get("ptt_general_key", "f2")
        start_key = self.settings.get("ptt_start_key", "b")
        target_key = self.settings.get("ptt_target_key", "v")
        self.hotkey_mgr.configure(general_key=gen_key, start_key=start_key, target_key=target_key)

    def _build_ui(self):
        # ==========================================
        # 1. DRAGGABLE TITLE BAR
        # ==========================================
        self.header_bar = tk.Frame(self, bg=self.COLOR_HEADER, height=26, cursor="fleur")
        self.header_bar.pack(fill=tk.X)

        self.lbl_title = tk.Label(
            self.header_bar,
            text="WD CALC",
            font=("Consolas", 8, "bold"),
            fg=self.COLOR_ACCENT,
            bg=self.COLOR_HEADER,
            cursor="fleur"
        )
        self.lbl_title.pack(side=tk.LEFT, padx=(6, 4), pady=3)

        self.lbl_ptt_badge = tk.Label(
            self.header_bar,
            text="🎙️ OFF",
            font=("Consolas", 7, "bold"),
            fg=self.COLOR_MUTED,
            bg="#212631",
            padx=4,
            pady=1,
            cursor="hand2"
        )
        self.lbl_ptt_badge.pack(side=tk.LEFT, padx=2)
        self.lbl_ptt_badge.bind("<Button-1>", lambda e: self.toggle_voice_listening())

        # Header Right Controls: Settings, Expand, Close
        btn_close = tk.Button(
            self.header_bar,
            text="✕",
            font=("Segoe UI", 7, "bold"),
            bg=self.COLOR_HEADER,
            fg=self.COLOR_RED,
            activebackground="#ff3333",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=5,
            pady=0,
            cursor="hand2",
            command=self._on_closing
        )
        btn_close.pack(side=tk.RIGHT, padx=(0, 2))

        self.btn_expand = tk.Button(
            self.header_bar,
            text="▲" if not self.is_compact else "▼",
            font=("Segoe UI", 7),
            bg=self.COLOR_HEADER,
            fg=self.COLOR_TEXT,
            activebackground="#2c3340",
            relief=tk.FLAT,
            padx=4,
            pady=0,
            cursor="hand2",
            command=self.toggle_compact_mode
        )
        self.btn_expand.pack(side=tk.RIGHT, padx=1)

        btn_settings = tk.Button(
            self.header_bar,
            text="⚙",
            font=("Segoe UI", 7),
            bg=self.COLOR_HEADER,
            fg=self.COLOR_TEXT,
            activebackground="#2c3340",
            relief=tk.FLAT,
            padx=4,
            pady=0,
            cursor="hand2",
            command=self.open_settings
        )
        btn_settings.pack(side=tk.RIGHT, padx=1)

        # ==========================================
        # 2. CORE COMPACT COORDINATES & RESULT HUD
        # ==========================================
        self.core_frame = tk.Frame(self, bg=self.COLOR_BG)
        self.core_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(2, 2))

        # Start Row: "S: [___]"
        row_s = tk.Frame(self.core_frame, bg=self.COLOR_BG)
        row_s.pack(fill=tk.X, pady=1)

        lbl_s = tk.Label(row_s, text="S:", font=("Consolas", 9, "bold"), fg="#7dd3fc", bg=self.COLOR_BG, width=2)
        lbl_s.pack(side=tk.LEFT)

        self.start_entry = tk.Entry(
            row_s,
            font=("Consolas", 10, "bold"),
            bg=self.COLOR_INPUT_BG,
            fg=self.COLOR_TEXT,
            insertbackground=self.COLOR_ACCENT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#2b3240",
            highlightcolor=self.COLOR_ACCENT
        )
        self.start_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=1)

        # Target Row: "T: [___]"
        row_t = tk.Frame(self.core_frame, bg=self.COLOR_BG)
        row_t.pack(fill=tk.X, pady=1)

        lbl_t = tk.Label(row_t, text="T:", font=("Consolas", 9, "bold"), fg="#f472b6", bg=self.COLOR_BG, width=2)
        lbl_t.pack(side=tk.LEFT)

        self.target_entry = tk.Entry(
            row_t,
            font=("Consolas", 10, "bold"),
            bg=self.COLOR_INPUT_BG,
            fg=self.COLOR_TEXT,
            insertbackground=self.COLOR_ACCENT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#2b3240",
            highlightcolor="#f472b6"
        )
        self.target_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=1)

        # Compact Result Bar
        self.compact_res_bar = tk.Frame(self.core_frame, bg="#161b22", highlightthickness=1, highlightbackground="#252a36")
        self.compact_res_bar.pack(fill=tk.X, pady=(2, 0))

        self.lbl_mini_dist = tk.Label(
            self.compact_res_bar,
            text="DIST: ---",
            font=("Consolas", 9, "bold"),
            fg=self.COLOR_ACCENT,
            bg="#161b22"
        )
        self.lbl_mini_dist.pack(side=tk.LEFT, padx=(5, 4), pady=2)

        self.lbl_mini_az = tk.Label(
            self.compact_res_bar,
            text="AZ: ---°",
            font=("Consolas", 9, "bold"),
            fg=self.COLOR_AMBER,
            bg="#161b22"
        )
        self.lbl_mini_az.pack(side=tk.LEFT, padx=4, pady=2)

        self.btn_copy_mini = tk.Button(
            self.compact_res_bar,
            text="📋",
            font=("Segoe UI", 7),
            bg="#212631",
            fg=self.COLOR_TEXT,
            activebackground="#2ea043",
            relief=tk.FLAT,
            padx=4,
            pady=0,
            cursor="hand2",
            command=self.copy_result
        )
        self.btn_copy_mini.pack(side=tk.RIGHT, padx=4, pady=2)

        # ==========================================
        # 3. EXPANDED HUD SECTION (COLLAPSIBLE)
        # ==========================================
        self.expanded_frame = tk.Frame(self, bg=self.COLOR_BG)

        # Scale row in expanded
        scale_box = tk.Frame(self.expanded_frame, bg=self.COLOR_CARD, highlightthickness=1, highlightbackground=self.COLOR_BORDER)
        scale_box.pack(fill=tk.X, padx=6, pady=3)

        tk.Label(scale_box, text="SCALE:", font=("Consolas", 7, "bold"), fg=self.COLOR_MUTED, bg=self.COLOR_CARD).pack(side=tk.LEFT, padx=4)
        for label, m_key, mult in [("1m", "1m", 1.0), ("100m", "100m", 100.0), ("1km", "1km", 1000.0)]:
            tk.Radiobutton(
                scale_box,
                text=label,
                variable=self.scale_mode,
                value=m_key,
                font=("Segoe UI", 7),
                fg=self.COLOR_TEXT,
                bg=self.COLOR_CARD,
                selectcolor=self.COLOR_BG,
                command=lambda m=mult, k=m_key: self._on_scale_change(m, k)
            ).pack(side=tk.LEFT, padx=2)

        # Action Buttons (Swap & Clear & Opacity)
        btn_row = tk.Frame(self.expanded_frame, bg=self.COLOR_BG)
        btn_row.pack(fill=tk.X, padx=6, pady=2)

        tk.Button(btn_row, text="⇅ Swap", font=("Consolas", 8), bg="#21262d", fg=self.COLOR_TEXT, relief=tk.FLAT, padx=6, pady=1, command=self.swap_coordinates).pack(side=tk.LEFT)
        tk.Button(btn_row, text="✕ Clear", font=("Consolas", 8), bg="#21262d", fg=self.COLOR_RED, relief=tk.FLAT, padx=6, pady=1, command=self.clear_all).pack(side=tk.LEFT, padx=4)
        
        self.btn_alpha = tk.Button(btn_row, text=f"🌓 {int(self.current_alpha*100)}%", font=("Segoe UI", 7), bg="#21262d", fg=self.COLOR_MUTED, relief=tk.FLAT, padx=5, pady=1, command=self.toggle_opacity)
        self.btn_alpha.pack(side=tk.RIGHT)

        # Tactical Details (Mils & Delta)
        details_box = tk.Frame(self.expanded_frame, bg="#161b22", highlightthickness=1, highlightbackground="#252a36")
        details_box.pack(fill=tk.X, padx=6, pady=3)

        self.lbl_mils_exp = tk.Label(details_box, text="MILS: --- / ---", font=("Consolas", 8), fg=self.COLOR_TEXT, bg="#161b22")
        self.lbl_mils_exp.pack(side=tk.LEFT, padx=6, pady=2)

        self.lbl_delta_exp = tk.Label(details_box, text="dX: --  |  dY: --", font=("Consolas", 8), fg=self.COLOR_MUTED, bg="#161b22")
        self.lbl_delta_exp.pack(side=tk.RIGHT, padx=6, pady=2)

        # Speech Transcript
        self.lbl_transcript = tk.Label(
            self.expanded_frame,
            text="PTT: Hold [V] Target | [B] Start",
            font=("Segoe UI", 7),
            fg=self.COLOR_MUTED,
            bg=self.COLOR_BG,
            anchor="w"
        )
        self.lbl_transcript.pack(fill=tk.X, padx=6, pady=(1, 4))

        if not self.is_compact:
            self.expanded_frame.pack(fill=tk.BOTH, expand=True)

        # ==========================================
        # 4. BOTTOM FOOTER & RESIZE CORNER HANDLE
        # ==========================================
        self.footer_frame = tk.Frame(self, bg=self.COLOR_BG, height=10)
        self.footer_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.lbl_wheel_hint = tk.Label(
            self.footer_frame,
            text="Scroll wheel: Opacity",
            font=("Segoe UI", 6),
            fg="#3e4859",
            bg=self.COLOR_BG
        )
        self.lbl_wheel_hint.pack(side=tk.LEFT, padx=6)

        # Corner Resize Grip (◢)
        self.resize_grip = tk.Label(
            self.footer_frame,
            text="◢",
            font=("Consolas", 8, "bold"),
            fg="#4a5568",
            bg=self.COLOR_BG,
            cursor="size_nw_se"
        )
        self.resize_grip.pack(side=tk.RIGHT, padx=(0, 2), pady=(0, 1))

    def _setup_bindings(self):
        # Dragging bindings
        for w in (self.header_bar, self.lbl_title):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._do_drag)
            w.bind("<ButtonRelease-1>", self._save_win_position)

        # Manual Corner Resize bindings
        self.resize_grip.bind("<Button-1>", self._start_resize)
        self.resize_grip.bind("<B1-Motion>", self._do_resize)
        self.resize_grip.bind("<ButtonRelease-1>", self._save_resize)

        # MouseWheel Transparency adjustment
        self.bind("<MouseWheel>", self._on_mousewheel_opacity)
        self.bind("<Control-MouseWheel>", self._on_mousewheel_opacity)

        # Recursively bind wheel to core frames for effortless scrolling
        for w in (self.core_frame, self.compact_res_bar, self.lbl_mini_dist, self.lbl_mini_az, self.footer_frame, self.lbl_wheel_hint):
            w.bind("<MouseWheel>", self._on_mousewheel_opacity)

        # Entry bindings
        self.start_entry.bind("<KeyRelease>", self._on_input_changed)
        self.target_entry.bind("<KeyRelease>", self._on_input_changed)
        self.start_entry.bind("<Return>", lambda e: self.target_entry.focus_set())
        self.target_entry.bind("<Return>", lambda e: self.copy_result())
        self.start_entry.bind("<Control-v>", self._on_start_paste)

    # --- DRAGGING LOGIC ---
    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _do_drag(self, event):
        x = self.winfo_x() + (event.x - self._drag_start_x)
        y = self.winfo_y() + (event.y - self._drag_start_y)
        self.geometry(f"+{x}+{y}")

    def _save_win_position(self, event=None):
        self.settings["win_x"] = self.winfo_x()
        self.settings["win_y"] = self.winfo_y()

    # --- CORNER RESIZE LOGIC ---
    def _start_resize(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_orig_w = self.winfo_width()
        self._resize_orig_h = self.winfo_height()

    def _do_resize(self, event):
        dx = event.x_root - self._resize_start_x
        dy = event.y_root - self._resize_start_y
        min_w = 200
        min_h = 100 if self.is_compact else 220
        new_w = max(min_w, self._resize_orig_w + dx)
        new_h = max(min_h, self._resize_orig_h + dy)
        cur_x = self.winfo_x()
        cur_y = self.winfo_y()
        self.geometry(f"{new_w}x{new_h}+{cur_x}+{cur_y}")

    def _save_resize(self, event=None):
        w = self.winfo_width()
        h = self.winfo_height()
        if self.is_compact:
            self.COMPACT_SIZE = (w, h)
            self.settings["compact_w"] = w
            self.settings["compact_h"] = h
        else:
            self.EXPANDED_SIZE = (w, h)
            self.settings["expanded_w"] = w
            self.settings["expanded_h"] = h
        save_settings(self.settings)

    # --- MOUSEWHEEL OPACITY LOGIC ---
    def _on_mousewheel_opacity(self, event):
        # Ignore if scrolling inside Settings dialog
        if self.settings_window is not None and tk.Toplevel.winfo_exists(self.settings_window):
            try:
                if event.widget.winfo_toplevel() == self.settings_window:
                    return
            except Exception:
                pass

        step = 0.05 if event.delta > 0 else -0.05
        self.current_alpha = max(0.20, min(1.0, round(self.current_alpha + step, 2)))
        self.attributes("-alpha", self.current_alpha)
        self.settings["opacity"] = self.current_alpha

        pct = int(self.current_alpha * 100)
        self.lbl_title.config(text=f"OPAC:{pct}%", fg=self.COLOR_AMBER)

        if self._opacity_timer:
            self.after_cancel(self._opacity_timer)
        self._opacity_timer = self.after(900, lambda: self.lbl_title.config(text="WD CALC", fg=self.COLOR_ACCENT))

        save_settings(self.settings)

    def toggle_compact_mode(self):
        """Switches between ultra-compact mini HUD and expanded view."""
        self.is_compact = not self.is_compact
        self.settings["compact_mode"] = self.is_compact

        cur_x = self.winfo_x()
        cur_y = self.winfo_y()

        if self.is_compact:
            self.expanded_frame.pack_forget()
            w, h = self.COMPACT_SIZE
            self.btn_expand.config(text="▼")
        else:
            self.expanded_frame.pack(fill=tk.BOTH, expand=True)
            w, h = self.EXPANDED_SIZE
            self.btn_expand.config(text="▲")

        self.geometry(f"{w}x{h}+{cur_x}+{cur_y}")
        log_info(f"Widget mode: {'COMPACT' if self.is_compact else 'EXPANDED'}")

    # --- GLOBAL PUSH-TO-TALK HOOKS ---
    def _on_global_ptt_down(self, role):
        self.after(0, lambda: self._apply_ptt_down_ui(role))
        self.voice_service.start_ptt(role=role)

    def _on_global_ptt_up(self, role):
        self.after(0, lambda: self._apply_ptt_up_ui())
        self.voice_service.stop_ptt(role=role)

    def _apply_ptt_down_ui(self, role):
        badge_text = "🔴 PTT:TGT" if role == "target" else ("🔴 PTT:START" if role == "start" else "🔴 PTT")
        self.lbl_ptt_badge.config(text=badge_text, bg="#851d1d", fg="#ffffff")
        self.lbl_transcript.config(text=f"Recording [{role.upper()}]... speak numbers", fg=self.COLOR_ACCENT)

    def _apply_ptt_up_ui(self):
        self.lbl_ptt_badge.config(text="🎙️ PTT", bg="#212631", fg=self.COLOR_MUTED)
        self.lbl_transcript.config(text="Transcribing...", fg=self.COLOR_AMBER)

    def toggle_voice_listening(self):
        is_now = self.voice_service.toggle_listening()
        if is_now:
            self.lbl_ptt_badge.config(text="🔴 LIVE", bg="#851d1d", fg="#ffffff")
        else:
            self.lbl_ptt_badge.config(text="🎙️ OFF", bg="#212631", fg=self.COLOR_MUTED)

    def _on_voice_action_async(self, action):
        self.after(0, lambda: self._apply_voice_action(action))

    def _on_voice_partial_async(self, partial_text):
        self.after(0, lambda: self._update_voice_partial(partial_text))

    def _on_voice_status_async(self, status_msg):
        self.after(0, lambda: self._update_voice_status(status_msg))

    def _update_voice_partial(self, text):
        truncated = text if len(text) < 32 else "..." + text[-30:]
        self.lbl_transcript.config(text=truncated, fg=self.COLOR_TEXT)

    def _update_voice_status(self, msg):
        self.lbl_transcript.config(text=msg[:32], fg=self.COLOR_MUTED)

    def _apply_voice_action(self, action):
        act_type = action.get('type')
        if act_type == 'swap':
            self.swap_coordinates()
        elif act_type == 'clear':
            self.clear_all()
        elif act_type == 'copy':
            self.copy_result()
        elif act_type == 'set_both':
            s = action.get('start', '')
            t = action.get('target', '')
            self.start_entry.delete(0, tk.END)
            self.start_entry.insert(0, s)
            self.target_entry.delete(0, tk.END)
            self.target_entry.insert(0, t)
            self.calculate()
            self._flash_widget(self.start_entry)
            self._flash_widget(self.target_entry)
            self.lbl_transcript.config(text=f"S: {s} | T: {t}", fg=self.COLOR_ACCENT)
        elif act_type == 'set_start':
            c = action.get('coord', '')
            self.start_entry.delete(0, tk.END)
            self.start_entry.insert(0, c)
            self.calculate()
            self._flash_widget(self.start_entry)
            self.lbl_transcript.config(text=f"Start: {c}", fg="#7dd3fc")
        elif act_type in ('set_target', 'raw_coord'):
            c = action.get('coord', '')
            self.target_entry.delete(0, tk.END)
            self.target_entry.insert(0, c)
            self.calculate()
            self._flash_widget(self.target_entry)
            self.lbl_transcript.config(text=f"Target: {c}", fg="#f472b6")

    def _flash_widget(self, entry_widget):
        orig = entry_widget.cget("highlightbackground")
        entry_widget.config(highlightbackground=self.COLOR_ACCENT)
        self.after(450, lambda: entry_widget.config(highlightbackground=orig))

    def _on_start_paste(self, event):
        self.after(50, self._check_quad_split)

    def _check_quad_split(self):
        txt = self.start_entry.get().strip()
        quad = detect_full_quad(txt)
        if quad:
            (x1, y1), (x2, y2) = quad
            self.start_entry.delete(0, tk.END)
            self.start_entry.insert(0, f"{x1:.2f} {y1:.2f}")
            self.target_entry.delete(0, tk.END)
            self.target_entry.insert(0, f"{x2:.2f} {y2:.2f}")
            self.calculate()

    def _on_scale_change(self, mult, mode_key):
        self.scale_multiplier.set(mult)
        self.settings["scale_mode"] = mode_key
        self.settings["scale_multiplier"] = mult
        self.calculate()

    def _on_input_changed(self, event=None):
        txt = self.start_entry.get().strip()
        quad = detect_full_quad(txt)
        if quad and not self.target_entry.get().strip():
            (x1, y1), (x2, y2) = quad
            self.start_entry.delete(0, tk.END)
            self.start_entry.insert(0, f"{x1:.2f} {y1:.2f}")
            self.target_entry.delete(0, tk.END)
            self.target_entry.insert(0, f"{x2:.2f} {y2:.2f}")

        self.calculate()

    def calculate(self):
        s_text = self.start_entry.get().strip()
        t_text = self.target_entry.get().strip()

        start_coord = parse_coordinate_string(s_text)
        target_coord = parse_coordinate_string(t_text)

        if not start_coord or not target_coord:
            self.lbl_mini_dist.config(text="DIST: ---", fg=self.COLOR_MUTED)
            self.lbl_mini_az.config(text="AZ: ---°", fg=self.COLOR_MUTED)
            self.lbl_mils_exp.config(text="MILS: --- / ---")
            self.lbl_delta_exp.config(text="dX: --  |  dY: --")
            return

        x1, y1 = start_coord
        x2, y2 = target_coord

        dx = x2 - x1
        dy = y2 - y1

        dist_raw = math.hypot(dx, dy)
        mult = self.scale_multiplier.get()
        dist_meters = dist_raw * mult

        angle_rad = math.atan2(dx, dy)
        bearing_deg = (math.degrees(angle_rad) + 360.0) % 360.0

        nato_mils = (bearing_deg / 360.0) * 6400.0
        soviet_mils = (bearing_deg / 360.0) * 6000.0

        self.lbl_mini_dist.config(text=f"{dist_meters:.1f}m", fg=self.COLOR_ACCENT)
        self.lbl_mini_az.config(text=f"{bearing_deg:05.1f}°", fg=self.COLOR_AMBER)
        self.lbl_mils_exp.config(text=f"MILS: {nato_mils:.0f} / {soviet_mils:.0f}")
        self.lbl_delta_exp.config(text=f"dX: {dx:+.2f} | dY: {dy:+.2f}")

        log_info(f"Calc: Dist={dist_meters:.1f}m, Az={bearing_deg:05.1f}°, dX={dx:+.2f}, dY={dy:+.2f}")

    def swap_coordinates(self):
        s = self.start_entry.get()
        t = self.target_entry.get()
        self.start_entry.delete(0, tk.END)
        self.start_entry.insert(0, t)
        self.target_entry.delete(0, tk.END)
        self.target_entry.insert(0, s)
        self.calculate()

    def clear_all(self):
        self.start_entry.delete(0, tk.END)
        self.target_entry.delete(0, tk.END)
        self.calculate()
        self.start_entry.focus_set()

    def copy_result(self):
        dist = self.lbl_mini_dist.cget("text")
        bearing = self.lbl_mini_az.cget("text")
        if "---" in dist:
            return
        result_str = f"Dist: {dist}, Az: {bearing}"
        self.clipboard_clear()
        self.clipboard_append(result_str)
        log_info(f"Copied: {result_str}")

        orig = self.btn_copy_mini.cget("text")
        self.btn_copy_mini.config(text="✓", bg="#1f6feb")
        self.after(1000, lambda: self.btn_copy_mini.config(text=orig, bg="#212631"))

    def toggle_opacity(self):
        if self.current_alpha >= 0.95:
            self.current_alpha = 0.80
        elif self.current_alpha >= 0.80:
            self.current_alpha = 0.65
        else:
            self.current_alpha = 0.95
        self.settings["opacity"] = self.current_alpha
        self.attributes("-alpha", self.current_alpha)
        self.btn_alpha.config(text=f"🌓 {int(self.current_alpha * 100)}%")

    def switch_language(self, lang):
        self.voice_lang = lang
        self.settings["language"] = lang
        threading.Thread(target=lambda: self.voice_service.set_language(lang), daemon=True).start()

    def open_settings(self):
        if self.settings_window is not None and tk.Toplevel.winfo_exists(self.settings_window):
            self.settings_window.lift()
            self.settings_window.focus_force()
            return
        self.settings_window = SettingsWindow(self, self)

    def _sync_mic_button_ui(self):
        if self.voice_service.is_listening:
            self.lbl_ptt_badge.config(text="🔴 LIVE", bg="#851d1d", fg="#ffffff")
        else:
            self.lbl_ptt_badge.config(text="🎙️ PTT", bg="#212631", fg=self.COLOR_MUTED)

    def _on_closing(self):
        log_info("Closing Wardogs Mortar Calculator overlay.")
        self._save_win_position()
        self._save_resize()
        try:
            self.hotkey_mgr.stop()
            self.voice_service.shutdown()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = MortarCalcWidget()
    app.mainloop()
