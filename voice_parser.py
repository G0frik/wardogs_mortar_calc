"""
VOICE COMMAND & COORDINATE PARSER (English & Ukrainian)
Converts spoken words and digits from speech recognition (Google, Whisper, Vosk)
into tactical coordinate strings (xx,xx yy,yy) and artillery commands.
Supports both digit-by-digit ("один два чотири три три вісім девять пять")
and compound numbers ("дванадцять сорок три").
"""

import re

UA_WORDS = {
    'нуль': 0, 'ноль': 0, 'зеро': 0, 'нулик': 0, 'нолик': 0,
    'один': 1, 'одна': 1, 'одне': 1, 'перший': 1, 'раз': 1,
    'два': 2, 'дві': 2, 'другий': 2, 'двійка': 2, 'двойка': 2,
    'три': 3, 'третій': 3, 'трійка': 3, 'тройка': 3,
    'чотири': 4, 'четвертий': 4, 'четвірка': 4,
    'п\'ять': 5, 'пять': 5, 'п\'ятий': 5, 'пятий': 5, 'п\'ятірка': 5, 'пятірка': 5,
    'шість': 6, 'шостий': 6, 'шістка': 6,
    'сім': 7, 'сьомий': 7, 'сімка': 7,
    'вісім': 8, 'восьмий': 8, 'вісімка': 8,
    'дев\'ять': 9, 'девять': 9, 'дев\'ятий': 9, 'девятий': 9, 'дев\'ятка': 9, 'девятка': 9,
    'десять': 10, 'десятий': 10, 'десятка': 10,
    'одинадцять': 11, 'дванадцять': 12, 'тринадцять': 13,
    'чотирнадцять': 14, 'п\'ятнадцять': 15, 'пятнадцять': 15,
    'шістнадцять': 16, 'сімнадцять': 17, 'вісімнадцять': 18,
    'дев\'ятнадцять': 19, 'девятнадцять': 19,
    'двадцять': 20, 'тридцять': 30, 'сорок': 40,
    'п\'ятдесят': 50, 'пятдесят': 50,
    'шістдесят': 60, 'сімдесят': 70,
    'вісімдесят': 80, 'дев\'яносто': 90, 'девяносто': 90,
    'сто': 100
}

EN_WORDS = {
    'zero': 0, 'oh': 0, 'nought': 0,
    'one': 1, 'first': 1,
    'two': 2, 'second': 2,
    'three': 3, 'third': 3,
    'four': 4, 'fourth': 4,
    'five': 5, 'fifth': 5,
    'six': 6, 'sixth': 6,
    'seven': 7, 'seventh': 7,
    'eight': 8, 'eighth': 8,
    'nine': 9, 'ninth': 9,
    'ten': 10, 'tenth': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13,
    'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
    'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
    'twenty': 20, 'thirty': 30, 'forty': 40,
    'fifty': 50, 'sixty': 60, 'seventy': 70,
    'eighty': 80, 'ninety': 90,
    'hundred': 100
}


def extract_numbers_and_digits(text: str, lang: str = 'uk'):
    """
    Extracts numerical content from spoken words or raw digits.
    Returns:
    - digits: list of single digits (0-9)
    - compounds: list of compound integers (e.g. 12, 34, 1234)
    """
    word_map = UA_WORDS if lang == 'uk' else EN_WORDS
    # Also allow recognizing English words if user accidentally speaks English in UK mode or vice-versa
    fallback_map = EN_WORDS if lang == 'uk' else UA_WORDS

    tokens = text.lower().replace("’", "'").replace("`", "'").split()

    digits = []
    compounds = []
    current_compound = 0
    in_compound = False

    for t in tokens:
        # Check if contains literal digits (e.g. "1243", "1", "12.34")
        t_clean = re.sub(r'[^\d]', '', t)
        if t_clean.isdigit():
            for ch in t_clean:
                digits.append(int(ch))
            compounds.append(int(t_clean))
            continue

        target_map = word_map if t in word_map else (fallback_map if t in fallback_map else None)

        if target_map:
            val = target_map[t]
            if val < 10:
                digits.append(val)
                if in_compound and current_compound in [20, 30, 40, 50, 60, 70, 80, 90]:
                    current_compound += val
                    compounds.append(current_compound)
                    current_compound = 0
                    in_compound = False
                elif in_compound:
                    compounds.append(current_compound)
                    compounds.append(val)
                    current_compound = 0
                    in_compound = False
                else:
                    compounds.append(val)
            elif val in [20, 30, 40, 50, 60, 70, 80, 90]:
                if in_compound and current_compound > 0:
                    compounds.append(current_compound)
                current_compound = val
                in_compound = True
                for ch in str(val):
                    digits.append(int(ch))
            else: # 10-19 or 100
                if in_compound and current_compound > 0:
                    compounds.append(current_compound)
                compounds.append(val)
                current_compound = 0
                in_compound = False
                for ch in str(val):
                    digits.append(int(ch))

    if in_compound and current_compound > 0:
        compounds.append(current_compound)

    return digits, compounds


