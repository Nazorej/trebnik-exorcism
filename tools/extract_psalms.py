# -*- coding: utf-8 -*-
"""Извлечение нужных псалмов из HTML Псалтири (foma.ru). v2

Заголовок псалма: <p><strong>...текст..., N</strong></p> (номер в конце).
Тело: параграфы, начинающиеся с цифры (номер стиха). Между псалмами: <em>Слава:</em>,
молитвы, заголовки кафизм <h2>.
"""
import re
import html as h

SRC = "/home/z/my-project/work/trebnik/psaltir_foma.html"
OUT = "/home/z/my-project/work/trebnik/psalms_raw.txt"

NEEDED = {3, 10, 12, 21, 22, 26, 30, 34, 50, 53, 67, 69, 90, 117, 142}

# инципиты по Требнику (для проверки)
INCIPITS = {
    3: "Господи что ся умножиша стужающии",
    10: "На Господа уповах како речете",
    12: "Доколе Господи забудеши мя",
    21: "Боже Боже мой вонми ми вскую оставил",
    22: "Господь пасет мя и ничтоже мя лишит",
    26: "Господь просвещение мое и Спаситель",
    30: "На Тя Господи уповах да не постыжуся",
    34: "Суди Господи обидящыя мя побори",
    50: "Помилуй мя Боже по велицей милости",
    53: "Боже во имя Твое спаси мя",
    67: "Да воскреснет Бог и расточатся",
    69: "Боже в помощь мою вонми Господи",
    90: "Живый в помощи Вышняго",
    117: "Исповедайтеся Господеви яко благ",
    142: "Господи услыши молитву мою внуши",
}


def main():
    html = open(SRC, encoding="utf-8", errors="ignore").read()
    text = h.unescape(html)

    # все элементы: h2 (кафизмы), p (абзацы)
    items = re.findall(r"<h2[^>]*>(.*?)</h2>|<p[^>]*>(.*?)</p>", text, re.S)
    seq = []  # (kind, text)
    for h2, p in items:
        raw = h2 if h2 else p
        # параграф целиком из strong?
        is_strong = re.fullmatch(r"\s*<strong>(.*?)</strong>\s*", p or "", re.S)
        clean = re.sub(r"<[^>]+>", " ", raw)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            continue
        if h2:
            seq.append(("h2", clean))
        elif is_strong:
            seq.append(("strong", clean))
        else:
            seq.append(("p", clean))

    psalms = {}
    cur = None
    for kind, t in seq:
        if kind == "strong":
            m = re.match(r"^(.*?)[,\s]?(\d{1,3})$", t)
            if m and int(m.group(2)) <= 151:
                cur = int(m.group(2))
                psalms[cur] = {"title": t, "verses": []}
                continue
        if kind == "h2":
            cur = None  # кафизма обрывает псалом
            continue
        # обычный абзац
        if cur is not None:
            if re.match(r"^\d[\d.,]*\s", t) or re.match(r"^\d+$", t[:3]):
                # убираем ведущие номера стихов
                v = re.sub(r"^\d[\d.,]*\s+", "", t)
                psalms[cur]["verses"].append(v)
            else:
                # не стих (молитва/Слава) — псалом закончен
                cur = None

    print(f"Извлечено псалмов: {len(psalms)}; найдены номера: {sorted(psalms)}")
    out = []
    ok = 0
    for n in sorted(NEEDED):
        d = psalms.get(n)
        if not d or not d["verses"]:
            print(f"  [!] Псалом {n}: НЕ НАЙДЕН")
            continue
        txt = " ".join(d["verses"])
        inc = INCIPITS[n].lower()
        norm = re.sub(r"[^а-яё ]", "", txt.lower()).replace("  ", " ")
        check = norm.startswith(inc.replace("  ", " "))
        mark = "OK " if check else "???"
        if check:
            ok += 1
        print(f"  [{mark}] Пс {n:3d} [{len(txt):5d} зн.] {txt[:65]}")
        out.append(f"=== ПСАЛОМ {n} ===")
        out.append(f"[надписание] {d['title']}")
        out.append(txt)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n\n".join(out))
    print(f"\nИнципиты подтверждены: {ok}/{len(NEEDED)}")


if __name__ == "__main__":
    main()
