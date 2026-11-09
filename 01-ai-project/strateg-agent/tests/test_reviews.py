# Тесты отзывов Google Play и очистки ПДн: без них в materials/ попадут имена, телефоны, почты, а окна сравнения посчитаются неверно.
import csv
import io
from datetime import datetime

import pytest

from tools import ingest, reviews
from tools.common import project_path, read_text, read_yaml


def _raw(i, text, day=1, score=3, version="1.0"):
    return {"reviewId": f"id-{i}", "userName": f"Автор {i}", "userImage": "http://x/y.png", "content": text, "score": score,
            "thumbsUpCount": 0, "reviewCreatedVersion": version, "at": datetime(2026, 9, day, 12, 0), "replyContent": None,
            "repliedAt": None, "appVersion": version}


class FakeGplay:
    """Подмена reviews(): отдаёт страницы по очереди, как продолжение по токену."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def __call__(self, app_id, **kw):
        self.calls.append((app_id, kw))
        if not self.pages:
            return [], None
        page = self.pages.pop(0)
        return page, ("tok" if self.pages else None)


def _csv_rows(text):
    return list(csv.reader(io.StringIO(text, newline="")))


def test_gplay_paginates_until_since_drops_authors(monkeypatch, tmp_path):
    fake = FakeGplay([
        [_raw(1, "новее", day=20), _raw(2, "ок", day=10)],
        [_raw(3, "у границы", day=2), _raw(4, "слишком старый", day=1)],
        [_raw(5, "не должен запрашиваться", day=1)],
    ])
    monkeypatch.setattr(reviews, "_gplay_reviews", fake)
    got = reviews.fetch_gplay("a.b.c", "2026-09-02")
    assert [r.text for r in got] == ["новее", "ок", "у границы"]
    assert len(fake.calls) == 2  # на странице со старым отзывом остановились
    assert fake.calls[0][1]["lang"] == "ru" and fake.calls[0][1]["country"] == "ru"
    assert fake.calls[1][1]["continuation_token"] == "tok"
    f = tmp_path / "r.csv"
    reviews.write_reviews_csv(got, f)
    text = f.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "date,rating,version,text"
    assert "Автор" not in text and "id-" not in text and "x/y.png" not in text
    assert _csv_rows(text)[1][:2] == ["2026-09-20", "3"]


def test_gplay_until_and_max_n(monkeypatch):
    monkeypatch.setattr(reviews, "_gplay_reviews", FakeGplay([[_raw(i, f"t{i}", day=30 - i) for i in range(10)]]))
    got = reviews.fetch_gplay("a.b.c", "2026-09-01", until="2026-09-25")
    assert all(r.date <= "2026-09-25" for r in got) and len(got) == 5
    monkeypatch.setattr(reviews, "_gplay_reviews", FakeGplay([[_raw(i, f"t{i}", day=30 - i) for i in range(10)]]))
    assert len(reviews.fetch_gplay("a.b.c", "2026-09-01", max_n=4)) == 4


def test_reviews_dedup_by_text_date_hash(monkeypatch):
    fake = FakeGplay([[_raw(1, "Одинаково", day=5), _raw(2, "Одинаково", day=5), _raw(3, "Одинаково", day=6)]])
    monkeypatch.setattr(reviews, "_gplay_reviews", fake)
    got = reviews.fetch_gplay("a.b.c", "2026-09-01")
    assert [(r.date, r.text) for r in got] == [("2026-09-05", "Одинаково"), ("2026-09-06", "Одинаково")]


def test_reviews_md_has_window_counts():
    rs = [reviews.Review("2026-09-03", 1, "1.0", "плохо"), reviews.Review("2026-09-04", 2, "", "так себе"),
          reviews.Review("2026-10-01", 5, "1.1", "отлично")]
    md, chars = reviews.render_md(rs)
    assert "2026-09: 2 отзыва, средняя оценка 1,50" in md
    assert "2026-10: 1 отзыв, средняя оценка 5,00" in md
    assert "<!-- ¶2 -->\n2026-09-03 · оценка 1 · v1.0 · плохо" in md
    assert reviews.window_counts(rs) == {"2026-09": (2, 1.5), "2026-10": (1, 5.0)}
    assert chars > 0


def test_mask_phone_and_email_but_not_plain_numbers():
    t, n = reviews.mask_pii("Звоните +7 900 000-00-00 или 8 (900) 111-22-33, пишите a.b@ex.test; цена 1 234 567 руб, 2026-09-01")
    assert "[телефон]" in t and "[email]" in t and n == 3
    assert "900" not in t and "ex.test" not in t and "1 234 567" in t and "2026-09-01" in t


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return path


def test_ingest_user_csv_drops_pii_columns_and_masks(tmp_project, tmp_path):
    f = _write_csv(tmp_path / "mine.csv", [
        ["Автор", "Телефон", "date", "rating", "version", "text", "e-mail"],
        ["Иван Тестов", "+7 900 000-00-00", "2026-09-01", "5", "1.0", "Звоните +7 900 111-22-33", "i@ex.test"],
        ["Пётр Вымышленный", "", "2026-10-02", "2", "", "Пишите p@ex.test", ""],
    ])
    sid, _ = ingest.ingest_ex(tmp_project, str(f), found_by="user")
    s = next(x for x in ingest._load_sources(tmp_project) if x["id"] == sid)
    mdir = project_path(tmp_project) / "materials"
    everything = "".join(read_text(p) for p in mdir.iterdir() if p.suffix in (".md", ".csv"))
    for bad in ("Иван", "Пётр", "900", "ex.test", "Вымышленный"):
        assert bad not in everything
    assert s["kind"] == "reviews"  # после очистки шапка ровно date,rating,version,text
    assert s["pii_removed"] == 6  # ячейки колонок: автор 2 + телефон 1 + e-mail 1; маски в тексте: телефон 1 + почта 1
    assert (mdir / f"{sid}.csv").read_text(encoding="utf-8").splitlines()[0] == "date,rating,version,text"


def test_ingest_report_mentions_pii_removed(tmp_project, tmp_path, capsys):
    f = _write_csv(tmp_path / "mine.csv", [["author", "date", "rating", "version", "text"],
                                           ["Анна", "2026-09-01", "4", "", "норм"]])
    from tools.common import projects_dir
    (projects_dir() / "CURRENT").write_text(tmp_project, encoding="utf-8")
    assert ingest.main([str(f), "--found-by", "user"]) == 0
    assert "убрано ПДн: 1" in capsys.readouterr().out


def test_reviews_header_recognised_as_reviews_with_windows(tmp_project, tmp_path):
    f = _write_csv(tmp_path / "rev.csv", [["date", "rating", "version", "text"],
                                          ["2026-09-03", "1", "1.0", "плохо"], ["2026-10-04", "5", "", "супер"],
                                          ["2026-10-05", "4", "", "хорошо"]])
    sid, _ = ingest.ingest_ex(tmp_project, str(f), found_by="user")
    s = next(x for x in ingest._load_sources(tmp_project) if x["id"] == sid)
    assert s["kind"] == "reviews" and s["pii_removed"] == 0
    md = read_text(project_path(tmp_project) / "materials" / f"{sid}.md")
    assert "2026-10: 2 отзыва, средняя оценка 4,50" in md
    assert "супер" in ingest.section(tmp_project, sid, "¶3")
    assert "2026-09-03" in ingest.section(tmp_project, sid, "¶2")


def test_ingest_gplay_end_to_end_without_disk_pii(monkeypatch, tmp_project, tmp_path):
    monkeypatch.setattr(reviews, "_gplay_reviews", FakeGplay([[_raw(1, "Мой телефон +7 900 000-00-00", day=5), _raw(2, "ок", day=6)]]))
    sid, _ = ingest.ingest_reviews(tmp_project, "gplay:a.b.c", since="2026-09-01", found_by="search:отзывы")
    mdir = project_path(tmp_project) / "materials"
    everything = "".join(read_text(p) for p in mdir.iterdir() if p.suffix in (".md", ".csv"))
    assert "900" not in everything and "Автор" not in everything and "id-1" not in everything
    s = next(x for x in ingest._load_sources(tmp_project) if x["id"] == sid)
    assert s["kind"] == "reviews" and s["pii_removed"] == 1 and "a.b.c" in s["url"]


def test_cli_requires_target_or_reviews(tmp_project, capsys):
    with pytest.raises(SystemExit) as e:
        ingest.main(["--found-by", "user"])
    assert e.value.code == 1
    assert "--reviews" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        ingest.main(["--reviews", "gplay:a.b.c", "--found-by", "user"])  # нет --since
