# Самоконтроль спортсменов — backend (Django + PostgreSQL) и клиент (Vue)

Монорепозиторий: `backend/` — Сергей, `frontend/` — Марват и Артем.

## Быстрый старт backend

Нужны: Python 3.12+, Docker Desktop (для PostgreSQL и Redis), Git.

```bash
# из корня репозитория
docker compose up -d                      # PostgreSQL (две БД: sport_main и sport_pii) + Redis

cd backend
python -m venv .venv
source .venv/bin/activate                 # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                      # Windows: copy .env.example .env  — и поменяйте SECRET_KEY

python manage.py makemigrations core accounts pii profiles assessments reminders
python manage.py migrate                  # основная БД (медицина, учётные записи)
python manage.py migrate --database=pii   # БД с ПДн (ФИО, контакты)
python manage.py import_sports            # справочник видов спорта (202 записи, Приложение В)
python manage.py createsuperuser          # администратор (логин любой, ПДн не нужны)
python manage.py runserver                # http://localhost:8000  (админка: /admin/, Swagger: /api/docs/)
```

Напоминания (Celery, в двух отдельных терминалах; на Windows добавьте `-P solo`):
```bash
celery -A config worker -l info
celery -A config beat -l info
```

Тесты: `pytest` (нужен запущенный PostgreSQL). Расчёты без БД: `pytest tests/test_scoring.py`.

## Папки

| Путь | Что внутри |
|---|---|
| `config/` | настройки, роутер БД (ПДн отдельно), Celery |
| `apps/core` | версии настроек (пороги/сроки/тексты), журнал обращений, права, админка |
| `apps/accounts` | пользователь без ПДн, согласие, регистрация/вход/OTP/сброс/удаление |
| `apps/pii` | ФИО, e-mail, телефон, одноразовые коды — **отдельная БД** |
| `apps/profiles` | профиль, справочник видов спорта, история изменений |
| `apps/assessments` | самооценки, RESTQ-Sport, расчёты (`scoring.py`), черновик, главная, данные для Excel |
| `apps/reminders` | расписание напоминаний, push-токены, Celery-задачи |

## API (кратко; полная схема — /api/docs/)

Все ответы JSON, ошибки: `{"detail": "...", "code": "...", "errors": {...}}`. Токен: `Authorization: Bearer <access>`.

| Метод и путь | Назначение |
|---|---|
| GET `/api/settings/` | действующие пороги, сроки, тексты (клиент кэширует для офлайна) |
| POST `/api/auth/register/start/` | `{contact, birth_date, consent}` → код (в dev приходит `debug_code`) |
| POST `/api/auth/register/verify/` | `{contact, code, password}` → `{access, refresh, user_code}` |
| POST `/api/auth/login/` · `/login/otp/start/` · `/login/otp/verify/` | вход по паролю или коду |
| POST `/api/auth/password-reset/start/` · `/confirm/` | восстановление доступа |
| POST `/api/auth/token/refresh/` · `/api/auth/logout/` | обновление токена / выход |
| GET, DELETE `/api/account/` · POST `/api/account/consent/revoke/` | сведения / удаление аккаунта (`{password}`) |
| GET `/api/sports/?q=` | справочник (id, name) |
| GET, PUT, PATCH `/api/profile/` · PUT `/api/profile/season/` · GET `/api/profile/history/` | профиль, период сезона, история |
| GET `/api/home/` | главный экран |
| GET, POST `/api/assessments/` · GET `/api/assessments/{id}/` | история (`?from=&to=`) · завершить самооценку · просмотр |
| GET, PUT, DELETE `/api/assessments/draft/` | черновик 72 ч: `{"data": {...}}` |
| GET `/api/export/data/?include_name=1` | все данные для Excel (файл формирует клиент) |
| GET, PUT `/api/reminders/settings/` · POST, DELETE `/api/devices/` | время напоминаний · push-токен |

Формат тела `POST /api/assessments/`: `{"client_uuid": "<uuid, создаёт клиент>", "filled_at": "<ISO, необязательно>", "answers": {...}}`.
Ключи ответов: `season_period`, `trainings_per_week`, `hours_per_week`, `tolerance` (2.1), `q2_2…q2_4`, `q3_1…q3_5`, `q3_3_detail` (`syncope`/`dizziness`),
`q4_1`, `q4_2` (список), `q4_3`, `q4_4`, `q5_1…q5_4`, `morning_pulse_today/usual`, `q6_1…q6_3`, `comment_2…comment_6`,
`bp` `{measured, sbp, dbp, pulse}`, `hrv` `{has_device, value, metric, device, date, conditions}`,
`restq` `{timing: before|after, answers: {"1":0..6, … "77":0..6}}` (только при `tolerance ≤ 3`).
Сервер пересчитывает всё сам и возвращает итог, тексты, индекс Кердо и шкалы RESTQ.

## Принятые допущения (согласовать с постановщиком)

1. «Срочное сообщение»: боль в груди (3.5) или в 3.3 выбран «обморок»; «головокружение» одно — без срочного сообщения (сценарий 10).
2. Баланс RESTQ = суммарное восстановление − суммарный стресс по **неокруглённым** значениям, затем округление до 0,01.
3. Черновик живёт 72 часа **от последнего сохранения** (параметр `drafts.ttl_hours`).
4. Просроченные офлайн-записи принимаются не старше 90 дней; профиль и срок напоминания обновляются только самой поздней записью.
5. Вид спорта в записи — по текущему профилю на момент синхронизации.

## Перед боевым запуском (не сделано в коде)

SMS-провайдер (`apps/accounts/services.py:send_code`), push (FCM/RuStore), Redis-кэш для throttle, шифрование дисков БД и бэкапов,
серверы в РФ (ч. 5 ст. 18 152-ФЗ), TLS ≥1.2 на прокси, ежедневный бэкап, модель угроз и уровень защищённости (ПП № 1119, приказ ФСТЭК № 21),
политика/согласие от оператора ПДн (версия — `POLICY_VERSION`), `DEBUG=False`, `DEV_ECHO_OTP=False`.
