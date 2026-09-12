# War Dogs Mortar Calculator 🎯

[English](#english) | [Українська](#українська)

---

<a name="english"></a>
## English

Lightweight, frameless tactical mortar overlay for **War Dogs**. Calculates real-time distance, azimuth, and mils with manual input or voice recognition (Ukrainian & English).

### 🚀 How to Run (Beginner Guide)

No coding knowledge required. Follow these steps:

#### 1. Install Python
1. Download Python 3.10+ from [python.org](https://www.python.org/downloads/).
2. Run the installer.
3. ⚠️ **CRITICAL**: Check the box **"Add python.exe to PATH"** at the bottom of the installer before clicking "Install Now".

#### 2. Download & Install
1. Download this repository (click green **Code** button -> **Download ZIP**) and extract it.
2. Double-click **`setup.bat`** (this automatically installs all required components).

#### 3. Launch
- Double-click **`launch.bat`** to start the calculator.

---

### 🎮 Controls & HUD

| Action | Control |
| :--- | :--- |
| **Move Overlay** | Click and drag the top header bar |
| **Adjust Opacity** | Scroll **Mouse Wheel** anywhere over the widget (0% - 100%) |
| **Resize** | Drag the bottom-right corner grip (`◢`) |
| **Mini / Full Mode** | Click `▼` or `▲` to toggle compact mode |
| **Settings Panel** | Click `⚙️` or press <kbd>F3</kbd> |
| **Live Voice Mode** | Click `🎙️ OFF` / `🔴 LIVE` badge in header to toggle continuous open-mic |
| **PTT Button & Indicator** | Shows `PTT` when idle and `🔴 PUSHED` when pressed (also supports click-and-hold with mouse) |
| **General PTT** | Hold <kbd>F2</kbd> (Interactive keybind: click to bind any key/Mouse 4/5 or ✕ to unbind) |
| **Target PTT** | Hold <kbd>V</kbd> while calling out target digits (Rebindable / Unbindable) |
| **Start PTT** | Hold <kbd>B</kbd> while calling out mortar position (Rebindable / Unbindable) |

---

### 🎙️ Voice Input (EN & UA)

Switch language with the `🇺🇦 UA` / `🇬🇧 EN` buttons.

#### Supported Callouts:
- **Two-Step Voice Arming (Hands-Free)**:
  - Say `"Start"` (or `"Target"`) alone → system arms the field for 7 seconds and glows blue/pink.
  - Speak numbers in one phrase (`"12 24"`) or in separate chunks (`"12"`, then `"24"`) → auto-appends and calculates!
- **Digit-by-digit**: Say numbers one by one:
  - `"target one two four three three eight nine five"` → Target: `12,43 38,95`
  - Or hold <kbd>V</kbd> and just say digits: `"one two four three three eight nine five"`
- **Full Mission**:
  - `"start 12 34 target 56 78"`
- **Quick Target**:
  - `"target 42 20"` or `"impact 15 40"`
- **Voice Utilities**:
  - `"swap"` (swaps start & target), `"clear"` (resets inputs), `"copy"` (copies result)

#### Speech Engines (in Settings ⚙️):
1. **Google Speech (Default)**: 0% CPU usage, fast, cloud-based, no setup required.
2. **Faster-Whisper**: Local offline neural model.
3. **Vosk**: Local offline Kaldi model (run `python download_models.py` to download weights).

---
---

<a name="українська"></a>
## Українська

Компактний тактичний віджет-оверлей для розрахунку дистанції, азимута та тисячних для мінометів у **War Dogs**. Підтримує ручне введення координат та голосове керування (українською та англійською).

### 🚀 Як запустити з нуля (для початківців)

Жодних навичок програмування не потрібно. Просто виконайте 3 кроки:

#### 1. Встановіть Python
1. Завантажте Python версії 3.10+ з офіційного сайту: [python.org](https://www.python.org/downloads/).
2. Запустіть встановлювач.
3. ⚠️ **ВАЖЛИВО**: Обов'язково поставте галочку **"Add python.exe to PATH"** внизу перед тим, як натиснути "Install Now".

#### 2. Завантаження та налаштування
1. Завантажте цей проєкт (зелена кнопка **Code** -> **Download ZIP**) та розпакуйте архів у будь-яку папку.
2. Запустіть файл **`setup.bat`** (він сам встановить усі потрібні бібліотеки).

#### 3. Запуск
- Двічі клікніть по **`launch.bat`** для запуску калькулятора.

---

### 🎮 Керування та HUD

| Дія | Як виконати |
| :--- | :--- |
| **Переміщення вікна** | Затисніть та тягніть верхню панель віджета |
| **Прозорість вікна** | Прокручуйте **коліщатко миші** над віджетом (вгору — яскравіше, вниз — прозоріше) |
| **Зміна розміру** | Тягніть за правий нижній кут (`◢`) |
| **Міні-режим** | Клік по кнопці `▼` або `▲` для згортання/розгортання |
| **Налаштування** | Клік по `⚙️` або клавіша <kbd>F3</kbd> |
| **Режим відкритого мікрофона (LIVE)** | Клікніть бейдж `🎙️ OFF` / `🔴 LIVE` для перемикання постійного прослуховування |
| **Кнопка та індикатор PTT** | Показує `PTT` у спокої та `🔴 PUSHED` при натисканні (працює також при затисканні мишкою) |
| **Загальний PTT** | Затиснути <kbd>F2</kbd> (Інтерактивний бінд: клікніть для призначення будь-якої клавіші/Mouse 4/5 або ✕ для очищення) |
| **PTT для Ціль** | Затисніть <kbd>V</kbd> і продиктуйте цифри цілі (Можна змінити або зняти бінд) |
| **PTT для Старт** | Затисніть <kbd>B</kbd> і продиктуйте координати міномета (Можна змінити або зняти бінд) |

---

### 🎙️ Голосове керування (UA та EN)

Перемикайте мову кнопками `🇺🇦 UA` / `🇬🇧 EN` у вікні.

#### Формати диктування:
- **Двоетапний запис (без рук)**:
  - Скажіть просто *"Старт"* (або *"Ціль"*) → відповідне поле підсвічується і очікує координати 7 секунд.
  - Продиктуйте цифри разом (*"12 24"*) або частинами (*"12"*, потім *"24"*) → калькулятор автоматично допише їх у поле та виконає розрахунок!
- **По одній цифрі (найзручніше під час бою)**:
  - *"ціль один два чотири три три вісім дев'ять п'ять"* → Ціль: `12,43 38,95`
  - Або затисніть <kbd>V</kbd> і просто диктуйте: *"один два чотири три три вісім дев'ять п'ять"*
- **Повна команда**:
  - *"старт дванадцять тридцять чотири ціль п'ятдесят шість сімдесят вісім"*
- **Лише ціль**:
  - *"ціль сорок два двадцять"* або *"приліт п'ятнадцять сорок"*
- **Швидкі команди**:
  - *"поміняти"* / *"своп"* (міняє старт і ціль місцями)
  - *"очистити"* / *"скинути"*
  - *"скопіювати"* (копіює результат у буфер обміну)

#### Двигуни розпізнавання (в Налаштуваннях ⚙️):
1. **Google Speech (за замовчуванням)**: 0% навантаження на процесор/відеокарту, висока точність, працює через інтернет.
2. **Faster-Whisper**: Локальна нейромережа, працює без інтернету.
3. **Vosk**: Локальна швидка офлайн-модель (завантажити моделі: запуск `python download_models.py`).

---

### 📄 Ліцензія
MIT License. Створено для спільноти гравців War Dogs.
