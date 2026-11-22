"""forecast: прогноз планового года по пяти строкам таблицы S-001 p.3 — основной и менее благоприятный ход.
Решение: сигнал о низком остатке доли участника + ссылка на существующую передачу; пилот во 2-м кв., распространение на все подходящие группы с 3-го кв.
Все параметры — допущения (hypothesis), не факт. Запуск: python tools/analyze.py calc C-048"""
BASE_PROFIT = 279.0          # млн руб., без изменений [C-016]
RATE = 500                   # руб. за доп. оплаченный месяц номера [C-017]
NOCH = dict(conn=8_000, act=5_000, owners=1_000, activation=0.45)   # без изменений [C-009], [C-011], [C-007]; владельцы — S-001 p.3
S = {
  "основной":   dict(extra_groups=600, new_num=0.3, suitable=0.5, event=0.2, avoided=0.03, months=0.3, act_share=0.675, activation=0.52, msg_cost=1.0),
  "менее благоприятный": dict(extra_groups=0, new_num=0.1, suitable=0.3, event=0.1, avoided=0.0, months=0.1, act_share=0.64, activation=0.46, msg_cost=1.5),
}
# extra_groups — группы сверх «без изменений» к концу года, добавляются равномерно во 2-м полугодии (в среднем 3 мес. в году) [C-042], [C-045]
# avoided — снижение доли ограничений, п.п./100 [C-039]; months — доп. месяцы на предотвращённое ограничение [C-041]
out = {}
for name, p in S.items():
    conn = NOCH["conn"] + p["extra_groups"]
    m_new = p["extra_groups"] * p["new_num"] * 3                       # месяцы новых номеров из дополнительных групп
    events_per_month = (6_500 + conn) / 2 * p["suitable"] * p["event"]  # события в месяц (среднее число групп за год)
    rollout_months = 6 + 0.5 * 3                                        # 3-й–4-й кв. на всех + 2-й кв. на половине (пилот)
    m_ret = events_per_month * rollout_months * p["avoided"] * p["months"]
    cost = events_per_month * rollout_months * 2 * p["msg_cost"] / 1e6  # 2 сообщения на событие, руб.
    gain = (m_new + m_ret) * RATE / 1e6 - cost
    profit = BASE_PROFIT + gain
    act = round(conn * p["act_share"], -1)
    out[name] = profit
    print(f"{name}: прибыль {profit:.2f} млн руб. (вклад {gain:.2f}: новые номера {m_new:.0f} мес., удержание {m_ret:.0f} мес., расходы {cost:.3f}); "
          f"подключённых групп {conn}; активных {act:.0f}; владельцев {NOCH['owners']}; активация {p['activation']:.0%}")
print(f"Разрыв до 285 млн руб.: основной {285-out['основной']:.2f}, менее благоприятный {285-out['менее благоприятный']:.2f} млн руб.")
print(f"Нужно доп. оплаченных месяцев для закрытия разрыва (основной): {(285-out['основной'])*1e6/RATE:,.0f}".replace(",", " "))
print(f"RESULT={out['основной']:.1f} млн ₽")
