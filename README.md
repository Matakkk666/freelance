# Fintech MVP

Личный кабинет финтех-сервиса: внутренний кошелёк (ledger), история операций, подписки,
реферальная программа, продукты партнёров (eSIM, подарочные карты и др.) и базовая админка.

Backend: FastAPI + PostgreSQL. Frontend: React + Vite (mobile-first).
Для разработчиков и ИИ-агентов главный документ — [AGENTS.md](AGENTS.md).

## Быстрый старт

Нужны Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 24, pnpm 10 и Docker или apt
(для PostgreSQL 16).

```bash
make setup   # PostgreSQL, .env из .env.example, зависимости, миграции
make dev     # backend http://localhost:8000, frontend http://localhost:5173
make check   # линтеры, типы, тесты, сборка (то же, что в CI)
```

Проверка: `curl http://localhost:8000/health` → `{"status":"ok","database":"ok"}`.
Документация API: http://localhost:8000/docs.

Всё в Docker: `docker compose up --build` → http://localhost:8080.

## Документация

- [docs/requirements.md](docs/requirements.md) — ТЗ
- [docs/architecture.md](docs/architecture.md) — архитектура
- [docs/decisions.md](docs/decisions.md) — решения и открытые вопросы
- [docs/roadmap.md](docs/roadmap.md) — задачи
- [docs/glossary.md](docs/glossary.md) — глоссарий
