# Деплой на VPS (anamnes.ikorsakov.tech)

Стек: **Streamlit** (анкета) + **telegram_bot.py** (ссылки для пациентов) + **Nginx** + **HTTPS**.

Данные MVP хранятся в `/opt/anamnes/data/` (JSON + файлы). PostgreSQL в этой ветке не требуется.

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

См. `scripts/backup_data.sh` и cron в README.

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
