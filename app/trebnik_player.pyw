#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
════════════════════════════════════════════════════════════════════════════
 ТРЕБНИКЪ — ОТЧИТКА · читалка и озвучка двух последований из
 «Требника Петра (Могилы), часть 3»:
   01 — Восследование молебное о избавлении недугующаго обуревания
        и насилия духов нечистых (от демонов), 32 части
   02 — Восследование молебное против чародеяний и обаяний
        человеков и скотов (от колдунов), 10 частей

 Возможности:
   • два вида текста: церковнославянский оригинал и адаптированный
     под озвучку (твёрдые знаки удалены — «твёрдый знак» больше
     не произносится в аудио);
   • настраиваемое имя вместо «Имярек» — мужское или женское,
     склоняется автоматически (по умолчанию — Максим);
   • ссылки на псалмы и евангелия вместо встроенных цитат
     (в церковнославянском виде);
   • локальный синтез аудио с выбором движка и голосов: на роль
     священника и на роль хора пользователь назначает любой
     из 17 проверенных голосов (Microsoft онлайн — Дмитрий,
     Светлана и др.; офлайн — Silero и Piper);
     скорость по умолчанию 0.8, MP3/WAV, один файл на часть;
   • караоке: подсветка читаемого места при прослушивании.

 Запуск:  python trebnik_player.pyw   (или двойной щелчок в Windows)
 Зависимости:  pip install -r requirements.txt
