"""estimate: разложение недобора активных групп базового года на «меньше групп» и «ниже доля активных».
Запуск: python tools/analyze.py calc C-047"""
PLAN_CONN, FACT_CONN = 7_500, 6_500     # подключённые группы, план и оценка [C-005]
PLAN_ACT, FACT_ACT = 5_000, 4_000       # активные группы, план и оценка [C-004]
plan_rate = PLAN_ACT / PLAN_CONN
fact_rate = FACT_ACT / FACT_CONN
at_plan_rate = FACT_CONN * plan_rate     # активных при плановой доле и фактическом числе групп
by_count = PLAN_ACT - at_plan_rate        # недобор из-за числа групп
by_rate = at_plan_rate - FACT_ACT         # недобор из-за доли активных
print(f"Доля активных: план {plan_rate:.1%}, оценка {fact_rate:.1%}")
print(f"Из-за меньшего числа групп: {by_count:.0f}; из-за меньшей доли активных: {by_rate:.0f}")
print(f"RESULT={by_count:.0f} групп")
