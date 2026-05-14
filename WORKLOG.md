# Work Log — SPVT (Система предвахтового тестирования)

Период: май 2026  
Репозиторий: https://github.com/DeNiS23208/SPVT  
Production: https://45-144-220-51.nip.io

---

## 1. Постановка задачи

**Цель:** веб-система, в которой каждый работник при заезде проходит тестирование, а начальник видит сводку и выгружает данные для анализа в Power BI (кто допущен к работе, кто нет).

**Решение:** MVP на FastAPI + БД + мобильный интерфейс для работника + кабинет начальника + выгрузка CSV / публичный HTTPS-эндпоинт для Power BI Service.

---

## 2. Разработка MVP (локально)

| Компонент | Содержание |
|-----------|------------|
| Backend | FastAPI, SQLAlchemy, JWT-авторизация |
| БД (dev) | SQLite (`spvt.db`), затем PostgreSQL на сервере |
| Роли | `manager`, `worker` |
| Тест | 5 вопросов, порог 80%, критические вопросы |
| Frontend | `index.html`, `worker.html`, `manager.html` — mobile-first |
| Seed | Тестовые пользователи, вопросы по ОТ и предвахтовому допуску |

**Тестовые аккаунты:**

| Логин | Пароль | Роль |
|-------|--------|------|
| `manager` | `manager123` | Начальник |
| `worker` | `worker123` | Работник (Иванов И.И.) |
| `worker2` | `worker123` | Работник (Петров П.П.) |
| `worker3` | `worker123` | Работник (Сидоров С.С.) |

---

## 3. Функции приложения

### Работник (`/worker`)
- Вход по логину/паролю
- Один тест в день (по дате смены)
- Результат: балл %, статус «Допущен» / «Не допущен»

### Начальник (`/manager`)
- Сводка по смене (дата)
- Статистика: прошли / допущены / не допущены / не начали
- Выгрузка CSV для Power BI (с JWT)
- Сброс попыток за дату (для тестирования)

### API
- `POST /api/auth/login`
- `GET /api/test/questions`, `POST /api/test/submit`
- `GET /api/manager/dashboard`
- `GET /api/manager/export/powerbi`

---

## 4. UI / брендинг

- Фон с буровой установкой на главной странице
- Логотип ИНК справа с shimmer-эффектом
- Убрана метка «SPVT MVP»
- Заголовки колонок CSV — на русском языке

---

## 5. Деплой на VPS

**Сервер:** `45.144.220.51` (Ubuntu)

| Слой | Технология |
|------|------------|
| Reverse proxy | nginx |
| App | uvicorn, systemd-сервис `spvt` |
| Конфиг | `/etc/spvt.env` |
| Код | `/opt/spvt` |

**Скрипты деплоя:** `deploy/post_deploy.sh`, `deploy/spvt.service`, `deploy/spvt.nginx`

Типичный деплой:
```bash
tar -czf spvt-deploy.tgz --exclude="__pycache__" app requirements.txt deploy scripts
scp spvt-deploy.tgz root@45.144.220.51:/opt/spvt/
ssh root@45.144.220.51 "cd /opt/spvt && tar xzf spvt-deploy.tgz && bash deploy/post_deploy.sh"
```

---

## 6. PostgreSQL

- Миграция с SQLite на PostgreSQL (`scripts/migrate_sqlite_to_postgres.py`)
- Пользователь приложения: `spvt_app`
- Read-only для аналитики: `powerbi_read`
- Представления для Power BI с русскими именами столбцов:
  - `v_powerbi_export`, `v_sotrudniki`, `v_voprosy`, `v_popytki`, `v_otvety`

---

## 7. Интеграция с Power BI

### Попытка 1 — прямое подключение к PostgreSQL
- Ошибки SSL-сертификата из облака Power BI
- Вариант с On-premises Gateway отклонён

### Решение — HTTPS CSV (Web connector)
Публичные эндпоинты (ключ в `POWERBI_EXPORT_KEY` на сервере):

| URL | Назначение |
|-----|------------|
| `/api/export/public/k/{key}/powerbi-svodka.csv` | Сводка: 1 строка = 1 попытка |
| `/api/export/public/k/{key}/powerbi.csv` | Детально: 1 строка = 1 ответ |
| `.../powerbi-svodka-today.csv` | Только текущая смена |
| `.../powerbi-today.csv` | Детально за сегодня |

**Настройка Power BI Service:**
1. Получить данные → Web → URL
2. Разделитель `;`, UTF-8
3. Опубликовать → Semantic model → Credentials: Anonymous
4. Обновлять **семантическую модель**, не только отчёт

**HTTPS:** Let's Encrypt через `45-144-220-51.nip.io` (`deploy/setup_https_export.sh`)

---

## 8. Импорт сотрудников из Excel

**Файл:** `Работники ИНКС.xlsx` (~2096 строк)  
**Колонки:** Сотрудник, Должность, Подразделение

**Реализация:**
- Поля `position`, `department` в таблице `users`
- `app/employee_import.py`, `scripts/import_employees.py`
- Логин: транслит фамилии + инициалы (`anisimov_la`)
- Пароль по умолчанию для новых: `INK2026` (env: `DEFAULT_WORKER_PASSWORD`)

**Результат импорта на сервере:**
- Создано: **2096** аккаунтов из Excel
- Всего работников: **2099** (+ 3 тестовых)
- Подразделений: **77** (буровые бригады, БПО и др.)

Файл Excel на сервере: `/opt/spvt/data/employees_ink.xlsx` (не в git)

Повторный импорт:
```bash
cd /opt/spvt
.venv/bin/python scripts/import_employees.py /opt/spvt/data/employees_ink.xlsx
```

---

## 9. Структура репозитория

```
app/
  main.py, database.py, models.py, schemas.py, auth.py, seed.py
  employee_import.py, pg_setup.py, schema_migrate.py
  routers/   — auth, test, manager, public_export
  services/  — export_csv.py
  static/    — HTML, CSS, JS, images
deploy/      — nginx, systemd, postgres, https
scripts/     — import, migrate, verify
requirements.txt
WORKLOG.md
cursor_.md   — экспорт переписки из Cursor
```

---

## 10. Git

| Дата | Действие |
|------|----------|
| 2026-05-14 | Первый push: MVP, деплой, импорт, Power BI export |
| 2026-05-14 | Work log + экспорт переписки (`cursor_.md`) |

**Не коммитится:** `spvt.db`, `data/*.xlsx`, `*.tgz`, `.env`, `.venv`, `__pycache__/`

---

## 11. Известные ограничения / дальнейшие шаги

- Кабинет начальника загружает список всех ~2100 работников — может потребоваться фильтр по подразделению/пагинация
- Пароли сотрудников единые (`INK2026`) — для продакшена нужна политика смены пароля или SSO
- Секреты (`SECRET_KEY`, `POWERBI_EXPORT_KEY`, пароли БД) только в `/etc/spvt.env` на сервере
- База вопросов пока seed из кода — планируется отдельная БД вопросов

---

## 12. Полезные ссылки

- Сайт: https://45-144-220-51.nip.io
- GitHub: https://github.com/DeNiS23208/SPVT
- Переписка по проекту: `cursor_.md`
