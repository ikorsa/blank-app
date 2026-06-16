# Деплой калькулятора выборки КИ

**URL:** http://ikorsakov.tech:8080/

Отдельный Streamlit-сервис, не связанный с анамнезом (`anamnes.ikorsakov.tech`).

## Стек

- `trial_calculator_app.py` — интерфейс
- `clinical/sample_size.py` — расчёты
- Streamlit на `127.0.0.1:8081`
- Nginx слушает `8080` и проксирует на Streamlit

## Установка на сервере

```bash
cd /opt/anamnes
git pull
source .venv/bin/activate
pip install -r requirements.txt

sudo cp deploy/trial-calculator.service /etc/systemd/system/
sudo cp deploy/nginx-trial-calculator.conf.example /etc/nginx/sites-available/trial-calculator
sudo ln -sf /etc/nginx/sites-available/trial-calculator /etc/nginx/sites-enabled/

sudo systemctl daemon-reload
sudo systemctl enable trial-calculator
sudo systemctl start trial-calculator
sudo nginx -t && sudo systemctl reload nginx
```

Проверка:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8081
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080
```

## Локальный запуск

```bash
pip install -r requirements.txt
streamlit run trial_calculator_app.py --server.port=8080
```

Откройте http://127.0.0.1:8080

## Поддерживаемые дизайны

1. Сравнение средних (t-критерий)
2. Сравнение долей (z-тест)
3. Непревосходство по доле (non-inferiority)
4. Время до события (Schoenfeld / log-rank)

Результаты ориентировочные; финальный расчёт — у биостатистика протокола.
