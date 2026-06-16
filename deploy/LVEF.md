# Деплой сервиса прогнозирования ФВ ЛЖ

**URL:** http://ikorsakov.tech:9999/

## Стек

- `lvef_app.py` — интерфейс
- `clinical/lvef.py` — расчёты (Симпсон, Teichholz, FS, клинический прогноз)
- Streamlit на `127.0.0.1:9991`
- Nginx слушает `9999`

## Установка

```bash
cd /opt/anamnes
git pull
source .venv/bin/activate
pip install -r requirements.txt

sudo cp deploy/lvef.service /etc/systemd/system/
sudo cp deploy/nginx-lvef.conf.example /etc/nginx/sites-available/lvef
sudo ln -sf /etc/nginx/sites-available/lvef /etc/nginx/sites-enabled/

sudo systemctl daemon-reload
sudo systemctl enable lvef
sudo systemctl start lvef
sudo nginx -t && sudo systemctl reload nginx
```

## Локально

```bash
streamlit run lvef_app.py --server.port=9999
```
