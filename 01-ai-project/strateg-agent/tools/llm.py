# Клиент модели (YandexGPT через OpenAI-совместимый API): ретраи, ремонт JSON, учёт токенов и ₽ в журнале; без него нет ни вызовов, ни стоимости.
from __future__ import annotations

import argparse
import json
import re
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.venv_boot import ensure_venv  # noqa: E402

ensure_venv(__file__)

from tools import log  # noqa: E402
from tools.common import ROOT, current_slug, read_yaml, setup_stdio  # noqa: E402

ENV_FILE: Path = ROOT / ".env"
PRICES_PATH: Path = ROOT / "config" / "prices.yaml"
RETRY_PAUSES = (2, 6)  # секунды; максимум 2 ретрая (Глобальное ограничение 10)
TIMEOUT_S = 180.0  # по умолчанию; переопределяется LLM_TIMEOUT_S в .env (Alice Flash на части 6 тыс. символов отвечает ~70 с)
NO_KEY_MSG = "НЕТ КЛЮЧА: работаю в режиме без ключа (см. README)"

# роль -> переменная модели
_ROLE_MODEL = {
    "extract": "EXTRACT_MODEL", "relevance": "EXTRACT_MODEL", "interview_coding": "EXTRACT_MODEL",
    "pro": "PRO_MODEL", "respond": "PRO_MODEL",
    "critic": "CRITIC_MODEL",
    "judge": "JUDGE_MODEL",
}


class NoKeyError(Exception):
    pass


class LLMUnavailable(Exception):
    pass


class LLMJSONError(Exception):
    pass


@dataclass
class LLMResult:
    text: str
    model: str
    role: str
    usage: dict = field(default_factory=dict)
    rub: float | None = None
    latency_s: float = 0.0
    attempts: int = 1
    truncated: bool = False


def load_env() -> None:
    """Простой разбор .env: KEY=VALUE, без перезаписи уже заданных переменных окружения."""
    if not ENV_FILE.is_file():
        return
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if k.isidentifier() and v and k not in os.environ:
            os.environ[k] = v


def _env(name: str) -> str:
    load_env()
    return os.environ.get(name, "").strip()


def _conn(role: str) -> dict:
    """Параметры подключения роли: у критика свои CRITIC_*, иначе общие LLM_*."""
    def pick(suffix: str) -> str:
        if role == "critic":
            v = _env("CRITIC_" + suffix)
            if v:
                return v
        return _env("LLM_" + suffix)
    return {"base_url": pick("BASE_URL"), "api_key": pick("API_KEY"), "project": pick("PROJECT")}


def has_key(role: str) -> bool:
    return bool(_conn(role)["api_key"])


def _model_for(role: str) -> str:
    if role not in _ROLE_MODEL:
        raise ValueError(f"неизвестная роль модели: {role}")
    m = _env(_ROLE_MODEL[role])
    if not m and role == "judge":
        m = _env("PRO_MODEL")
    return m


def _require_config(role: str, model: str | None) -> str:
    if not has_key(role):
        raise NoKeyError(NO_KEY_MSG + ". Что сделать: впишите ключ в .env (шаблон .env.example) или работайте без ключа по README.")
    name = model or _model_for(role)
    if not name:
        raise NoKeyError(f"не задана модель для роли «{role}». Что сделать: впишите {_ROLE_MODEL.get(role, '<роль>_MODEL')} в .env (см. .env.example, README).")
    if not _conn(role)["base_url"]:
        raise NoKeyError("не задан LLM_BASE_URL. Что сделать: впишите адрес OpenAI-совместимого API в .env (см. .env.example, README).")
    return name


def price_rub(model: str, usage: dict) -> float | None:
    """₽ за вызов по config/prices.yaml; None, если цена неизвестна (У12)."""
    try:
        cfg = read_yaml(PRICES_PATH) or {}
    except OSError:
        return None
    models = cfg.get("models") or {}
    p = models.get(model)
    if p is None and model.startswith("gpt://"):
        parts = model[len("gpt://"):].split("/")
        if len(parts) >= 2:
            p = models.get(parts[1])
    if not p or p.get("input_per_1k_rub") is None or p.get("output_per_1k_rub") is None:
        return None
    pin = usage.get("prompt_tokens") or 0
    pout = usage.get("completion_tokens") or 0
    return round(pin / 1000 * p["input_per_1k_rub"] + pout / 1000 * p["output_per_1k_rub"], 6)


