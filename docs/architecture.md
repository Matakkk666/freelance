# Архитектура

Описывает целевую архитектуру MVP. Сейчас (после T-01) реализован только каркас:
конфиг, БД, миграции, `/health`, стартовая страница. Разделы о модулях описывают то, как
их нужно строить. При реализации сверяйся с этим документом и обновляй его, если решение
меняется (с записью в [decisions.md](decisions.md)).

## 1. Общая схема

```
 Браузер / Telegram WebView
          │  HTTPS (JSON)
          ▼
 ┌─────────────────────┐        ┌─────────────────────┐
 │ frontend (SPA)      │        │ worker              │  тот же код backend,
 │ React: кабинет +    │        │ фоновые задачи      │  отдельный процесс
 │ /admin              │        └──────────┬──────────┘
 └─────────┬───────────┘                   │
           │ /api/v1, /health              │
           ▼                               ▼
 ┌─────────────────────┐        ┌─────────────────────┐
 │ api (FastAPI)       │───────▶│ PostgreSQL          │  данные, ledger,
 │ модульный монолит   │        │                     │  очередь задач
 └─────────┬───────────┘        └─────────────────────┘
           │ адаптеры (httpx)
           ▼
 Партнёры: криптопроцессинг, виджет обмена RUB → USDT, eSIM, подарочные карты, (этап 2) криптокарты, VPN
```

- **Модульный монолит.** Один репозиторий, один backend, одна БД. Модули разделены пакетами
  и явными зависимостями, а не сетью.
- **Процессы:** `api` (uvicorn) и `worker` (`python -m app.workers`, появится в T-05).
  Оба используют одну кодовую базу и одну БД.
- **Хранилище:** только PostgreSQL. Очередь фоновых задач тоже в нём (решение D-012).

## 2. Модули backend

| Модуль | Пакет | Отвечает за | Зависит от |
|---|---|---|---|
| Ledger | `modules/ledger` | валюты, счета, проводки, резервы, балансы | — |
| Auth / Users | `modules/auth` | пользователи, способы входа, токены, роли | — |
| Audit | `modules/audit` | журнал действий админов и важных событий | auth |
| Jobs | `workers/` + `modules/jobs` | очередь задач, планировщик, повторы | — |
| Wallet | `modules/wallet` | пополнения, входящие webhook процессинга, история операций | ledger, integrations.processing |
| Billing | `modules/billing` | тарифы, функции тарифов, комиссии, подписки, продление | ledger, jobs |
| Referrals | `modules/referrals` | коды, привязка приглашённых, правила, вознаграждения | ledger, auth |
| Orders | `modules/orders` | каталог продуктов партнёров, заказы, поток покупки, сверка | ledger, billing (комиссии), integrations.* |
| Admin | `modules/admin` | эндпоинты админки поверх сервисов других модулей | все + audit |
| Integrations | `integrations/<service>` | адаптеры внешних сервисов | — |

Правило: модуль вызывает сервисные функции другого модуля, а не пишет в его таблицы.
Писать в таблицы ledger может только ledger (M2).

## 3. Ledger (внутренний кошелёк)

Двойная запись: каждая денежная операция — это `ledger_transaction` с набором проводок
(`ledger_entries`), сумма которых в каждой валюте равна нулю. Баланс счёта — денормализованная
сумма его проводок, обновляется в той же транзакции БД.

### Таблицы

```
currencies(code PK, precision)                          -- 'USDT', 6

accounts(
  id UUID PK,
  owner_type  'user' | 'system',
  user_id     UUID NULL FK users,                        -- NULL для системных счетов
  kind        'available' | 'reserved' | <системный вид>,
  currency    FK currencies,
  balance     NUMERIC(38,18) NOT NULL DEFAULT 0,
  allow_negative BOOL NOT NULL DEFAULT false,
  created_at,
  UNIQUE (user_id, kind, currency),                      -- для пользовательских
  UNIQUE (kind, currency) WHERE owner_type = 'system',
  CHECK (allow_negative OR balance >= 0)                 -- M4
)

ledger_transactions(
  id UUID PK,
  kind            'deposit' | 'hold' | 'capture' | 'release' | 'subscription_charge'
                  | 'referral_reward' | 'adjustment' | 'reversal' | ...,
  idempotency_key TEXT NOT NULL UNIQUE,                   -- M5
  reference_type  TEXT NULL, reference_id UUID NULL,      -- 'order', 'deposit', 'subscription', ...
  reason          TEXT NULL,                              -- обязателен для adjustment/referral (M9)
  created_by      UUID NULL,                              -- инициатор: админ или NULL = система
  reverses_id     UUID NULL FK ledger_transactions,        -- для сторно (M12)
  created_at
)

ledger_entries(
  id UUID PK,
  transaction_id FK ledger_transactions,
  account_id     FK accounts,
  amount         NUMERIC(38,18) NOT NULL CHECK (amount <> 0),   -- + приход, − расход
  currency       FK currencies,                                  -- = валюта счёта
  created_at
)
-- deferred constraint trigger: SUM(amount) по transaction_id и currency = 0 (M3)
-- триггер/права: UPDATE и DELETE на ledger_* запрещены (M12)
```

