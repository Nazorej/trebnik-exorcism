# -*- coding: utf-8 -*-
"""Извлечение текста из EPUB Требника и поиск последования от колдунов/демонов."""
import os
import re
from html.parser import HTMLParser

SRC_DIR = "/home/z/my-project/work/trebnik/extracted"
OUT_DIR = "/home/z/my-project/work/trebnik/text"
os.makedirs(OUT_DIR, exist_ok=True)


class TextExtractor(HTMLParser):
    """Простой извлекатель текста из XHTML с обработкой блоков."""

    def __init__(self):
        super().__init__()
        self.parts = []
        self.block_tags = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                           "li", "br", "tr", "table", "blockquote", "section"}
        self.skip_tags = {"style", "script", "head"}
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self._skip_depth += 1
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        self.parts.append(data)

    def get_text(self):
        raw = "".join(self.parts)
        lines = re.split(r"\n+", raw)
        cleaned = [re.sub(r"\s+", " ", ln).strip() for ln in lines]
        return "\n".join(ln for ln in cleaned if ln)


def extract_file(path):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    p = TextExtractor()
    p.feed(content)
    return p.get_text()


def main():
    files = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".xhtml"))
    all_texts = {}
    for fn in files:
        text = extract_file(os.path.join(SRC_DIR, fn))
        all_texts[fn] = text

    combined = []
    for fn in files:
        combined.append(f"===== FILE: {fn} =====")
        combined.append(all_texts[fn])
    with open(os.path.join(OUT_DIR, "all_text.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(combined))

    keywords = ["колдун", "волхв", "демон", "бесов", "обаятел", "чарод",
                "волшеб", "наветы", "нечист"]
    print("=== НАЙДЕННЫЕ ФАЙЛЫ ПО КЛЮЧЕВЫМ СЛОВАМ ===")
    for fn in files:
        text = all_texts[fn].lower()
        hits = {kw: text.count(kw) for kw in keywords if kw in text}
        if hits:
            first_line = all_texts[fn].split("\n")[0][:100] if all_texts[fn] else ""
            print(f"{fn}: {hits} | {first_line}")

    print("\n=== ФАЙЛЫ СО СЛОВОМ 'ПОСЛЕДОВАНИЕ'/'ЧИН' в первых строках ===")
    for fn in files:
        lines = all_texts[fn].split("\n")
        head = " ".join(lines[:5]).lower()
        if any(w in head for w in ["последование", "чин ", "чина", "молитва"]):
            print(f"{fn}: {' / '.join(l[:80] for l in lines[:3] if l)}")


if __name__ == "__main__":
    main()
