"""Общий разбор S-001 (materials/S-001.md, ЕМИСС 38480): поездки граждан РФ за рубеж по странам и кварталам.
Строки «Итого по целям визита»; итоговой строки по всем странам в таблице нет, сумма — по 160 странам."""
import re, collections
from pathlib import Path
P = Path(__file__).resolve().parents[1] / "materials" / "S-001.md"
R = re.compile(r"^Данные!([A-Z]+)(\d+) \[col1=([^;]*); col2=Итого по целям визита; Год=(\d+); Квартал=(\d)\] = ([\d  ]+)$")

def load():
    tot = collections.Counter(); by = collections.defaultdict(collections.Counter)
    for ln in P.read_text(encoding="utf-8").splitlines():
        m = R.match(ln.strip())
        if not m:
            continue
        _, _, c, y, q, v = m.groups()
        v = int(re.sub(r"\D", "", v)); key = (int(y), int(q))
        tot[key] += v; by[c.strip()][key] += v
    return tot, by

def s9(cnt, y):
    return sum(cnt[(y, q)] for q in (1, 2, 3))

def year(cnt, y):
    return sum(cnt[(y, q)] for q in (1, 2, 3, 4))