def _create(role: str, model: str, messages: list, temperature: float, max_tokens: int) -> tuple[str, dict]:
    """Единственная сетевая точка: один запрос без ретраев (ретраи наши).
    В usage дополнительно лежит "truncated" (finish_reason == length); chat() вынимает его из usage."""
    import openai

    c = _conn(role)
    client = openai.OpenAI(
        base_url=c["base_url"], api_key=c["api_key"], project=c["project"] or None,
        timeout=float(os.environ.get("LLM_TIMEOUT_S") or TIMEOUT_S), max_retries=0,
    )
    resp = client.chat.completions.create(
        model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
    )
    text = (resp.choices[0].message.content or "") if resp.choices else ""
    truncated = bool(resp.choices) and resp.choices[0].finish_reason == "length"
    u = resp.usage
    usage = {
        "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
        "total_tokens": getattr(u, "total_tokens", 0) or 0,
        "truncated": truncated,
    }
    return text, usage


def _retryable(e: BaseException) -> bool:
    code = getattr(e, "status_code", None)
    if isinstance(code, int):
        return code == 429 or code >= 500
    if isinstance(e, (TimeoutError, ConnectionError)):
        return True
    return type(e).__name__ in {"APITimeoutError", "APIConnectionError"}


_MODEL_URI_RE = re.compile(r"^[a-z]+://[^/]+/")


def public_model_name(model) -> str:
    """«gpt://<ID каталога>/yandexgpt-5.1» → «yandexgpt-5.1»: ID каталога облака не попадает в журнал и репозиторий."""
    return _MODEL_URI_RE.sub("", str(model)) if model else model


def _log(slug, kind: str, **fields) -> None:
    if slug is None and current_slug() is None:
        return
    if "model" in fields:
        fields["model"] = public_model_name(fields["model"])
    log.event(slug, kind, **fields)


def _emit_llm(slug, r: LLMResult, category: str, action_id) -> None:
    """Одно событие llm на каждый вызов. Вызов после ретрая всегда «retry» (У2)."""
    cat = category if r.attempts == 1 else "retry"
    _log(slug, "llm", role=r.role, model=r.model, usage=r.usage, rub=r.rub, latency_s=r.latency_s,
         attempts=r.attempts, category=cat, truncated=r.truncated, action_id=action_id)


def chat(messages, *, role, slug=None, action_id=None, temperature=0.2, max_tokens=2000, model=None,
         category: str = "yandex", _emit: bool = True) -> LLMResult:
    """Вызов модели с ≤2 ретраями (паузы 2 и 6 с на 429/5xx/таймаут) и записью в журнал.
    category: «yandex» для успешного первого вызова; повторы, ремонты и эскалации идут как «retry» (У2).
    _emit=False: событие llm пишет вызывающий (chat_json, после разбора ответа)."""
    name = _require_config(role, model)
    t0 = time.monotonic()
    for attempt in range(1, len(RETRY_PAUSES) + 2):
        try:
            text, usage = _create(role, name, messages, temperature, max_tokens)
            break
        except NoKeyError:
            raise
        except Exception as e:  # noqa: BLE001
            status = getattr(e, "status_code", None)
            if not _retryable(e):
                _log(slug, "error", role=role, model=name, status=status, error=type(e).__name__,
                     attempts=attempt, action_id=action_id)
                raise LLMUnavailable(f"модель «{name}» отклонила запрос ({type(e).__name__}, код {status}). Что сделать: проверьте ключ, модель и LLM_BASE_URL в .env.") from None
            if attempt > len(RETRY_PAUSES):
                _log(slug, "error", role=role, model=name, status=status, error=type(e).__name__,
                     attempts=attempt, action_id=action_id)
                raise LLMUnavailable(f"модель «{name}» недоступна после {attempt} попыток ({type(e).__name__}, код {status}). Что сделать: повторите позже или задайте вопрос человеку.") from None
            pause = RETRY_PAUSES[attempt - 1]
            _log(slug, "retry", role=role, model=name, attempt=attempt, error=type(e).__name__, status=status,
                 pause_s=pause, action_id=action_id)
            time.sleep(pause)
    latency = round(time.monotonic() - t0, 3)
    usage = dict(usage)
    truncated = bool(usage.pop("truncated", False))
    r = LLMResult(text=text, model=name, role=role, usage=usage, rub=price_rub(name, usage),
                  latency_s=latency, attempts=attempt, truncated=truncated)
    if _emit:
        _emit_llm(slug, r, category, action_id)
    return r


