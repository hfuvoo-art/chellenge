# Eval чисел с единицами (docs/07 «check.py» п.2 + У9): без него «+3 п.п.» сойдёт за «3 %», а «7 $ за 15 ГБ» — за «15 $ за 3 ГБ».
from tools.check import check_numbers, check_quote
from tools.numbers import num_match, parse_numbers


def _levels(fact: str, quote: str, as_of: str | None = "2024-05-01") -> set[str]:
    c = {"id": "C-001", "type": "fact", "text": fact, "quote": quote}
    return {f.level for f in check_numbers(c, quote, as_of)}


def _vals(text: str):
    return [(n.value, n.unit) for n in parse_numbers(text)]


# ---- 8 случаев docs/07, дословно ----

def test_percent_vs_fraction_ok():
    assert _levels("доля 42%", "доля составила 0.42") == {"OK"}


def test_thousands_space_ok():
    assert _levels("1 302", "итого 1302") == {"OK"}


def test_decimal_comma_ok():
    assert _levels("44,5", "значение 44.5") == {"OK"}


def test_million_suffix_ok():
    assert _levels("15 млн", "всего 15 000 000") == {"OK"}


def test_wrong_units_fail():
    assert "FAIL" in _levels("7 $ за 15 ГБ", "15 $ за 3 ГБ на 7 дней")


def test_quarter_roman_ok():
    assert _levels("3 кв. 2024", "III квартал 2024") == {"OK"}


def test_number_missing_in_quote_fail():
    assert "FAIL" in _levels("рост 15%", "рост значительный")


def test_negation_in_fact_fail():
    f = check_quote({"quote": "выручка не выросла на 12%"}, "Выручка выросла на 12%.")
    assert f.level == "FAIL" and f.check == 1


# ---- Фокус ревью п.5 ----

def test_pp_vs_percent_fail():
    assert "FAIL" in _levels("+3 п.п.", "выросла на 3 %")
    assert "FAIL" in _levels("на 3 %", "выросла на +3 п.п.")
    assert _levels("+3 п.п.", "выросла на 3 п.п.") == {"OK"}


def test_unicode_minus():
    assert _vals("−3,4 %") == _vals("-3,4%") == [(-3.4, "%")]
    assert _levels("−3,4 %", "изменение -3,4%") == {"OK"}


def test_range_both_ends():
    assert _vals("15–20 %") == [(15, "%"), (20, "%")]
    assert _levels("15–20 %", "от 15 до 20 %") == {"OK"}
    assert "FAIL" in _levels("15–20 %", "15–25 %")


def test_thousands_suffix():
    n = parse_numbers("1,5 тыс.")[0]
    assert n.value == 1500 and n.unit is None
    assert _levels("1,5 тыс.", "в базе 1500") == {"OK"}
    assert "FAIL" in _levels("1,5 тыс.", "в базе 150")


def test_times_unit():
    assert _vals("в 2 раза") == [(2, "раз")]
    assert _levels("в 2 раза", "вырос в 2 раза") == {"OK"}
    assert "FAIL" in _levels("в 2 раза", "вырос в 3 раза")
    assert "FAIL" in _levels("в 2 раза", "вырос на 2 %")


def test_num_match_tolerance_by_record_precision():
    f = parse_numbers("44,5")[0]
    assert num_match(f, parse_numbers("44.5")) and not num_match(f, parse_numbers("44.7"))
