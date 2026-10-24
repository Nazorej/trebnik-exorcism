# -*- coding: utf-8 -*-
"""Парсер оглавления EPUB Требника: toc.ncx -> компактный список с нормализованными заголовками."""
import re
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
import normalize_slavonic as ns

TOC = "/home/z/my-project/work/trebnik/extracted/toc.ncx"
OUT = "/home/z/my-project/work/trebnik/toc_list.txt"

ACCENTS = re.compile(r"[\u0300-\u036F\u0483-\u0487\u2DE0-\u2DFF\uA66F\uA67C\uA67D\uFE2E\uFE2F\u1AB0-\u1AFF\u1DC0-\u1DFF]")


def norm_line(ln, report):
    for a, b in ns.PRE_REPLACE:
        ln = ln.replace(a, b)
    for rx, rep in ns.LINE_JUNK:
        ln = rx.sub(rep, ln)
    ln = ln.strip()
    if not ln:
        return ""
    new = ns.TOKEN_RE.sub(lambda m: ns.normalize_token(m.group(0), report), ln)
    new = ns.convert_letters(new)
    new = ns.num_words_line(new)
    new = ns.final_cleanup(new)
    new = ACCENTS.sub("", new)
    new = re.sub(r"\s+", " ", new).strip()
    return new


def main():
    with open(TOC, encoding="utf-8") as f:
        xml = f.read()
    # navPoint блоки
    blocks = re.findall(
        r'<navPoint[^>]*playOrder="(\d+)"[^>]*>(.*?)</navPoint>', xml, re.S
    )
    # вложенные navPoint: блоки могут быть вложены, re.findall с жадным .*? возьмёт внешние
    # вместо этого вытащим пары (playOrder, src, text) по порядку появления
    entries = []
    pos = 0
    pattern = re.compile(
        r'<navPoint[^>]*playOrder="(\d+)"[^>]*id="([^"]+)"[^>]*>(.*?)(?=<navPoint |</navMap>|</navPoint>)',
        re.S,
    )
    # проще: сканируем все <navLabel><text>..</text> вместе с последующим <content src>
    pair_re = re.compile(
        r'<navLabel>\s*<text>(.*?)</text>\s*</navLabel>\s*<content src="([^"]+)"', re.S
    )
    for m in pair_re.finditer(xml):
        raw = m.group(1).strip()
        src = m.group(2)
        entries.append((raw, src))

    report = []
    out = []
    for i, (raw, src) in enumerate(entries, 1):
        norm = norm_line(raw, report)
        # уровень вложенности: по отступу в src-файлах не определить, пометим все
        out.append(f"[{i:03d}] {src} | {norm}")
        out.append(f"      RAW: {raw}")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"Всего пунктов оглавления: {len(entries)}")
    print(f"Нераспознанных титлов в заголовках: {len(set(report))}")
    for t in sorted(set(report)):
        print(f"  {t}")


if __name__ == "__main__":
    main()
