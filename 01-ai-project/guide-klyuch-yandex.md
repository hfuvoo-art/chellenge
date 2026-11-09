# Как получить ключ Yandex AI Studio для strateg-agent (09.11.2026)

Нужно 2 значения: **API-ключ** (секрет) и **ID каталога** (folder_id). Оба кладём только в `01-ai-project/strateg-agent/.env` — он в `.gitignore`. В чат, коммиты, скриншоты и журналы ключ не попадает.

## Шаги

1. Войти в Yandex Cloud: https://console.yandex.cloud (Яндекс ID). Если платёжного аккаунта нет — создать его (нужна карта). Есть ли сейчас стартовый грант, на странице цен не указано — смотри в консоли при создании платёжного аккаунта.
2. Открыть AI Studio: https://aistudio.yandex.cloud/platform/ и выбрать каталог (по умолчанию `default`).
3. Нажать **«Создать API-ключ»** в правом верхнем углу → описание, срок действия → **«Создать»**.
   - Будет создан сервисный аккаунт с ролью `ai.editor` и ключ с областью `yc.ai.languageModels.execute` — этого хватает.
   - Нужна роль `resource-manager.admin` на каталог (у владельца облака она есть).
   - **Секретный ключ показывают один раз** — сразу вставь его в `.env`.
4. ID каталога: в консоли Yandex Cloud открыть каталог → скопировать «Идентификатор» (строка вида `b1g…`).
5. Создать `.env` из шаблона и заполнить:

```bash
cd 01-ai-project/strateg-agent
cp .env.example .env
```

```ini
LLM_BASE_URL=https://llm.api.cloud.yandex.net/v1
LLM_API_KEY=<секретный ключ>
LLM_PROJECT=<ID каталога>
EXTRACT_MODEL=gpt://<ID каталога>/aliceai-llm-flash
PRO_MODEL=gpt://<ID каталога>/yandexgpt-5.1
CRITIC_MODEL=gpt://<ID каталога>/yandexgpt-5.1
```

6. Проверка (после задачи 2): `python tools/llm.py ping --role extract` и `--role pro` → `LLM OK …`. Написать в чат только «ключ готов» — сам ключ не присылать.

## Что важно знать

- **YandexGPT Lite 5 (`yandexgpt-5-lite`) объявлена устаревшей и будет отключена 15.11.2026** — до сдачи. Поэтому дешёвую роль `extract` берём на **Alice AI LLM Flash** (`aliceai-llm-flash`), спайк (задача 6) сравнивает её с YandexGPT Pro 5.1. Источник: https://aistudio.yandex.ru/docs/ru/ai-studio/concepts/generation/models
- Цены за 1000 токенов, ₽ с НДС, синхронный режим (вход / выход): Alice AI LLM Flash 0,1 / 0,2; YandexGPT Pro 5.1 0,8 / 0,8; Qwen3.6 35B 0,2 / 0,3. Источник: https://aistudio.yandex.ru/docs/ru/ai-studio/pricing
- Адрес `https://llm.api.cloud.yandex.net/v1` и передача ID каталога через `project` (заголовок `OpenAI-Project`) взяты из заготовки `02-vibe-coding` и выдачи поиска по документации; страница OpenAI-совместимости на 09.11 отдаёт 404. **Не проверено** — подтвердится первым `ping`. Запасной адрес из туториала Yandex: `https://ai.api.cloud.yandex.net/v1`.
- Для маршрута OpenCode критик другого семейства есть в том же каталоге: Qwen3.6 35B (`qwen3.6-35b-a3b`), DeepSeek V4.1 Flash, gpt-oss-120b.
