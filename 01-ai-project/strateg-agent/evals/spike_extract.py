# Спайк извлечения (задача 6): режет тексты на части, гоняет prompts/extract.md через lite и pro, сверяет цитаты; без него выбор EXTRACT_MODEL остаётся на глаз.
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rapidfuzz import fuzz  # noqa: E402

from tools import llm  # noqa: E402
from tools.common import ROOT, read_jsonl, setup_stdio, write_text_atomic  # noqa: E402

MAX_PART = 12_000
PARTIAL_MIN = 92
MIN_QUOTE = 25  # символов после нормализации: короче - не цитата («ГБ», «рост», «12%» совпадают с чем угодно)
PROMPT_PATH = ROOT / "prompts" / "extract.md"
TABLE_PATH = ROOT / "evals" / "spike-extract.md"
ROLES = {"lite": "extract", "pro": "pro"}
LITE_NOTE = (
    "YandexGPT Lite 5 отключается 15.11.2026, поэтому «lite» в этом замере — Alice AI LLM Flash "
    "(aliceai-llm-flash), «pro» — YandexGPT Pro 5.1 (yandexgpt-5.1). "
    "Источник: https://aistudio.yandex.ru/docs/ru/ai-studio/concepts/generation/models."
)


def split_parts(text: str, limit: int = MAX_PART) -> list[str]:
    """Части ≤limit символов по абзацам; следующая часть начинается с последнего абзаца предыдущей (перекрытие 1 абзац)."""
    paras: list[str] = []
    for p in re.split(r"\n\s*\n", text):
        p = p.strip()
        while len(p) > limit:  # абзац длиннее части: режем жёстко
            paras.append(p[:limit])
            p = p[limit:]
        if p:
            paras.append(p)
    parts: list[str] = []
    cur: list[str] = []
    size = 0
    for p in paras:
        add = len(p) + (2 if cur else 0)
        if cur and size + add > limit:
            parts.append("\n\n".join(cur))
            last = cur[-1]
            cur = [last] if len(last) + 2 + len(p) <= limit else []
            size = len(last) if cur else 0
            add = len(p) + (2 if cur else 0)
        cur.append(p)
        size += add
    if cur:
        parts.append("\n\n".join(cur))
    return parts


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _nums(s: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUM.findall(s)}


def check_quote(quote, part: str) -> str:
    """«точно» | «partial» | «коротко» | «числа» | «провал».
    Короче MIN_QUOTE → «коротко». Точное вхождение после нормализации пробелов → «точно».
    Иначе partial_ratio ≥92 и те же числовые токены в цитате и в лучшем фрагменте части → «partial»;
    числа разошлись → «числа»; ниже порога → «провал»."""
    if not isinstance(quote, str):
        return "провал"
    q, p = _norm(quote), _norm(part)
    if len(q) < MIN_QUOTE:
        return "коротко"
    if q in p:
        return "точно"
    al = fuzz.partial_ratio_alignment(q, p)
    if al is None or al.score < PARTIAL_MIN:
        return "провал"
    a, b = al.dest_start, al.dest_end
    while a > 0 and not p[a - 1].isspace():
        a -= 1
    while b < len(p) and not p[b].isspace():
        b += 1
    return "partial" if _nums(q) == _nums(p[a:b]) else "числа"


def model_label(role: str) -> str:
    """Имя модели без gpt://<folder>/ (folder_id в отчёт не попадает)."""
    m = llm._model_for(role)
    if m.startswith("gpt://"):
        m = m[len("gpt://"):].split("/", 1)[-1]
    return m or "модель не задана"


def load_prompt() -> str:
    t = PROMPT_PATH.read_text(encoding="utf-8")
    return re.sub(r"\A\s*<!--.*?-->\s*", "", t, flags=re.S).strip()


def _journal_stats(slug: str) -> dict:
    """₽ и счётчики из log.jsonl песочницы: все категории, включая ремонты и вызовы, закончившиеся LLMJSONError."""
    ev = read_jsonl(Path(os.environ["STRATEG_PROJECTS_DIR"]) / slug / "log.jsonl")
    llm_ev = [e for e in ev if e["kind"] == "llm"]
    return {"calls": len(llm_ev), "rub": sum(e["rub"] for e in llm_ev if e.get("rub") is not None),
            "rub_unknown": any(e.get("rub") is None for e in llm_ev),
            "repairs": sum(1 for e in ev if e["kind"] == "repair"),
            "retries": sum(1 for e in ev if e["kind"] == "retry"),
            "truncated": sum(1 for e in llm_ev if e.get("truncated")),
            "errors": sum(1 for e in ev if e["kind"] == "error")}


