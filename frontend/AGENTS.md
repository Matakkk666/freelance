# frontend/AGENTS.md

Правила кода frontend. Общие правила — в [../AGENTS.md](../AGENTS.md).

## Запуск и проверки

Из корня: `make dev-frontend` (http://localhost:5173, `/api` и `/health` проксируются на :8000),
`make frontend-lint`, `make frontend-typecheck`, `make frontend-test`, `make frontend-build`.
Из `frontend/`: `pnpm test`, `pnpm exec vitest run <file>`, `pnpm format`.

## Принципы

- **Mobile-first.** Базовые стили рассчитаны на экран 360px, широкие экраны — через
  `@media (min-width: ...)`. Приложение позже откроется как Telegram Mini App, поэтому:
  не полагаемся на hover, всплывающие окна (`window.open`) и сторонние cookies;
  учитываем `env(safe-area-inset-*)`; цвета берём только из CSS-переменных в `src/styles.css`,
  чтобы потом связать их с темой Telegram.
- **Frontend не принимает денежных решений.** Балансы, комиссии и итоги считает backend.
  Суммы приходят строками (`"12.500000"`) и отображаются без преобразования в `number`
  (M1; eslint запрещает `parseFloat`). Форматирование — через общий хелпер (появится
  с кошельком), используя `Intl.NumberFormat`, который принимает строку.
- **Права проверяет backend.** Админка — раздел `/admin` этого же приложения. Скрытие кнопок
  на клиенте нужно только для удобства, а не для защиты.
- **Дизайн не шаблонный (R-21).** Перед любой работой с интерфейсом — скилл
  [ui-design](../.agents/skills/ui-design/SKILL.md) и правила [docs/design.md](../docs/design.md).
  Собственные компоненты и CSS без UI-кита в стиле по умолчанию (D-038). Все значения — из токенов.
  Текущая стартовая страница — временная, её переделывает T-20.

## Структура

```
src/
  api/client.ts     единственное место с fetch: базовый URL, ошибки (ApiError)
  api/<domain>.ts   типизированные функции и типы ответов; типы повторяют Pydantic-схемы backend
  pages/            страницы (одна страница — один файл + тест рядом)
  components/       переиспользуемые компоненты
  lib/              утилиты без React (форматирование и т. п.)
  test/setup.ts     настройка Vitest
```

- Компоненты вызывают функции из `src/api/<domain>.ts`, а не `fetch` напрямую.
- Типы API описываются вручную рядом с функцией и повторяют схему backend (комментарий
  со ссылкой на схему). Генерацию из OpenAPI добавим, когда эндпоинтов станет много.
- Роутер (`react-router`) и библиотека запросов (TanStack Query) подключаются, когда появится
  первая задача, где они нужны, с записью в `docs/decisions.md`.
- Тексты интерфейса на русском.

## Код

- TypeScript strict + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`, eslint
  `strictTypeChecked`, prettier. `any` и небезопасные приведения запрещены.
- Импорты с расширением `.ts`/`.tsx` (как в существующем коде).
- Состояние загрузки описывается размеченным объединением (`{ kind: "loading" } | ...`),
  а не набором boolean (пример — `src/pages/HomePage.tsx`).

## Тесты

- Vitest + Testing Library, файл `*.test.tsx` рядом с компонентом.
- Проверяется то, что видит пользователь (`findByText`, `getByRole`), а не внутреннее состояние.
- Сеть подменяется через `vi.stubGlobal("fetch", ...)`, после теста — `vi.unstubAllGlobals()`.
