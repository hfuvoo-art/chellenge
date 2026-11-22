"""estimate: ориентир на конец 3-го года и предельная сумма вложений, окупаемая до конца 3-го года (условный расчёт).
Допущения — hypothesis [C-049], [C-041], [C-042], [C-037], [C-038], [C-039]; ставка 500 руб. [C-017]. Запуск: python tools/analyze.py calc C-050"""
RATE = 500
BASE_START, NOCH_GROWTH = 6_500, 1_500          # [C-005], [C-009], [C-049]
EXTRA = [600, 1_000, 1_500]                     # группы сверх «без изменений» по годам [C-049]
NEW_NUM, SUIT, EVENT, AVOID, MONTHS = 0.3, 0.5, 0.2, 0.03, 0.3
cum_extra, carry_numbers, total = 0, 0.0, 0.0
for y, e in enumerate(EXTRA, 1):
    noch = BASE_START + NOCH_GROWTH * y
    conn_end = noch + cum_extra + e
    avg_groups = (noch - NOCH_GROWTH + cum_extra + conn_end) / 2
    months_signal = 7.5 if y == 1 else 12          # 1-й год: половина 2-го кв. + 3-й–4-й кв. [C-048]
    m_new = carry_numbers * 12 + e * NEW_NUM * (3 if y == 1 else 6)
    m_ret = avg_groups * SUIT * EVENT * months_signal * AVOID * MONTHS
    cost = avg_groups * SUIT * EVENT * months_signal * 2 * 1.0 / 1e6
    gain = (m_new + m_ret) * RATE / 1e6 - cost
    total += gain
    carry_numbers += e * NEW_NUM
    cum_extra += e
    print(f"Год {y}: подключённых групп на конец {conn_end:,.0f}; вклад {gain:.2f} млн руб.; накопленно {total:.2f} млн руб.".replace(",", " "))
share = conn_end / 100_000
print(f"Ориентир конца 3-го года: {conn_end:,.0f} групп = {share:.1%} доступных 100 тыс. домохозяйств [C-002]".replace(",", " "))
print(f"При 0,1 нового номера на группу вклад за 3 года ≈ {total*0.1/0.3:.1f} млн руб. (грубо, пропорционально)")
print(f"RESULT={total:.1f} млн ₽")
