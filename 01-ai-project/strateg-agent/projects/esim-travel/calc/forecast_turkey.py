"""Прогноз (forecast) выручки пакета eSIM для Турции за год. Сценарии — по допущениям (hypothesis), не факт.
Запуск: python projects/esim-travel/calc/forecast_turkey.py"""
from emiss import load, year
tot, by = load()
TRIPS = year(next(v for k, v in by.items() if k.startswith("ТУРЦИЯ")), 2025)  # поездок в Турцию за 2025 год, S-001 (calc/emiss_totals.py; строка 139, пример [C-134])
PRICE = 518      # ₽ за пакет 5 ГБ на 30 дней — цена МТС [C-115]; своя цена — допущение «как у МТС»
SHARE = {"низкий": 0.005, "базовый": 0.01, "высокий": 0.03}   # hypothesis: доля поездок с покупкой нашей eSIM
REFUND = {"низкий": 0.10, "базовый": 0.05, "высокий": 0.03}   # hypothesis: доля возвратов «не заработало»
print(f"Поездок в Турцию за 2025 год: {TRIPS:,} поездок".replace(",", " "))
for s in SHARE:
    n = TRIPS * SHARE[s]; gross = n * PRICE; net = gross * (1 - REFUND[s])
    print(f"{s}: пакетов {n:,.0f}; выручка {gross/1e6:.1f} млн ₽ в год; после возвратов {net/1e6:.1f} млн ₽ в год".replace(",", " "))
# Чувствительность базового: ±20 % доли меняет выручку на ±20 %; цена закупки трафика неизвестна — маржу не считаем.
n = TRIPS * SHARE["базовый"]
print(f"RESULT={n * PRICE * (1 - REFUND['базовый']) / 1e6:.1f} млн ₽ в год")
