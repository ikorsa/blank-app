# Анамнез эндокринолога

MVP веб-анкеты для предварительного сбора эндокринологического анамнеза перед приемом врача.

Приложение работает на Streamlit и содержит:

- пациентскую анкету с ветвлениями по основной причине обращения;
- загрузку анализов, УЗИ и выписок в форматах PDF/JPG/PNG;
- локальное сохранение анкет и файлов;
- простую врачебную панель с паролем;
- автоматическое текстовое резюме для врача;
- выгрузку резюме в TXT и PDF;
- фильтры и статусы просмотра в кабинете врача;
- опциональные email- и Telegram-уведомления.

## Запуск локально

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

По умолчанию приложение слушает порт `9090`. В продакшене его лучше запускать через `systemd` на `127.0.0.1:9090` и отдавать наружу через Nginx:

```text
https://anamnes.ikorsakov.tech
```

Пошаговый деплой (systemd, Nginx, `/etc/anamnes.env`): см. [deploy/DEPLOY.md](deploy/DEPLOY.md).

После обновления кода на сервере:

```bash
cd /opt/anamnes
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart anamnes
```

## Переменные окружения

```bash
export ANAMNES_ADMIN_PASSWORD="сложный-пароль-для-врача"
export ANAMNES_DATA_DIR="/opt/anamnes/data"
export ANAMNES_DOCTORS_FILE="/opt/anamnes/data/doctors.json"
```

Если `ANAMNES_ADMIN_PASSWORD` не задан, используется тестовый пароль:

```text
admin
```

Для реального сервера пароль по умолчанию нужно обязательно заменить.

## Несколько врачей и персональные ссылки

Для каждого врача можно завести отдельную ссылку пациента:

```text
https://anamnes.ikorsakov.tech/?doctor=ivanova
https://anamnes.ikorsakov.tech/?doctor=petrov
```

Пациентская анкета будет автоматически привязана к врачу из параметра `doctor`.
В кабинете врач входит своим логином и паролем и видит только свои анкеты.
Администратор входит логином `admin` и паролем `ANAMNES_ADMIN_PASSWORD`, видит все анкеты.

Пример файла врачей есть в:

```text
config/doctors.example.json
```

На сервере его лучше хранить вне git, например:

```bash
cp config/doctors.example.json /opt/anamnes/data/doctors.json
nano /opt/anamnes/data/doctors.json
sudo systemctl restart anamnes
```

Формат врача:

```json
{
  "id": "ivanova",
  "name": "Иванова Анна Сергеевна",
  "specialty": "Эндокринолог",
  "email": "ivanova@example.com",
  "telegram_chat_id": "123456789",
  "password": "сложный-пароль-врача"
}
```

Если у врача указан `email`, email-копия анкеты будет отправляться этому врачу. Если указан `telegram_chat_id`, Telegram-уведомление будет отправляться ему.

Красивые ссылки вида `/ivanova` можно позже сделать через Nginx redirect/rewrite на `/?doctor=ivanova`.

## Email-копия анкеты

После успешной отправки анкеты приложение может продублировать резюме врачу на email. Это опционально: если SMTP-переменные не заданы, анкета просто сохраняется локально.

Для Gmail нужен не обычный пароль от аккаунта, а **App Password**:

1. Включить двухфакторную аутентификацию Google.
2. Создать пароль приложения: Google Account -> Security -> 2-Step Verification -> App passwords.
3. Указать его в `ANAMNES_SMTP_PASSWORD`.

Пример переменных:

```bash
export ANAMNES_SMTP_HOST="smtp.gmail.com"
export ANAMNES_SMTP_PORT="587"
export ANAMNES_SMTP_USER="your-gmail@gmail.com"
export ANAMNES_SMTP_PASSWORD="gmail-app-password"
export ANAMNES_SMTP_FROM="your-gmail@gmail.com"
export ANAMNES_SMTP_TO="igor.korsa@gmail.com"
```

Письмо содержит текстовое резюме и JSON-анкеты во вложении. Загруженные пациентом файлы не прикладываются к письму; они доступны в кабинете врача.

## Telegram-уведомления

Опционально можно отправлять врачу короткое Telegram-уведомление о новой анкете. Для этого создайте бота через `@BotFather`, получите token и узнайте `chat_id` получателя.

```bash
export ANAMNES_PUBLIC_URL="https://anamnes.ikorsakov.tech"
export ANAMNES_TELEGRAM_BOT_TOKEN="123456:telegram-token"
export ANAMNES_TELEGRAM_CHAT_ID="123456789"
```

Если переменные не заданы, приложение просто не отправляет Telegram-уведомления.

## Telegram-бот для пациентов

