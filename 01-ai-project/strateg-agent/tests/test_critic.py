# Тесты critic.py (критика вариантов, обещаний, проверка толкования, режим без ключа); без них критик увидит материалы, его ответ станет «фактом» или плохой ответ модели пройдёт молча.
import json

import pytest

from tools import claims, critic, ingest, state, status
from tools.common import project_path, read_jsonl, read_text

SECRET = "СЕКРЕТНЫЙ АБЗАЦ МАТЕРИАЛА про внутренний тариф Альфа-77"
P = [
    "Отток абонентов в третьем квартале 2024 года составил 4,2 % в месяц.",
    "Цена пакета eSIM для поездок в Турцию составляет 650 рублей за семь дней.",
    "Конкурент снизил цену на аналогичный пакет в третьем квартале 2024 года.",
    SECRET + " и ещё немного текста материала.",
]


def _log(slug):
    return read_jsonl(project_path(slug) / "log.jsonl")


def _setup(slug):
    root = project_path(slug)
    src = root.parent / "src.txt"
    src.write_text("\n\n".join(P) + "\n", encoding="utf-8")
    sid = ingest.ingest(slug, src, found_by="user")
    ids = []
    for i in (0, 1, 2):
        ids.append(claims.add(slug, {"type": "fact", "text": f"Утверждение номер {i}", "source": sid, "locator": f"¶{i + 1}",
                                     "quote": P[i], "question": ["Q1"], "extracted_by": "extract.py:test"}))
    (root / "questions.md").write_text("- Q1: Почему падает спрос на пакеты?\n", encoding="utf-8")
    (root / "options.md").write_text(
        "# Варианты\n\n<!-- шаблон: ## O1 · status_quo · Название -->\n\n"
        "## O1 · status_quo · Оставить как есть\nСуть: ничего не менять.\nВозражения:\n- В1: отток растёт [C-001]\n- В2: цена не меняется\n"
        "Что заставит передумать: отток упадёт ниже 3 %.\n\n"
        "## O2 · close · Закрыть направление\nСуть: закрыть.\nВозражения:\n- В1: потеряем выручку [C-002]\n- В2: бренд\n"
        "Что заставит передумать: убыток превысит порог.\n\n"
        "## O3 · option · Снизить цену\nСуть: цена вниз.\nВозражения:\n- В1: конкурент уже снизил [C-002]\n- В2: маржа\n"
        "Что заставит передумать: эластичность спроса ниже 0,5.\n", encoding="utf-8")
    return sid, ids


def _good():
    obj = {"objections": [], "weak_support": [{"claim": "C-001", "reason": "один источник"}], "reconsider": []}
    for o in ("O1", "O2", "O3"):
        obj["objections"] += [
            {"option": o, "text": f"{o}: возражение с опорой на факт", "claim": "C-001", "kind": "evidence"},
            {"option": o, "text": f"{o}: второе возражение, предположение", "claim": None, "kind": "hypothesis"},
        ]
        obj["reconsider"].append({"option": o, "text": f"{o}: что заставит передумать"})
    return obj


def test_critic_payload_only_options_and_cited_quotes(fake_llm, tmp_project):
    _setup(tmp_project)
    fake_llm.add(json.dumps(_good(), ensure_ascii=False))
    path = critic.critique_options(tmp_project)
    assert path == project_path(tmp_project) / "critique.md"
    payload = "\n".join(m["content"] for m in fake_llm.calls[0]["messages"])
    assert P[0] in payload and P[1] in payload  # цитаты утверждений, на которые ссылаются варианты
    assert P[2] not in payload  # C-003 вариантами не цитируется
    assert SECRET not in payload and "внутренний тариф" not in payload  # текста материалов в запросе нет
    assert "O1 · status_quo" in payload and "<<<ВАРИАНТЫ" in payload and "<<<УТВЕРЖДЕНИЯ" in payload
    assert len(fake_llm.calls) == 1 and fake_llm.calls[0]["role"] == "critic"


def test_critique_two_objections_per_option(fake_llm, tmp_project):
    _setup(tmp_project)
    before = claims.load(tmp_project)
    fake_llm.add(json.dumps(_good(), ensure_ascii=False))
    text = read_text(critic.critique_options(tmp_project))
    for o in ("O1", "O2", "O3"):
        block = text.split(f"## {o} ")[1].split("\n## ")[0]
        assert block.count("- В") >= 2 and "[C-001]" in block and "Что заставит передумать:" in block
    assert "Слабые опоры" in text and "не факты" in text
    assert claims.load(tmp_project) == before  # ответ критика не становится утверждением, тем более fact


def test_critique_deficient_answer_retried_once_then_ok(fake_llm, tmp_project):
    _setup(tmp_project)
    bad = _good()
    bad["objections"] = [o for o in bad["objections"] if not (o["option"] == "O2" and o["claim"] is None)]  # у O2 одно возражение
    for o in bad["objections"]:
        if o["option"] == "O1":
            o["claim"] = "C-999"  # несуществующая ссылка не засчитывается
    fake_llm.add(json.dumps(bad, ensure_ascii=False), json.dumps(_good(), ensure_ascii=False))
    path = critic.critique_options(tmp_project)
    assert path.is_file() and len(fake_llm.calls) == 2
    assert "C-999" not in read_text(path)
    assert any(e["kind"] == "critic_retry" for e in _log(tmp_project))