Точность: `NUMERIC(38,18)` хранит любую валюту, суммы квантуются до `currencies.precision`
при создании проводки (M1).

На запуске одна валюта — USDT. Позже добавляется EUR (R-18, D-032): новая строка в `currencies`
и счета пользователя и системы в этой валюте. Конвертация между валютами, если понадобится,
проектируется в T-19 (Q-19).

### Счета

У каждого пользователя в каждой валюте два счёта:

- `available` — доступный баланс, его пользователь видит как «баланс»;
- `reserved` — средства, зарезервированные под незавершённые покупки.

Системные счета (по одному на валюту, `allow_negative` там, где указано):

| kind | Назначение | allow_negative |
|---|---|---|
| `processing_clearing` | зеркало средств у криптопроцессинга: пополнение = списание отсюда | да |
| `partner_payable` | долг перед партнёрами за купленные товары | нет |
| `revenue_subscriptions` | выручка от подписок | нет |
| `revenue_fees` | комиссии | нет |
| `referral_expense` | расходы на реферальные вознаграждения | да |
| `adjustments` | ручные корректировки | да |

### Типовые проводки (USDT)

| Операция | Проводки |
|---|---|
| Пополнение 100 | `processing_clearing −100`, `user.available +100` |
| Резерв под покупку 25 + комиссия 1 | `user.available −26`, `user.reserved +26` |
| Списание после успеха | `user.reserved −26`, `partner_payable +25`, `revenue_fees +1` |
| Снятие резерва после отказа | `user.reserved −26`, `user.available +26` |
| Оплата подписки 10 | `user.available −10`, `revenue_subscriptions +10` |
| Реферальное вознаграждение 2 | `referral_expense −2`, `referrer.available +2` (reason, created_by) |
| Ручная корректировка +5 | `adjustments −5`, `user.available +5` (reason, created_by = админ) |
| Сторно операции X | те же проводки с обратным знаком, `reverses_id = X` |

### API сервиса ledger (T-02)

- `post_transaction(session, *, kind, idempotency_key, entries, reference=None, reason=None, created_by=None)`:
  проверяет сумму ноль (M3) и квантование, блокирует счета `FOR UPDATE` по возрастанию id (M4),
  вставляет проводки, обновляет балансы. Повтор с тем же ключом и теми же параметрами
  возвращает существующую транзакцию, с другими параметрами — ошибку (M5). Commit не делает.
- Производные: `hold`, `capture`, `release`, `deposit`, `adjust`, `reverse`.
- `get_balance`, `list_entries(user, cursor)` — для истории операций.

Контроль целостности: периодическая задача сверяет `accounts.balance` с суммой проводок
и пишет в лог (а позже — алерт) при расхождении.

## 4. Поток покупки у партнёра

Статусы заказа (`orders.status`):

```
created ─▶ reserved ─▶ submitted ─┬─▶ completed    (списание)
                                  ├─▶ failed       (снятие резерва)
                                  └─▶ processing ─▶ completed | failed   (после сверки)
```

1. **Транзакция 1:** создать заказ (цена и комиссия фиксируются в заказе из текущих настроек
   тарифа), `hold` на сумму + комиссию, статус `reserved`, commit. Недостаточно средств —
   ошибка `insufficient_funds`, заказ не создаётся.
2. **Вызов партнёра** вне транзакции (M6) с ключом идемпотентности, равным id заказа
   (если партнёр поддерживает). Запрос и ответ (без ПДн и секретов) пишутся в `partner_requests`.
3. **Транзакция 2:**
   - успех → `capture`, статус `completed`, сохранить выданный товар (данные eSIM, код карты;
     чувствительные данные шифруются или хранятся у партнёра);
   - явный отказ → `release`, статус `failed`;
   - таймаут, 5xx, непонятный ответ → статус `processing`, задача `order.reconcile`.
