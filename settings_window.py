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
from hotkey_manager import VK_TABLE
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

        # PTT keys
        self.ptt_gen_var = tk.StringVar(value=main_app.settings.get("ptt_general_key", "f2"))
        self.ptt_start_var = tk.StringVar(value=main_app.settings.get("ptt_start_key", "b"))
        self.ptt_target_var = tk.StringVar(value=main_app.settings.get("ptt_target_key", "v"))

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
            text="2. GLOBAL PUSH-TO-TALK (PTT) KEYS",
            font=("Consolas", 9, "bold"),
            fg=self.COLOR_ACCENT,
            bg=self.COLOR_CARD
        ).pack(side=tk.LEFT)

        tk.Label(
            card_ptt,
            text="Hold key in-game to speak. Released key calculates coordinates instantly.",
            font=("Segoe UI", 8, "italic"),
            fg=self.COLOR_MUTED,
            bg=self.COLOR_CARD,
            anchor="w"
        ).pack(fill=tk.X, padx=10, pady=(0, 4))

        ptt_grid = tk.Frame(card_ptt, bg=self.COLOR_CARD)
        ptt_grid.pack(fill=tk.X, padx=10, pady=(0, 6))

        avail_keys = sorted(list(VK_TABLE.keys()))

        # General PTT
        row1 = tk.Frame(ptt_grid, bg=self.COLOR_CARD)
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="General PTT Key:", font=("Consolas", 8), fg=self.COLOR_TEXT, bg=self.COLOR_CARD, width=18, anchor="w").pack(side=tk.LEFT)
        cb_gen = ttk.Combobox(row1, textvariable=self.ptt_gen_var, values=avail_keys, state="readonly", width=12)
        cb_gen.pack(side=tk.LEFT, padx=4)

        # Start PTT
        row2 = tk.Frame(ptt_grid, bg=self.COLOR_CARD)
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Start-only PTT [S]:", font=("Consolas", 8), fg="#7dd3fc", bg=self.COLOR_CARD, width=18, anchor="w").pack(side=tk.LEFT)
        cb_start = ttk.Combobox(row2, textvariable=self.ptt_start_var, values=avail_keys, state="readonly", width=12)
        cb_start.pack(side=tk.LEFT, padx=4)
        tk.Label(row2, text="(forces Start coord)", font=("Segoe UI", 7), fg=self.COLOR_MUTED, bg=self.COLOR_CARD).pack(side=tk.LEFT)

        # Target PTT
        row3 = tk.Frame(ptt_grid, bg=self.COLOR_CARD)
        row3.pack(fill=tk.X, pady=2)
        tk.Label(row3, text="Target-only PTT [T]:", font=("Consolas", 8), fg="#f472b6", bg=self.COLOR_CARD, width=18, anchor="w").pack(side=tk.LEFT)
        cb_tgt = ttk.Combobox(row3, textvariable=self.ptt_target_var, values=avail_keys, state="readonly", width=12)
        cb_tgt.pack(side=tk.LEFT, padx=4)
        tk.Label(row3, text="(forces Target coord)", font=("Segoe UI", 7), fg=self.COLOR_MUTED, bg=self.COLOR_CARD).pack(side=tk.LEFT)

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

    def _save_and_apply(self):
        disp = self.combo_var.get()
        dev_info = self.device_map.get(disp)
        if dev_info:
            self.main_app.settings["device_idx"] = dev_info['index']
            self.main_app.settings["device_name"] = dev_info['name']

        # Save PTT hotkeys
        self.main_app.settings["ptt_general_key"] = self.ptt_gen_var.get().lower()
        self.main_app.settings["ptt_start_key"] = self.ptt_start_var.get().lower()
        self.main_app.settings["ptt_target_key"] = self.ptt_target_var.get().lower()
        self.main_app._sync_hotkeys_config()

        self.main_app.settings["engine"] = self.selected_engine
        self.main_app.settings["language"] = self.current_test_lang
        
        # Save logging preference
        is_logging = self.log_enabled_var.get()
        self.main_app.settings["enable_logging"] = is_logging
        set_file_logging(is_logging)

        save_settings(self.main_app.settings)

        messagebox.showinfo("Settings Saved", "Settings & PTT Hotkeys saved successfully!", parent=self)
        self._on_close()

    def _on_close(self):
        self.voice_service.on_audio_level = None
        self.voice_service.on_raw_speech = None
        unsubscribe_from_logs(self._on_new_log_async)

        if self.is_testing_voice:
            self.is_testing_voice = False
            self.voice_service.stop_listening()
            self.main_app._sync_mic_button_ui()

        self.destroy()
