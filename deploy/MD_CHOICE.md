# Деплой MD Choice

**URL:** http://ikorsakov.tech:7777/

```bash
cd /opt/anamnes && git pull && pip install -r requirements.txt
sudo cp deploy/md-choice.service /etc/systemd/system/
sudo cp deploy/nginx-md-choice.conf.example /etc/nginx/sites-available/md-choice
sudo ln -sf /etc/nginx/sites-available/md-choice /etc/nginx/sites-enabled/
sudo systemctl daemon-reload && sudo systemctl enable --now md-choice
sudo nginx -t && sudo systemctl reload nginx
```
