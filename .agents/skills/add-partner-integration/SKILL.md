---
name: add-partner-integration
description: Step-by-step guide for adding an adapter for an external service (crypto processing, eSIM, gift cards, crypto cards, VPN, KYC) or replacing a mock with a real client. Use whenever code talks to a third-party API.
---

# Интеграция с партнёром

## 0. Есть ли документация

Проверь `docs/partners/<partner>/`. **API не выдумываем** (D-004).

- Документации нет → делаешь только шаги 1, 2, 3 (мок), 5, 6. Вопросы к партнёру и допущения
  записываешь в `docs/decisions.md`.
- Документация есть → сначала заполни `docs/partners/<partner>/NOTES.md` по шаблону
  из [docs/partners/README.md](../../../docs/partners/README.md). Каждое поле и путь в клиенте
  должно иметь источник в документации. Если чего-то нет в документации, это открытый вопрос,
  а не догадка.

## 1. Интерфейс в терминах нашего домена

`backend/app/integrations/<service>/base.py`:

- `Protocol` с методами, которые нужны нашим модулям (например, `list_products`, `create_order`,
  `get_order_status`), а не зеркало API партнёра;
- DTO — dataclass или Pydantic-модели. Суммы — `Decimal`, валюта явно;
- каждый метод, создающий что-то у партнёра, принимает `idempotency_key: str`;
- ошибки: `PartnerRejected` (явный отказ, деньги можно вернуть), `PartnerUnavailable`
  (запрос точно не дошёл, можно повторить), `PartnerUnknownOutcome` (таймаут или 5xx после
  отправки: исход неизвестен, нужна сверка — M6).

## 2. Выбор провайдера

- `app/config.py`: `<service>_provider: Literal["mock", "<partner>"] = "mock"`, ключи партнёра
  как `SecretStr | None`, base URL, таймаут.
- `.env.example`: те же переменные с пустыми значениями и комментарием.
- `integrations/<service>/__init__.py`: фабрика `get_<service>_client(settings)`. Если
  выбран реальный провайдер без ключей, фабрика падает при старте, а не при первом запросе.

## 3. Мок

`mock.py` реализует тот же `Protocol`: детерминированный каталог, сценарии успеха, отказа
и таймаута (например, по сумме или специальному id). Идемпотентен: повтор с тем же ключом
возвращает тот же результат. Мок — провайдер по умолчанию в local и test.

## 4. Реальный клиент (только по документации)

- `httpx.AsyncClient` с явными таймаутами (connect/read), без повторов внутри клиента: повторы
  делает фоновая задача с тем же ключом идемпотентности.
- Маппинг статусов и ошибок партнёра в наши — таблицей в NOTES.md и в коде.
- В лог — операция, id, статус, длительность. Тела запросов, ключи и ПДн не логируются (M8).
- Каждый запрос пишется в `partner_requests` (появится в T-10).

## 5. Webhook (если есть)

`webhooks.py`: проверка подписи **до** разбора тела (`hmac.compare_digest`, допуск по timestamp),
затем сохранение сырого события в `webhook_events` (UNIQUE `(provider, external_event_id)`),
затем обработка. Неверная подпись → 401, ничего не записывается (M7).

## 6. Тесты

- Контрактные тесты интерфейса, которые проходят и мок, и реальный клиент.
- Реальный клиент — через `httpx.MockTransport` с ответами из примеров документации партнёра
  (успех, отказ, таймаут, 5xx, битый JSON). Сеть в тестах запрещена.
- Webhook: верная подпись, неверная, отсутствующая, просроченный timestamp, повтор события.

## 7. Документация

Обнови статус в `docs/partners/README.md`, раздел адаптеров в `docs/architecture.md`,
решения и вопросы в `docs/decisions.md`, переменные в `.env.example`.
