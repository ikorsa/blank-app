# Анамнез эндокринолога

MVP веб-анкеты для предварительного сбора эндокринологического анамнеза перед приемом врача.

Приложение работает на Streamlit и содержит:

- пациентскую анкету с ветвлениями по основной причине обращения;
- загрузку анализов, УЗИ и выписок в форматах PDF/JPG/PNG;
- локальное сохранение анкет и файлов;
- простую врачебную панель с паролем;
- автоматическое текстовое резюме для врача.

## Запуск локально

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

По умолчанию приложение слушает порт `9090` и адрес `0.0.0.0`, поэтому на сервере будет доступно как:

```text
http://ikorsakov.tech:9090
http://anamnes.ikorsakov.tech:9090
```

## Переменные окружения

```bash
export ANAMNES_ADMIN_PASSWORD="сложный-пароль-для-врача"
export ANAMNES_DATA_DIR="/opt/anamnes/data"
```

Если `ANAMNES_ADMIN_PASSWORD` не задан, используется тестовый пароль:

```text
admin
```

Для реального сервера пароль по умолчанию нужно обязательно заменить.

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
