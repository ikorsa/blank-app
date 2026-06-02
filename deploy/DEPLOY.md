# Деплой на VPS (anamnes.ikorsakov.tech)

**Рекомендуемый стек:** **Django** (gunicorn `:8000`) + **Nginx** + **HTTPS** + **telegram_bot.py** (ссылки для пациентов).

Legacy **Streamlit** (`:9090`) — только для отката; после проверки отключите `anamnes.service`.

Данные: SQLite/PostgreSQL (`ANAMNES_DATABASE_URL`) + файлы в `/opt/anamnes/media/`. JSON-legacy в `/opt/anamnes/data/` при миграции.

## Быстрый чеклист продакшена (Django)

1. Смержить PR в `main`, на VPS: `git pull origin main`.
2. `/etc/anamnes.env` — скопировать из `deploy/anamnes.env.example`, задать `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS=anamnes.ikorsakov.tech`, `ANAMNES_ADMIN_PASSWORD`, SMTP.
3. Один раз: `sudo bash /opt/anamnes/deploy/switch-to-django-only.sh`  
   (пользователь сервиса = владелец `/opt/anamnes`, обычно `ikorsa`; иначе `export ANAMNES_USER=ikorsa`)
4. Проверка: `sudo bash /opt/anamnes/deploy/check-production.sh`
5. SSL: при ошибке Chrome `NET::ERR_CERT_COMMON_NAME_INVALID` → `sudo bash /opt/anamnes/deploy/fix-ssl-cert.sh`

Обновление после правок:

```bash
cd /opt/anamnes && sudo -u anamnes git pull
sudo -u anamnes .venv/bin/pip install -r requirements.txt
sudo -u anamnes .venv/bin/python manage.py migrate --noinput
sudo -u anamnes .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart anamnes-django
```

## 1. Подготовка сервера (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y git python3 python3-venv nginx certbot python3-certbot-nginx
sudo useradd -r -m -d /opt/anamnes -s /bin/bash anamnes || true
sudo mkdir -p /opt/anamnes/data /opt/anamnes/backups
sudo chown -R anamnes:anamnes /opt/anamnes
```

## 2. Код с GitHub

```bash
sudo -u anamnes -H bash -lc '
  cd /opt/anamnes
  git clone https://github.com/ikorsa/blank-app.git . || true
  git fetch origin cursor/anamnes-web-mvp-8f37
  git checkout cursor/anamnes-web-mvp-8f37
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
'
```

Если репозиторий уже есть — `git pull` и `pip install -r requirements.txt`.

## 3. Конфигурация

```bash
sudo cp /opt/anamnes/deploy/anamnes.env.example /etc/anamnes.env
sudo chmod 600 /etc/anamnes.env
sudo nano /etc/anamnes.env
```

Обязательно задать:

- `ANAMNES_ADMIN_PASSWORD`
- `ANAMNES_PUBLIC_URL=https://anamnes.ikorsakov.tech`
- `ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN` (токен от @BotFather)

Врачи:

```bash
sudo -u anamnes cp /opt/anamnes/config/doctors.example.json /opt/anamnes/data/doctors.json
sudo -u anamnes nano /opt/anamnes/data/doctors.json
```

## 4. systemd

```bash
sudo cp /opt/anamnes/deploy/anamnes.service /etc/systemd/system/
sudo cp /opt/anamnes/deploy/anamnes-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable anamnes anamnes-bot
sudo systemctl start anamnes anamnes-bot
sudo systemctl status anamnes anamnes-bot --no-pager
```

Проверка локально на сервере: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9090`

## 5. Nginx + HTTPS

```bash
sudo cp /opt/anamnes/deploy/nginx-anamnes.conf.example /etc/nginx/sites-available/anamnes
sudo ln -sf /etc/nginx/sites-available/anamnes /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d anamnes.ikorsakov.tech
```

Certbot пропишет `ssl_certificate` в конфиг. Если вручную копировали `nginx-anamnes-django.conf.example` — **раскомментируйте** строки `ssl_certificate` или снова запустите certbot.

### Ошибка Chrome `NET::ERR_CERT_COMMON_NAME_INVALID`

Браузер видит сертификат **не для** `anamnes.ikorsakov.tech` (часто дефолтный nginx или сертификат другого сайта).

На VPS:

```bash
# Проверка: для какого имени выдан текущий сертификат
echo | openssl s_client -connect anamnes.ikorsakov.tech:443 -servername anamnes.ikorsakov.tech 2>/dev/null \
  | openssl x509 -noout -subject -ext subjectAltName