4. **Сверка** (`order.reconcile`): запрашивает статус у партнёра с backoff и доводит заказ до
   `completed`/`failed`. После N неудачных попыток заказ остаётся `processing` и попадает
   в админку для ручного разбора. **Автоматического возврата нет** (D-003).

Webhook партнёра о статусе заказа (если есть) обрабатывается так же, как результат сверки,
идемпотентно.

## 5. Пополнение через криптопроцессинг

1. Пользователь запрашивает пополнение → адаптер `processing` создаёт инвойс или адрес.
   Запись `deposits` (status `pending`).
2. Процессинг присылает webhook → проверка подписи (M7) → сохранение сырого события
   в `webhook_events` (UNIQUE `(provider, external_event_id)`, M5) → ответ 200.
3. Обработка события (сразу или задачей): при подтверждении — `deposit` в ledger
   с `idempotency_key = "deposit:<provider>:<external_id>"`, статус `credited`.
   Повторный webhook не создаёт второго начисления.
4. Периодическая сверка висящих `pending` с процессингом.

Минимальная сумма, комиссия пополнения и число подтверждений — настройки в БД (M11).
Вывод средств пока не входит в этап 1 (открытый вопрос Q-03).

**Виджет обмена RUB → USDT** (R-07, D-031): сторонний виджет на экране пополнения. Пользователь
платит рубли внутри виджета, виджет отправляет USDT на адрес или инвойс пополнения этого
пользователя (шаг 1). Дальше работает обычный поток: webhook процессинга → `deposit` в ledger.
Виджет не пишет в ledger напрямую. Если провайдер виджета присылает свои webhook, они
используются только для отображения статуса, а не для начисления. Пересматривается после
ответа на Q-18.

## 6. Адаптеры партнёров

```
app/integrations/<service>/
  base.py      Protocol интерфейса + доменные DTO + ошибки (PartnerRejected, PartnerUnavailable, PartnerUnknownOutcome)
  mock.py      мок: детерминированное поведение, сценарии успеха, отказа и таймаута для тестов и демо
  <partner>.py реальный клиент по docs/partners/<partner>/ (httpx.AsyncClient, таймауты)
  webhooks.py  проверка подписи и разбор webhook (если есть)
  __init__.py  фабрика get_<service>_client(settings) по <SERVICE>_PROVIDER
```

Сервисы: `processing` (криптопроцессинг), `esim`, `giftcards`, `cards` (криптокарты, этап 2),
`vpn` (этап 2, объём зависит от Q-17). KYC не проводим (D-029), адаптера `kyc` нет.
Интерфейс описывается в терминах нашего домена
(«выпустить eSIM по плану X»), а не партнёра, чтобы замена поставщика не трогала модули.
Общие таблицы: `partner_requests` (журнал исходящих запросов: сервис, операция, ключ
идемпотентности, статус, длительность, код ошибки) и `webhook_events`.

Пошагово: [.agents/skills/add-partner-integration/SKILL.md](../.agents/skills/add-partner-integration/SKILL.md).

## 7. Подписки и тарифы

```
plans(id, code 'standard'|'plus'|'premium', name, price, currency, period_days, is_active, sort_order)
plan_features(plan_id, feature_key, value JSONB)           -- например esim_discount_percent, max_cards
fee_rules(id, plan_id NULL, product_type, fee_type 'percent'|'fixed', value, min_fee, currency)
subscriptions(id, user_id, plan_id, status 'active'|'past_due'|'cancelled'|'expired',
              current_period_start, current_period_end, auto_renew, created_at)
```

- Все значения — данные в БД, seed в миграции, редактирование в админке с аудитом (M10, M11).
- Проверка возможностей только через сервис: `billing.get_entitlements(user)` →
  `has_feature(key)` / `get_limit(key)`. Код модулей не сравнивает названия тарифов.
- Комиссия заказа считается `billing.calculate_fee(user, product_type, amount)` и фиксируется
  в заказе.
- Оплата — операция ledger `subscription_charge` с ключом `subscription:<id>:<period_start>`.
- Продление — задача `subscription.renew` за период до `current_period_end`. Не хватает денег —
  статус `past_due` и повторные попытки в течение льготного периода (настройка), затем `expired`.
- Смена тарифа, пропорциональный пересчёт, бесплатен ли «Стандарт» — открытые вопросы (Q-07).

## 8. Реферальная программа