def test_critique_bad_answers_escalate_to_human(fake_llm, tmp_project, monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("AGENT_ROUTE", raising=False)
    _setup(tmp_project)
    fake_llm.add("не json", "и это не json")
    with pytest.raises(critic.Escalated) as ei:
        critic.critique_options(tmp_project)
    assert ei.value.to == "human"
    assert not (project_path(tmp_project) / "critique.md").exists()
    assert state.load(tmp_project)["waiting"]["point"] == "critic"
    assert any(e["kind"] == "escalation" and e["step"] == "critic->human" for e in _log(tmp_project))


def test_critique_bad_answers_claude_code_emits_prompt(fake_llm, tmp_project, monkeypatch, capsys):
    monkeypatch.setenv("AGENT_ROUTE", "claude-code")
    _setup(tmp_project)
    fake_llm.add("мусор", "мусор")
    with pytest.raises(critic.Escalated) as ei:
        critic.critique_options(tmp_project)
    assert ei.value.to == "env-model" and ei.value.path.parent.name == "prompts"
    assert ":" not in ei.value.path.name and "--apply" in capsys.readouterr().out


def test_critique_rerun_no_duplicate_calls(fake_llm, tmp_project):
    _setup(tmp_project)
    fake_llm.add(json.dumps(_good(), ensure_ascii=False))
    first = read_text(critic.critique_options(tmp_project))
    again = critic.critique_options(tmp_project)  # ответы закончились: вызов дал бы AssertionError
    assert read_text(again) == first and len(fake_llm.calls) == 1


def test_critic_no_key_raises(tmp_project):
    _setup(tmp_project)
    with pytest.raises(critic.llm.NoKeyError):
        critic.critique_options(tmp_project)


def test_emit_apply_roundtrip_logs_degraded(tmp_project, capsys):
    _setup(tmp_project)
    ans = critic.emit_critique(tmp_project)
    out = capsys.readouterr().out
    assert ans.suffix == ".json" and ans.parent.name == "prompts" and ":" not in ans.name
    assert P[0] in out and SECRET not in out and "--apply" in out
    ans.write_text(json.dumps(_good(), ensure_ascii=False), encoding="utf-8")
    path = critic.apply_critique(tmp_project, ans)
    assert path.is_file()
    assert any(e["kind"] == "degraded" and e["flag"] == "env-model" for e in _log(tmp_project))
    assert state.load(tmp_project)["degraded"][0]["flag"] == "env-model"
    rendered = status.render(tmp_project)
    assert "[КРАСНАЯ]" in rendered and "модель среды" in rendered


def test_apply_rejects_deficient_answer(tmp_project):
    _setup(tmp_project)
    ans = critic.emit_critique(tmp_project)
    bad = _good()
    bad["objections"] = bad["objections"][:2]
    ans.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="Что сделать"):
        critic.apply_critique(tmp_project, ans)
    assert not (project_path(tmp_project) / "critique.md").exists()


def test_same_family_sets_yellow_degraded(fake_llm, tmp_project, monkeypatch):
    monkeypatch.setenv("MAIN_MODEL_FAMILY", "claude")
    monkeypatch.setenv("CRITIC_MODEL_FAMILY", "claude")
    _setup(tmp_project)
    fake_llm.add(json.dumps(_good(), ensure_ascii=False))
    critic.critique_options(tmp_project)
    st = state.load(tmp_project)
    assert any(d["flag"] == "critic-same-family" and "того же семейства" in d["note"] for d in st["degraded"])
    assert any(e["kind"] == "degraded" and e["flag"] == "critic-same-family" for e in _log(tmp_project))
    text = status.render(tmp_project)
    assert "[ЖЁЛТАЯ]" in text and "критик того же семейства" in text


def test_different_family_no_degraded(fake_llm, tmp_project, monkeypatch):
    monkeypatch.setenv("MAIN_MODEL_FAMILY", "claude")
    monkeypatch.setenv("CRITIC_MODEL_FAMILY", "yandexgpt")
    _setup(tmp_project)
    fake_llm.add(json.dumps(_good(), ensure_ascii=False))
    critic.critique_options(tmp_project)
    assert state.load(tmp_project)["degraded"] == []


# ---- обещания ----

def _promises_setup(slug):
    root = project_path(slug)
    (root / "strategy.md").write_text(
        "# Стратегия\n\n## Коммуникационная стратегия\n"
        "- «Установка по QR за три шага» → F-1\n- «Автоподключение при посадке» → F-2\n- «Возврат остатка трафика» → F-9\n- «Без роуминга»\n",
        encoding="utf-8")
    (root / "product.yaml").write_text(
        "features:\n- {id: F-1, what: eSIM по QR, status: exists}\n- {id: F-2, what: автоподключение, status: planned}\n", encoding="utf-8")


