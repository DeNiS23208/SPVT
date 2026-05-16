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
| `admin` | `admin123` | Администратор (настройки сайта, вопросы) |
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
- `GET /api/public/site-settings` — публичные настройки внешнего вида (без авторизации)
- `GET/PUT /api/admin/settings`, `POST /api/admin/upload/background`, `POST /api/admin/upload/logo`, CRUD `/api/admin/questions` — только роль `admin`
- Роль `admin` также имеет доступ к эндпоинтам менеджера (сводка, CSV, сброс)

---

## 4. UI / брендинг

- Фон главной настраивается из БД; без «мигания» старой картинки: главная `/` отдаётся **шаблоном** `app/templates/index.html` с встроенным в `<head>` фоном и `preload` изображений
- Логотип ИНК справа с **shimmer** (блик по маске логотипа; слой блика поверх `img`, `mix-blend-mode: overlay`)
- Подхват настроек в браузере: `app/static/js/site_settings.js`
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

**Скрипты деплоя:** `deploy/post_deploy.sh`, `deploy/spvt.service`, `deploy/spvt.nginx`, `deploy/spvt.nginx.ssl`

**nginx:** для загрузки картинок в админке задано `client_max_body_size 25M;` (иначе ошибка **413** на больших PNG).

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
  templates/index.html   — главная страница (Jinja2, настройки из БД в первом кадре)
  routers/   — auth, test, manager, admin, public, public_export
  services/  — export_csv.py, site_settings.py, image_optimize.py
  static/    — worker.html, manager.html, css, js, images (без index.html — см. templates)