════════════════════════════════════════════════════════════════════════════
"""
import os
import re
import sys
import json
import time
import asyncio
import hashlib
import traceback
import urllib.request
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

from PyQt6.QtCore import (Qt, QThread, pyqtSignal, QTimer, QSettings,
                          QUrl, QObject, QSize)
from PyQt6.QtGui import (QIcon, QFont, QTextCursor, QKeySequence,
                         QAction, QDesktopServices)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QComboBox,
                             QListWidget, QListWidgetItem, QTextBrowser,
                             QPushButton, QToolButton, QProgressBar, QSlider,
                             QDoubleSpinBox, QFileDialog, QMessageBox, QDialog,
                             QStatusBar, QSplitter, QRadioButton, QButtonGroup,
                             QGroupBox, QStyle, QSpacerItem, QSizePolicy,
                             QFrame, QCheckBox, QPlainTextEdit)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

APP_TITLE = "Требникъ — Отчитка"
APP_DIR = os.path.dirname(os.path.abspath(__file__))


# ═════════════════════════════════════════════════════════════════════════
#  ПУТИ
# ═════════════════════════════════════════════════════════════════════════
def find_base():
    """Папка с texts/ — рядом со скриптом, уровнем выше или в cwd."""
    for c in (APP_DIR, os.path.dirname(APP_DIR), os.getcwd()):
        if os.path.isfile(os.path.join(c, "texts", "01_ot_demonov_tts.txt")):
            return c
    return APP_DIR


BASE = find_base()
TEXTS_DIR = os.path.join(BASE, "texts")
AUDIO_DIR = os.path.join(BASE, "audio")

SERVICE_FILES = {
    1: ("Последование о недугующих… от демонов",
         "01_ot_demonov_tts.txt", "01_ot_demonov_slavonic.txt", "ot_demonov"),
    2: ("Последование против чародеяний… от колдунов",
         "02_ot_koldunov_tts.txt", "02_ot_koldunov_slavonic.txt", "ot_koldunov"),
}
REFERENCES_FILE = os.path.join(TEXTS_DIR, "references.txt")

VOICE_D = "ru-RU-DmitryNeural"     # священник / заклинатель (совместимость)
VOICE_S = "ru-RU-SvetlanaNeural"   # хор, предстоящие (совместимость)
ROLE_NAME = {"Д": "Священник", "С": "Хор"}
CH_PER_SEC = {"Д": 12.0, "С": 12.3}   # символов в секунду при скорости 0.8

# ═════════════════════════════════════════════════════════════════════
#  ГОЛОСА — 17 шт. (проверены синтезом, ASR и формантами F1/F2).
#  Запись: (ключ, имя, пол, движок, голос движка, дефект «Ии», примечание)
#    движок: "edge" — Microsoft edge-tts, онлайн, MP3, скорость = rate
#            "silero" — офлайн (pip install silero), WAV 48 кГц
#            "piper" — офлайн (pip install piper-tts), WAV 22 кГц
#    дефект «Ии» = True: голос читает «Иисусе» как «Эсусе»; лечится
#    подменой «Ии→Йи» (только в тексте синтеза, на экране не меняется).
#  Роли назначает пользователь: любой голос на любую роль, любого пола.
# ═════════════════════════════════════════════════════════════════════
VOICES = [
    ("dmitry",   "Дмитрий",  "М", "edge", "ru-RU-DmitryNeural",            True,  ""),
    ("svetlana", "Светлана", "Ж", "edge", "ru-RU-SvetlanaNeural",          True,  ""),
    ("andrew",   "Эндрю",    "М", "edge", "en-US-AndrewMultilingualNeural", True,  "коверкает «о рабе твоем»"),
    ("brian",    "Брайан",   "М", "edge", "en-US-BrianMultilingualNeural", False, "коверкает «о рабе твоем»"),
    ("ava",      "Ава",      "Ж", "edge", "en-US-AvaMultilingualNeural",   False, "коверкает «о рабе твоем»"),
    ("emma",     "Эмма",      "Ж", "edge", "en-US-EmmaMultilingualNeural",  True,  ""),
    ("ostap",    "Остап",    "М", "edge", "uk-UA-OstapNeural",             False, "украинское произношение (г→ґ, ы→и)"),
    ("polina",   "Полина",   "Ж", "edge", "uk-UA-PolinaNeural",            False, "украинское произношение (г→ґ, ы→и)"),
    ("kseniya",  "Ксения",   "Ж", "silero", ("v4_ru", "kseniya"),          False, "лучший голос проверки: «Иисусе», «рабе» — чисто"),
    ("xenia",    "xenia v5", "Ж", "silero", ("v5_ru", "xenia"),           False, "местами спотыкается"),
    ("aidar",    "Айдар",    "М", "silero", ("v4_ru", "aidar"),            True,  ""),
    ("eugene",   "Евгений",  "М", "silero", ("v4_ru", "eugene"),           True,  ""),
    ("aidar5",   "Айдар v5", "М", "silero", ("v5_ru", "aidar"),            True,  ""),
    ("pdmitri",  "Дмитрий",  "М", "piper", "dmitri",                       True,  "эксперим.: глотает слоги во фразах"),
    ("pruslan",  "Руслан",   "М", "piper", "ruslan",                       False, "эксперим.: глотает слоги во фразах"),
    ("pdenis",   "Денис",    "М", "piper", "denis",                        False, "эксперим.: глотает слоги во фразах"),
    ("pirina",   "Ирина",     "Ж", "piper", "irina",                        False, "эксперим.: глотает слоги во фразах"),
]
ENGINE_TAG = {"edge": "MS", "silero": "Silero", "piper": "Piper"}
ENGINE_EXT = {"edge": ".mp3", "silero": ".wav", "piper": ".wav"}
ENGINE_SR = {"edge": 0, "silero": 48000, "piper": 22050}   # 0 = MP3-поток
ENGINE_PKG = {"silero": "silero", "piper": "piper"}    # имена импорта
PIP_NAME = {"silero": "silero", "piper": "piper-tts"}   # имена pip-пакетов

# Ревизия текстовых правок для кэша аудио. Увеличивать при каждой смене
# tts_clean (ударения, подмены) или разметки [Д]/[С] — чтобы старые
# закэшированные файлы считались устаревшими и пересинтезировались.
TEXT_FIX_REV = "3"


def voice_by_key(key):
    for v in VOICES:
        if v[0] == key:
            return v
    return VOICES[0]


def package_ok(engine):
    """Установлен ли пакет офлайн-движка."""
    try:
        import importlib.util as ilu
        return ilu.find_spec(ENGINE_PKG.get(engine, "")) is not None
    except Exception:
        return False


def voice_label(v):
    return "%s · %s · %s" % (v[1], ENGINE_TAG[v[3]], v[2])


def voice_tooltip(v):
    tip = {"edge": "Microsoft edge-tts, онлайн (интернет нужен при синтезе)",
           "silero": "Silero, офлайн (pip install silero)",
           "piper": "Piper, офлайн (pip install piper-tts), экспериментальный"}[v[3]]
    tip += ("\nДефект: «Иисусе» читает как «Эсусе» —"
            " лечится подменой «Ии→Йи»" if v[5] else
            "\n«Иисусе» читает правильно, подмена не нужна")
    if v[6]:
        tip += "\nПримечание: " + v[6]
    return tip

# ═════════════════════════════════════════════════════════════════════════
#  ТРАНСЛИТЕРАЦИЯ ИМЕНИ ФАЙЛА
# ═════════════════════════════════════════════════════════════════════════
_TR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def translit(s: str, maxlen: int = 42) -> str:
    out = "".join(_TR.get(ch, ch) for ch in s.lower())
    out = re.sub(r"[^a-z0-9]+", "_", out).strip("_")
    out = re.sub(r"_{2,}", "_", out)
    return out[:maxlen].strip("_") or "part"


# ═════════════════════════════════════════════════════════════════════════
#  СКЛОНЕНИЕ ИМЁН
# ═════════════════════════════════════════════════════════════════════════
CASES = ("И", "Р", "Д", "В", "Т", "П")


def guess_gender(name: str) -> str:
    """Первичное угадывание: а/я/ия — женское, прочее — мужское."""
    n = name.strip().lower()
    if not n:
        return "М"
    if n[-1] in "ая" or n.endswith("ия"):
        return "Ж"
    return "М"


def decline_name(name: str, gender: str) -> Dict[str, str]:
    """Формы имени по падежам. Неизвестные окончания — имя не склоняем."""
    n = name.strip()
    if not n:
        return {c: n for c in CASES}
    low = n.lower()
    end = low[-1]

    def f(im, ro, da, vn, tv, pr):
        return {"И": im, "Р": ro, "Д": da, "В": vn, "Т": tv, "П": pr}

    # 1-е склонение: -а, -я, -ия (и мужские: Никита, Илья)
    if end == "а":
        stem = n[:-1]
        ro = stem + ("и" if stem[-1:] in "кгхжшчщ" else "ы")
        return f(n, ro, stem + "е", stem + "у", stem + "ой", stem + "е")
    if end == "я":
        if low.endswith("ия"):
            return f(n, n[:-2] + "ии", n[:-2] + "ии", n[:-2] + "ию",
                     n[:-2] + "ией", n[:-2] + "ии")
        return f(n, n[:-1] + "и", n[:-1] + "е", n[:-1] + "ю",
                 n[:-1] + "ей", n[:-1] + "е")
    if end == "й":                      # Андрей
        return f(n, n[:-1] + "я", n[:-1] + "ю", n[:-1] + "я",
                 n[:-1] + "ем", n[:-1] + "е")
    if end == "ь":
        if gender == "Ж":               # Любовь
            return f(n, n[:-1] + "и", n[:-1] + "и", n,
                     n[:-1] + "ью", n[:-1] + "и")
        return f(n, n[:-1] + "я", n[:-1] + "ю", n[:-1] + "я",
                 n[:-1] + "ем", n[:-1] + "е")   # Игорь
    if gender == "М" and end.isalpha():  # согласная: Максим
        return f(n, n + "а", n + "у", n + "а", n + "ом", n + "е")
    # не смогли склонить — одинаково во всех падежах
    return {c: n for c in CASES}


# ═════════════════════════════════════════════════════════════════════════
#  ТОКЕНЫ ИМЕНИ И РОДА
# ═════════════════════════════════════════════════════════════════════════
TOKEN_TABLE = {
    "РАБ_П":    ("рабе твоем",  "рабе твоей"),
    "РАБ_Г":    ("раба твоего", "рабы твоея"),
    "РАБ_Д":    ("рабу твоему", "рабе твоей"),
    "РАБ_В":    ("раба твоего", "рабу твою"),
    "РАБ_СВ_В": ("раба своего", "рабу свою"),
    "РАБ_ЕГ_Г": ("раба его",    "рабы ея"),
    "РАБ_БР_Г": ("раба Божия",  "рабы Божия"),
    "РАБ_БР_П": ("рабе Божии",  "рабе Божией"),
    "СЕГО_Г":   ("сего",        "сея"),
    "СЕГО_В":   ("сего",        "сию"),
    "ПРЕДСТ_В": ("предстоящаго", "предстоящую"),
}

RE_MZ = re.compile(r"\{М=([^|}]*)\|Ж=([^}]*)\}")
RE_NAME_TOK = re.compile(r"\{ИМЯ(?:_([ИРДВТП]))?\}")


def resolve_tokens(text: str, name: str, gender: str) -> str:
    """Подстановка имени и родовых форм в текст."""
    forms = decline_name(name, gender)

    def name_sub(m):
        case = m.group(1) or "И"
        return forms[case]

    text = RE_NAME_TOK.sub(name_sub, text)
    text = RE_MZ.sub(lambda m: m.group(1) if gender == "М" else m.group(2), text)
    for tok, (m_form, f_form) in TOKEN_TABLE.items():
        text = text.replace("{%s}" % tok, m_form if gender == "М" else f_form)
    return text


# ═════════════════════════════════════════════════════════════════════════
#  ТЕКСТОВАЯ МОДЕЛЬ
# ═════════════════════════════════════════════════════════════════════════
@dataclass
class Part:
    num: int
    title: str
    lo: int = 0
    hi: int = 0
    lines: List[Tuple[str, str]] = field(default_factory=list)  # (роль, текст)


@dataclass
class Service:
    key: int
    name: str
    dir_tag: str
    parts: List[Part] = field(default_factory=list)
    cs_lines: List[str] = field(default_factory=list)
    raw_tts: str = ""
    raw_cs: str = ""


def parse_parts(tts_text: str) -> List[Part]:
    parts = []
    cur = None
    for line in tts_text.splitlines():
        m = re.match(r"^--- ЧАСТЬ (\d+)\. (.*?) \(строки книги (\d+)-(\d+)\) ---$", line)
        if m:
            if cur:
                parts.append(cur)
            cur = Part(int(m.group(1)), m.group(2),
                       int(m.group(3)), int(m.group(4)))
        elif cur is not None:
            ls = line.strip()
            if not ls or ls.startswith("===") or ls.startswith("Всего знаков"):
                continue
            if ls.startswith("[Д] ") or ls.startswith("[С] "):
                cur.lines.append((ls[1], ls[3:].strip()))
            else:
                if ls.startswith("Обозначения") or ls.startswith("Молитвы, псалмы"):
                    continue
                cur.lines.append(("С", ls))
    if cur:
        parts.append(cur)
    return parts


def load_service(key: int) -> Service:
    name, tts_file, cs_file, dir_tag = SERVICE_FILES[key]
    svc = Service(key, name, dir_tag)
    with open(os.path.join(TEXTS_DIR, tts_file), encoding="utf-8-sig") as fh:
        svc.raw_tts = fh.read()
    svc.parts = parse_parts(svc.raw_tts)
    with open(os.path.join(TEXTS_DIR, cs_file), encoding="utf-8-sig") as fh:
        raw_cs = fh.read()
    svc.raw_cs = raw_cs
    svc.cs_lines = raw_cs.splitlines()
    return svc


def load_references() -> Dict[str, str]:
    """{'ПСАЛОМ 90': текст, 'МОЛИТВА: ОТЧЕ НАШ': текст, 'ЕВАНГЕЛИЕ ОТ ЛУКИ…': …}"""
    out = {}
    p = REFERENCES_FILE
    if not os.path.isfile(p):
        return out
    with open(p, encoding="utf-8-sig") as fh:
        raw = fh.read()
    for m in re.finditer(r"=== ([^=]+?) ===\n(.*?)(?=\n=== |\Z)", raw, re.S):
        out[m.group(1).strip()] = m.group(2).strip()
    return out


# ═════════════════════════════════════════════════════════════════════════
#  ЦЕРКОВНОСЛАВЯНСКИЕ ЧИСЛА И ССЫЛКИ
# ═════════════════════════════════════════════════════════════════════════
COMB = re.compile("[\u0300-\u036f\u0483-\u0489\u2de0-\u2dff]")

SLAV_DIGITS = {
    "а": 1, "в": 2, "г": 3, "д": 4, "е": 5, "ѕ": 6, "з": 7, "и": 8, "ѳ": 9,
    "і": 10, "к": 20, "л": 30, "м": 40, "н": 50, "ѯ": 60,
    "ѻ": 70, "о": 70, "п": 80, "ч": 90, "р": 100, "с": 200, "т": 300,
    "у": 400, "ф": 500, "х": 600, "ѱ": 700, "ѿ": 800, "ц": 900,
}


def fold_line(s: str) -> Tuple[str, List[int]]:
    """Строка без надстрочников + карта индексов оригинала."""
    buf, idx = [], []
    for i, ch in enumerate(s):
        if COMB.match(ch):
            continue
        buf.append(ch)
        idx.append(i)
    return "".join(buf), idx


def decode_slav_number(s: str) -> Optional[int]:
    total = 0
    for ch in s:
        total += SLAV_DIGITS.get(ch, 0)
    return total or None


BOOK_ALIASES = [
    (re.compile(r"(Мар|Маѵрк)"), "МАРКА"),
    (re.compile(r"(Маѳ|Матѳ|Матф)"), "МАТФЕЯ"),
    (re.compile(r"(Лꙋк|Лук)"), "ЛУКИ"),
    (re.compile(r"(Іѡан|Іоан|Иоан)"), "ИОАННА"),
]

PRAYER_LINKS = [
    (re.compile(r"Тртое|Трїсвѧт"), "МОЛИТВА: ТРИСВЯТОЕ"),
    (re.compile(r"(Ѿ|Ѻ)че\s+наш"), "МОЛИТВА: ОТЧЕ НАШ"),
    (re.compile(r"нбныи|нбный"), "МОЛИТВА: ЦАРЮ НЕБЕСНЫЙ"),
    (re.compile(r"Достойн[оѡ]"), "МОЛИТВА: ДОСТОЙНО ЕСТЬ"),
    (re.compile(r"имв[оѡ]л\w*\s+вѣр|Верꙋю"), "МОЛИТВА: СИМВОЛ ВЕРЫ"),
    (re.compile(r"Бце\s+Дво|Богородиц"), "МОЛИТВА: БОГОРОДИЦЕ ДЕВО"),
    (re.compile(r"Во[зꙁ]бранн"), "МОЛИТВА: ВОЗБРАННОЙ ВОЕВОДЕ"),
]

RE_PSALM_REF = re.compile(
    r"([пѰѱ]ало?м[а-џѡѣѧѭѵъ]{0,4}(?:\s+се[йя])?)\s*,\s*([а-џѡѣѳѵѯѻѿц]{1,5})\b")
RE_GOSPEL_REF = re.compile(r"(?:ѿ|ѡт|от|ᲃт)\s*([А-Яа-џꙋѵѡѧі]{2,6})\b")


def linkify_cs(line: str) -> str:
    """HTML строки ЦС с якорями на псалмы, евангелия и молитвы."""
    folded, idx = fold_line(line)
    events = []  # (start_folded, end_folded, href)

    for m in RE_PSALM_REF.finditer(folded):
        n = decode_slav_number(m.group(2))
        if n and 1 <= n <= 150:
            events.append((m.start(1), m.end(2), f"psalm:{n}"))

    if "Еѵ" in folded:
        for m in RE_GOSPEL_REF.finditer(folded):
            for rx, book in BOOK_ALIASES:
                if rx.match(m.group(1)):
                    events.append((m.start(1), m.end(1), f"gospel:{book}"))
                    break

    for rx, target in PRAYER_LINKS:
        for m in rx.finditer(folded):
            events.append((m.start(), m.end(), f"prayer:{target}"))

    if not events:
        return html_escape(line)

    # убираем пересечения — берём непересекающиеся спаны
    events.sort(key=lambda e: (e[0], -(e[1] - e[0])))
    chosen, last_end = [], -1
    for s, e, href in events:
        if s >= last_end:
            chosen.append((s, e, href))
            last_end = e

    out, pos = [], 0
    for s, e, href in chosen:
        o_s, o_e = idx[s], idx[e - 1] + 1
        out.append(html_escape(line[pos:o_s]))
        out.append('<a href="%s">%s</a>' % (href, html_escape(line[o_s:o_e])))
        pos = o_e
    out.append(html_escape(line[pos:]))
    return "".join(out)


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ═════════════════════════════════════════════════════════════════════════
#  ПОДГОТОВКА ТЕКСТА К СИНТЕЗУ
# ═════════════════════════════════════════════════════════════════════════
def tts_clean(text: str, fix_ii: bool = True, stress_marks: bool = False) -> str:
    """Защита от произнесения буквы: твёрдый знак вычищаем полностью,
    фразы-названия букв удаляем. «ь» остаётся — TTS её не читает.

    fix_ii: часть голосов (в т.ч. «Дмитрий» И «Светлана» — проверено
    акустически) произносит «Ии» в начале слова как «э-и»: «Иисусе» →
    «Эсусе». Начальное «Й» даёт правильное «Йи-». Замена применяется
    ТОЛЬКО к тексту синтеза — на экране и в файлах текст канонический.
    Голосам без дефекта (например, Silero «Ксения») fix_ii=False —
    для них текст не меняется вовсе.

    stress_marks: только движку edge (Microsoft), у которого движок
    сам ставит ударения по своей догадке. Знак U+0301 проверен
    синтезом и ASR 2026-10-26:
      • «рабе» → «ра́бе»: без знака конец слова читается с ударением
        и «э»-окраской («рабЭ» — то, что слышно как «Рабэ»), со знаком
        ударение правильно уходит на «рА» (профиль энергии 1.88→2.62);
      • «Иисус…» → «Иису́с…» («Йису́с…» при fix_ii): церковное
        ударение «Иису́се» на «у».
    Вариант «рабье» отвергнут: ASR слышит лишнее «й» («рабьйе»).
    Движку Silero метки не нужны (ставит ударения сам, put_accent)
    и не ставятся; Piper — тоже без меток."""
    text = text.replace("ъ", "").replace("Ъ", "")
    for phrase in ("твёрдый знак", "твердый знак", "мягкий знак"):
        text = re.sub(r"(?i)[,«\s]*%s\s*[,»]?\.?" % phrase, "", text)
    if fix_ii:
        sub = "Йису\u0301с" if stress_marks else "Йисус"
        text = re.sub(r"\bИисус", sub, text)
        text = re.sub(r"\bиисус", sub.lower(), text)
    elif stress_marks:
        text = re.sub(r"\bИисус", "Иису\u0301с", text)
        text = re.sub(r"\bиисус", "иису\u0301с", text)
    if stress_marks:
        text = re.sub(r"\bрабе\b", "ра\u0301бе", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def split_long(text: str, limit: int = 850) -> List[str]:
    """Делит сверхдлинную строку по предложениям, затем по запятым и словам."""
    if len(text) <= limit:
        return [text]
    out, cur = [], ""
    for sent in re.split(r"(?<=[.:;!?])\s+", text):
        if cur and len(cur) + len(sent) + 1 > limit:
            out.append(cur)
            cur = sent
        else:
            cur = (cur + " " + sent).strip() if cur else sent
    if cur:
        out.append(cur)
    # если отдельное «предложение» всё ещё длиннее — режем по запятым
    final = []
    for piece in out:
        if len(piece) <= limit:
            final.append(piece)
            continue
        cur = ""
        for part in re.split(r"(?<=,)\s+", piece):
            if cur and len(cur) + len(part) + 1 > limit:
                final.append(cur)
                cur = part
            else:
                cur = (cur + " " + part).strip() if cur else part
        if cur:
            final.append(cur)
    # совсем монстры — по словам
    result = []
    for piece in final:
        while len(piece) > limit:
            cut = piece.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            result.append(piece[:cut].strip())
            piece = piece[cut:].strip()
        if piece:
            result.append(piece)
    return result or [text]


def build_chunks(part: Part, name: str, gender: str,
                 limit: int = 850,
                 fix_by_role: Optional[Dict[str, bool]] = None,
                 stress_marks: bool = False
                 ) -> List[Tuple[str, str]]:
    """[(роль, текст)] → серии подряд идущих строк одной роли ≤ limit знаков.

    fix_by_role: {"Д": bool, "С": bool} — нужна ли подмена «Ии→Йи»
    каждой роли (зависит от выбранного голоса роли).
    stress_marks: ставить ли ударения «ра́бе» и «Иису́с» (нужно движку
    edge; Silero/Piper — нет)."""
    chunks: List[Tuple[str, str]] = []
    cur_role, cur_buf = None, []

    def flush():
        nonlocal cur_role, cur_buf
        if cur_role and cur_buf:
            for piece in split_long(" ".join(cur_buf), limit):
                chunks.append((cur_role, piece))
        cur_role, cur_buf = None, []

    for role, raw in part.lines:
        text = tts_clean(resolve_tokens(raw, name, gender),
                         fix_ii=(fix_by_role or {}).get(role, True),
                         stress_marks=stress_marks)
        if not text:
            continue
        if role != cur_role or sum(len(t) for t in cur_buf) + len(text) > limit:
            flush()
            cur_role = role
        cur_buf.append(text)
    flush()
    return chunks


def part_signature(chunks, name, gender, speed, vd, vs):
    h = hashlib.md5()
    for role, text in chunks:
        h.update((role + "|" + text + "\n").encode("utf-8"))
    h.update(f"|{name}|{gender}|{speed}|{vd}|{vs}|rev:{TEXT_FIX_REV}".encode("utf-8"))
    return h.hexdigest()[:16]


def part_filename(part: Optional[Part], service: Service, ext: str = ".mp3") -> str:
    if part is None:
        return "00_polnostyu" + ext
    return "%02d_%s%s" % (part.num, translit(part.title), ext)


# ═════════════════════════════════════════════════════════════════════════
#  ПОТЕРПИМЫЙ ДЛИТЕЛЬНОСТИ MP3 (mutagen, необязателен)
# ═════════════════════════════════════════════════════════════════════════
def mp3_duration_ms(path: str) -> Optional[int]:
    try:
        from mutagen.mp3 import MP3
        return int(MP3(path).info.length * 1000)
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════════
#  ПОТОК СИНТЕЗА (edge — онлайн / silero, piper — офлайн)
# ═════════════════════════════════════════════════════════════════════════
SILERO_MODELS = {}
PIPER_MODELS = {}
PIPER_DIR = os.path.join(AUDIO_DIR, "piper_models")


def silero_load(model_name):
    """Загрузка (и кэш) модели Silero; дружелюбные ошибки по стадиям."""
    if model_name not in SILERO_MODELS:
        if not package_ok("silero"):
            raise RuntimeError(
                "Пакет silero не найден тем Python'ом, который запускает плеер:\n"
                "  %s\n\n"
                "Установите из терминала именно этим Python'ом\n"
                "(подставьте путь из сообщения выше):\n"
                "  1) ... -m pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
                "     — компактная CPU-сборка torch ~200 МБ; без этого шага pip\n"
                "       потянет гигабайтную сборку с CUDA;\n"
                "  2) ... -m pip install silero\n\n"
                "Модель ≈38 МБ скачается один раз при первом синтезе\n"
                "(нужен доступ к github.com и models.silero.ai)." % sys.executable)
        try:
            from silero import silero_tts
            m = silero_tts(language="ru", speaker=model_name)
        except ImportError as e:
            raise RuntimeError(
                "Не импортируется silero/torch:\n  %s\n\n"
                "Частые причины на Windows:\n"
                " • пакеты ставились ДРУГИМ Python'ом — переустановите тем же:\n"
                "   «%s» -m pip install --force-reinstall silero\n"
                " • нет Microsoft Visual C++ Redistributable (из-за него torch\n"
                "   падает с «DLL load failed») — поставьте vc_redist.x64.exe\n"
                "   с сайта Microsoft и перезапустите плеер;\n"
                " • повреждён torch — «%s» -m pip install --force-reinstall "
                "torch --index-url https://download.pytorch.org/whl/cpu"
                % (e, sys.executable, sys.executable))
        except Exception as e:
            raise RuntimeError(
                "Не удалось скачать/загрузить модель Silero:\n  %s\n\n"
                "На первом синтезе нужно скачать ≈38 МБ с github.com\n"
                "и models.silero.ai — проверьте интернет (или антивирус,\n"
                "который мог заблокировать загрузку), затем повторите." % e)
        if isinstance(m, tuple):
            m = m[0]
        SILERO_MODELS[model_name] = m
    return SILERO_MODELS[model_name]


def silero_pcm(text: str, model_name: str, speaker: str,
               sr: int = ENGINE_SR["silero"]) -> bytes:
    """Синтез Silero → PCM int16 моно."""
    model = silero_load(model_name)
    t = model.apply_tts(text=text, speaker=speaker, sample_rate=sr,
                        put_accent=True, put_yo=True)
    data = t.detach().cpu().numpy()
    if data.ndim > 1:
        data = data[0]
    return (data * 32767).clip(-32768, 32767).astype("<i2").tobytes()


def piper_load(name: str):
    """Загрузка (с скачиванием при первом обращении) модели Piper."""
    if name not in PIPER_MODELS:
        if not package_ok("piper"):
            raise RuntimeError(
                "Пакет piper-tts не найден тем Python'ом, который запускает плеер:\n"
                "  %s\n\n"
                "Установите из терминала именно этим Python'ом:\n"
                "  ... -m pip install piper-tts\n\n"
                "Модель ≈60 МБ скачается один раз при первом синтезе." % sys.executable)
        os.makedirs(PIPER_DIR, exist_ok=True)
        onnx = os.path.join(PIPER_DIR, "ru_RU-%s-medium.onnx" % name)
        jsn = onnx + ".json"
        # два зеркала: huggingface.co и hf-mirror.com (недоступность HF —
        # частая причина сбоев загрузки; зеркало пробуется автоматически)
        bases = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                 "ru/ru_RU/%s/medium/ru_RU-%s-medium.%s",
                 "https://hf-mirror.com/rhasspy/piper-voices/resolve/main/"
                 "ru/ru_RU/%s/medium/ru_RU-%s-medium.%s")
        try:
            if not os.path.isfile(onnx):
                _urlretrieve_any(bases, name, "onnx", onnx)
            if not os.path.isfile(jsn):
                _urlretrieve_any(bases, name, "onnx.json", jsn)
        except Exception as e:
            raise RuntimeError(
                "Не удалось скачать модель Piper:\n  %s\n\n"
                "Нужен доступ к huggingface.co (или зеркалу hf-mirror.com,\n"
                "пробуется сам), ≈60 МБ. Проверьте интернет и повторите." % e)
        try:
            from piper import PiperVoice
            PIPER_MODELS[name] = PiperVoice.load(onnx)
        except Exception as e:
            raise RuntimeError(
                "PiperVoice.load не смог открыть модель (%s).\n"
                "Полная трассировка — в окне ошибки (кнопка «Скопировать всё»)\n"
                "и в файле error_log.txt рядом с плеером — пришлите её." % e)
    return PIPER_MODELS[name]


def _urlretrieve_any(bases, name, suffix, dest):
    last = None
    for base in bases:
        try:
            urllib.request.urlretrieve(base % (name, name, suffix), dest)
            return
        except Exception as e:
            last = e
    raise last


def piper_pcm(text: str, name: str, length_scale: float = 1.25
              ) -> Tuple[bytes, int]:
    """Синтез Piper → (PCM int16 моно, sample_rate).
    Совместим и с piper-tts >= 1.3 (SynthesisConfig), и с 1.2.0
    (keyword-аргументы): у API двух версий разные сигнатуры."""
    import io
    import wave
    voice = piper_load(name)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        try:
            from piper import SynthesisConfig      # piper-tts >= 1.3
            voice.synthesize_wav(text, w,
                                 syn_config=SynthesisConfig(
                                     length_scale=length_scale))
        except ImportError:                        # старый piper-tts 1.2.0
            voice.synthesize(text, w, length_scale=length_scale)
    buf.seek(0)
    with wave.open(buf, "rb") as r:
        return r.readframes(r.getnframes()), r.getframerate()


def wav_write(path: str, pcm: bytes, sr: int):
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def wav_read_frames(path: str) -> Tuple[bytes, int]:
    import wave
    with wave.open(path, "rb") as w:
        return w.readframes(w.getnframes()), w.getframerate()


def edge_apply_v2() -> bool:
    """Переводит edge-tts на новый протокол v2 (октябрь 2026).

    Microsoft закрывает старый WebSocket-эндпоинт
    speech.platform.bing.com: обновлённые серверы отвечают 403
    либо завершают сессию без аудио («No audio was received»).
    Новый протокол: api.msedgeservices.com, ключ передаётся
    параметром Ocp-Apim-Subscription-Key, Sec-MS-GEC-Version
    2-155.0.4283.45, UA Edge 155. Идемпотентно; False — если
    патчить нечего (установленный edge-tts уже сам на v2)."""
    try:
        import edge_tts.communicate as comm
    except ImportError:
        return False
    if "speech.platform.bing.com" not in getattr(comm, "WSS_URL", ""):
        return False                     # уже v2 / другая структура
    token = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"   # публичный ключ Read Aloud
    try:
        from edge_tts.constants import TRUSTED_CLIENT_TOKEN as token
    except ImportError:
        pass
    comm.WSS_URL = ("wss://api.msedgeservices.com/tts/cognitiveservices"
                    "/websocket/v1?Ocp-Apim-Subscription-Key=" + token)
    comm.SEC_MS_GEC_VERSION = "2-155.0.4283.45"
    ua = comm.WSS_HEADERS.get("User-Agent", "")
    m = re.search(r"Chrome/(\d+)", ua)
    if m and int(m.group(1)) < 155:
        comm.WSS_HEADERS["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"
            " Edg/155.0.0.0")
    return True


class SynthWorker(QThread):
    sig_progress = pyqtSignal(int, int, str)   # сделано, всего, подпись
    sig_part = pyqtSignal(int, str)            # индекс части, путь
    sig_error = pyqtSignal(str)
    sig_finished = pyqtSignal(bool)            # True = отменено

    def __init__(self, service, indexes, name, gender, speed, out_dir,
                 voice_d, voice_s, fix_d, fix_s, parent=None):
        super().__init__(parent)
        self.service = service
        self.indexes = indexes           # список индексов частей или None → все
        self.name = name
        self.gender = gender
        self.speed = speed
        self.out_dir = out_dir
        self.v_d = voice_by_key(voice_d)   # голос роли «священник»
        self.v_s = voice_by_key(voice_s)   # голос роли «хор»
        self.engine = self.v_d[3]
        self.fix_by_role = {"Д": bool(fix_d), "С": bool(fix_s)}
        # ударения «ра́бе» и «Иису́с» — только движку edge (проверено ASR;
        # Silero ставит ударения сам, Piper — экспериментальный)
        self.stress_marks = self.engine == "edge"
        self.ext = ENGINE_EXT[self.engine]
        self.sr = ENGINE_SR[self.engine]   # 0 = MP3-поток (edge)
        self.with_full = indexes is None or indexes == "all"
        self._cancel = False

    # public
    def stop(self):
        self._cancel = True

    # internal
    def run(self):
        try:
            asyncio.run(self._run())
        except Cancelled:
            pass
        except Exception:
            self.sig_error.emit(traceback.format_exc(limit=5))
        finally:
            self.sig_finished.emit(self._cancel)

    def _sig_voices(self):
        return (self.v_d[0] + ("|fix" if self.fix_by_role["Д"] else ""),
                self.v_s[0] + ("|fix" if self.fix_by_role["С"] else ""))

    async def _chunk_edge(self, text: str, voice_id: str, rate: str) -> bytes:
        import edge_tts
        if not text or not text.strip():
            return b""                    # нечего озвучивать — тишина
        last_err = None
        for attempt in range(4):
            if self._cancel:
                raise Cancelled()
            try:
                buf = bytearray()
                comm = edge_tts.Communicate(text, voice_id, rate=rate, pitch="-2Hz")
                async for piece in comm.stream():
                    if piece["type"] == "audio":
                        buf.extend(piece["data"])
                if buf:
                    return bytes(buf)
                last_err = RuntimeError("пустой ответ TTS")
            except Cancelled:
                raise
            except Exception as e:
                last_err = e
            # Microsoft закрывает старый протокол Read Aloud (окт. 2026):
            # часть серверов уже отвечает 403/без аудио. Первый сбой —
            # переключаемся на протокол v2 и продолжаем попытки.
            edge_apply_v2()
            await asyncio.sleep(1.2 * (attempt + 1))
        raise RuntimeError(
            "edge-tts: %s\n\n"
            "Онлайн-движок Microsoft не ответил. Старый протокол\n"
            "speech.platform.bing.com закрыт (с октября 2026 серверы\n"
            "переведены на api.msedgeservices.com — плеер пробует его\n"
            "автоматически). Если ошибка повторяется:\n"
            "  • проверьте интернет и не блокирует ли файрвол/антивирус\n"
            "    исходящие wss://-соединения;\n"
            "  • обновите пакет тем же Python'ом:\n"
            "    «%s» -m pip install -U edge-tts\n"
            "    (в будущих версиях новый протокол — из коробки);\n"
            "  • либо выберите офлайн-голоса (Silero/Piper) — им для\n"
            "    синтеза интернет не нужен.\n\n"
            "Уже синтезированные части сохранены в папке audio/."
            % (last_err, sys.executable))

    def _chunk_offline(self, text: str, v) -> bytes:
        if self._cancel:
            raise Cancelled()
        if self.engine == "silero":
            model_name, speaker = v[4]
            return silero_pcm(text, model_name, speaker, self.sr)
        pcm, got_sr = piper_pcm(text, v[4],
                                max(0.6, min(2.2, 1.0 / max(0.4, self.speed))))
        if got_sr != self.sr:
            self.sr = got_sr     # все ru_RU-medium = 22.05 кГц, но на всякий случай
        return pcm

    async def _run(self):
        os.makedirs(self.out_dir, exist_ok=True)
        if self.engine != "edge":
            # предзагрузка моделей обеих ролей — быстрый отказ + кэш
            for v in dict.fromkeys((self.v_d, self.v_s)):
                if self.engine == "silero":
                    silero_load(v[4][0])
                else:
                    piper_load(v[4])
        pause = self._load_pause()
        rate = "%+d%%" % round((self.speed - 1.0) * 100)
        is_mp3 = self.engine == "edge"
        vd, vs = self._sig_voices()

        idxs = list(range(len(self.service.parts))) if self.indexes in (None, "all") \
            else list(self.indexes)
        total = len(idxs) + (1 if self.with_full else 0)
        done = 0
        cache = self._read_cache()

        for i in idxs:
            if self._cancel:
                return
            part = self.service.parts[i]
            fname = part_filename(part, self.service, self.ext)
            fpath = os.path.join(self.out_dir, fname)
            chunks = build_chunks(part, self.name, self.gender,
                                  fix_by_role=self.fix_by_role,
                                  stress_marks=self.stress_marks)
            sig = part_signature(chunks, self.name, self.gender,
                                 self.speed, vd, vs)
            if os.path.isfile(fpath) and cache.get(fname) == sig:
                done += 1
                self.sig_progress.emit(done, total, "готово: %s" % fname)
                self.sig_part.emit(i, fpath)
                continue
            self.sig_progress.emit(done, total, "часть %02d: %s" % (part.num, part.title))
            audio = bytearray()
            for j, (role, text) in enumerate(chunks):
                if self._cancel:
                    return
                v = self.v_d if role == "Д" else self.v_s
                if is_mp3:
                    audio.extend(await self._chunk_edge(text, v[4], rate))
                else:
                    audio.extend(self._chunk_offline(text, v))
                if pause and j < len(chunks) - 1:
                    audio.extend(pause)
            if is_mp3:
                with open(fpath, "wb") as fh:
                    fh.write(audio)
            else:
                wav_write(fpath, bytes(audio), self.sr)
            cache[fname] = sig
            self._write_cache(cache)
            done += 1
            self.sig_progress.emit(done, total, "часть %02d готова" % part.num)
            self.sig_part.emit(i, fpath)

        if self.with_full and not self._cancel:
            self.sig_progress.emit(done, total, "склейка полного файла")
            full_path = os.path.join(self.out_dir,
                                     part_filename(None, self.service, self.ext))
            if is_mp3:
                with open(full_path, "wb") as out:
                    for k, i in enumerate(idxs):
                        p = os.path.join(self.out_dir, part_filename(
                            self.service.parts[i], self.service, self.ext))
                        with open(p, "rb") as fh:
                            out.write(fh.read())
                        if k != len(idxs) - 1 and pause:
                            out.write(pause)
                            out.write(pause)
            else:
                import wave as _w
                with _w.open(full_path, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(self.sr)
                    for k, i in enumerate(idxs):
                        if self._cancel:
                            return
                        p = os.path.join(self.out_dir, part_filename(
                            self.service.parts[i], self.service, self.ext))
                        frames, _sr = wav_read_frames(p)
                        w.writeframes(frames)
                        if k != len(idxs) - 1:
                            w.writeframes(pause)
                            w.writeframes(pause)
            cache[part_filename(None, self.service, self.ext)] = "full-" + self._full_sig()
            self._write_cache(cache)
            done += 1
            self.sig_part.emit(-1, full_path)

    def _full_sig(self):
        sigs = []
        vd, vs = self._sig_voices()
        for part in self.service.parts:
            chunks = build_chunks(part, self.name, self.gender,
                                  fix_by_role=self.fix_by_role,
                                  stress_marks=self.stress_marks)
            sigs.append(part_signature(chunks, self.name, self.gender,
                                       self.speed, vd, vs))
        return hashlib.md5("|".join(sigs).encode()).hexdigest()[:16]

    def _load_pause(self):
        if self.engine == "edge":
            for cand in (os.path.join(APP_DIR, "pause_400ms.mp3"),):
                if os.path.isfile(cand):
                    with open(cand, "rb") as fh:
                        return fh.read()
            return b""
        return b"\x00\x00" * int(0.4 * self.sr)

    def _read_cache(self):
        p = os.path.join(self.out_dir, ".cache.json")
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                return {}
        return {}

    def _write_cache(self, cache):
        p = os.path.join(self.out_dir, ".cache.json")
        try:
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(cache, fh, ensure_ascii=False, indent=1)
        except Exception:
            pass


class Cancelled(Exception):
    pass


# ═════════════════════════════════════════════════════════════════════════
#  КАРАОКЕ: раскладка строк по времени
# ═════════════════════════════════════════════════════════════════════════
class KaraokeTrack:
    def __init__(self, lines, speed, part_bounds=None):
        """lines: [(роль, текст)]; part_bounds: [мс границ частей] (для полного)."""
        self.entries = []  # (start_ms_estimate, line_index_global)
        self.part_bounds = part_bounds or []
        k = speed / 0.8
        t = 0.0
        for role, text in lines:
            dur = max(1.8, len(text) / (CH_PER_SEC[role] * k)) * 1000
            self.entries.append(t)
            t += dur
        self.estimated_total = t

    def line_at(self, position_ms: int, actual_duration_ms: int) -> int:
        if not self.entries:
            return -1
        if not actual_duration_ms:
            scale = 1.0
        else:
            scale = min(2.5, max(0.3, actual_duration_ms / max(1, self.estimated_total)))
        arr = [e * scale for e in self.entries]
        lo, hi = 0, len(arr) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if arr[mid] <= position_ms:
                lo = mid
            else:
                hi = mid - 1
        return lo


# ═════════════════════════════════════════════════════════════════════════
#  ДИАЛОГ ССЫЛКИ (псалом / евангелие / молитва)
# ═════════════════════════════════════════════════════════════════════════
class ErrorDialog(QDialog):
    """Окно ошибки с ВЫДЕЛЯЕМЫМ текстом: Ctrl+C, ПКМ → Копировать,
    кнопка «Скопировать всё» — чтобы можно было переслать ошибку."""

    def __init__(self, title, text, note="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 500)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.edit = QPlainTextEdit(text)
        self.edit.setReadOnly(True)
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSize(9)
        self.edit.setFont(f)
        lay.addWidget(self.edit, 1)
        self.noteLabel = QLabel(note)
        self.noteLabel.setWordWrap(True)
        lay.addWidget(self.noteLabel)
        bar = QHBoxLayout()
        bar.addStretch(1)
        btnCopy = QPushButton("Скопировать всё")
        btnCopy.clicked.connect(self.copy_all)
        btnClose = QPushButton("Закрыть")
        btnClose.clicked.connect(self.accept)
        btnClose.setDefault(True)
        bar.addWidget(btnCopy)
        bar.addWidget(btnClose)
        lay.addLayout(bar)

    def copy_all(self):
        QApplication.clipboard().setText(self.edit.toPlainText())
        self.noteLabel.setText(
            "Скопировано в буфер обмена — можно вставить (Ctrl+V) в письмо.")


class ReferenceDialog(QDialog):
    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(
            "<p style='font-size:15px; line-height:150%%'>%s</p>"
            % html_escape(text).replace("\n", "<br><br>"))
        lay.addWidget(browser)
        btn = QPushButton("Закрыть")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)


# ═════════════════════════════════════════════════════════════════════════
#  ГЛАВНОЕ ОКНО
# ═════════════════════════════════════════════════════════════════════════
QSS = """
QMainWindow, QDialog { background: #14161c; }
QWidget { background: #14161c; color: #d8d3c4; font-size: 13px; }
QLabel { color: #b9b2a0; }
QLabel#titleLabel {
    font-size: 17px; font-weight: 600; color: #e6c35c; padding: 2px 0;
}
QLabel#partLabel { font-size: 12px; color: #8f8875; }
QLineEdit, QDoubleSpinBox, QComboBox {
    background: #1e2129; border: 1px solid #3a3f4d; border-radius: 6px;
    padding: 5px 8px; color: #e8e3d5; min-height: 22px;
}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid #c9a227; }
QCheckBox { color: #cfc7b0; }
QCheckBox::indicator { width: 14px; height: 14px; }
QComboBox QAbstractItemView {
    background: #1e2129; border: 1px solid #3a3f4d;
    selection-background-color: #4a3c14; selection-color: #e6c35c;
}
QPushButton, QToolButton {
    background: #23262f; border: 1px solid #3a3f4d; border-radius: 6px;
    padding: 6px 14px; color: #d8d3c4;
}
QPushButton:hover, QToolButton:hover { background: #2b2f3a; border-color: #c9a227; }
QPushButton:disabled, QToolButton:disabled { color: #615f57; border-color: #2b2f36; }
QPushButton#gold {
    background: #4a3c14; border: 1px solid #c9a227; color: #f2dfa0; font-weight: 600;
}
QPushButton#gold:hover { background: #5d4b1a; }
QToolButton:checked {
    background: #4a3c14; border: 1px solid #c9a227; color: #f2dfa0; font-weight: 600;
}
QListWidget {
    background: #181b22; border: 1px solid #2b2f3a; border-radius: 6px;
    padding: 4px; font-size: 12px;
}
QListWidget::item { padding: 6px 8px; border-radius: 5px; color: #cfc9ba; }
QListWidget::item:selected { background: #4a3c14; color: #f2dfa0; }
QListWidget::item:hover { background: #23262f; }
QTextBrowser {
    background: #101216; border: 1px solid #2b2f3a; border-radius: 6px;
    padding: 10px; color: #e8e3d5; font-size: 15px;
    selection-background-color: #5d4b1a; selection-color: #f2dfa0;
}
QPlainTextEdit {
    background: #101216; border: 1px solid #2b2f3a; border-radius: 6px;
    padding: 8px; color: #e8e3d5; font-size: 12px;
    selection-background-color: #5d4b1a; selection-color: #f2dfa0;
}
a { color: #e6c35c; }
QProgressBar {
    background: #1e2129; border: 1px solid #3a3f4d; border-radius: 6px;
    text-align: center; color: #b9b2a0; min-height: 18px;
}
QProgressBar::chunk { background: #c9a227; border-radius: 5px; margin: 1px; }
QSlider::groove:horizontal { height: 5px; background: #2b2f3a; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #c9a227; width: 12px; margin: -5px 0; border-radius: 5px;
}
QSlider::sub-page:horizontal { background: #6b5518; border-radius: 2px; }
QStatusBar { background: #101216; color: #8f8875; }
QStatusBar QLabel { color: #8f8875; font-size: 11px; }
QSplitter::handle { background: #2b2f3a; width: 3px; }
QGroupBox {
    border: 1px solid #2b2f3a; border-radius: 8px; margin-top: 10px;
    padding: 8px; font-size: 12px; color: #8f8875;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QRadioButton { spacing: 6px; }
QRadioButton::indicator { width: 15px; height: 15px; border-radius: 8px;
    border: 1px solid #3a3f4d; background: #1e2129; }
QRadioButton::indicator:checked { background: #c9a227; border-color: #c9a227; }
"""

SPEAKER_STYLE = {"Д": "#d2b55a", "С": "#7f96b8"}


class Browser(QTextBrowser):
    """Текстовая панель с пунктом «Копировать всё» в контекстном меню
    (когда ничего не выделено) — выделение на тёмной теме теперь видно."""

    def contextMenuEvent(self, ev):
        menu = self.createStandardContextMenu()
        if not self.textCursor().hasSelection():
            menu.addSeparator()
            act = menu.addAction("Копировать всё")
            act.triggered.connect(
                lambda: QApplication.clipboard().setText(self.toPlainText()))
        menu.exec(ev.globalPos())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        avail = self.screen().availableGeometry() if self.screen() \
            else QApplication.primaryScreen().availableGeometry()
        # окно подстраивается под экран пользователя (напр. 1366×768)
        self.resize(min(1180, avail.width() - 70),
                    min(730, avail.height() - 70))
        self.settings = QSettings("TrebnikOtchitka", "trebnik_player")

        # состояние
        self.services = {1: load_service(1), 2: load_service(2)}
        self.references = load_references()
        self.svc_key = int(self.settings.value("service", 1))
        if self.svc_key not in self.services:
            self.svc_key = 1
        self.name = str(self.settings.value("name", "Максим"))
        self.gender = str(self.settings.value("gender", "М"))
        self.speed = float(self.settings.value("speed", 0.8))
        self.view = str(self.settings.value("view", "tts"))
        self.sel = int(self.settings.value("sel", -1))   # -1 = полностью
        # голоса ролей: любой голос на любую роль, пол — на выбор пользователя
        self.voice_d = str(self.settings.value("voice_d", "dmitry"))
        self.voice_s = str(self.settings.value("voice_s", "svetlana"))
        if self.voice_d not in [v[0] for v in VOICES]:
            self.voice_d = "dmitry"
        if self.voice_s not in [v[0] for v in VOICES]:
            self.voice_s = "svetlana"
        self.fix_ii = self.settings.value("fix_ii", True, type=bool)

        self.player = None
        self.track = None          # KaraokeTrack
        self.view_lines = []       # (роль, текст) текущей страницы для караоке
        self.karaoke_line = -1
        self.worker = None
        self.audio_path = None

        self.karaoke_timer = QTimer(self, interval=180)
        self.karaoke_timer.timeout.connect(self.on_karaoke_tick)

        self._build_ui()
        self._init_player()
        self.apply_state()
        self.on_select()

    # ── интерфейс ────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 6)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        #левая колонка
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(6)
        self.titleLabel = QLabel("Требникъ — Отчитка")
        self.titleLabel.setObjectName("titleLabel")
        lv.addWidget(self.titleLabel)
        self.serviceCombo = QComboBox()
        for k in (1, 2):
            self.serviceCombo.addItem(self.services[k].name, k)
        self.serviceCombo.currentIndexChanged.connect(self.on_service)
        lv.addWidget(self.serviceCombo)
        self.partList = QListWidget()
        self.partList.currentRowChanged.connect(self.on_select)
        lv.addWidget(self.partList, 1)
        splitter.addWidget(left)

        #правая колонка
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(6)

        # строка 1: переключатель вида
        bar1 = QHBoxLayout()
        bar1.setSpacing(6)
        self.btnTts = QToolButton(text="Под озвучку")
        self.btnCs = QToolButton(text="Церковнославянскій")
        for b in (self.btnTts, self.btnCs):
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.viewGroup = QButtonGroup(self)
        self.viewGroup.setExclusive(True)
        self.viewGroup.addButton(self.btnTts)
        self.viewGroup.addButton(self.btnCs)
        self.btnTts.toggled.connect(lambda v: self.on_view("tts" if v else "cs"))
        self.btnCs.toggled.connect(lambda v: self.on_view("cs" if v else "tts"))
        bar1.addWidget(self.btnTts)
        bar1.addWidget(self.btnCs)
        self.partLabel = QLabel("")
        self.partLabel.setObjectName("partLabel")
        bar1.addStretch(1)
        bar1.addWidget(self.partLabel)
        rv.addLayout(bar1)

        # строка 2: имя и параметры
        bar2 = QHBoxLayout()
        bar2.setSpacing(8)
        bar2.addWidget(QLabel("Имя:"))
        self.nameEdit = QLineEdit(self.name)
        self.nameEdit.setFixedWidth(170)
        self.nameEdit.setToolTip("Имя вместо «Имярек».\n"
                                  "Склоняется автоматически; мужское или женское — ниже.")
        self.nameEdit.editingFinished.connect(self.on_name_changed)
        bar2.addWidget(self.nameEdit)
        self.rbM = QRadioButton("муж.")
        self.rbF = QRadioButton("жен.")
        self.rbM.toggled.connect(lambda: self.on_gender("М"))
        self.rbF.toggled.connect(lambda: self.on_gender("Ж"))
        bar2.addWidget(self.rbM)
        bar2.addWidget(self.rbF)
        bar2.addSpacing(10)
        bar2.addWidget(QLabel("Скорость:"))
        self.speedSpin = QDoubleSuffixProxy()
        self.speedSpin.setRange(0.5, 1.2)
        self.speedSpin.setSingleStep(0.05)
        self.speedSpin.setValue(self.speed)
        self.speedSpin.valueChanged.connect(self.on_speed)
        bar2.addWidget(self.speedSpin)
        bar2.addStretch(1)
        rv.addLayout(bar2)

        # строка 2b: голоса ролей (священник / хор) — любой из 17 голосов
        bar2v = QHBoxLayout()
        bar2v.setSpacing(8)
        bar2v.addWidget(QLabel("Священник:"))
        self.comboD = QComboBox()
        self.comboS = QComboBox()
        for combo in (self.comboD, self.comboS):
            for v in VOICES:
                combo.addItem(voice_label(v), v[0])
                combo.setItemData(combo.count() - 1, voice_tooltip(v),
                                  Qt.ItemDataRole.ToolTipRole)
            combo.setMinimumContentsLength(14)
            combo.currentIndexChanged.connect(lambda _=0: self.on_voice_changed())
        self.comboD.setToolTip("Голос роли «священник» — любой, пол не важен;\n"
                               "обычай — мужской, но выбор за вами")
        self.comboS.setToolTip("Голос роли «хор» (также наставления и рубрики).\n"
                               "Оба голоса должны быть из одного движка")
        bar2v.addWidget(self.comboD)
        bar2v.addWidget(QLabel("Хор:"))
        bar2v.addWidget(self.comboS)
        self.chkFix = QCheckBox("Ии→Йи (лечить дефект)")
        self.chkFix.setToolTip(
            "Часть голосов (Дмитрий, Светлана, Эндрю, Эмма, Айдар,\n"
            "Евгений и др.) читает «Иисусе» как «Эсусе» — проверено\n"
            "акустически. Подмена «Ии→Йи» делает произношение правильным\n"
            "и применяется ТОЛЬКО к тексту синтеза: на экране и в файлах\n"
            "текст канонический. Голосам без дефекта подмена не нужна.\n\n"
            "Кроме неё, для голосов Microsoft автоматически ставятся\n"
            "знаки ударения: «ра́бе» (без знака слышится «рабЭ»/«Рабэ»,\n"
            "со знаком — правильное «рАбе») и «Иису́се» с ударением на «у»,\n"
            "как в церковном чтении. Silero ударения ставит сам.")
        self.chkFix.toggled.connect(self.on_fix_toggled)
        bar2v.addWidget(self.chkFix)
        bar2v.addStretch(1)
        rv.addLayout(bar2v)

        # строка 3: плеер
        bar3 = QHBoxLayout()
        bar3.setSpacing(8)
        self.btnPlay = QPushButton("Слушать")
        self.btnPlay.setObjectName("gold")
        self.btnPlay.clicked.connect(self.on_play)
        self.btnStop = QPushButton("Стоп")
        self.btnStop.clicked.connect(self.on_stop)
        self.btnGen = QPushButton("Синтезировать часть")
        self.btnGen.clicked.connect(self.on_gen_part)
        self.btnGenAll = QPushButton("Всё последование")
        self.btnGenAll.clicked.connect(self.on_gen_all)
        self.btnCancel = QPushButton("Отмена")
        self.btnCancel.clicked.connect(self.on_cancel)
        self.btnCancel.setVisible(False)
        for w in (self.btnPlay, self.btnStop, self.btnGen, self.btnGenAll, self.btnCancel):
            bar3.addWidget(w)
        bar3.addStretch(1)
        bar3.addWidget(QLabel("…"))
        self.timeLabel = QLabel("00:00 / 00:00")
        bar3.addWidget(self.timeLabel)
        rv.addLayout(bar3)

        # строка 4: ползунок позиции
        bar4 = QHBoxLayout()
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.sliderMoved.connect(self.on_seek)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(self.settings.value("volume", 80)))
        self.volume.setFixedWidth(120)
        self.volume.setToolTip("Громкость")
        self.volume.sliderMoved.connect(self.on_volume)
        bar4.addWidget(self.seek, 1)
        bar4.addWidget(self.volume)
        rv.addLayout(bar4)

        # текст
        self.browser = Browser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.on_anchor)
        rv.addWidget(self.browser, 1)

        # прогресс
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        rv.addWidget(self.progress)

        splitter.addWidget(right)
        splitter.setSizes([330, 910])

        sb = QStatusBar()
        self.setStatusBar(sb)
        self.statusMsg = QLabel("")
        sb.addWidget(self.statusMsg, 1)

    def _init_player(self):
        try:
            self.player = QMediaPlayer(self)
            self.audio_out = QAudioOutput(self)
            self.player.setAudioOutput(self.audio_out)
            self.player.positionChanged.connect(self.on_position)
            self.player.durationChanged.connect(self.on_duration)
            self.player.playbackStateChanged.connect(self.on_play_state)
            self.audio_out.setVolume(self.settings.value("volume", 80, type=float) / 100.0)
        except Exception as e:
            self.player = None
            self.status_show("Аудиоплеер недоступен: %s" % e)

    # ── применение состояния ────────────────────────────────────────────
    def apply_state(self):
        idx = 0 if self.svc_key == 1 else 1
        self.serviceCombo.setCurrentIndex(idx)
        if self.gender == "Ж":
            self.rbF.setChecked(True)
        else:
            self.rbM.setChecked(True)
        self.btnTts.setChecked(self.view == "tts")
        self.btnCs.setChecked(self.view == "cs")
        keys = [v[0] for v in VOICES]
        self.comboD.setCurrentIndex(max(0, keys.index(self.voice_d)))
        self.comboS.setCurrentIndex(max(0, keys.index(self.voice_s)))
        self.chkFix.setChecked(self.fix_ii)
        self.apply_voice_ui()
        self.refresh_list()

    def refresh_list(self):
        svc = self.services[self.svc_key]
        self.partList.blockSignals(True)
        self.partList.clear()
        item = QListWidgetItem("▸  Полностью (все части)")
        item.setData(Qt.ItemDataRole.UserRole, -1)
        self.partList.addItem(item)
        for i, p in enumerate(svc.parts):
            it = QListWidgetItem("%02d · %s" % (p.num, p.title))
            it.setData(Qt.ItemDataRole.UserRole, i)
            self.partList.addItem(it)
        row = 0 if self.sel == -1 else self.sel + 1
        self.partList.setCurrentRow(min(row, self.partList.count() - 1))
        self.partList.blockSignals(False)

    # ── обработчики ─────────────────────────────────────────────────────
    def on_service(self, idx):
        self.svc_key = self.serviceCombo.itemData(idx)
        self.settings.setValue("service", self.svc_key)
        self.sel = -1
        self.refresh_list()
        self.on_select()

    def on_select(self):
        if not self.partList.currentItem():
            return
        self.sel = self.partList.currentItem().data(Qt.ItemDataRole.UserRole)
        self.settings.setValue("sel", self.sel)
        self.stop_playback()
        self.render()

    def on_view(self, view):
        if self.view == view:
            return
        self.view = view
        self.settings.setValue("view", view)
        self.render()

    def on_name_changed(self):
        nm = self.nameEdit.text().strip()
        if not nm:
            nm = "Максим"
        if nm != self.name:
            self.name = nm
            self.settings.setValue("name", nm)
            self.auto_gender()
            self.render()
            self.check_audio_stale()
        self.nameEdit.setText(nm)

    def auto_gender(self):
        g = guess_gender(self.name)
        if g == "Ж":
            self.rbF.setChecked(True)
        else:
            self.rbM.setChecked(True)
        self.gender = g
        self.settings.setValue("gender", g)

    def on_gender(self, g):
        other = self.rbF if g == "М" else self.rbM
        if other.isChecked():
            return  # пользователь снял флажок
        self.gender = g
        self.settings.setValue("gender", g)
        self.render()
        self.check_audio_stale()

    def on_speed(self, val):
        self.speed = round(float(val), 2)
        self.settings.setValue("speed", self.speed)
        self.check_audio_stale()

    def on_volume(self, v):
        if self.player:
            self.audio_out.setVolume(v / 100.0)
        self.settings.setValue("volume", v)

    # ── голоса ролей ───────────────────────────────────────────────────────
    def fix_map(self):
        """{роль: применять ли подмену «Ии»} — по голосу роли и галочке."""
        v1 = voice_by_key(self.voice_d)
        v2 = voice_by_key(self.voice_s)
        return {"Д": v1[5] and self.fix_ii,
                "С": v2[5] and self.fix_ii}

    def sig_pair(self):
        fm = self.fix_map()
        return (self.voice_d + ("|fix" if fm["Д"] else ""),
                self.voice_s + ("|fix" if fm["С"] else ""))

    def apply_voice_ui(self):
        v1 = voice_by_key(self.voice_d)
        v2 = voice_by_key(self.voice_s)
        engine = v1[3]
        # скорость: MS = rate, Piper = length_scale, Silero — свой темп
        self.speedSpin.setEnabled(engine in ("edge", "piper"))
        self.speedSpin.setToolTip(
            "Скорость чтения" +
            (" (голоса Microsoft)" if engine == "edge" else
             " (Piper: длина фонем)" if engine == "piper" else
             " — движок Silero читает в естественном темпе"))
        # галочка нужна, только если хотя бы один голос роли с дефектом
        self.chkFix.setVisible(v1[5] or v2[5])

    def on_voice_changed(self, _=None):
        vd = self.comboD.currentData()
        vs = self.comboS.currentData()
        if vd and vd != self.voice_d:
            self.voice_d = vd
            self.settings.setValue("voice_d", vd)
        if vs and vs != self.voice_s:
            self.voice_s = vs
            self.settings.setValue("voice_s", vs)
        self.apply_voice_ui()
        self.update_audio_status()
        self.check_audio_stale()
        v1 = voice_by_key(self.voice_d)
        v2 = voice_by_key(self.voice_s)
        if v1[3] != v2[3]:
            self.status_show("⚠ Голоса ролей из разных движков (%s и %s) — "
                             "выберите оба из одного движка, иначе синтез "
                             "недоступен." % (ENGINE_TAG[v1[3]], ENGINE_TAG[v2[3]]))
        else:
            self.status_show("Озвучка: священник — %s, хор — %s" % (v1[1], v2[1]))

    def on_fix_toggled(self, on):
        if self.fix_ii == bool(on):
            return
        self.fix_ii = bool(on)
        self.settings.setValue("fix_ii", self.fix_ii)
        self.check_audio_stale()

    def on_seek(self, v):
        if self.player and self.player.duration():
            self.player.setPosition(int(v * self.player.duration() / 1000))

    # ── рендер текста ───────────────────────────────────────────────────
    def current_part(self):
        svc = self.services[self.svc_key]
        return None if self.sel == -1 else svc.parts[self.sel]

    def render(self):
        self.karaoke_line = -1
        svc = self.services[self.svc_key]
        part = self.current_part()
        if part:
            self.partLabel.setText("Часть %02d · строки книги %d–%d"
                                   % (part.num, part.lo, part.hi))
        else:
            self.partLabel.setText("Полное последование · %d частей" % len(svc.parts))

        if self.view == "tts":
            self.render_tts(svc, part)
        else:
            self.render_cs(svc, part)
        self.update_audio_status()

    def render_tts(self, svc, part):
        if part:
            lines = [(r, resolve_tokens(t, self.name, self.gender))
                     for r, t in part.lines]
            header = "ЧАСТЬ %02d · %s" % (part.num, part.title)
        else:
            lines = []
            for p in svc.parts:
                for r, t in p.lines:
                    lines.append((r, resolve_tokens(t, self.name, self.gender)))
            header = svc.name
        self.view_lines = lines
        self.track = KaraokeTrack(
            [(r, tts_clean(t)) for r, t in lines], self.speed)
        self.render_html(header, lines, highlight=-1)

    def render_cs(self, svc, part):
        if part:
            lo = max(1, part.lo)
            hi = min(len(svc.cs_lines), part.hi)
            chunk = svc.cs_lines[lo - 1:hi]
        else:
            chunk = svc.cs_lines
        resolved = [resolve_tokens(ln, self.name, self.gender) for ln in chunk]
        self.view_lines = []
        self.track = None
        header = "Церковнославянский текстъ" + (
            " · часть %02d" % part.num if part else "")
        self.render_html_cs(header, resolved)

    def render_html(self, header, lines, highlight):
        parts_html = ["<p id='top' style='color:#e6c35c; font-size:16px'>%s</p>"
                      % html_escape(header)]
        for i, (role, text) in enumerate(lines):
            label = ROLE_NAME.get(role, role)
            col = SPEAKER_STYLE.get(role, "#b9b2a0")
            hl_open = ("<span style='background-color:#4a3c14; "
                       "border-radius:4px'>") if i == highlight else ""
            hl_close = "</span>" if i == highlight else ""
            parts_html.append(
                "<p id='L%d' style='margin:6px 0; line-height:150%%'>"
                "<span style='color:%s; font-size:11px; font-weight:600'>%s · </span>"
                "%s%s%s</p>" % (i, col, html_escape(label),
                                hl_open, html_escape(text), hl_close))
        self.browser.setHtml("".join(parts_html))
        if highlight >= 0:
            self.browser.scrollToAnchor("L%d" % highlight)

    def render_html_cs(self, header, lines):
        parts_html = ["<p id='top' style='color:#e6c35c; font-size:16px'>%s</p>"
                      "<p style='color:#8f8875; font-size:11px'>"
                      "Ссылки (псалмы, евангелия, молитвы) — золотые, нажмите, "
                      "чтобы открыть текст. Женские варианты, которые даёт сама "
                      "книга, сохранены в скобках: «(и҆ли …)».</p>" % html_escape(header)]
        for ln in lines:
            if not ln.strip():
                continue
            parts_html.append(
                "<p style='margin:7px 0; line-height:150%%'>%s</p>" % linkify_cs(ln))
        self.browser.setHtml("".join(parts_html))

    # ── ссылки ──────────────────────────────────────────────────────────
    def on_anchor(self, url: QUrl):
        ref = url.toString()
        kind, _, key = ref.partition(":")
        if kind == "psalm":
            title, body = "Псалом %s" % key, self.references.get("ПСАЛОМ %s" % key, "")
        elif kind == "gospel":
            cands = [v for k, v in self.references.items()
                     if k.startswith("ЕВАНГЕЛИЕ ОТ " + key)]
            title, body = "Евангелие от %s" % key.title(), "\n\n· · ·\n\n".join(cands[:3])
        elif kind == "prayer":
            title, body = key.replace("МОЛИТВА: ", ""), self.references.get(key, "")
        else:
            QDesktopServices.openUrl(url)
            return
        if not body:
            self.status_show("Текст «%s» не найден в references.txt" % key)
            return
        ReferenceDialog(title, body, self).exec()

    # ── аудио ──────────────────────────────────────────────────────────
    def audio_file(self):
        svc = self.services[self.svc_key]
        part = self.current_part()
        engine = voice_by_key(self.voice_d)[3]
        return os.path.join(AUDIO_DIR, svc.dir_tag,
                            part_filename(part, svc, ENGINE_EXT[engine]))

    def update_audio_status(self):
        path = self.audio_file()
        self.audio_path = path if os.path.isfile(path) else None
        if self.audio_path:
            self.btnPlay.setText("Слушать")
            self.status_show("Аудио: %s" % os.path.basename(self.audio_path))
        else:
            self.btnPlay.setText("Слушать (нужно синтезировать)")
            self.status_show("Аудио ещё не создано. Нажмите «Синтезировать часть».")

    def check_audio_stale(self):
        svc = self.services[self.svc_key]
        path = self.audio_file()
        if not os.path.isfile(path):
            return
        cache_p = os.path.join(os.path.dirname(path), ".cache.json")
        try:
            with open(cache_p, encoding="utf-8") as fh:
                cache = json.load(fh)
        except Exception:
            return
        part = self.current_part()
        if part is None:
            return
        fm = self.fix_map()
        vd, vs = self.sig_pair()
        chunks = build_chunks(part, self.name, self.gender, fix_by_role=fm,
                              stress_marks=voice_by_key(self.voice_d)[3] == "edge")
        sig = part_signature(chunks, self.name, self.gender,
                             self.speed, vd, vs)
        if cache.get(os.path.basename(path)) != sig:
            self.status_show("Имя, род, скорость или голоса изменились — "
                             "пересинтезируйте, чтобы аудио им совпадало.")

    # проигрывание
    def on_play(self):
        if self.player is None:
            QMessageBox.warning(self, "Плеер", "QtMultimedia недоступен.")
            return
        state = self.player.playbackState()
        # идёт воспроизведение → пауза (раньше кнопка ошибочно
        # перезапускала файл с начала — "Пауза не работала")
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            return
        # на паузе → продолжаем с того же места
        if state == QMediaPlayer.PlaybackState.PausedState:
            self.player.play()
            if self.view == "tts":
                self.karaoke_timer.start()
            return
        if not self.audio_path:
            self.on_gen_part()
            return
        self.player.setSource(QUrl.fromLocalFile(self.audio_path))
        self.player.play()
        if self.view == "tts":
            self.karaoke_timer.start()

    def stop_playback(self):
        if self.player:
            self.player.stop()
        self.karaoke_timer.stop()
        self.karaoke_line = -1

    def on_stop(self):
        self.stop_playback()

    def on_position(self, pos):
        if self.player and self.player.duration():
            self.seek.blockSignals(True)
            self.seek.setValue(int(pos * 1000 / self.player.duration()))
            self.seek.blockSignals(False)
        self.timeLabel.setText("%s / %s" % (fmt_ms(pos), fmt_ms(self.player.duration() if self.player else 0)))

    def on_duration(self, dur):
        self.timeLabel.setText("00:00 / %s" % fmt_ms(dur))

    def on_play_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btnPlay.setText("Пауза")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.btnPlay.setText("Продолжить")
        else:
            self.btnPlay.setText("Слушать")
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self.karaoke_timer.stop()

    # караоке
    def on_karaoke_tick(self):
        if not (self.player and self.track):
            return
        state = self.player.playbackState()
        if state != QMediaPlayer.PlaybackState.PlayingState:
            return
        pos = self.player.position()
        dur = self.player.duration()
        idx = self.track.line_at(pos, dur)
        if idx != self.karaoke_line and 0 <= idx < len(self.view_lines):
            self.karaoke_line = idx
            part = self.current_part()
            if part:
                header = "ЧАСТЬ %02d · %s" % (part.num, part.title)
            else:
                header = self.services[self.svc_key].name
            self.render_html(header, self.view_lines, highlight=idx)

    # ── синтез ──────────────────────────────────────────────────────────
    def start_synth(self, indexes):
        if self.worker and self.worker.isRunning():
            self.status_show("Синтез уже идёт…")
            return
        svc = self.services[self.svc_key]
        out_dir = os.path.join(AUDIO_DIR, svc.dir_tag)
        v1 = voice_by_key(self.voice_d)
        v2 = voice_by_key(self.voice_s)
        if v1[3] != v2[3]:
            QMessageBox.warning(self, "Разные движки",
                "Священник и хор назначены голосам разных движков\n"
                "(%s и %s) — склеить аудио невозможно.\n\n"
                "Выберите оба голоса из одного движка."
                % (ENGINE_TAG[v1[3]], ENGINE_TAG[v2[3]]))
            return
        fm = self.fix_map()
        self.worker = SynthWorker(svc, indexes, self.name, self.gender,
                                  self.speed, out_dir,
                                  self.voice_d, self.voice_s,
                                  fm["Д"], fm["С"])
        self.worker.sig_progress.connect(self.on_synth_progress)
        self.worker.sig_part.connect(self.on_synth_part)
        self.worker.sig_error.connect(self.on_synth_error)
        self.worker.sig_finished.connect(self.on_synth_done)
        self.btnCancel.setVisible(True)
        self.btnGen.setEnabled(False)
        self.btnGenAll.setEnabled(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(1)
        self.worker.start()
        self.status_show("Синтез запущен: %s (священник: %s, хор: %s, "
                         "скорость %.2f)" % (svc.name, v1[1], v2[1], self.speed))

    def on_gen_part(self):
        if self.sel == -1:
            self.on_gen_all()
            return
        self.start_synth([self.sel])

    def on_gen_all(self):
        self.start_synth(None)

    def on_cancel(self):
        if self.worker:
            self.worker.stop()
            self.status_show("Остановка после текущей части…")

    def on_synth_progress(self, done, total, label):
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        self.status_show(label)

    def on_synth_part(self, idx, path):
        if idx == self.sel or (self.sel == -1 and idx == -1):
            self.update_audio_status()

    def on_synth_error(self, msg):
        """Окно ошибки с КОПИРУЕМЫМ текстом (QMessageBox не копировался)
        и дублем в error_log.txt — теперь ошибку можно переслать целиком."""
        logp = log_error(msg)
        note = ("Полный текст также дописан в файл:\n%s\n\n"
                "Пришлите его целиком — по трассировке видно, на каком шаге\n"
                "всё упало, и я скажу точное лечение." % logp) if logp else ""
        ErrorDialog("Ошибка синтеза",
                    "Не удалось завершить синтез.\n\n%s" % msg, note,
                    self).exec()

    def on_synth_done(self, cancelled):
        self.btnCancel.setVisible(False)
        self.btnGen.setEnabled(True)
        self.btnGenAll.setEnabled(True)
        self.progress.setValue(self.progress.maximum())
        self.update_audio_status()
        if not cancelled:
            self.status_show("Синтез завершён.")
        else:
            self.status_show("Синтез остановлен.")

    def status_show(self, msg):
        self.statusMsg.setText(msg)

    def closeEvent(self, ev):
        self.stop_playback()
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        super().closeEvent(ev)


class QDoubleSuffixProxy(QDoubleSpinBox):
    def textFromValue(self, v):
        return "%.2f" % v


def fmt_ms(ms):
    ms = max(0, int(ms))
    m, s = divmod(ms // 1000, 60)
    return "%02d:%02d" % (m, s)


def log_error(text: str) -> Optional[str]:
    """Дописывает ошибку в error_log.txt рядом с плеером.
    Возвращает путь файла или None (тогда текст только в окне)."""
    try:
        p = os.path.join(APP_DIR, "error_log.txt")
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("\n[%s]\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
        return p
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ═════════════════════════════════════════════════════════════════════════
def main():
    if not os.path.isdir(TEXTS_DIR):
        QMessageBox.critical(None, APP_TITLE,
                             "Не найдена папка texts/.\n"
                             "Положите trebnik_player.pyw в папку репозитория\n"
                             "(рядом с папкой texts).")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyleSheet(QSS)
    font = QFont("Georgia")
    font.setStyleHint(QFont.StyleHint.Serif)
    app.setFont(font)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    # .pyw в Windows запускается без консоли — ошибки пишем в лог рядом
    try:
        main()
    except Exception:
        try:
            with open(os.path.join(APP_DIR, "error_log.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write(traceback.format_exc())
        finally:
            raise
