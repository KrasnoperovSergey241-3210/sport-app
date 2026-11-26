# Самоконтроль спортсменов — backend (Django + PostgreSQL) и клиент (Vue)

Монорепозиторий: `backend/` — Сергей, `frontend/` — Марват и Артем.

## Клиент Vue и TypeScript

Клиент использует Django API для регистрации, входа и сохранения данных. Для первого запуска в PowerShell из корня репозитория скопируйте `backend/.env.example` в `backend/.env` и задайте собственный `SECRET_KEY`. Затем выполните:

```powershell
docker compose --env-file backend/.env up -d --wait
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe backend/manage.py migrate --database=default
backend/.venv/Scripts/python.exe backend/manage.py migrate --database=pii
backend/.venv/Scripts/python.exe backend/manage.py import_sports
backend/.venv/Scripts/python.exe backend/manage.py runserver 127.0.0.1:8000
```

В другой вкладке терминала выполните `npm.cmd ci` для установки зависимостей и `npm.cmd run dev` для запуска клиента. Откройте `http://127.0.0.1:5173`. Регистрация проходит по электронной почте и паролю без кода подтверждения. Для входа по коду и восстановления пароля локальные коды доступны в консоли Django. При `DEV_ECHO_OTP=True` сервер также возвращает код клиенту разработки. Для доставки пользователям требуется настроить почту или SMS на сервере. Адрес прокси можно задать через `SPORT_API_TARGET`, прямой адрес API через `VITE_API_BASE_URL`.

`npm test` запускает тесты расчётов, `npm run typecheck` проверяет типы. Чтобы проверить перезагрузку без сети, запустите `npm run build` и `npm run preview`, откройте приложение онлайн один раз и дождитесь установки service worker. Черновик и очередь отправки доступны при перезагрузке той же вкладки. Чтобы отправить офлайн-запись, оставьте вкладку открытой до синхронизации. Синхронизированный черновик можно восстановить с сервера до окончания его срока хранения.

При низкой оценке переносимости Django требует RESTQ-Sport. Пока этот блок не подключён, анкета открывает предварительный результат и сохраняет черновик. Для подключения блок получает `current` и `save` через слот `restq` в `Questionnaire.vue`. `save` принимает `RestqAnswers` из `frontend/src/lib/forms.ts`. Приложение отправит заполненный блок вместе с остальными полями анкеты.