spvt-admin/  — десктоп-админка macOS (PySide6): сводка, настройки, вопросы; сборка .app через PyInstaller
deploy/      — nginx, systemd, postgres, https
scripts/     — import, migrate, verify, rebuild_ink_logo.py
requirements.txt   — включая Pillow (сжатие загрузок)
WORKLOG.md
```

**Экспорт переписки из Cursor:** файл в корне репозитория (например `cursor_.md` или `cursor_cursor_md.md`) — для продолжения работы на другом ПК; в git по желанию или в `.gitignore`.

---

## 10. Git

| Дата | Действие |
|------|----------|
| 2026-05-14 | Первый push: MVP, деплой, импорт, Power BI export |
| 2026-05-14 | Work log + экспорт переписки (`cursor_.md`) |
| 2026-05-14 (вечер) | Admin API, десктоп-админка, оптимизация медиа, главная через шаблон, логотип и блик — см. **раздел 13** |

**Не коммитится:** `spvt.db`, `data/*.xlsx`, `*.tgz`, `.env`, `.venv`, `__pycache__/`, `spvt-admin/build`, `spvt-admin/dist`

---

## 11. Известные ограничения / дальнейшие шаги

- Кабинет начальника загружает список всех ~2100 работников — может потребоваться фильтр по подразделению/пагинация
- Пароли сотрудников единые (`INK2026`) — для продакшена нужна политика смены пароля или SSO
- Секреты (`SECRET_KEY`, `POWERBI_EXPORT_KEY`, пароли БД) только в `/etc/spvt.env` на сервере
- Вопросы теста редактируются через админку/API; при желании — отдельная политика версий вопросов

---

## 12. Полезные ссылки

- Сайт: https://45-144-220-51.nip.io
- GitHub: https://github.com/DeNiS23208/SPVT
- Переписка по проекту: **`cursor_cursor_md.md`** в корне репозитория (см. **§ 16.10**)

---

## 13. Доработки 14 мая 2026 (вечер) — админка, медиа, UX главной

### 13.1 Роль `admin` и настройки сайта

- В `UserRole` добавлено значение `admin`; пользователь **`admin` / `admin123`** создаётся в `seed.py`.
- Таблица **`site_settings`** (ключ–значение), миграция в `schema_migrate.py`, enum PostgreSQL дополняется при старте.
- Сервис `app/services/site_settings.py`: дефолты (заголовок, подзаголовок, URL фона/логотипа, оверлей, акцент, порог прохождения).
- Порог прохождения теста читается из БД в `app/routers/test.py` (`get_pass_threshold`).
- Роутер **`app/routers/admin.py`**: настройки, загрузка фона/логотипа, CRUD вопросов.
- Роутер **`app/routers/public.py`**: `GET /api/public/site-settings` для фронта без JWT.
- Эндпоинты менеджера принимают и **`admin`** (`manager.py`).

### 13.2 Оптимизация загрузок изображений

- Зависимость **`Pillow`**; модуль **`app/services/image_optimize.py`**.
- После загрузки: **фон** → WebP, ширина до 1920px, качество ~84; **логотип** → PNG с альфой, ширина до 960px (стабильная маска для CSS).
- На сервере тяжёлый PNG фона (~2.6 МБ) пересобран в **WebP ~300 КБ** (`hero-bg-*-opt.webp`), в БД обновлён URL.

### 13.3 nginx

- В конфиг добавлено **`client_max_body_size 25M`** (устранение **413** при загрузке больших PNG).

### 13.4 Главная страница без «мигания» старого фона

- **`/`** отдаёт **`Jinja2Templates`** (`app/templates/index.html`): в `<head>` встроены фон, оверлей, акцент, заголовки, `src` логотипа и **`rel="preload"`** для фона и логотипа из текущих настроек БД.
- Из **`app/static/css/style.css`** убран захардкоженный фон у `body.page-home` (остаётся только `background-color` до стилей из шаблона).
- Статический **`app/static/index.html`** удалён (главная только через шаблон).

### 13.5 Логотип ИНК и блик

- Пересборка **`ink-logo.png`** из оригинала: фон убирается по правилу **низкая яркость + низкая насыщенность**, чтобы **не съедать тёмно-серые «лепестки»**.
- Скрипт **`scripts/rebuild_ink_logo.py`** (нужен `numpy`) для повторной сборки из файла-оригинала.
- **Shimmer:** псевдоэлемент `::before` с **`z-index` выше**, чем у `img`, чтобы блик был виден на непрозрачных частях; маска по `--logo-mask` (в **`site_settings.js`** для маски используется **pathname без query**).
- Лёгкая подсветка за блоком логотипа (радиальный градиент в CSS).

### 13.6 Десктоп-админка (macOS)

- Папка **`spvt-admin/`**: PySide6, вкладки **Сводка** (manager + admin), **Настройки сайта** и **Вопросы** (только admin).
- Запуск: `spvt-admin/run.sh`; сборка **`.app`**: `spvt-admin/build_mac.sh` → `spvt-admin/dist/SPVT Admin.app` (PyInstaller, `SPVT-Admin.spec`).
- Клиент **`requests`**: для загрузок задаётся корректный MIME; при **413** — понятное сообщение.

### 13.7 Прочее

- Загрузка фона: сервер принимает и **`application/octet-stream`**, если по расширению файла MIME угадывается как изображение (`admin.py`).
- **`site_settings.js`:** при совпадении URL фона с `data-hero-url` с сервера не перерисовывать фон повторно после fetch (меньше мигания).

### 13.8 Деплой на сервер в этот день

- Обновления на **`45.144.220.51`**: `tar` + `deploy/post_deploy.sh`, отдельные `scp` для статики при необходимости.

---

## 14. Доработки 15 мая 2026 — вход по подразделениям, ~2100 сотрудников, один админ

### 14.1 Импорт и синхронизация с Excel

- Источник: **`Работники ИНКС.xlsx`** (~2096 строк, 77 подразделений).
- Модули: `app/employee_import.py`, `app/employee_sync.py`, `app/name_utils.py` (нормализация ФИО, `ё`→`е`).
- Скрипты:
  - `scripts/import_employees.py` — первичный импорт;
  - `scripts/sync_employees_from_excel.py` — пересинхронизация должности/подразделения (`--no-create` на деплое);
  - `scripts/audit_excel_exact_match.py`, `scripts/report_department_mismatches.py`, `scripts/compare_dept_counts.py` — проверка БД vs Excel.
- На продакшене после сверки: **0 расхождений** по подразделению при точном совпадении ФИО.
- Файл на сервере: `/opt/spvt/data/employees_ink.xlsx` (в git не коммитится).

### 14.2 Логины и пароли

- Пароль для всех работников: **`123`** (`app/usernames.py`, `DEFAULT_PASSWORD`).
- Логин кириллицей: **`фамилия_инициалы`** (`username_from_name()`), например `гуляев_дм`.
- Скрипт `scripts/apply_auth_policy.py` — массовая смена логинов.
- Удалены тестовые работники: `scripts/remove_test_users.py` (в `post_deploy.sh`).

### 14.3 Главная страница — вход работника

- **`app/templates/index.html`**: выбор **подразделение → ФИО** → пароль.
- **`app/static/js/login.js`**: загрузка `/api/public/departments`, `/api/public/department-workers`.
- **`app/routers/auth.py`**: поле `department` при логине; проверка в `authenticate_user()`.
- Убраны карточки тестовых аккаунтов и кнопка «Вход для начальника или администратора».
- Убраны подписи «ИНК-СЕРВИС» под/над логотипом (только картинка логотипа справа).

### 14.4 Один администратор

- **`app/admin_account.py`**, `scripts/ensure_single_admin.py` (в `post_deploy.sh`).
- Единственный админ: **Гуляев Денис Михайлович** — логин **`гуляев_дм`**, пароль **`123`**, подразделение «Отдел АСУП (месторождение)».
- Удалены служебные учётки `админ` / `начальник`; остальные роли `admin`/`manager` понижены до `worker`.
- Вход админа на сайте: подразделение АСУП → своё ФИО → `/manager`.
- **SPVT-Admin (Windows):** логин `гуляев_дм` / `123`, только роль `admin`.

### 14.5 Эксперимент с логотипом «ИНК-СЕРВИС» (откат, май 2026)

- Попытка заменить в PNG текст «Иркутская нефтяная компания» на «ИНК-СЕРВИС» (`scripts/relabel_ink_logo.py`, `ink-logo-inkservice.png`).
- Проблемы: наложение текста на значок; **двойной логотип** (фон с животными содержит «ИНК» в сердце + отдельный PNG справа).
- **Откат** (`scripts/rollback_site_media.py`): снова `ink-logo.png` + `hero-bg-d7b69497f2-opt.webp`.

### 14.6 Логотип «ИНК-СЕРВИС» — финальная версия (15 мая 2026)

- Утверждён логотип, подготовленный вручную: эмблема ИНК + надпись **«ИНК-СЕРВИС»** справа, без наложения на лепестки.
- Файл: **`app/static/images/ink-logo.png`** (~19 КБ, прозрачный фон: тёмные пиксели фона вырезаны для корректного блика).
- На главной: блок **`.logo-shine`**, анимация **`logo-shimmer`** (белый блик по маске PNG) — без изменений в CSS.
- Сброс кэша браузера: `?v=10` в `index.html` и `site_settings.js`.
- Production: залито на `45.144.220.51`, `logo_url` в БД: `/static/images/ink-logo.png`.

### 14.7 Текущее состояние production

| Параметр | Значение |
|----------|----------|
| Сайт | https://45-144-220-51.nip.io |
| Работников в БД | ~2096 |
| `logo_url` | `/static/images/ink-logo.png` (ИНК-СЕРВИС, прозрачный PNG) |
| `hero_background_url` | `/static/images/hero-bg-d7b69497f2-opt.webp` |
| Админ | `гуляев_дм` / `123` |
| Кэш логотипа на главной | `?v=10` |

### 14.8 Деплой (типовой, май 2026)

```bash
tar -czf spvt-deploy.tgz --exclude="__pycache__" --exclude=".venv" --exclude="spvt-admin" --exclude="*.db" --exclude="data" app requirements.txt deploy scripts
scp spvt-deploy.tgz root@45.144.220.51:/opt/spvt/
ssh root@45.144.220.51 "cd /opt/spvt && tar xzf spvt-deploy.tgz && bash deploy/post_deploy.sh"
```

`post_deploy.sh` дополнительно: `remove_test_users.py` → `sync_employees_from_excel.py` (если есть xlsx) → `ensure_single_admin.py`.

### 14.9 Переписка (Cursor)

- Полный экспорт чата (май 2026): **`cursor_cursor_md.md`** в корне репозитория (обновляется при крупных сессиях).
- Краткий лог сессии 15.05.2026: **`docs/CHAT_LOG_2026-05-15.md`**.
- ID транскрипта агента (в Cursor): `09e5edee-5876-4c0b-8d91-f1de3ca5dda4`.

---

## 16. Доработки 16 мая 2026 — несколько тестов, билеты, кабинет начальника, случайный билет

### 16.1 Несколько типов тестов и билеты

- Модель **`TestType`** (slug, title, description, `is_active`, sort_order); вопросы и попытки привязаны к `test_type_id`.
- Модель **`TestTicket`** — билеты внутри теста; у вопроса поле **`ticket_id`**.
- Миграции в **`app/schema_migrate.py`**: таблицы билетов, `ticket_id` у попыток (`TestAttempt.ticket_id`), статус **`reset`** для пересдачи.
- Сервисы:
  - **`app/services/test_types.py`** — slug, каталог для работника, последняя попытка;
  - **`app/services/test_tickets.py`** — backfill «Билет 1», **`balance_questions_across_tickets()`** (если все вопросы в одном билете при нескольких билетах — разнести по кругу);
  - **`app/services/attempt_tickets.py`** — **`pick_random_ticket()`** (`secrets.choice`), восстановление билета по ответам, backfill `ticket_id` у старых попыток.
- **`app/seed.py`**: типы `gnvp`, `pdd`; при старте — backfill билетов и балансировка вопросов.

### 16.2 Работник — выбор теста и случайный билет

- **`/worker`** — хаб выбора теста (`worker_hub.js`, `worker.html`).
- **`/worker/test?type=<slug>`** — прохождение (`worker_test.js`, `worker_test.html`).
- API: `GET /api/test/catalog`, `GET /api/test/status`, `GET /api/test/questions`, `POST /api/test/submit` с параметром **`test_type`**.
- При **первом заходе** на вопросы создаётся попытка за смену и назначается **случайный билет** (только билеты с активными вопросами).
- Порядок вопросов в билете **перемешивается** по `attempt.id` (стабильно при обновлении страницы).
- После **сброса** начальником — новый случайный билет, по возможности **не тот же**, что был.
- **Исправление (16.05):** у теста `gnvp` все 8 вопросов были в «Билете 1», «Билет 2» пустой — все работники получали один билет; на production вопросы разнесены **4+4**, логика выбора усилена.

### 16.3 Кабинет начальника

- Карточки статистики на **`/manager`** кликабельны → **`/manager/workers`** с фильтром (`all` / `ready` / `not_ready` / `not_started`) и датой смены.
- **`GET /api/manager/workers`** — пагинация (50/стр.), поиск по ФИО, фильтры: подразделение, должность, тест, дата.
- **`GET /api/manager/workers/filter-options`** — справочники для фильтров.
- В таблице результатов колонка **«Билет»** (`attempt_ticket_label`).
- Управление тестами: карточки с числом вопросов/билетов, переключатель **Активен / Неактивен** (`PATCH /api/manager/test-types/{slug}`).
- CRUD билетов и вопросов: **`/manager/test-questions`**, **`/manager/test-new`**.
- Модальные подтверждения вместо `confirm()` — **`confirmDialog()`** в `app.js` (удаление теста, сброс попытки, массовый сброс, деактивация).
- Сброс попытки: в статусе показываются **дата и время** (`formatDateIrkutskShortWithTime`).
- Убрана дублирующая кнопка «+ Добавить тест» в верхней панели.

### 16.4 Импорт теста ПРВТ из Word

- Скрипт **`scripts/import_prvt_gnvp_from_docx.py`**: парсинг `.docx`, тест **«Тест по ГНВП для ПРВТ»**, slug **`gnvp_prvt`**, разбивка на N билетов (на prod: **5×5** вопросов, seed `20260516`).
- **`app/services/question_import.py`** — общая логика импорта вопросов.

### 16.5 Вход работника — исправление

- **`login.js`**: убрана ошибка **`help is not defined`** (лишний вызов в цикле загрузки сотрудников) — из‑за неё не подгружался список ФИО на главной.

### 16.6 UI / стили

- Стили поиска и фильтров на странице работников; карточки тестов (`test-card-metric`); оформление `input[type="search"]` как у остальных полей.
- Версии кэша статики подняты в HTML (`app.js`, `manager_tests.js`, `style.css` и др.).

### 16.7 SPVT-Admin (десктоп)

- Вкладка вопросов: поддержка нескольких типов тестов / билетов (`questions_tab.py`, `question_dialog.py`).

### 16.8 Production (16.05.2026)

| Параметр | Значение |
|----------|----------|
| Тесты | `gnvp` (2 билета × 4 вопроса), `gnvp_prvt` (5×5), `pdd`, … |
| Деплой | `tar` каталога `app/` → `/opt/spvt`, `systemctl restart spvt` |
| Балансировка `gnvp` | 4 вопроса перенесены на «Билет 2» |

### 16.9 Новые и изменённые файлы (ориентир)

| Область | Файлы |
|---------|--------|
| API тест / менеджер | `app/routers/test.py`, `manager.py`, `schemas.py`, `models.py` |
| Сервисы | `attempt_tickets.py`, `test_tickets.py`, `test_types.py`, `worker_lookup.py`, `question_import.py` |
| Работник (статика) | `worker_hub.js`, `worker_test.js`, `worker_test.html`, `worker.html` |
| Начальник (статика) | `manager_tests.js`, `manager_workers.js`, `manager_test_*.html/js` |
| Скрипты | `scripts/import_prvt_gnvp_from_docx.py` |

### 16.10 Переписка (Cursor, сессия 16.05.2026)

- Полный экспорт диалога по доработкам мая 2026: **`cursor_cursor_md.md`** (коммитится в репозиторий).
- Темы в переписке: статистика и список работников, билеты в результатах, модальные окна, импорт ПРВТ, **случайный билет** при прохождении теста.

---

## 15. Актуальные учётные данные (не коммитить пароли в публичные места)

| Роль | Логин | Пароль | Примечание |
|------|-------|--------|------------|
| Администратор | `гуляев_дм` | `123` | Сайт + SPVT-Admin |
| Работник | `фамилия_инициалы` | `123` | Список по подразделению на главной |

Секреты сервера: `/etc/spvt.env`, `/root/spvt-db-credentials.txt`.
