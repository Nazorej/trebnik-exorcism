# -*- coding: utf-8 -*-
"""Извлечение двух последований и сбор уникальных слов с титлами."""
import os
import re
import json
from html.parser import HTMLParser

SRC_DIR = "/home/z/my-project/work/trebnik/extracted"
OUT_DIR = "/home/z/my-project/work/trebnik"
# Настоящие титлы-сокращения (требуют расшифровки по словарю)
TITLO_MARKS = set("\u0483\u0487\uA67C\u2DE0\u2DE1\u2DE2\u2DE3\u2DE4\u2DE5\u2DE6\u2DE7\u2DE8\u2DE9\u2DEA\u2DEB\u2DEC\u2DED\u2DEE\u2DEF\u033E\uA69C\uA69D")
# Знаки, которые просто удаляются (придыхание, ударения, диерезис)
STRIP = r"[\u0486\u0485\u0484\u0301\u0300\u0308\u033E]"


class TE(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head"):
            self.skip += 1
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "br", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head") and self.skip:
            self.skip -= 1
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "br", "li"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def extract_file(path):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    p = TE()
    p.feed(content)
    raw = "".join(p.parts)
    lines = [re.sub(r"\s+", " ", l).strip() for l in re.split(r"\n+", raw)]
    return [l for l in lines if l]


SERVICES = {
    # Последование об избавлении от духов нечистых (демоны)
    "01_ot_demonov": [f"{i:03d}" for i in range(66, 83)],
    # Последование против чародеяний (колдуны), включая чин над домом
    "02_ot_koldunov": [f"{i:03d}" for i in range(83, 89)],
}

titlo_words = {}

for svc, ids in SERVICES.items():
    svc_lines = []
    for i in ids:
        fn = f"index_split_{i}.xhtml"
        lines = extract_file(os.path.join(SRC_DIR, fn))
        svc_lines.extend(lines)
        for ln in lines:
            # токены: буквы (вкл. комбинируемые знаки), скобки, пунктуация отдельно
            for tok in re.findall(r"[\w\u0300-\u036F\u0483-\u0489\uA640-\uA69F\u2DE0-\u2DFF\u1C80-\u1C8F]+", ln, re.UNICODE):
                if any(ch in TITLO_MARKS for ch in tok):
                    # titlo-токен: удаляем придыхание и ударения для словаря
                    key = re.sub(STRIP, "", tok)
                    titlo_words.setdefault(key, 0)
                    titlo_words[key] += 1
    with open(os.path.join(OUT_DIR, f"{svc}.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(svc_lines))
    print(f"{svc}: {len(svc_lines)} строк, {sum(len(l) for l in svc_lines)} знаков")

with open(os.path.join(OUT_DIR, "titlo_words.json"), "w", encoding="utf-8") as f:
    json.dump(dict(sorted(titlo_words.items(), key=lambda x: -x[1])), f, ensure_ascii=False, indent=1)

print(f"\nУникальных слов с титлами: {len(titlo_words)}")
print("\n=== ТОП-60 ===")
for i, (w, c) in enumerate(sorted(titlo_words.items(), key=lambda x: -x[1])):
    if i >= 60:
        break
    print(f"{c:>5}  {w}")