def _verdicts(**over):
    base = {"P-1": ("F-1", "ok", ""), "P-2": ("F-2", "ok", ""), "P-3": (None, "missing", "нет функции возврата"), "P-4": (None, "missing", "")}
    base.update(over)
    return json.dumps([{"promise": k, "feature": v[0], "verdict": v[1], "note": v[2]} for k, v in base.items()], ensure_ascii=False)


def test_promises_planned_without_date_flagged(fake_llm, tmp_project):
    _promises_setup(tmp_project)
    fake_llm.add(_verdicts())
    fs = critic.check_promises(tmp_project)
    by = {}
    for f in fs:
        by.setdefault(f.target, []).append(f)
    assert any(f.level == "WARN" and "срок" in f.msg for f in by["P-2"])  # planned без available_from
    assert any(f.level == "FAIL" and "F-9" in f.msg for f in by["P-3"])  # F-9 нет в product.yaml
    assert any(f.level == "FAIL" for f in by["P-4"])  # обещание без → F-n
    assert not any(f.level != "OK" for f in by["P-1"])
    payload = "\n".join(m["content"] for m in fake_llm.calls[0]["messages"])
    assert "Установка по QR" in payload and "<<<ОБЕЩАНИЯ" in payload and "<<<ПРОДУКТ" in payload


def test_promises_model_disagrees_with_author_link(fake_llm, tmp_project):
    _promises_setup(tmp_project)
    fake_llm.add(_verdicts(**{"P-1": ("F-2", "partial", "покрывает лишь часть")}))
    fs = critic.check_promises(tmp_project)
    p1 = [f for f in fs if f.target == "P-1"]
    assert any(f.level == "WARN" and "покрывает лишь часть" in f.msg for f in p1)
    assert any(f.level == "WARN" and "F-2" in f.msg and "F-1" in f.msg for f in p1)


def test_promises_incomplete_answer_escalates(fake_llm, tmp_project, monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("AGENT_ROUTE", raising=False)
    _promises_setup(tmp_project)
    fake_llm.add("[]", "[]")
    with pytest.raises(critic.Escalated):
        critic.check_promises(tmp_project)


# ---- проверка толкования ----

def _many_claims(slug, k=12):
    root = project_path(slug)
    paras = [f"Показатель номер {i} в отчёте равен {i}0 условных единиц за квартал." for i in range(1, k + 1)]
    src = root.parent / "many.txt"
    src.write_text("\n\n".join(paras) + "\n", encoding="utf-8")
    sid = ingest.ingest(slug, src, found_by="user")
    for i, p in enumerate(paras, 1):
        claims.add(slug, {"type": "fact", "text": f"Показатель {i} вырос", "source": sid, "locator": f"¶{i}", "quote": p,
                          "question": ["Q1"], "extracted_by": "extract.py:test"})


def test_claims_sample_reproducible_with_seed(fake_llm, tmp_project):
    _many_claims(tmp_project)
    a = [p["id"] for p in critic.pick_pairs(tmp_project, 5, seed=42)]
    b = [p["id"] for p in critic.pick_pairs(tmp_project, 5, seed=42)]
    c = [p["id"] for p in critic.pick_pairs(tmp_project, 5, seed=43)]
    assert a == b and len(set(a)) == 5 and a != c
    assert [p["id"] for p in critic.pick_pairs(tmp_project, 99, seed=1)] == sorted(x["id"] for x in claims.load(tmp_project))
    verdicts = ["faithful", "overreach", "contradiction", "faithful", "faithful"]
    ans = json.dumps([{"id": i, "verdict": v, "note": "причина"} for i, v in zip(a, verdicts)], ensure_ascii=False)
    fake_llm.add(ans)
    path = critic.sample_claims(tmp_project, n=5, seed=42)
    text = read_text(path)
    assert path.name == "critique-claims.md" and "seed: 42" in text
    assert "верно" in text and "неточно" in text and "неверно" in text and "причина" in text
    assert "Проверено 5: верно 3, неточно 1, неверно 1" in text
    assert all(i in text for i in a)
    payload = "\n".join(m["content"] for m in fake_llm.calls[0]["messages"])
    assert "<<<ПАРЫ" in payload and all(i in payload for i in a)
    again = critic.sample_claims(tmp_project, n=5, seed=42)  # повтор: тот же action_id, вызова нет
    assert again == path and len(fake_llm.calls) == 1


def test_claims_sample_missing_ids_not_silently_accepted(fake_llm, tmp_project, monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("AGENT_ROUTE", raising=False)
    _many_claims(tmp_project)
    ids = [p["id"] for p in critic.pick_pairs(tmp_project, 3, seed=1)]
    part = json.dumps([{"id": ids[0], "verdict": "faithful", "note": "ок"}])
    fake_llm.add(part, part)
    with pytest.raises(critic.Escalated):
        critic.sample_claims(tmp_project, n=3, seed=1)
    assert not (project_path(tmp_project) / "critique-claims.md").exists()


def test_cli_help_is_russian(capsys):
    with pytest.raises(SystemExit):
        critic.main(["--help"])
    out = capsys.readouterr().out
    assert "критик" in out.lower() and "--claims-sample" in out and "--emit-prompt" in out and "--apply" in out
