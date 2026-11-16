#!/usr/bin/env bash
# 새 Ubuntu 서버에서 한 번 실행한다. Docker를 설치하고 API 스택(Postgres·API·Caddy)을 띄운다.
# 사용: bash server-setup.sh
# 다시 실행해도 안전하다(이미 있는 .env와 DB는 건드리지 않는다).
set -euo pipefail

REPO=https://github.com/yongnyong/cuk-career-ai.git
DIR=$HOME/cuk-career-ai

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone "$REPO" "$DIR"
fi
cd "$DIR"

if [ ! -f .env ]; then
  # 도메인을 사지 않고 HTTPS를 쓰기 위해 sslip.io 주소를 쓴다(서버 공인 IP가 그대로 도메인이 된다).
  IP=$(curl -fsS https://checkip.amazonaws.com | tr -d '\n')
  umask 077
  cat > .env <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 24)
DOMAIN=${IP//./-}.sslip.io
EOF
  echo ".env 생성: DOMAIN=${IP//./-}.sslip.io"
fi

sudo docker compose up -d --build
sleep 5
sudo docker compose ps
echo "확인: curl https://$(grep ^DOMAIN= .env | cut -d= -f2)/api/health"
