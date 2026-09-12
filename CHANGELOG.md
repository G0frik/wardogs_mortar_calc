# Changelog

All notable changes to the War Dogs Mortar Calculator project are documented in this file.

---

### [`3bbfff8`](https://github.com/G0frik/wardogs_mortar_calc/commit/3bbfff8) - Standalone Voice Arming & Number Appending
- **Voice Parser**: Full Ukrainian & English keyword coverage for "Start" (`старт`, `старту`, `позиція`, `міномет`, `start`, `pos`) and "Target" (`ціль`, `мішень`, `target`, `impact`).
- **Standalone Arming**: Speaking "Start" or "Target" alone arms that field for 7 seconds with glowing visual cues (`[START ARMED]` / `[TARGET ARMED]`).
- **Progressive Appending**: Coordinates spoken in chunks (e.g. `"12"` followed by `"24"`) automatically append into `"12 24"` and calculate.
- **Number Parsing**: Expanded colloquial Ukrainian digits (`двійка`, `трійка`, `четвірка`) and fixed partial coordinate formatting.

---

### [`384a83a`](https://github.com/G0frik/wardogs_mortar_calc/commit/384a83a) - Audio Isolation & Separate UI Badges
- **Voice Service**: Decoupled continuous listening (`LIVE`) from Push-to-Talk (`PTT`). Audio callback drops all mic input when neither is active, preventing audio leakage and background VAD triggers.
- **Header Badges**: Split header into two independent elements: `[ 🎙️ OFF ]` / `[ 🔴 LIVE ]` toggle and a dedicated `[ PTT ]` indicator.
- **Visual Feedback**: PTT indicator reflects pushed state only while held down (via keyboard, mouse 4/5, or mouse click-and-hold) without overwriting LIVE mode status.

---

### [`42588ad`](https://github.com/G0frik/wardogs_mortar_calc/commit/42588ad) - Interactive Keybind Manager
- **PTT Binding**: Interactive click-to-bind UI in Settings for General, Start, and Target PTT.
- **Mouse & Keyboard Support**: Supports keyboard keys, modifiers, and Mouse 4 / Mouse 5.
- **Unbind & Replace**: Dedicated `[✕]` button to clear bindings or assign replacement keys.

---

### [`5aca9a7`](https://github.com/G0frik/wardogs_mortar_calc/commit/5aca9a7) - Log Retention & Disk Optimization
- **File Logging**: Disabled file logging by default (`mortar_calc.log`) to conserve disk space.
- **Log Retention**: Added 256 KB file size limit and automatic backup rotation (max 1 backup).
- **Log Management**: Added one-click log clearing button in Settings and a toggle for file logging.

---

### [`5b68011`](https://github.com/G0frik/wardogs_mortar_calc/commit/5b68011) - Initial Release
- **Core HUD**: Borderless, draggable mini-window with mousewheel opacity and manual corner resize handle (`◢`).
- **Artillery Calculator**: Real-time distance, azimuth, and Soviet/NATO mils calculations for War Dogs 100m/200m/400m grids.
- **Voice Recognition**: Multi-engine STT support (Google Speech, Faster-Whisper, Vosk) with English and Ukrainian language models.
- **Setup Scripts**: Standalone `setup.bat` and `launch.bat` for one-click dependency installation and execution.
