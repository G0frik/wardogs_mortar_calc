"""
MULTI-ENGINE VOICE RECOGNITION SERVICE (OPTIMIZED)
Supports:
1. Google Speech Recognition (Cloud / 0% CPU load / Highest Accuracy for Ukrainian & English)
2. Faster-Whisper (Local Neural AI / Offline / High Accuracy)
3. Vosk (Local Kaldi / Offline / Lightweight)
Includes Global Push-to-Talk (PTT) with dedicated Start and Target role routing.
"""

import array
import io
import json
import os
import queue
import threading
import time
import sounddevice as sd

import speech_recognition as sr
from voice_parser import parse_voice_text, extract_numbers_and_digits, format_single_point
from logger import log_info, log_warning, log_error

# Lazy engine imports to minimize RAM & startup latency
VOSK_AVAILABLE = True
WHISPER_AVAILABLE = True

VOSK_MODEL_CONFIGS = {
    "en": {
        "dir": "vosk-model-small-en-us-0.15",
        "label": "English (US)"
    },
    "uk": {
        "dir": "vosk-model-small-uk-v3-nano",
        "label": "Ukrainian (UA)"
    }
}


def get_available_input_devices():
    """Returns a list of all valid audio input devices."""
    results = []
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception as e:
        log_error(f"Failed to query audio devices: {e}")
        return results

    for idx, d in enumerate(devices):
        if d.get('max_input_channels', 0) > 0:
            hostapi_idx = d.get('hostapi', None)
            api_name = hostapis[hostapi_idx]['name'] if hostapi_idx is not None and hostapi_idx < len(hostapis) else 'Standard'
            
            supported_rates = []
            for r in [48000, 44100, 16000]:
                try:
                    sd.check_input_settings(device=idx, channels=1, dtype='int16', samplerate=r)
                    supported_rates.append(r)
                except Exception:
                    pass

            if supported_rates:
                results.append({
                    "index": idx,
                    "name": d['name'],
                    "api": api_name,
                    "channels": d['max_input_channels'],
                    "supported_rates": supported_rates,
                    "default_rate": supported_rates[0]
                })

    return results


def find_optimal_input_device():
    """Auto-detects the best microphone device."""
    devs = get_available_input_devices()
    if not devs:
        return None, None, None

    for d in devs:
        name_lower = d['name'].lower()
        if any(k in name_lower for k in ['g435', 'mic', 'microphone', 'headset']):
            return d['index'], d['default_rate'], d['name']

    return devs[0]['index'], devs[0]['default_rate'], devs[0]['name']


