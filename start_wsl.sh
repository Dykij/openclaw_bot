#!/bin/bash
# Инициализация и запуск OpenClaw Gateway в среде WSL 2 с поддержкой Webhook

# Автоматически определяем IP Windows хоста для сети WSL2 (наиболее надежный метод)
WIN_HOST_IP=$(ip route show | grep -i default | awk '{ print $3 }')
export OLLAMA_HOST="${WIN_HOST_IP:-192.168.0.212}:11434"
export WSL_ENV="1"

echo "==========================================="
echo "🚀 Starting OpenClaw Python Backend in WSL2"
echo "📡 OLLAMA_HOST is set to ${OLLAMA_HOST}"
echo "==========================================="

# Проверка системных пакетов
if ! command -v python3 &> /dev/null || ! python3 -m venv --help &> /dev/null; then
    echo "📦 Отсутствует Python 3 или модуль venv. Установка (потребуется sudo пароль от WSL)..."
    sudo apt-get update -q
    sudo apt-get install -y python3 python3-venv python3-pip
fi

# Проверяем, существует ли виртуальное окружение, если нет - создаем
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения (venv)..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
source venv/bin/activate

# Обновляем пакеты, если нужно 
echo "🔄 Установка зависимостей..."
pip install --upgrade pip -q
pip install aiogram aiohttp psutil -q

# --- НАСТРОЙКА WEBHOOK СЕРВЕРА (CLOUDFLARE TUNNEL) ---
if [ ! -f "cloudflared" ]; then
    echo "☁️ Скачивание Cloudflare Tunnel (для Webhook)..."
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared
    chmod +x cloudflared
fi

# ФИКС DNS (более агрессивный, удаляем symlink если он есть)
if [ ! -f "/etc/resolv.conf.bak" ]; then
    sudo cp /etc/resolv.conf /etc/resolv.conf.bak || true
fi
echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf > /dev/null
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf > /dev/null

echo "🌐 Запуск локального Webhook сервера..."
pkill -f cloudflared # Убиваем старые туннели
rm -f cloudflared.log

# Запускаем туннель с принудительным IPv4, протоколом HTTP2 (TCP) и отключенным автоапдейтом
# HTTP2 (порт 443 TCP) намного стабильнее в WSL, чем QUIC (UDP), который часто блокируется
export TUNNEL_UPDATE_DISABLE=true

./cloudflared tunnel --edge-ip-version 4 --protocol http2 --url http://localhost:8080 > cloudflared.log 2>&1 &

echo "⏳ Ожидание генерации публичного URL..."
for i in {1..25}; do
    sleep 1
    # Ищем ссылку, которая НЕ является api.trycloudflare.com и начинается с https://
    PUBLIC_URL=$(grep -o 'https://[-a-zA-Z0-9]*\.trycloudflare\.com' cloudflared.log | grep -v 'api.trycloudflare.com' | head -1)
    if [ -n "$PUBLIC_URL" ]; then
        break
    fi
done

if [ -z "$PUBLIC_URL" ]; then
    echo "⚠️ Не удалось получить ссылку Cloudflare (проверьте интернет в WSL)."
    echo "Будет использован Long-Polling (стандартный метод)."
    export USE_WEBHOOK=0
else
    echo "✅ Webhook URL получен: ${PUBLIC_URL}"
    export USE_WEBHOOK=1
    export WEBHOOK_URL="${PUBLIC_URL}/webhook"
fi

echo "==========================================="
echo "🧠 Loading 20 Specialized Roles via Config..."
echo "⚙️ Нажмите Ctrl+C для Graceful Shutdown"
echo "==========================================="

# Запуск бота 
python3 main.py

# Очистка после звершения бота (Ctrl+C)
echo "🛑 Остановка локального Webhook сервера (Cloudflare Tunnel)..."
pkill -f cloudflared
echo "✅ Завершено чисто!"