Отдельный файл `telegram_bot.py` запускает простого Telegram-бота-оболочку. Он не собирает анкету внутри Telegram, а выдает пациенту кнопку на веб-анкету нужного врача.

Ссылка для пациента:

```text
https://t.me/<bot_username>?start=doctor_ivanova
```

Бот откроет анкету:

```text
https://anamnes.ikorsakov.tech/?doctor=ivanova
```

Создание:

1. В Telegram открыть `@BotFather`.
2. Выполнить `/newbot`.
3. Скопировать token.
4. Добавить в `/etc/anamnes.env`:

```env
ANAMNES_PUBLIC_URL=https://anamnes.ikorsakov.tech
ANAMNES_TELEGRAM_PATIENT_BOT_TOKEN=123456:patient-bot-token
ANAMNES_DOCTORS_FILE=/opt/anamnes/data/doctors.json
```

Ручная проверка на сервере:

```bash
cd /opt/anamnes
source .venv/bin/activate
python telegram_bot.py
```

Команды бота:

- `/start doctor_ivanova` — выдать ссылку врача `ivanova`;
- `/doctors` — список врачей из `doctors.json`;
- `/help` — помощь.

Пример systemd-сервиса `/etc/systemd/system/anamnes-bot.service`:

```ini
[Unit]
Description=Anamnes Telegram patient bot
After=network-online.target
Wants=network-online.target

[Service]
User=ikorsa
Group=ikorsa
WorkingDirectory=/opt/anamnes
EnvironmentFile=/etc/anamnes.env
ExecStart=/opt/anamnes/.venv/bin/python /opt/anamnes/telegram_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable anamnes-bot
sudo systemctl start anamnes-bot
sudo systemctl status anamnes-bot --no-pager -l
```

## Черновик анкеты

Пациент может **сохранить прогресс** без отправки врачу:

- кнопка «Сохранить черновик и получить ссылку»;
- ссылка вида `https://anamnes.ikorsakov.tech/?doctor=ivanova&draft=...` — продолжение с другого устройства;
- **автосохранение** каждые ~2,5 мин., если в URL есть `draft=...`;
- файлы черновика хранятся в `data/draft_uploads/` (срок хранения по умолчанию 30 дней).

После «Отправить анкету врачу» черновик удаляется, данные попадают в `data/submissions/`.

Переменные: `ANAMNES_DRAFT_RETENTION_DAYS`, `ANAMNES_AUTOSAVE_INTERVAL_SECONDS`.

## Хранение данных

По умолчанию данные сохраняются в папку:

```text
data/
```

Структура:

```text
data/submissions/   JSON-анкеты
data/uploads/       загруженные файлы пациентов
```

Папка `data/` исключена из git.

## Резервные копии

В репозитории есть скрипт:

```bash
scripts/backup_data.sh
```

Он архивирует `ANAMNES_DATA_DIR` в `ANAMNES_BACKUP_DIR` и удаляет копии старше `ANAMNES_BACKUP_RETENTION_DAYS`.

Пример ручного запуска на сервере:

```bash
cd /opt/anamnes
chmod +x scripts/backup_data.sh
ANAMNES_DATA_DIR=/opt/anamnes/data \
ANAMNES_BACKUP_DIR=/opt/anamnes/backups \
ANAMNES_BACKUP_RETENTION_DAYS=14 \
./scripts/backup_data.sh
```

Пример ежедневного cron-задания:

```bash
crontab -e
```

Добавить строку:

```cron
15 2 * * * cd /opt/anamnes && ANAMNES_DATA_DIR=/opt/anamnes/data ANAMNES_BACKUP_DIR=/opt/anamnes/backups ANAMNES_BACKUP_RETENTION_DAYS=14 ./scripts/backup_data.sh >> /opt/anamnes/backups/backup.log 2>&1
```

Папку `/opt/anamnes/backups` желательно периодически копировать за пределы сервера.

## Разделы приложения

В левом меню есть два раздела:

1. **Анкета пациента** — заполнение анамнеза.
2. **Кабинет врача** — просмотр анкет, резюме и файлов.

## Ветки анкеты

MVP поддерживает направления:

- щитовидная железа;
- сахарный диабет / высокий сахар;
- лишний вес / ожирение;
- нарушение цикла / гормоны / бесплодие;
- усталость / слабость / выпадение волос;
- остеопороз / витамин D / кальций;
- другое.

## Важно по безопасности

Текущая версия подходит для тестирования MVP. Для работы с реальными медицинскими данными нужно:

- включить HTTPS через Nginx и Let's Encrypt;
- задать сложный `ANAMNES_ADMIN_PASSWORD`;
- ограничить доступ к серверу и файлам;
- не отправлять реальные данные через открытый HTTP;
- регулярно делать резервные копии `ANAMNES_DATA_DIR`.