def format_single_point(digits, compounds):
    """
    Converts extracted numbers into a map point string (xx,xx yy,yy or xx xx),
    or returns partial coordinate strings (e.g. '12') for progressive voice input.
    """
    # 1. Exactly 8 individual digits (e.g. 1 2 4 3 3 8 9 5) -> "12,43 38,95"
    if len(digits) == 8:
        return f"{digits[0]}{digits[1]},{digits[2]}{digits[3]} {digits[4]}{digits[5]},{digits[6]}{digits[7]}"

    # 2. Exactly 4 two-digit numbers (e.g. 12, 43, 38, 95) -> "12,43 38,95"
    if len(compounds) == 4 and all(10 <= n <= 99 for n in compounds):
        return f"{compounds[0]:02d},{compounds[1]:02d} {compounds[2]:02d},{compounds[3]:02d}"

    # 3. Exactly 2 four-digit numbers (e.g. 1243, 3895) -> "12,43 38,95"
    if len(compounds) == 2 and all(1000 <= n <= 9999 for n in compounds):
        s1 = f"{compounds[0]:04d}"
        s2 = f"{compounds[1]:04d}"
        return f"{s1[:2]},{s1[2:]} {s2[:2]},{s2[2:]}"

    # 4. Six individual digits (3 per axis, e.g. 1 2 4 3 8 9) -> "12,4 38,9"
    if len(digits) == 6:
        return f"{digits[0]}{digits[1]},{digits[2]} {digits[3]}{digits[4]},{digits[5]}"

    # 5. Exactly 4 individual digits (e.g. 1 2 4 3) -> "12 43"
    if len(digits) == 4:
        return f"{digits[0]}{digits[1]} {digits[2]}{digits[3]}"

    # 6. Two compound numbers of at least 2 digits (e.g. 12 43) -> "12 43"
    if len(compounds) == 2 and all(10 <= n <= 99 for n in compounds):
        return f"{compounds[0]:02d} {compounds[1]:02d}"

    # 7. Exactly one 4-digit number (e.g. 1243) -> "12 43"
    if len(compounds) == 1 and 1000 <= compounds[0] <= 9999:
        s = f"{compounds[0]:04d}"
        return f"{s[:2]} {s[2:]}"

    # --- PARTIAL COORDINATE SUPPORT (For progressive voice appending) ---
    # 8. Exactly 2 digits (e.g. 1 2 or 4 3) -> "12" or "43"
    if len(digits) == 2:
        return f"{digits[0]}{digits[1]}"

    # 9. Exactly one 2-digit number (e.g. 12) -> "12"
    if len(compounds) == 1 and 0 <= compounds[0] <= 99:
        return f"{compounds[0]:02d}"

    # 10. Exactly 3 digits (e.g. 1 2 3) -> "12,3"
    if len(digits) == 3:
        return f"{digits[0]}{digits[1]},{digits[2]}"

    # 11. Single digit -> "1"
    if len(digits) == 1:
        return f"{digits[0]}"

    # 12. Fallback if compound numbers available
    if len(compounds) == 2:
        return f"{compounds[0]:02d} {compounds[1]:02d}"
    if compounds:
        return " ".join(str(c) for c in compounds)
    if digits:
        return "".join(str(d) for d in digits)

    return ""


# Regex patterns matching Ukrainian and English triggers with full inflections
START_PATTERN = (
    r'\b(?:'
    r'старт[а-яіїєґ\']*|'
    r'стар\b|'
    r'спорт\b|'
    r'позиці[а-яіїєґ]*|'
    r'баз[а-яіїєґ]*|'
    r'міномет[а-яіїєґ]*|'
    r'звідки|'
    r'start[a-z]*|'
    r'pos(?:ition)?|'
    r'base|'
    r'mortar'
    r')\b'
)