def run_model(key: str, role: str, parts: list[tuple[str, int, int, str]], prompt: str, log=print) -> dict:
    """Прогон одной модели по всем частям в песочнице-проекте; сбои считаются и печатаются, не глотаются.
    Требует STRATEG_PROJECTS_DIR на временную папку (её создаёт main)."""
    slug = f"spike-{key}"
    (Path(os.environ["STRATEG_PROJECTS_DIR"]) / slug).mkdir(parents=True, exist_ok=True)
    st = {"key": key, "role": role, "model": model_label(role), "parts": 0, "json_ok": 0, "unavail": 0,
          "claims": 0, "точно": 0, "partial": 0, "провал": 0, "коротко": 0, "числа": 0, "secs": 0.0}
    for name, i, n, text in parts:
        st["parts"] += 1
        user = f"Фрагмент {i} из {n} (источник: {name}).\n\n<<<ИСТОЧНИК\n{text}\nИСТОЧНИК>>>"
        t0 = time.monotonic()
        try:
            obj, r = llm.chat_json([{"role": "system", "content": prompt}, {"role": "user", "content": user}],
                                   role=role, slug=slug, action_id=f"spike:{name}:{i}", required_keys=["claims"],
                                   max_tokens=4000, temperature=0)
        except llm.LLMJSONError as e:
            st["secs"] += time.monotonic() - t0
            log(f"  [{key}] {name} {i}/{n}: НЕВАЛИДНЫЙ JSON: {e}")
            continue
        except llm.LLMUnavailable as e:
            st["secs"] += time.monotonic() - t0
            st["unavail"] += 1
            log(f"  [{key}] {name} {i}/{n}: ПРОВАЛ ВЫЗОВА: {e}")
            continue
        st["secs"] += time.monotonic() - t0
        st["json_ok"] += 1
        claims = obj.get("claims")
        if not isinstance(claims, list):
            log(f"  [{key}] {name} {i}/{n}: «claims» не список, часть считается без утверждений")
            continue
        for c in claims:
            st["claims"] += 1
            v = check_quote(c.get("quote") if isinstance(c, dict) else None, text)
            if v in ("коротко", "числа"):
                st[v] += 1
                v = "провал"
            st[v] += 1
        log(f"  [{key}] {name} {i}/{n}: утверждений {len(claims)}, {r.latency_s:.1f} с")
    st.update(_journal_stats(slug))
    return st


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f} %" if b else "—"


def render_table(results: list[dict], sources: list[tuple[str, int, int]] | None, when: str | None) -> str:
    head = f"""# Спайк извлечения: замер lite/pro (задача 6)

{LITE_NOTE}

## Методика

- Тексты: `evals/spike/*.md`. Режутся на части ≤12 000 символов по абзацам, перекрытие 1 абзац (Глобальное ограничение 8).
- Каждая часть каждой модели уходит с `prompts/extract.md` (v0) через `llm.chat_json` (температура 0, один ремонтный повтор по У1).
- **% валидного JSON** = части с разобранным ответом (есть ключ `claims`) / все части. `LLMJSONError` и `LLMUnavailable` считаются провалом части.
- Цитата сверяется с текстом той части, из которой извлечена, после нормализации пробелов:
  **точно** — дословное вхождение; **partial** — не точно, но `rapidfuzz.fuzz.partial_ratio` ≥ 92 **и** множества числовых токенов цитаты и лучшего совпавшего фрагмента части равны (иначе провал: «чужие» числа); **провал** — остальное.
  Минимальная длина цитаты `MIN_QUOTE` = 25 символов после нормализации: короче — провал, даже если вхождение точное («ГБ», «рост», «12%» встречаются в тексте всегда). Колонки «коротких» и «числа расходятся» — часть провалов, не отдельные категории.
  Проценты цитат считаются от всех утверждений модели: точно + partial + провал = 100 %.
- ₽, ремонты, ретраи, обрезанные ответы и ошибки берутся из `log.jsonl` временного проекта-песочницы (папка удаляется после прогона), по всем вызовам и категориям: первый вызов при ремонте и вызовы, закончившиеся `LLMJSONError`, тоже учтены. Цена по `config/prices.yaml`; если неизвестна — «цена неизвестна». Секунды — среднее время на часть (с ремонтами и ретраями).

## Правила решения (шаг 4)

- Lite даёт ≥80 % точных цитат и ≤10 % провалов → `EXTRACT_MODEL` = lite; иначе по умолчанию pro.
- Обе модели ниже 60 % точных цитат → остановиться и решить с пользователем: менять промпт (например, номера абзацев вместо цитат) или модель.
- Решение и цифры записываются в `01-ai-project/build-log.md`.

## Результаты
"""
    if not results:
        return head + "\n**замер не выполнен: нет ключа (09.11)**\n\n" + _table([]) + "\n"
    src = "; ".join(f"{n}: {c} симв., {p} ч." for n, c, p in (sources or []))
    out = head + f"\nПрогон: {when}. Источники: {src}.\n\n" + _table(results) + "\n"
    return out