```
referral_codes(user_id UNIQUE, code UNIQUE)                -- создаётся при регистрации
referrals(referred_user_id UNIQUE, referrer_user_id, code, created_at)  -- привязка неизменяема
referral_rules(id, event 'first_deposit'|'subscription_payment'|'order_completed',
               reward_type 'fixed'|'percent', value, currency, max_reward, hold_days,
               is_active, valid_from, valid_to)
referral_rewards(id, referrer_user_id, referred_user_id, rule_id, source_type, source_id,
                 amount, status 'pending'|'credited'|'cancelled', ledger_transaction_id,
                 UNIQUE(rule_id, source_type, source_id))
```

- Ссылка вида `https://<host>/?ref=<code>`, код сохраняется на клиенте до регистрации
  и передаётся в запросе регистрации. Привязка только при регистрации, самоприглашение
  запрещено. Уровень один.
- Событие-источник (оплата подписки, первое пополнение и т. п.) создаёт `referral_reward`
  по активным правилам. Начисление — проводка ledger `referral_reward` с `reason`
  и ключом `referral:<reward_id>` (M9). При `hold_days > 0` начисление делает фоновая задача.
- Вознаграждения начисляются на постоянной основе (D-033): привязка приглашённого бессрочна,
  правило начисляет награду за каждое подходящее событие, пока оно активно. Ограничения
  по сроку на приглашённого нет, `valid_from`/`valid_to` ограничивают только действие самого правила.
- Пользователь видит код, ссылку, число приглашённых и историю вознаграждений.

## 9. Авторизация и админка

- Пользователь и способы входа разделены: `users` + `user_identities(provider 'email'|'telegram', ...)`,
  чтобы добавить вход через Telegram без переделки (D-018).
- Роли: `user`, `admin` (позже, возможно, `support`). Проверка прав — зависимость FastAPI
  на backend. Эндпоинты админки — `/api/v1/admin/*`.
- Журнал аудита: `audit_log(id, actor_user_id, action, target_type, target_id, before JSONB,
  after JSONB, ip, user_agent, created_at)` пишется в той же транзакции (M10).
- Админка MVP: пользователи (поиск, просмотр баланса и операций), ручная корректировка
  через ledger, тарифы и комиссии, правила рефералки, заказы в `processing`, журнал аудита.

## 10. Фоновые задачи

Очередь в PostgreSQL (D-012):

```
jobs(id, kind, payload JSONB, status 'queued'|'running'|'done'|'failed',
     run_at, attempts, max_attempts, locked_until, last_error, dedup_key UNIQUE NULL, created_at)
```

- Воркер берёт задачи `SELECT ... WHERE status='queued' AND run_at <= now() FOR UPDATE SKIP LOCKED`.
  Если воркер упал, задача с истёкшим `locked_until` берётся снова. Ошибки ведут к повтору
  с экспоненциальной задержкой до `max_attempts`, затем `failed` и видимость в админке.
- Обработчики идемпотентны: задача может выполниться дважды.
- Периодические задачи (планировщик в том же воркере): `subscription.renew_due`,
  `order.reconcile_processing`, `deposit.reconcile_pending`, `referral.credit_due`,
  `ledger.verify_balances`.
- Повторы запросов к партнёрам — задачи `partner.retry` с тем же ключом идемпотентности.

## 11. Безопасность

- Секреты — env и `SecretStr` (M8). ПДн маскируются в логах (`app/logging.py`).
- Webhook: подпись до обработки (M7), лимит размера тела.
- Пароли: argon2. Rate limiting на вход, регистрацию и денежные эндпоинты (T-03).
- CORS — только разрешённые origin (`CORS_ORIGINS`).
- Данные товаров (коды подарочных карт и т. п.) показываются только владельцу.

## 12. Frontend

SPA на React, mobile-first. Разделы: `/` (главная и баланс), `/wallet` (пополнение),
`/history`, `/subscription`, `/referrals`, `/shop` (eSIM, подарочные карты), `/profile`,
`/admin/*`. Все данные только через `/api/v1`. Подробнее — [frontend/AGENTS.md](../frontend/AGENTS.md).

## 13. Окружения и деплой

- Локально и в песочнице агента: `make setup`, `make dev`.
- `docker-compose.yml`: `db`, `backend` (миграции при старте), `frontend` (nginx со статикой
  и прокси `/api`, `/health`). Сервис `worker` добавится в T-05.
- Хостинг не выбран (Q-12). Конфигурация целиком через env.
