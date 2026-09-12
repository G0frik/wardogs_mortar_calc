"""
SETTINGS & VOICE TEST WINDOW
Provides interactive microphone selection, Push-to-Talk (PTT) key configuration,
STT Engine selector (Google Speech, Whisper, Vosk), real-time audio volume VU meter,
live speech recognition testing for English & Ukrainian, and diagnostic logging.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

from voice_service import get_available_input_devices
from hotkey_manager import (
    VK_TABLE, format_key_display, vk_to_storage_name,
    storage_name_to_vk, CHECKED_VKS, user32
)
from logger import (
    log_info, log_error, get_recent_logs, subscribe_to_logs,
    unsubscribe_from_logs, clear_log_file, set_file_logging,
    is_file_logging_enabled, get_log_file_size_kb, LOG_FILE
)
from settings_manager import save_settings


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.parent = parent
        self.main_app = main_app
        self.voice_service = main_app.voice_service

        self.title("SETTINGS & VOICE DIAGNOSTICS // WARDOGS")
        self.geometry("490x740")
        self.minsize(460, 640)
        self.configure(bg=main_app.COLOR_BG)

        if main_app.always_on_top:
            self.attributes("-topmost", True)

        self.devices = []
        self.device_map = {}
        self.selected_device_idx = main_app.settings.get("device_idx")

        # Hotkeys state
        self.ptt_gen_var = tk.StringVar(value=main_app.settings.get("ptt_general_key", "f2"))
        self.ptt_start_var = tk.StringVar(value=main_app.settings.get("ptt_start_key", "b"))
        self.ptt_target_var = tk.StringVar(value=main_app.settings.get("ptt_target_key", "v"))
        self.toggle_hide_var = tk.StringVar(value=main_app.settings.get("toggle_hide_key", "f4"))

        self.keybind_vars = {
            "general": self.ptt_gen_var,
            "start": self.ptt_start_var,
            "target": self.ptt_target_var,
            "hide": self.toggle_hide_var
        }
        self.keybind_buttons = {}
        self.active_bind_role = None
        self._poll_keybind_timer = None
        self._keys_down_at_start = set()

        # Engine & Language
        self.selected_engine = main_app.settings.get("engine", "google")
        self.current_test_lang = main_app.voice_lang
        self.is_testing_voice = False

        # Palette
        self.COLOR_BG = main_app.COLOR_BG
        self.COLOR_CARD = main_app.COLOR_CARD
        self.COLOR_CARD_BORDER = main_app.COLOR_BORDER
        self.COLOR_TEXT = main_app.COLOR_TEXT
        self.COLOR_MUTED = main_app.COLOR_MUTED
        self.COLOR_ACCENT = main_app.COLOR_ACCENT
        self.COLOR_AMBER = main_app.COLOR_AMBER
        self.COLOR_RED = main_app.COLOR_RED

        self._build_ui()
        self._load_devices()
        self._setup_voice_hooks()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        header = tk.Frame(self, bg=self.COLOR_BG)
        header.pack(fill=tk.X, padx=14, pady=(10, 4))

        tk.Label(
            header,
            text="SETTINGS & VOICE DIAGNOSTICS",
            font=("Consolas", 12, "bold"),
            fg=self.COLOR_ACCENT,
            bg=self.COLOR_BG
        ).pack(side=tk.LEFT)

        main_frame = tk.Frame(self, bg=self.COLOR_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=2)

        # ==========================================
        # SECTION 1: MICROPHONE HARDWARE
        # ==========================================
        card_mic = tk.Frame(main_frame, bg=self.COLOR_CARD, highlightbackground=self.COLOR_CARD_BORDER, highlightthickness=1)
        card_mic.pack(fill=tk.X, pady=(0, 6))

        mic_header = tk.Frame(card_mic, bg=self.COLOR_CARD)
        mic_header.pack(fill=tk.X, padx=10, pady=(6, 2))

        tk.Label(
            mic_header,
            text="1. MICROPHONE INPUT DEVICE",
            font=("Consolas", 9, "bold"),
            fg=self.COLOR_ACCENT,
            bg=self.COLOR_CARD
        ).pack(side=tk.LEFT)

        refresh_btn = tk.Button(
            mic_header,
            text="🔄 Refresh",
            font=("Segoe UI", 8),
            bg="#212631",
            fg=self.COLOR_TEXT,
            activebackground="#2c3340",
            relief=tk.FLAT,
            padx=6,
            pady=1,
            cursor="hand2",
            command=self._load_devices
        )
        refresh_btn.pack(side=tk.RIGHT)

        self.combo_var = tk.StringVar()
        self.combo_devices = ttk.Combobox(
            card_mic,
            textvariable=self.combo_var,
            state="readonly",
            font=("Segoe UI", 9)
        )
        self.combo_devices.pack(fill=tk.X, padx=10, pady=(2, 4))
        self.combo_devices.bind("<<ComboboxSelected>>", self._on_device_selected)

        # VU Volume Meter
        meter_frame = tk.Frame(card_mic, bg=self.COLOR_CARD)
        meter_frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        tk.Label(
            meter_frame,
            text="MIC LEVEL:",
            font=("Consolas", 8, "bold"),
            fg=self.COLOR_MUTED,
            bg=self.COLOR_CARD
        ).pack(side=tk.LEFT)

        self.canvas_meter = tk.Canvas(meter_frame, height=10, bg="#0d1117", highlightthickness=1, highlightbackground="#30363d")
        self.canvas_meter.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        self.meter_bar = self.canvas_meter.create_rectangle(0, 0, 0, 10, fill=self.COLOR_ACCENT, width=0)

        self.lbl_meter_pct = tk.Label(
            meter_frame,
            text="0%",
            font=("Consolas", 8),
            fg=self.COLOR_MUTED,
            bg=self.COLOR_CARD,
            width=5
        )
        self.lbl_meter_pct.pack(side=tk.RIGHT)

        # ==========================================
        # SECTION 2: PUSH-TO-TALK (PTT) HOTKEYS
        # ==========================================
        card_ptt = tk.Frame(main_frame, bg=self.COLOR_CARD, highlightbackground=self.COLOR_CARD_BORDER, highlightthickness=1)
        card_ptt.pack(fill=tk.X, pady=(0, 6))

        ptt_header = tk.Frame(card_ptt, bg=self.COLOR_CARD)
        ptt_header.pack(fill=tk.X, padx=10, pady=(6, 2))

        tk.Label(
            ptt_header,
            text="2. HOTKEYS & PUSH-TO-TALK (PTT)",
            font=("Consolas", 9, "bold"),
            fg=self.COLOR_ACCENT,
            bg=self.COLOR_CARD
        ).pack(side=tk.LEFT)

        tk.Label(
            card_ptt,
            text="Hold PTT to speak, or use Toggle Hide key to show/hide overlay in-game.",
            font=("Segoe UI", 8, "italic"),
            fg=self.COLOR_MUTED,
            bg=self.COLOR_CARD,
            anchor="w"
        ).pack(fill=tk.X, padx=10, pady=(0, 4))

        ptt_grid = tk.Frame(card_ptt, bg=self.COLOR_CARD)
        ptt_grid.pack(fill=tk.X, padx=10, pady=(0, 4))

        roles_info = [
            ("general", "General PTT:", "Voice missions & tactical commands", self.COLOR_TEXT),
            ("start", "Start-only PTT [S]:", "Forces digits directly to Start", "#7dd3fc"),
            ("target", "Target-only PTT [T]:", "Forces digits directly to Target", "#f472b6"),
            ("hide", "Toggle Hide / Show:", "Show or hide HUD overlay in-game", self.COLOR_AMBER)
        ]

        for role, label_text, sub_text, color in roles_info:
            row = tk.Frame(ptt_grid, bg=self.COLOR_CARD)
            row.pack(fill=tk.X, pady=3)

            lbl_col = tk.Frame(row, bg=self.COLOR_CARD, width=155)
            lbl_col.pack(side=tk.LEFT, fill=tk.Y)
            lbl_col.pack_propagate(False)

            tk.Label(
                lbl_col,
                text=label_text,
                font=("Consolas", 8, "bold"),
                fg=color,
                bg=self.COLOR_CARD,
                anchor="w"
            ).pack(anchor="w")

            tk.Label(
                lbl_col,
                text=sub_text,
                font=("Segoe UI", 6, "italic"),
                fg=self.COLOR_MUTED,
                bg=self.COLOR_CARD,
                anchor="w"
            ).pack(anchor="w")

            cur_key = self.keybind_vars[role].get()
            is_unbound = (cur_key.lower() in ("none", "0", ""))

            btn_slot = tk.Button(
                row,
                text=f"[ {format_key_display(cur_key)} ]",
                font=("Consolas", 8, "bold"),
                bg="#1a202c" if not is_unbound else "#161b22",
                fg=self.COLOR_ACCENT if not is_unbound else self.COLOR_MUTED,
                activebackground="#2d3748",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                width=19,
                padx=4,
                pady=2,
                cursor="hand2",
                command=lambda r=role: self._start_bind(r)
            )
            btn_slot.pack(side=tk.LEFT, padx=(4, 4))
            self.keybind_buttons[role] = btn_slot

            btn_unbind = tk.Button(
                row,
                text="✕",
                font=("Segoe UI", 7, "bold"),
                bg="#21262d",
                fg=self.COLOR_RED,
                activebackground="#3b1d1d",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                padx=6,
                pady=1,
                cursor="hand2",
                command=lambda r=role: self._unbind_key(r)
            )
            btn_unbind.pack(side=tk.LEFT, padx=2)

        self.lbl_bind_hint = tk.Label(
            card_ptt,
            text="Click slot to bind any key or mouse side button • ✕ to unbind",
            font=("Segoe UI", 7, "italic"),
            fg=self.COLOR_MUTED,
            bg=self.COLOR_CARD,
            anchor="w"
        )
        self.lbl_bind_hint.pack(fill=tk.X, padx=10, pady=(2, 6))

        # ==========================================
        # SECTION 3: SPEECH RECOGNITION ENGINE
        # ==========================================
        card_engine = tk.Frame(main_frame, bg=self.COLOR_CARD, highlightbackground=self.COLOR_CARD_BORDER, highlightthickness=1)
        card_engine.pack(fill=tk.X, pady=(0, 6))

        engine_header = tk.Frame(card_engine, bg=self.COLOR_CARD)
        engine_header.pack(fill=tk.X, padx=10, pady=(6, 2))

        tk.Label(
            engine_header,
            text="3. SPEECH-TO-TEXT (STT) ENGINE",
            font=("Consolas", 9, "bold"),
            fg=self.COLOR_ACCENT,
            bg=self.COLOR_CARD
        ).pack(side=tk.LEFT)

        self.engine_var = tk.StringVar(value=self.selected_engine)

        engines_box = tk.Frame(card_engine, bg=self.COLOR_CARD)
        engines_box.pack(fill=tk.X, padx=10, pady=(0, 6))

        engines = [
            ("Google Speech (Cloud / 0% CPU - Best Accuracy)", "google"),
            ("Faster-Whisper (Local AI / Offline)", "whisper"),
            ("Vosk (Local Offline / Fast)", "vosk")
        ]

        for label, key in engines:
            rb = tk.Radiobutton(
                engines_box,
                text=label,
                variable=self.engine_var,
                value=key,
                font=("Segoe UI", 8),
                fg=self.COLOR_TEXT,
                bg=self.COLOR_CARD,
                selectcolor=self.COLOR_BG,
                activebackground=self.COLOR_CARD,
                activeforeground=self.COLOR_ACCENT,
                command=self._on_engine_changed
            )
            rb.pack(anchor="w", pady=1)

        # ==========================================
        # SECTION 4: LIVE SPEECH TEST AREA
        # ==========================================
        card_test = tk.Frame(main_frame, bg=self.COLOR_CARD, highlightbackground=self.COLOR_CARD_BORDER, highlightthickness=1)
        card_test.pack(fill=tk.X, pady=(0, 6))

        test_header = tk.Frame(card_test, bg=self.COLOR_CARD)
        test_header.pack(fill=tk.X, padx=10, pady=(6, 2))

        tk.Label(
            test_header,
            text="4. VOICE TEST (SPEAK NUMBERS)",
            font=("Consolas", 9, "bold"),
            fg=self.COLOR_AMBER,
            bg=self.COLOR_CARD
        ).pack(side=tk.LEFT)

        lang_subframe = tk.Frame(test_header, bg=self.COLOR_CARD)
        lang_subframe.pack(side=tk.RIGHT)

        self.test_btn_ua = tk.Button(
            lang_subframe,
            text="🇺🇦 UA",
            font=("Segoe UI", 8, "bold" if self.current_test_lang == "uk" else "normal"),
            bg="#0f382c" if self.current_test_lang == "uk" else "#212631",
            fg=self.COLOR_ACCENT if self.current_test_lang == "uk" else self.COLOR_MUTED,
            relief=tk.FLAT,
            padx=6,
            pady=1,
            cursor="hand2",
            command=lambda: self._set_test_language("uk")
        )
        self.test_btn_ua.pack(side=tk.LEFT, padx=2)

        self.test_btn_en = tk.Button(
            lang_subframe,
            text="🇬🇧 EN",
            font=("Segoe UI", 8, "bold" if self.current_test_lang == "en" else "normal"),
            bg="#0f382c" if self.current_test_lang == "en" else "#212631",
            fg=self.COLOR_ACCENT if self.current_test_lang == "en" else self.COLOR_MUTED,
            relief=tk.FLAT,
            padx=6,
            pady=1,
            cursor="hand2",
            command=lambda: self._set_test_language("en")
        )
        self.test_btn_en.pack(side=tk.LEFT, padx=2)

        self.lbl_test_hint = tk.Label(
            card_test,
            text="Speak single digits (e.g. 'один два чотири три три вісім девять пять')",
            font=("Segoe UI", 8, "italic"),
            fg=self.COLOR_MUTED,
            bg=self.COLOR_CARD,
            anchor="w"
        )
        self.lbl_test_hint.pack(fill=tk.X, padx=10, pady=(0, 4))

        test_display_frame = tk.Frame(card_test, bg="#0d1117", highlightthickness=1, highlightbackground="#252a36")
        test_display_frame.pack(fill=tk.X, padx=10, pady=(2, 6))

        # Status
        row_partial = tk.Frame(test_display_frame, bg="#0d1117")
        row_partial.pack(fill=tk.X, padx=8, pady=(4, 2))
        tk.Label(row_partial, text="STATUS:     ", font=("Consolas", 7, "bold"), fg=self.COLOR_MUTED, bg="#0d1117").pack(side=tk.LEFT)
        self.lbl_test_partial = tk.Label(row_partial, text="Click Start Test below or hold PTT key", font=("Segoe UI", 9, "bold"), fg=self.COLOR_TEXT, bg="#0d1117")
        self.lbl_test_partial.pack(side=tk.LEFT, padx=6)

        # Raw Output
        row_raw = tk.Frame(test_display_frame, bg="#0d1117")
        row_raw.pack(fill=tk.X, padx=8, pady=2)
        tk.Label(row_raw, text="TRANSCRIPT: ", font=("Consolas", 7, "bold"), fg=self.COLOR_MUTED, bg="#0d1117").pack(side=tk.LEFT)
        self.lbl_test_raw = tk.Label(row_raw, text="---", font=("Consolas", 9), fg=self.COLOR_AMBER, bg="#0d1117")
        self.lbl_test_raw.pack(side=tk.LEFT, padx=6)

        # Parsed Data
        row_parsed = tk.Frame(test_display_frame, bg="#0d1117")
        row_parsed.pack(fill=tk.X, padx=8, pady=(2, 6))
        tk.Label(row_parsed, text="PARSED DATA:", font=("Consolas", 7, "bold"), fg=self.COLOR_MUTED, bg="#0d1117").pack(side=tk.LEFT)
        self.lbl_test_parsed = tk.Label(row_parsed, text="---", font=("Consolas", 9, "bold"), fg=self.COLOR_ACCENT, bg="#0d1117")
        self.lbl_test_parsed.pack(side=tk.LEFT, padx=6)

        self.btn_toggle_test = tk.Button(
            card_test,
            text="🎙️ START VOICE TEST",
            font=("Consolas", 9, "bold"),
            bg="#21262d",
            fg=self.COLOR_ACCENT,
            activebackground="#30363d",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._toggle_test
        )
        self.btn_toggle_test.pack(fill=tk.X, padx=10, pady=(2, 6))

        # ==========================================
        # SECTION 5: SYSTEM LOGS & RETENTION
        # ==========================================
        card_log = tk.Frame(main_frame, bg=self.COLOR_CARD, highlightbackground=self.COLOR_CARD_BORDER, highlightthickness=1)
        card_log.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        log_header = tk.Frame(card_log, bg=self.COLOR_CARD)
        log_header.pack(fill=tk.X, padx=10, pady=(6, 2))

        tk.Label(
            log_header,
            text="5. DIAGNOSTIC LOG",
            font=("Consolas", 9, "bold"),
            fg=self.COLOR_TEXT,
            bg=self.COLOR_CARD
        ).pack(side=tk.LEFT)

        btn_box = tk.Frame(log_header, bg=self.COLOR_CARD)
        btn_box.pack(side=tk.RIGHT)

        tk.Button(
            btn_box,
            text="📄 Open File",
            font=("Segoe UI", 7),
            bg="#212631",
            fg=self.COLOR_TEXT,
            activebackground="#2c3340",
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            command=self._open_log_file
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            btn_box,
            text="✕ Clear",
            font=("Segoe UI", 7),
            bg="#212631",
            fg=self.COLOR_RED,
            activebackground="#2c3340",
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            command=self._clear_logs
        ).pack(side=tk.LEFT, padx=2)

        # File logging toggle & size indicator
        log_ctrl_row = tk.Frame(card_log, bg=self.COLOR_CARD)
        log_ctrl_row.pack(fill=tk.X, padx=10, pady=(2, 4))

        self.log_enabled_var = tk.BooleanVar(value=self.main_app.settings.get("enable_logging", False))
        chk_log = tk.Checkbutton(
            log_ctrl_row,
            text="Save to disk (mortar_calc.log)",
            variable=self.log_enabled_var,
            font=("Segoe UI", 8),
            bg=self.COLOR_CARD,
            fg=self.COLOR_TEXT,
            selectcolor="#0c0e12",
            activebackground=self.COLOR_CARD,
            activeforeground=self.COLOR_TEXT,
            command=self._on_toggle_file_logging
        )
        chk_log.pack(side=tk.LEFT)

        self.lbl_log_size = tk.Label(
            log_ctrl_row,
            text=self._get_size_display_text(),
            font=("Consolas", 7),
            fg=self.COLOR_MUTED,
            bg=self.COLOR_CARD
        )
        self.lbl_log_size.pack(side=tk.RIGHT)

        self.txt_log = tk.Text(
            card_log,
            bg="#0c0e12",
            fg="#94a3b8",
            insertbackground=self.COLOR_ACCENT,
            font=("Consolas", 8),
            relief=tk.FLAT,
            wrap=tk.WORD,
            height=4
        )
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 6))

        for l in get_recent_logs():
            self.txt_log.insert(tk.END, l + "\n")
        self.txt_log.see(tk.END)

        # ==========================================
        # BOTTOM SAVE & CLOSE
        # ==========================================
        bottom_bar = tk.Frame(self, bg=self.COLOR_BG)
        bottom_bar.pack(fill=tk.X, padx=14, pady=(0, 10))

        btn_save = tk.Button(
            bottom_bar,
            text="✓ SAVE & APPLY SETTINGS",
            font=("Segoe UI", 9, "bold"),
            bg="#238636",
            fg="#ffffff",
            activebackground="#2ea043",
            relief=tk.FLAT,
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._save_and_apply
        )
        btn_save.pack(side=tk.LEFT)

        btn_close = tk.Button(
            bottom_bar,
            text="CLOSE",
            font=("Segoe UI", 9),
            bg="#21262d",
            fg=self.COLOR_MUTED,
            activebackground="#30363d",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._on_close
        )
        btn_close.pack(side=tk.RIGHT)

    def _setup_voice_hooks(self):
        self.voice_service.on_audio_level = self._on_audio_level_async
        self.voice_service.on_raw_speech = self._on_raw_speech_async
        subscribe_to_logs(self._on_new_log_async)

    def _load_devices(self):
        self.devices = get_available_input_devices()
        self.device_map = {}
        display_list = []

        current_active_idx = self.voice_service.active_device_idx

        selected_display = ""
        for d in self.devices:
            disp = f"[{d['index']}] {d['name']} ({d['api']})"
            self.device_map[disp] = d
            display_list.append(disp)
            if d['index'] == current_active_idx:
                selected_display = disp

        self.combo_devices["values"] = display_list
        if selected_display:
            self.combo_var.set(selected_display)
        elif display_list:
            self.combo_var.set(display_list[0])
            self.selected_device_idx = self.devices[0]['index']

    def _on_device_selected(self, event=None):
        disp = self.combo_var.get()
        dev_info = self.device_map.get(disp)
        if dev_info:
            self.selected_device_idx = dev_info['index']
            self.voice_service.set_device(self.selected_device_idx)
            self.main_app.settings["device_idx"] = self.selected_device_idx
            self.main_app.settings["device_name"] = dev_info['name']

    def _on_engine_changed(self):
        eng = self.engine_var.get()
        self.selected_engine = eng
        self.voice_service.set_engine(eng)
        self.main_app.settings["engine"] = eng
        log_info(f"Engine selected: {eng.upper()}")

    def _set_test_language(self, lang):
        self.current_test_lang = lang
        if lang == "uk":
            self.test_btn_ua.config(bg="#0f382c", fg=self.COLOR_ACCENT, font=("Segoe UI", 8, "bold"))
            self.test_btn_en.config(bg="#212631", fg=self.COLOR_MUTED, font=("Segoe UI", 8))
            self.lbl_test_hint.config(text="Speak single digits (e.g. 'один два чотири три три вісім девять пять')")
        else:
            self.test_btn_en.config(bg="#0f382c", fg=self.COLOR_ACCENT, font=("Segoe UI", 8, "bold"))
            self.test_btn_ua.config(bg="#212631", fg=self.COLOR_MUTED, font=("Segoe UI", 8))
            self.lbl_test_hint.config(text="Speak single digits (e.g. 'one two four three three eight nine five')")

        self.main_app.switch_language(lang)

    def _toggle_test(self):
        if self.is_testing_voice:
            self.is_testing_voice = False
            self.voice_service.stop_listening()
            self.btn_toggle_test.config(
                text="🎙️ START VOICE TEST",
                bg="#21262d",
                fg=self.COLOR_ACCENT
            )
            self.lbl_test_partial.config(text="Test stopped.")
        else:
            self.is_testing_voice = True
            self.voice_service.start_listening()
            self.btn_toggle_test.config(
                text="⏹️ STOP TEST (LISTENING...)",
                bg="#851d1d",
                fg="#ffffff"
            )
            self.lbl_test_partial.config(text="Listening... speak numbers now!")
            self.lbl_test_raw.config(text="---")
            self.lbl_test_parsed.config(text="---")

    def _on_audio_level_async(self, level):
        self.after(0, lambda: self._update_meter_ui(level))

    def _update_meter_ui(self, level):
        if not self.winfo_exists():
            return
        try:
            width = self.canvas_meter.winfo_width()
            if width <= 1:
                width = 200
            bar_w = int(level * width)
            
            bar_color = self.COLOR_ACCENT
            if level > 0.85:
                bar_color = self.COLOR_RED
            elif level > 0.60:
                bar_color = self.COLOR_AMBER

            self.canvas_meter.coords(self.meter_bar, 0, 0, bar_w, 10)
            self.canvas_meter.itemconfig(self.meter_bar, fill=bar_color)
            self.lbl_meter_pct.config(text=f"{int(level * 100)}%")
        except Exception:
            pass

    def _on_raw_speech_async(self, raw_text, action):
        self.after(0, lambda: self._update_speech_test_ui(raw_text, action))

    def _update_speech_test_ui(self, raw_text, action):
        if not self.winfo_exists():
            return
        try:
            self.lbl_test_partial.config(text="Speech registered!", fg=self.COLOR_ACCENT)
            self.lbl_test_raw.config(text=f"\"{raw_text}\"")

            if action:
                act_type = action.get('type')
                if act_type == 'set_both':
                    parsed_str = f"Set Both -> Start: {action.get('start')} | Target: {action.get('target')}"
                elif act_type == 'set_start':
                    parsed_str = f"Set Start -> {action.get('coord')}"
                elif act_type == 'set_target':
                    parsed_str = f"Set Target -> {action.get('coord')}"
                elif act_type == 'raw_coord':
                    parsed_str = f"Coordinate -> {action.get('coord')}"
                else:
                    parsed_str = f"Command -> {act_type.upper()}"
                self.lbl_test_parsed.config(text=parsed_str, fg=self.COLOR_ACCENT)
            else:
                self.lbl_test_parsed.config(text="Unrecognized pattern", fg=self.COLOR_MUTED)
        except Exception:
            pass

    def _on_new_log_async(self, log_msg):
        self.after(0, lambda: self._append_log_line(log_msg))

    def _get_size_display_text(self):
        size_kb = get_log_file_size_kb()
        status = "Active" if self.log_enabled_var.get() else "Off"
        return f"Disk: {size_kb} KB ({status}) | Max 256 KB"

    def _update_log_size_ui(self):
        if hasattr(self, 'lbl_log_size') and self.winfo_exists():
            try:
                self.lbl_log_size.config(text=self._get_size_display_text())
            except Exception:
                pass

    def _on_toggle_file_logging(self):
        enabled = self.log_enabled_var.get()
        set_file_logging(enabled)
        self.main_app.settings["enable_logging"] = enabled
        self._update_log_size_ui()

    def _append_log_line(self, log_msg):
        if not self.winfo_exists():
            return
        try:
            self.txt_log.insert(tk.END, log_msg + "\n")
            self.txt_log.see(tk.END)
            self._update_log_size_ui()
        except Exception:
            pass

    def _clear_logs(self):
        clear_log_file()
        self.txt_log.delete("1.0", tk.END)
        self._update_log_size_ui()
        messagebox.showinfo("Logs Cleared", "Log file and memory buffer have been reset to 0 KB.", parent=self)

    def _open_log_file(self):
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
            try:
                os.startfile(LOG_FILE)
            except Exception as e:
                log_error(f"Failed to open log file: {e}")
        else:
            messagebox.showinfo(
                "No Log File",
                "Log file is empty or file logging is currently disabled.\nEnable 'Save to disk' to write logs.",
                parent=self
            )

    def _save_all_settings_silent(self):
        """Silently persists all settings dialog states to disk."""
        try:
            disp = self.combo_var.get()
            dev_info = self.device_map.get(disp)
            if dev_info:
                self.main_app.settings["device_idx"] = dev_info['index']
                self.main_app.settings["device_name"] = dev_info['name']

            self.main_app.settings["ptt_general_key"] = self.ptt_gen_var.get().lower()
            self.main_app.settings["ptt_start_key"] = self.ptt_start_var.get().lower()
            self.main_app.settings["ptt_target_key"] = self.ptt_target_var.get().lower()
            self.main_app.settings["toggle_hide_key"] = self.toggle_hide_var.get().lower()
            self.main_app._sync_hotkeys_config()

            self.main_app.settings["engine"] = self.selected_engine
            self.main_app.settings["language"] = self.current_test_lang
            
            is_logging = self.log_enabled_var.get()
            self.main_app.settings["enable_logging"] = is_logging
            set_file_logging(is_logging)

            save_settings(self.main_app.settings)
        except Exception as e:
            log_warning(f"Failed to auto-save settings: {e}")

    def _save_and_apply(self):
        self._save_all_settings_silent()
        messagebox.showinfo("Settings Saved", "Settings & Hotkeys saved successfully!", parent=self)
        self._on_close()

    # ==========================================
    # INTERACTIVE KEYBIND CAPTURE LOGIC
    # ==========================================
    def _start_bind(self, role):
        """Puts the selected PTT slot into listening/recording mode."""
        if self.active_bind_role == role:
            self._cancel_bind()
            return

        self._cancel_bind()

        self.active_bind_role = role
        btn = self.keybind_buttons.get(role)
        if btn:
            btn.config(
                text="[ PRESS ANY KEY... ]",
                bg="#4a3800",
                fg=self.COLOR_AMBER,
                activebackground="#4a3800",
                activeforeground=self.COLOR_AMBER
            )

        self.lbl_bind_hint.config(
            text=">>> Press any Key, Mouse 4/5, or ESC/✕ to Unbind <<<",
            fg=self.COLOR_AMBER
        )

        # Snapshot keys already down at start so holding a key doesn't trigger immediately
        self._keys_down_at_start = {
            vk for vk in CHECKED_VKS if user32.GetAsyncKeyState(vk) & 0x8000
        }
        self._poll_keybind_timer = self.after(30, self._poll_keybind)

    def _poll_keybind(self):
        if not self.winfo_exists() or not self.active_bind_role:
            return

        for vk in CHECKED_VKS:
            if vk == 0x01:  # Left mouse click ignored as keybind
                continue

            if user32.GetAsyncKeyState(vk) & 0x8000:
                if vk in self._keys_down_at_start:
                    continue  # Still held down from before click

                # Captured key!
                if vk in (0x1B, 0x08, 0x2E):  # ESC, Backspace, Delete -> unbind
                    self._apply_bind(self.active_bind_role, "none")
                else:
                    name = vk_to_storage_name(vk)
                    self._apply_bind(self.active_bind_role, name)
                return

        # Keep checking every 25ms
        self._poll_keybind_timer = self.after(25, self._poll_keybind)

    def _apply_bind(self, role, key_name):
        # Resolve conflicts: if another slot already uses this key, clear it
        if key_name != "none":
            for other_role, var in self.keybind_vars.items():
                if other_role != role and var.get().lower() == key_name.lower():
                    var.set("none")

        var = self.keybind_vars.get(role)
        if var:
            var.set(key_name)

        self._sync_live_hotkeys()
        self._cancel_bind()
        self._refresh_keybind_ui()

    def _unbind_key(self, role):
        self._cancel_bind()
        var = self.keybind_vars.get(role)
        if var:
            var.set("none")
        self._sync_live_hotkeys()
        self._refresh_keybind_ui()

    def _cancel_bind(self):
        if self._poll_keybind_timer:
            try:
                self.after_cancel(self._poll_keybind_timer)
            except Exception:
                pass
            self._poll_keybind_timer = None

        self.active_bind_role = None
        self._refresh_keybind_ui()

    def _sync_live_hotkeys(self):
        """Immediately applies and persists keybind changes to settings and hotkey manager."""
        gen_k = self.ptt_gen_var.get().lower()
        start_k = self.ptt_start_var.get().lower()
        target_k = self.ptt_target_var.get().lower()
        hide_k = self.toggle_hide_var.get().lower()

        # Update main app settings in-memory
        self.main_app.settings["ptt_general_key"] = gen_k
        self.main_app.settings["ptt_start_key"] = start_k
        self.main_app.settings["ptt_target_key"] = target_k
        self.main_app.settings["toggle_hide_key"] = hide_k

        # Reconfigure active live hotkey manager
        try:
            self.main_app.hotkey_mgr.configure(
                general_key=gen_k,
                start_key=start_k,
                target_key=target_k,
                toggle_hide_key=hide_k
            )
        except Exception:
            pass

        # Persist immediately to disk so changes are never lost
        save_settings(self.main_app.settings)

    def _refresh_keybind_ui(self):
        if not self.winfo_exists():
            return
        for r, btn in self.keybind_buttons.items():
            if self.active_bind_role == r:
                continue
            cur_key = self.keybind_vars[r].get()
            is_unbound = (cur_key.lower() in ("none", "0", ""))
            disp_text = f"[ {format_key_display(cur_key)} ]"
            btn.config(
                text=disp_text,
                bg="#1a202c" if not is_unbound else "#161b22",
                fg=self.COLOR_ACCENT if not is_unbound else self.COLOR_MUTED,
                activebackground="#2d3748",
                activeforeground="#ffffff"
            )
        if not self.active_bind_role and hasattr(self, 'lbl_bind_hint'):
            self.lbl_bind_hint.config(
                text="Click slot to bind any key or mouse side button • ✕ to unbind",
                fg=self.COLOR_MUTED
            )

    def _on_close(self):
        self._save_all_settings_silent()
        self._cancel_bind()
        self.voice_service.on_audio_level = None
        self.voice_service.on_raw_speech = None
        unsubscribe_from_logs(self._on_new_log_async)

        if self.is_testing_voice:
            self.is_testing_voice = False
            self.voice_service.stop_listening()
            self.main_app._sync_mic_button_ui()

        self.destroy()