def _table(results: list[dict]) -> str:
    rows = ["| Модель | Частей | Валидный JSON | Утверждений | Точных | Partial ≥92 | Провалов | из них коротких / числа расходятся | ₽ (все вызовы) | ₽/часть | Ремонтов / обрезано / ошибок | Сек/часть |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in results:
        n = s["claims"]
        if s["rub_unknown"]:
            rub, per = "цена неизвестна", "цена неизвестна"
        else:
            rub = f"{s['rub']:.2f} ₽"
            per = f"{s['rub'] / s['parts']:.3f} ₽" if s["parts"] else "—"
        secs = f"{s['secs'] / s['parts']:.1f}" if s["parts"] else "—"
        rows.append(f"| {s['key']} = {s['model']} | {s['parts']} | {_pct(s['json_ok'], s['parts'])} | {n} | "
                    f"{_pct(s['точно'], n)} | {_pct(s['partial'], n)} | {_pct(s['провал'], n)} | {s['коротко']} / {s['числа']} | {rub} | {per} | "
                    f"{s['repairs']} / {s['truncated']} / {s['errors']} | {secs} |")
    if not results:
        rows.append("| — | — | — | — | — | — | — | — | — | — | — | — |")
    return "\n".join(rows)


def write_placeholder() -> None:
    write_text_atomic(TABLE_PATH, render_table([], None, None))


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(
        description="Спайк извлечения: режет тексты на части ≤12 000 символов, гонит промпт prompts/extract.md "
                    "через модели lite и pro, сверяет цитаты с текстом и пишет таблицу в evals/spike-extract.md.")
    ap.add_argument("files", nargs="+", type=Path, help="тексты .md или .txt")
    ap.add_argument("--models", default="lite,pro",
                    help="какие модели гнать: lite (роль extract, EXTRACT_MODEL) и/или pro (роль pro, PRO_MODEL); по умолчанию lite,pro")
    a = ap.parse_args(argv)

    keys = [k.strip() for k in a.models.split(",") if k.strip()]
    bad = [k for k in keys if k not in ROLES]
    if bad or not keys:
        print(f"Ошибка: неизвестная модель {bad or a.models!r}. Что сделать: укажите --models lite, pro или lite,pro.", file=sys.stderr)
        return 2
    missing = [f for f in a.files if not f.is_file()]
    if missing:
        print(f"Ошибка: нет файла {missing[0]}. Что сделать: проверьте путь (тексты лежат в evals/spike/).", file=sys.stderr)
        return 2
    if not all(llm.has_key(ROLES[k]) for k in keys):
        print("НЕТ КЛЮЧА: замер lite/pro невозможен без ключа Yandex. Что сделать: впишите LLM_API_KEY, "
              "LLM_BASE_URL, EXTRACT_MODEL и PRO_MODEL в .env (шаблон .env.example) и запустите снова.")
        return 3

    prompt = load_prompt()
    parts: list[tuple[str, int, int, str]] = []
    sources: list[tuple[str, int, int]] = []
    for f in a.files:
        text = f.read_text(encoding="utf-8")
        ps = split_parts(text)
        sources.append((f.name, len(text), len(ps)))
        parts += [(f.name, i, len(ps), p) for i, p in enumerate(ps, 1)]
    print(f"Частей: {len(parts)} из {len(a.files)} файлов")

    results = []
    tmp = tempfile.mkdtemp(prefix="spike-")  # песочница для log.jsonl; в репо ничего не пишем
    old_env = os.environ.get("STRATEG_PROJECTS_DIR")
    os.environ["STRATEG_PROJECTS_DIR"] = tmp
    try:
        for k in keys:
            print(f"Модель {k} ({model_label(ROLES[k])}):")
            results.append(run_model(k, ROLES[k], parts, prompt))
    except llm.NoKeyError as e:
        print(f"НЕТ КЛЮЧА: {e}")
        return 3
    finally:
        if old_env is None:
            os.environ.pop("STRATEG_PROJECTS_DIR", None)
        else:
            os.environ["STRATEG_PROJECTS_DIR"] = old_env
        shutil.rmtree(tmp, ignore_errors=True)
    write_text_atomic(TABLE_PATH, render_table(results, sources, time.strftime("%d.%m.%Y %H:%M")))
    print(f"Таблица записана: {TABLE_PATH}")
    for s in results:
        n = s["claims"]
        print(f"  {s['key']}: JSON {_pct(s['json_ok'], s['parts'])}, точно {_pct(s['точно'], n)}, "
              f"partial {_pct(s['partial'], n)}, провал {_pct(s['провал'], n)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