def _extract_json(text: str):
    """Только первое вхождение { или [: если оно не разбирается (обрезанный ответ), это ValueError, а не «кусок» JSON."""
    starts = [k for k in (text.find("{"), text.find("[")) if k >= 0]
    if not starts:
        raise ValueError("JSON не найден")
    obj, _ = json.JSONDecoder().raw_decode(text, min(starts))
    return obj


def _valid(obj, required_keys) -> bool:
    if required_keys:
        return isinstance(obj, dict) and all(k in obj for k in required_keys)
    return True


def chat_json(messages, *, role, slug=None, action_id=None, required_keys=None, **kw):
    """chat + разбор JSON (У1): один «ремонтный» повтор, затем LLMJSONError (эскалация - дело вызывающего).
    У2: событие llm первого вызова пишется после разбора: валидный JSON - категория вызывающего (по умолчанию
    «yandex»), не-JSON - «retry»; ремонтный вызов всегда «retry». Каждый вызов пишется один раз, двойного счёта нет."""
    first_cat = kw.pop("category", "yandex")
    kw.pop("_emit", None)
    r = chat(messages, role=role, slug=slug, action_id=action_id, _emit=False, **kw)
    try:
        obj = _extract_json(r.text)
        if _valid(obj, required_keys):
            _emit_llm(slug, r, first_cat, action_id)
            return obj, r
    except ValueError:
        pass
    _emit_llm(slug, r, "retry", action_id)
    _log(slug, "repair", role=role, model=r.model, action_id=action_id,
         reason="невалидный или обрезанный JSON", truncated=r.truncated)
    fix = list(messages) + [
        {"role": "assistant", "content": r.text},
        {"role": "user", "content": "Верни только JSON, без пояснений и ограждений ```."
         + (f" Обязательные ключи: {', '.join(required_keys)}." if required_keys else "")},
    ]
    r2 = chat(fix, role=role, slug=slug, action_id=action_id, category="retry", **kw)
    try:
        obj = _extract_json(r2.text)
        if _valid(obj, required_keys):
            return obj, r2
    except ValueError:
        pass
    raise LLMJSONError(f"модель «{r2.model}» дважды вернула не-JSON. Что сделать: эскалация по маршруту или вопрос человеку.")


def _ping(a) -> int:
    role = a.role
    if not has_key(role):
        print(NO_KEY_MSG)
        return 3
    try:
        r = chat([{"role": "user", "content": "Ответь одним словом: pong"}], role=role, max_tokens=20, temperature=0)
    except NoKeyError as e:
        print(str(e))
        return 3
    except LLMUnavailable as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1
    price = f"{r.rub:.2f} ₽" if r.rub is not None else "цена неизвестна"
    print(f"LLM OK · {r.model} · {r.usage.get('total_tokens', 0)} ток. · {price} · {r.latency_s:.1f} с")
    return 0


def main(argv=None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(description="Клиент модели: проверка связи (ping).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ping", help="проверить ключ и модель одним коротким запросом")
    p.add_argument("--role", choices=["extract", "pro", "critic"], default="extract", help="роль модели (по умолчанию extract)")
    a = ap.parse_args(argv)
    return _ping(a)


if __name__ == "__main__":
    sys.exit(main())