sudo bash /opt/anamnes/deploy/fix-ssl-cert.sh
```

Открывайте **точно** `https://anamnes.ikorsakov.tech` (без `www.`). DNS A-запись поддомена должна указывать на VPS.

## 6. Проверка

- Сайт: https://anamnes.ikorsakov.tech/?doctor=ivanova  
- Бот в Telegram: `/start doctor_ivanova` → кнопка на тот же URL  
- Кабинет врача: раздел «Кабинет врача», логин `ivanova` / пароль из `doctors.json`

## 7. Обновление после правок

```bash
cd /opt/anamnes
sudo -u anamnes git pull
sudo -u anamnes .venv/bin/pip install -r requirements.txt
sudo systemctl restart anamnes anamnes-bot
```

## 8. Бэкапы

- Файлы и JSON: `scripts/backup_data.sh` (cron в README).
- PostgreSQL: тот же cron вызывает `scripts/backup_postgres.sh`, если задан `ANAMNES_DATABASE_URL` (дампы `anamnes-pg-*.dump` в `/opt/anamnes/backups/`).
- Восстановление БД: `scripts/restore_postgres.sh /opt/anamnes/backups/anamnes-pg-....dump` (осторожно: перезаписывает данные).

```bash
sudo apt install -y postgresql-client
chmod +x /opt/anamnes/scripts/backup_postgres.sh /opt/anamnes/scripts/restore_postgres.sh
```

## 8.1. Короткие ссылки и QR

После обновления Nginx (`deploy/nginx-anamnes.conf.example`, блок `/d/...`):

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Пациентская ссылка: `https://anamnes.ikorsakov.tech/d/ivanova` → анкета врача `ivanova`.

В **Управление врачами**: скачивание QR PNG и кнопка «Отправить тестовое уведомление».

## 9. PostgreSQL (опционально)

По умолчанию анкеты и врачи хранятся в `data/` (JSON). Для PostgreSQL:

```bash
sudo apt install -y postgresql
sudo -u postgres createuser anamnes --pwprompt
sudo -u postgres createdb anamnes -O anamnes
```

В `/etc/anamnes.env` (см. `deploy/postgres.env.example`):

```bash
ANAMNES_DATABASE_URL=postgresql://anamnes:PASSWORD@127.0.0.1:5432/anamnes
```

Миграция существующих JSON:

```bash
cd /opt/anamnes
source .venv/bin/activate
pip install -r requirements.txt
ANAMNES_DATABASE_URL='postgresql://...' python scripts/migrate_json_to_postgres.py
sudo -n /usr/bin/systemctl restart anamnes anamnes-bot
```

Файлы загрузок остаются в `data/uploads/` и `data/draft_uploads/`.

## 10. Админка врачей

В приложении: **Управление врачами** (логин `admin`, пароль `ANAMNES_ADMIN_PASSWORD`).

Добавление/редактирование врачей без `nano` на сервере. Работает и с JSON, и с PostgreSQL.

## Важно

- На ПК **не запускайте** `telegram_bot.py` с тем же токеном, что на сервере (ошибка 409).
- Медицинские данные: только **HTTPS**, сильные пароли, бэкапы `data/`.

---

## Django-контур (надёжный режим, вместо Streamlit)

Ниже минимальные шаги переключения на Django + gunicorn.

### 1) Установить зависимости и миграции

```bash
cd /opt/anamnes
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py sync_doctors_from_legacy
```

### 2) Включить systemd-сервис Django

```bash
sudo cp /opt/anamnes/deploy/anamnes-django.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable anamnes-django
sudo systemctl restart anamnes-django
sudo systemctl status anamnes-django --no-pager -l
```

### 3) Переключить Nginx на Django

```bash
sudo cp /opt/anamnes/deploy/nginx-anamnes-django.conf.example /etc/nginx/sites-available/anamnes
sudo ln -sf /etc/nginx/sites-available/anamnes /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Если HTTPS ещё не выпускали:

```bash
sudo certbot --nginx -d anamnes.ikorsakov.tech
```

### 4) Остановить старый Streamlit-сервис (после проверки)

```bash
sudo systemctl stop anamnes
sudo systemctl disable anamnes
```

### 5) Быстрый rollback

```bash
sudo systemctl stop anamnes-django
sudo systemctl disable anamnes-django
sudo systemctl enable anamnes
sudo systemctl restart anamnes
```