class VoiceRecognitionService:
    def __init__(self, models_dir="models", on_action=None, on_partial=None, on_status=None, on_audio_level=None, on_raw_speech=None):
        self.models_dir = os.path.abspath(models_dir)
        self.on_action = on_action
        self.on_partial = on_partial
        self.on_status = on_status
        self.on_audio_level = on_audio_level
        self.on_raw_speech = on_raw_speech

        self.current_engine = "google"  # Default 0% CPU engine
        self.current_lang = "uk"
        self.is_listening = False
        self.is_running = False

        # Audio Hardware
        self.active_rate = 48000
        self.active_device_idx = None
        self.active_device_name = "Default Mic"
        self.stream = None

        # Engine objects (Lazy Loaded)
        self.sr_recognizer = sr.Recognizer()
        self.whisper_model = None
        self.vosk_models = {}
        self.active_vosk_recognizer = None

        # VAD & Push-To-Talk state
        self.vad_threshold = 0.022
        self.is_speaking = False
        self.is_ptt_active = False
        self.active_ptt_role = "general"
        self.speech_frames = []
        self.silence_frames_count = 0
        self.pre_speech_buffer = []
        self.pre_buffer_max_chunks = 5

        # Threading
        self.audio_queue = queue.Queue()
        self.transcribe_queue = queue.Queue()
        self.worker_thread = None
        self.transcribe_thread = None

    def initialize(self, default_lang="uk", preferred_device_idx=None, engine="google"):
        """Initializes selected audio device and recognition engine with lazy loading."""
        self._notify_status("Initializing audio hardware...")
        
        dev_idx = None
        rate = None
        dev_name = None

        if preferred_device_idx is not None:
            available = get_available_input_devices()
            match = next((d for d in available if d['index'] == preferred_device_idx), None)
            if match:
                dev_idx = match['index']
                rate = match['default_rate']
                dev_name = match['name']
                log_info(f"Using preferred audio input device: [{dev_idx}] {dev_name}")

        if dev_idx is None:
            dev_idx, rate, dev_name = find_optimal_input_device()

        if dev_idx is None:
            log_error("No audio input devices found on system!")
            self._notify_status("Error: No microphone found")
            return False

        self.active_device_idx = dev_idx
        self.active_rate = rate
        self.active_device_name = dev_name
        self.current_lang = default_lang
        self.current_engine = engine
        log_info(f"Audio device: [{dev_idx}] {dev_name} at {rate} Hz (Engine: {engine.upper()})")

        self.set_engine(engine)
        self._notify_status(f"Ready ({engine.upper()} | {default_lang.upper()})")
        return True

    def set_engine(self, engine_name: str):
        """Switches the STT engine ('google', 'whisper', 'vosk') strictly on demand."""
        self.current_engine = engine_name
        log_info(f"Switching STT Engine to: {engine_name.upper()}")

        if engine_name == "whisper":
            if self.whisper_model is None:
                def _load_whisper():
                    self._notify_status("Loading Whisper AI (tiny)...")
                    try:
                        from faster_whisper import WhisperModel
                        self.whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
                        log_info("Faster-Whisper tiny loaded successfully.")
                        self._notify_status(f"Standby [WHISPER | {self.current_lang.upper()}]")
                    except Exception as e:
                        log_error(f"Failed to load Faster-Whisper: {e}")
                        self._notify_status(f"Whisper load error: {e}")
                threading.Thread(target=_load_whisper, daemon=True).start()
            else:
                self._notify_status(f"Standby [WHISPER | {self.current_lang.upper()}]")

        elif engine_name == "vosk":
            self._prepare_vosk(self.current_lang)

        else: # "google"
            self._notify_status(f"Standby [GOOGLE | {self.current_lang.upper()}]")

    def _prepare_vosk(self, lang):
        """Loads Vosk model on demand."""
        if lang not in self.vosk_models:
            model_path = os.path.join(self.models_dir, VOSK_MODEL_CONFIGS[lang]["dir"])
            if not os.path.exists(model_path):
                log_error(f"Vosk model missing: {model_path}")
                return False
            try:
                import vosk
                vosk.SetLogLevel(-1)
                self.vosk_models[lang] = vosk.Model(model_path)
                log_info(f"Loaded Vosk model for {lang.upper()}")
            except Exception as e:
                log_error(f"Error loading Vosk model: {e}")
                return False

        try:
            import vosk
            self.active_vosk_recognizer = vosk.KaldiRecognizer(
                self.vosk_models[lang],
                float(self.active_rate)
            )
            return True
        except Exception as e:
            log_error(f"Error creating Vosk KaldiRecognizer: {e}")
            return False

    def set_device(self, dev_idx: int):
        """Switches the active microphone device."""
        available = get_available_input_devices()
        match = next((d for d in available if d['index'] == dev_idx), None)
        if not match:
            log_warning(f"Device index {dev_idx} not found")
            return False

        was_listening = self.is_listening
        if was_listening:
            self.stop_listening()

        new_rate = match['default_rate']
        rate_changed = (new_rate != self.active_rate)

        self.active_device_idx = match['index']
        self.active_rate = new_rate
        self.active_device_name = match['name']
        log_info(f"Switched microphone to: [{match['index']}] {match['name']} ({new_rate} Hz)")

        if rate_changed and self.current_engine == "vosk":
            self._prepare_vosk(self.current_lang)

        if was_listening:
            self.start_listening()
        else:
            self._notify_status(f"Standby [{self.current_engine.upper()} | {self.current_lang.upper()}]")

        return True

    def set_language(self, lang: str):
        """Switches active language ('uk' or 'en')."""
        self.current_lang = lang
        log_info(f"Language set to: {lang.upper()}")

        if self.current_engine == "vosk":
            self._prepare_vosk(lang)

        if self.is_listening:
            self._notify_status(f"Listening [{self.current_engine.upper()} | {lang.upper()}]")
        else:
            self._notify_status(f"Standby [{self.current_engine.upper()} | {lang.upper()}]")
        return True

    def _audio_callback(self, indata, frames, time_info, status):
        """Streaming callback from sounddevice."""
        if self.is_listening and self.is_running:
            raw_bytes = bytes(indata)
            self.audio_queue.put(raw_bytes)

            if self.on_audio_level:
                try:
                    shorts = array.array('h', raw_bytes)
                    peak = max(abs(x) for x in shorts) if shorts else 0
                    level = min(1.0, peak / 32768.0)
                    self.on_audio_level(level)
                except Exception:
                    pass

    # --- PUSH-TO-TALK (PTT) METHODS ---
    def start_ptt(self, role="general"):
        """Triggered when a PTT key is pressed down."""
        self.active_ptt_role = role
        self.is_ptt_active = True
        self.speech_frames = []

        if not self.is_listening:
            self.start_listening()

        self._notify_status(f"🔴 PTT [{role.upper()}]: Speaking...")

    def stop_ptt(self, role="general"):
        """Triggered when a PTT key is released."""
        if not self.is_ptt_active:
            return
        self.is_ptt_active = False

        if self.speech_frames:
            full_audio = b"".join(self.speech_frames)
            self.speech_frames = []
            if len(full_audio) >= (self.active_rate * 0.3 * 2):
                if self.on_partial:
                    self.on_partial(f"Transcribing [{role.upper()}]...")
                self.transcribe_queue.put((full_audio, role))

        self._notify_status(f"Standby [{self.current_engine.upper()}]")

    def start_listening(self):
        """Starts audio stream and worker threads."""
        if self.is_listening:
            return

        self.is_running = True
        self.is_listening = True
        self.is_speaking = False
        self.speech_frames = []
        self.silence_frames_count = 0
        self.pre_speech_buffer = []

        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()

        if self.transcribe_thread is None or not self.transcribe_thread.is_alive():
            self.transcribe_thread = threading.Thread(target=self._transcribe_worker, daemon=True)
            self.transcribe_thread.start()

        try:
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception: pass
                self.stream = None

            self.stream = sd.RawInputStream(
                samplerate=self.active_rate,
                blocksize=4000,
                device=self.active_device_idx,
                dtype='int16',
                channels=1,
                callback=self._audio_callback
            )
            self.stream.start()
            log_info(f"Audio stream started [{self.current_engine.upper()} | {self.current_lang.upper()}]")
            self._notify_status(f"🎙️ Listening [{self.current_engine.upper()}]...")
        except Exception as e:
            self.is_listening = False
            log_error(f"Error opening audio stream: {e}")
            self._notify_status(f"Mic error: {e}")

    def stop_listening(self):
        """Stops audio stream."""
        self.is_listening = False
        self.is_ptt_active = False
        try:
            if self.stream and self.stream.active:
                self.stream.stop()
        except Exception:
            pass

        if self.speech_frames:
            full_audio = b"".join(self.speech_frames)
            self.speech_frames = []
            self.transcribe_queue.put((full_audio, self.active_ptt_role))

        if self.on_audio_level:
            try: self.on_audio_level(0.0)
            except Exception: pass

        log_info("Audio stream paused.")
        self._notify_status(f"Mic Muted [{self.current_engine.upper()}]")

    def toggle_listening(self):
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()
        return self.is_listening

    def _worker_loop(self):
        """Processes incoming audio chunks efficiently."""
        while self.is_running:
            try:
                data = self.audio_queue.get(timeout=0.3)
            except queue.Empty:
                continue

            if not self.is_listening:
                continue

            # If PTT is currently active, buffer audio frames directly
            if self.is_ptt_active:
                self.speech_frames.append(data)
                continue

            # Continuous listening mode
            if self.current_engine == "vosk":
                self._process_vosk_chunk(data)
            else:
                self._process_vad_chunk(data)

    def _process_vosk_chunk(self, data):
        if self.active_vosk_recognizer is None:
            return

        if self.active_vosk_recognizer.AcceptWaveform(data):
            res_raw = self.active_vosk_recognizer.Result()
            res = json.loads(res_raw)
            text = res.get("text", "").strip()
            if text:
                self._handle_recognized_phrase(text, role="general")
        else:
            part_raw = self.active_vosk_recognizer.PartialResult()
            part = json.loads(part_raw)
            partial_text = part.get("partial", "").strip()
            if partial_text and self.on_partial:
                self.on_partial(partial_text)

    def _process_vad_chunk(self, data):
        try:
            shorts = array.array('h', data)
            peak = (max(abs(x) for x in shorts) / 32768.0) if shorts else 0
        except Exception:
            peak = 0

        self.pre_speech_buffer.append(data)
        if len(self.pre_speech_buffer) > self.pre_buffer_max_chunks:
            self.pre_speech_buffer.pop(0)

        is_voice = (peak >= self.vad_threshold)

        if is_voice:
            if not self.is_speaking:
                self.is_speaking = True
                self.speech_frames = list(self.pre_speech_buffer)
                if self.on_partial:
                    self.on_partial("Listening (Speaking)...")
            self.speech_frames.append(data)
            self.silence_frames_count = 0
        else:
            if self.is_speaking:
                self.speech_frames.append(data)
                self.silence_frames_count += 1
                chunks_for_pause = int(0.65 * (self.active_rate / 4000))
                if self.silence_frames_count >= chunks_for_pause:
                    full_audio = b"".join(self.speech_frames)
                    self.speech_frames = []
                    self.is_speaking = False
                    self.silence_frames_count = 0
                    if len(full_audio) >= (self.active_rate * 0.35 * 2):
                        if self.on_partial:
                            self.on_partial("Transcribing...")
                        self.transcribe_queue.put((full_audio, "general"))

    def _transcribe_worker(self):
        """Worker thread executing cloud/local transcription."""
        while self.is_running:
            try:
                item = self.transcribe_queue.get(timeout=0.3)
            except queue.Empty:
                continue

            if isinstance(item, tuple):
                audio_bytes, role = item
            else:
                audio_bytes, role = item, "general"

            try:
                if self.current_engine == "google":
                    text = self._transcribe_with_google(audio_bytes)
                elif self.current_engine == "whisper":
                    text = self._transcribe_with_whisper(audio_bytes)
                else:
                    text = None

                if text:
                    self._handle_recognized_phrase(text, role=role)
                else:
                    if self.on_partial:
                        self.on_partial("...")
            except Exception as e:
                log_error(f"Transcription error: {e}")

    def _transcribe_with_google(self, audio_bytes):
        try:
            audio_data = sr.AudioData(audio_bytes, self.active_rate, 2)
            lang_code = "uk-UA" if self.current_lang == "uk" else "en-US"
            text = self.sr_recognizer.recognize_google(audio_data, language=lang_code)
            return text.strip()
        except sr.UnknownValueError:
            return None
        except Exception as e:
            log_warning(f"Google Speech warning: {e}")
            return None

    def _transcribe_with_whisper(self, audio_bytes):
        if self.whisper_model is None:
            return None
        try:
            audio_data = sr.AudioData(audio_bytes, self.active_rate, 2)
            wav_bytes = audio_data.get_wav_data()
            wav_stream = io.BytesIO(wav_bytes)

            segments, _ = self.whisper_model.transcribe(
                wav_stream,
                language=self.current_lang,
                beam_size=1
            )
            text = " ".join(s.text for s in segments).strip()
            return text
        except Exception as e:
            log_warning(f"Whisper warning: {e}")
            return None

    def _handle_recognized_phrase(self, text: str, role="general"):
        """Parses recognized phrase into coordinate action with role routing."""
        # Check if role forces destination
        if role == "start":
            d, c = extract_numbers_and_digits(text, self.current_lang)
            coord = format_single_point(d, c)
            if coord:
                action = {'type': 'set_start', 'coord': coord, 'raw': text}
            else:
                action = parse_voice_text(text, self.current_lang)
        elif role == "target":
            d, c = extract_numbers_and_digits(text, self.current_lang)
            coord = format_single_point(d, c)
            if coord:
                action = {'type': 'set_target', 'coord': coord, 'raw': text}
            else:
                action = parse_voice_text(text, self.current_lang)
        else:
            action = parse_voice_text(text, self.current_lang)

        log_info(f"[{self.current_engine.upper()}|{role.upper()}]: \"{text}\" -> {action}")

        if self.on_raw_speech:
            self.on_raw_speech(text, action)

        if action and self.on_action:
            self.on_action(action)
        elif self.on_partial:
            self.on_partial(f"\"{text}\"")

    def _notify_status(self, msg: str):
        if self.on_status:
            self.on_status(msg)

    def shutdown(self):
        """Clean shutdown."""
        self.is_listening = False
        self.is_running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception: pass
        log_info("VoiceRecognitionService shutdown complete.")
