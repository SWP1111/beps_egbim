#!/bin/bash

# 1️⃣ 업데이트 및 필수 패키지 설치
echo "🔹 시스템 업데이트 중..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip nginx git

# 2️⃣ Flask 프로젝트 폴더 설정
APP_DIR="/home/$USER/flask_app"
if [ ! -d "$APP_DIR" ]; then
    echo "🔹 Flask 프로젝트 폴더 생성: $APP_DIR"
    mkdir -p $APP_DIR
fi
cd $APP_DIR

# 3️⃣ 가상환경 생성 및 패키지 설치
echo "🔹 가상환경 생성 및 패키지 설치 중..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4️⃣ Gunicorn 실행 (Flask 앱 구동)
echo "🔹 Gunicorn 실행 중..."
pkill gunicorn  # 기존 Gunicorn 프로세스 종료
gunicorn -w 4 -b 0.0.0.0:5000 app:app --daemon  # 백그라운드 실행

# 5️⃣ Nginx 설정 추가 (리버스 프록시 설정)
NGINX_CONF="/etc/nginx/sites-available/flask_app"
if [ ! -f "$NGINX_CONF" ]; then
    echo "🔹 Nginx 설정 추가..."
    sudo tee $NGINX_CONF > /dev/null <<EOF
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    sudo ln -s /etc/nginx/sites-available/flask_app /etc/nginx/sites-enabled
    sudo systemctl restart nginx
    sudo ufw allow 'Nginx Full'  # 방화벽 설정
fi

# 6️⃣ Flask 앱을 Systemd 서비스로 등록하여 자동 실행
echo "🔹 Flask 앱을 systemd 서비스로 등록 중..."
SERVICE_FILE="/etc/systemd/system/flask_app.service"
if [ ! -f "$SERVICE_FILE" ]; then
    sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Flask App with Gunicorn
After=network.target

[Service]
User=$USER
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl start flask_app
    sudo systemctl enable flask_app
fi

# 7️⃣ 배포 완료 메시지
echo "✅ Flask 앱이 성공적으로 배포되었습니다!"
echo "🌎 서버 실행: http://$(curl -s ifconfig.me)"
