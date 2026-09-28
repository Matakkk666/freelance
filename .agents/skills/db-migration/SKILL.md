---
name: db-migration
description: How to change the database schema with Alembic in this repo (models, autogenerate, review, seeds, tests). Use for any new table, column, index, constraint or seed data.
---

# Миграция БД

1. Измени или добавь модели в `backend/app/modules/<name>/models.py` и импортируй модуль
   в `backend/app/models.py`. Без этого Alembic не увидит таблицу.
2. Убедись, что БД на последней ревизии: `make migrate`.
3. Создай миграцию со следующим номером (посмотри последний в `backend/migrations/versions/`):
   `make migration name="add ledger" rev=0002`.
4. **Прочитай сгенерированный файл и поправь руками.** Autogenerate не видит или делает неверно:
   - `CHECK`-ограничения, триггеры, функции, частичные уникальные индексы — дописываются через
     `op.create_check_constraint`, `op.execute(...)`;
   - `server_default` и переименования (autogenerate превращает переименование в drop + add
     с потерей данных);
   - seed-данные (валюты, тарифы, системные счета) — `op.bulk_insert` в той же миграции (M11).
5. `downgrade()` обязателен и полностью откатывает `upgrade()`, включая триггеры и seed.
6. Проверь: `cd backend && uv run pytest tests/test_migrations.py` (upgrade → downgrade → upgrade
   и `alembic check`: схема совпадает с моделями), затем `make check`.

Правила:

- Миграции из `main` не редактируются. Ошибку исправляет новая миграция.
- Имена ограничений задаёт naming convention в `app/db.py`, руками их не придумывай.
- Деньги — `sa.Numeric(38, 18)`, время — `sa.DateTime(timezone=True)`, id — `sa.Uuid`,
  перечисления — `sa.String` + `CHECK` (D-016).
- Долгие операции на больших таблицах (индексы, заполнение данных) — отдельной миграцией,
  с оценкой блокировок в описании PR.
