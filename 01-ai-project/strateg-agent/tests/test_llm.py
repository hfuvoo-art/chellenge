# Тесты клиента модели: считают токены и ₽, ретраи, ремонт JSON; без них учёт стоимости и устойчивость к плохим ответам не проверены.
import os

import pytest
import yaml

from tests.conftest import HttpError
from tools import llm
from tools.common import project_path, read_jsonl

MSG = [{"role": "user", "content": "x"}]


def _log(slug):
    return read_jsonl(project_path(slug) / "log.jsonl")


def test_chat_logs_usage_and_rub(fake_llm, tmp_project):
    fake_llm.add("ответ")
    r = llm.chat(MSG, role="extract", slug=tmp_project, action_id="extract:S-001:part-01:abc")
    assert r.rub == pytest.approx(0.4)
    assert r.text == "ответ" and r.attempts == 1 and r.model == "test-model"
    ev = [e for e in _log(tmp_project) if e["kind"] == "llm"]
    assert len(ev) == 1
    e = ev[0]
    assert e["role"] == "extract" and e["model"] == "test-model" and e["rub"] == pytest.approx(0.4)
    assert e["usage"]["prompt_tokens"] == 1000 and e["usage"]["completion_tokens"] == 500
    assert e["action_id"] == "extract:S-001:part-01:abc"
    assert e["category"] == "yandex"
    assert "test-key" not in str(e)


def test_retries_twice_then_unavailable(fake_llm, tmp_project):
    fake_llm.add(HttpError(429), HttpError(429), HttpError(429))
    with pytest.raises(llm.LLMUnavailable):
        llm.chat(MSG, role="extract", slug=tmp_project)
    assert len(fake_llm.calls) == 3
    assert fake_llm.sleeps == [2, 6]
    assert len([e for e in _log(tmp_project) if e["kind"] == "retry"]) == 2


def test_non_retryable_error_not_retried(fake_llm, tmp_project):
    fake_llm.add(HttpError(400))
    with pytest.raises(llm.LLMUnavailable):
        llm.chat(MSG, role="extract", slug=tmp_project)
    assert len(fake_llm.calls) == 1 and fake_llm.sleeps == []


def test_retry_then_success_counts_as_failure_cost(fake_llm, tmp_project):
    fake_llm.add(HttpError(503), "ок")
    r = llm.chat(MSG, role="extract", slug=tmp_project)
    assert r.attempts == 2
    e = [e for e in _log(tmp_project) if e["kind"] == "llm"][0]
    assert e["category"] == "retry"  # У2: не в статье «Yandex»


def test_chat_json_strips_fence(fake_llm, tmp_project):
    fake_llm.add('```json\n{"claims": []}\n```')
    obj, r = llm.chat_json(MSG, role="extract", slug=tmp_project)
    assert obj == {"claims": []}
    assert len(fake_llm.calls) == 1


def test_chat_json_repair_once(fake_llm, tmp_project):
    fake_llm.add("не json вообще", '{"a":1}')
    obj, r = llm.chat_json(MSG, role="extract", slug=tmp_project)
    assert obj == {"a": 1}
    assert len(fake_llm.calls) == 2
    log = _log(tmp_project)
    assert any(e["kind"] == "repair" for e in log)
    assert [e["category"] for e in log if e["kind"] == "llm"] == ["yandex", "retry"]


def test_chat_json_gives_up_after_repair(fake_llm, tmp_project):
    fake_llm.add("мусор", "опять мусор")
    with pytest.raises(llm.LLMJSONError):
        llm.chat_json(MSG, role="extract", slug=tmp_project)
    assert len(fake_llm.calls) == 2


def test_chat_json_required_keys_and_array(fake_llm, tmp_project):
    fake_llm.add('{"b":1}', 'Вот: {"claims": [1]} конец')
    obj, _ = llm.chat_json(MSG, role="extract", slug=tmp_project, required_keys=["claims"])
    assert obj == {"claims": [1]}
    fake_llm.add("[1, 2]")
    obj, _ = llm.chat_json(MSG, role="extract", slug=tmp_project)
    assert obj == [1, 2]


def test_no_key_error_has_hint():
    assert llm.has_key("extract") is False
    with pytest.raises(llm.NoKeyError) as ei:
        llm.chat(MSG, role="extract")
    assert ".env" in str(ei.value) and "README" in str(ei.value)


def test_critic_key_overrides(monkeypatch):
    monkeypatch.setenv("CRITIC_API_KEY", "k2")
    assert llm.has_key("critic") is True and llm.has_key("extract") is False


def test_unknown_price_none_and_logged(fake_llm, tmp_project, monkeypatch):
    monkeypatch.setenv("EXTRACT_MODEL", "mystery-model")
    fake_llm.add("ответ")
    r = llm.chat(MSG, role="extract", slug=tmp_project)
    assert r.rub is None
    e = [e for e in _log(tmp_project) if e["kind"] == "llm"][0]
    assert e["rub"] is None and e["model"] == "mystery-model"


def test_price_rub_null_prices_and_yandex_uri(tmp_path, monkeypatch):
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump({"models": {
        "yandexgpt-lite": {"input_per_1k_rub": None, "output_per_1k_rub": None},
        "yandexgpt": {"input_per_1k_rub": 1.0, "output_per_1k_rub": 2.0}}}), encoding="utf-8")
    monkeypatch.setattr(llm, "PRICES_PATH", p)
    u = {"prompt_tokens": 1000, "completion_tokens": 1000}
    assert llm.price_rub("gpt://folder/yandexgpt-lite/latest", u) is None
    assert llm.price_rub("gpt://folder/yandexgpt/latest", u) == pytest.approx(3.0)


def test_shipped_prices_yaml_has_no_invented_prices():
    cfg = yaml.safe_load(open(llm.ROOT / "config" / "prices.yaml", encoding="utf-8"))
    assert cfg["as_of"] is None and cfg["sources"] == []
    assert llm.price_rub("yandexgpt-lite", {"prompt_tokens": 1, "completion_tokens": 1}) is None


def test_load_env_parses_file_without_overriding(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('# c\nLLM_API_KEY="abc"\nPRO_MODEL = m1  \nBAD LINE\nEXTRACT_MODEL=\n', encoding="utf-8")
    monkeypatch.setattr(llm, "ENV_FILE", f)
    monkeypatch.setenv("PRO_MODEL", "from-env")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    llm.load_env()
    assert os.environ["LLM_API_KEY"] == "abc" and os.environ["PRO_MODEL"] == "from-env"
    monkeypatch.delenv("LLM_API_KEY")


def test_ping_without_key_exit_3(capsys):
    assert llm.main(["ping", "--role", "extract"]) == 3
    assert "НЕТ КЛЮЧА" in capsys.readouterr().out


def test_ping_ok(fake_llm, capsys):
    fake_llm.add("pong")
    assert llm.main(["ping", "--role", "pro"]) == 0
    assert "LLM OK · test-model · 1500 ток. · 0.40 ₽" in capsys.readouterr().out
