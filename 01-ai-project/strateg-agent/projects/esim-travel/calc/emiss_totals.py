"""Сводка по S-001 для шага 3: python projects/esim-travel/calc/emiss_totals.py"""
from emiss import load, s9, year
tot, by = load()
print("Стран:", len(by))
for y in (2023, 2024, 2025):
    print(f"{y}: год = {year(tot, y):,} поездок; I–III кв. = {s9(tot, y):,}".replace(",", " "))
print(f"2026: I–III кв. = {s9(tot, 2026):,}".replace(",", " "))
for y in (2025, 2026):
    print(f"Рост I–III кв. {y} к {y-1}: {100*(s9(tot,y)/s9(tot,y-1)-1):.1f} %")
t26 = s9(tot, 2026)
for c in sorted(by, key=lambda c: -s9(by[c], 2026))[:12]:
    a, b = s9(by[c], 2026), s9(by[c], 2025)
    print(f"  {c[:40]}: {a:,}; {100*a/t26:.1f} %; {100*(a/b-1):+.1f} %".replace(",", " "))