TARGET_PATTERN = (
    r'\b(?:'
    r'ціль[а-яіїєґ]*|'
    r'ціл[а-яіїєґ]*|'
    r'ці\b|'
    r'циль\b|'
    r'сіль\b|'
    r'мішень[а-яіїєґ]*|'
    r'мішен[а-яіїєґ]*|'
    r'приліт[а-яіїєґ]*|'
    r'прильот[а-яіїєґ]*|'
    r'вогонь\b|'
    r'вогн[а-яіїєґ]*|'
    r'ворог[а-яіїєґ]*|'
    r'куди|'
    r'target[a-z]*|'
    r'impact|'
    r'fire|'
    r'aim|'
    r'enemy'
    r')\b'
)


def parse_voice_text(text: str, lang: str = 'uk'):
    """
    Parses speech text into tactical mortar action dict.
    Supports standalone keywords (arms field for subsequent numbers),
    compound single-utterance commands, and raw numeric coordinates.
    """
    raw = text.strip().lower()
    if not raw:
        return None

    # 1. Tactical Control Commands
    if any(k in raw for k in ['swap', 'switch', 'поміняти', 'своп', 'перемкнути']):
        return {'type': 'swap', 'raw': raw}
    if any(k in raw for k in ['clear', 'reset', 'очистити', 'скинути', 'чисто']):
        return {'type': 'clear', 'raw': raw}
    if any(k in raw for k in ['copy', 'скопіювати', 'копіювати']):
        return {'type': 'copy', 'raw': raw}

    # 2. Check for dual-target command: Start and Target in the same utterance
    has_start = bool(re.search(START_PATTERN, raw, re.IGNORECASE))
    has_target = bool(re.search(TARGET_PATTERN, raw, re.IGNORECASE))

    if has_start and has_target:
        both_match = re.search(rf'{START_PATTERN}\s*(.*?)\s*{TARGET_PATTERN}\s*(.*)', raw, re.IGNORECASE)
        if both_match:
            s_part = both_match.group(1)
            t_part = both_match.group(2)
            s_d, s_c = extract_numbers_and_digits(s_part, lang)
            t_d, t_c = extract_numbers_and_digits(t_part, lang)
            s_coord = format_single_point(s_d, s_c)
            t_coord = format_single_point(t_d, t_c)
            if s_coord and t_coord:
                return {'type': 'set_both', 'start': s_coord, 'target': t_coord, 'raw': raw}

    # 3. Check Start keyword alone or with numbers
    if has_start and not has_target:
        # Extract numerical content from phrase (omitting the keyword)
        d, c = extract_numbers_and_digits(raw, lang)
        if not d and not c:
            # Standalone Start keyword! Arm Start field for upcoming numbers
            return {'type': 'arm_start', 'raw': raw}

        # If user spoke 16 digits without saying "target" explicitly
        if len(d) == 16:
            s_coord = format_single_point(d[:8], c[:4])
            t_coord = format_single_point(d[8:], c[4:])
            return {'type': 'set_both', 'start': s_coord, 'target': t_coord, 'raw': raw}

        coord = format_single_point(d, c)
        if coord:
            return {'type': 'set_start', 'coord': coord, 'digits': d, 'compounds': c, 'raw': raw}

    # 4. Check Target keyword alone or with numbers
    if has_target and not has_start:
        d, c = extract_numbers_and_digits(raw, lang)
        if not d and not c:
            # Standalone Target keyword! Arm Target field for upcoming numbers
            return {'type': 'arm_target', 'raw': raw}

        coord = format_single_point(d, c)
        if coord:
            return {'type': 'set_target', 'coord': coord, 'digits': d, 'compounds': c, 'raw': raw}

    # 5. Direct Coordinate Callout (No keywords specified)
    d, c = extract_numbers_and_digits(raw, lang)
    if not d and not c:
        return None

    if len(d) == 16:
        # Full fire mission (8 digits Start + 8 digits Target)
        s_coord = format_single_point(d[:8], c[:4])
        t_coord = format_single_point(d[8:], c[4:])
        return {'type': 'set_both', 'start': s_coord, 'target': t_coord, 'raw': raw}

    coord = format_single_point(d, c)
    if coord:
        return {'type': 'coord_input', 'coord': coord, 'digits': d, 'compounds': c, 'raw': raw}

    return None
