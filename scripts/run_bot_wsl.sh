#!/bin/bash
# OpenClaw Python Bot — WSL Launcher
# Usage: bash scripts/run_bot_wsl.sh
# Requires: Ubuntu WSL, Python 3.12+

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${HOME}/openclaw_bot_venv"
PYTHON_BIN="${VENV_DIR}/bin/python3"
REQ_FILE="${REPO_ROOT}/requirements.txt"

echo "===================================================="
echo " OpenClaw Python Bot — WSL Launcher"
echo " Repo: ${REPO_ROOT}"
echo " Venv: ${VENV_DIR}"
echo "===================================================="

# 1. Убеждаемся что python3 и pip есть
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 не найден. Установи: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

PYTHON3_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Найден Python ${PYTHON3_VER}"

# 2. Создаём venv если не существует
if [ ! -f "${PYTHON_BIN}" ]; then
    echo "Создаём Linux venv в ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
    echo "Venv создан."
fi

# 3. Обновляем pip и устанавливаем зависимости
echo "Устанавливаем/обновляем зависимости..."
"${PYTHON_BIN}" -m pip install --quiet --upgrade pip
"${PYTHON_BIN}" -m pip install --quiet \
    -r "${REQ_FILE}" \
    python-dotenv \
    pyyaml \
    httpx

echo "Зависимости установлены."

# 4. Проверяем что aiogram импортится
"${PYTHON_BIN}" -c "import aiogram; print(f'aiogram {aiogram.__version__} OK')"

# 5. Загружаем .env если он есть (sed strips Windows CRLF)
if [ -f "${REPO_ROOT}/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source <(sed 's/\r//' "${REPO_ROOT}/.env" | grep -v '^#' | grep -v '^$')
    set +a
    echo ".env загружен."
fi

export PYTHONPATH="${REPO_ROOT}"

# 6. Переходим в корень репо и запускаем бота
cd "${REPO_ROOT}"
echo ""
echo "Запускаем бота... (Ctrl+C для остановки)"
echo "===================================================="

exec "${PYTHON_BIN}" -m src.main
