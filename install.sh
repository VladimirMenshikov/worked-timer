#!/bin/bash
set -e

echo "=== Work Timer — установка ==="
echo ""

echo "[1/4] Системные зависимости..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-gi \
    python3-gi-cairo \
    libnotify-bin \
    zenity \
    gir1.2-ayatanaappindicator3-0.1 \
    libayatana-appindicator3-1 2>/dev/null || \
sudo apt-get install -y \
    gir1.2-appindicator3-0.1 2>/dev/null || true

echo "[2/4] Виртуальное окружение..."
python3 -m venv .venv
source .venv/bin/activate

echo "[3/4] Python зависимости..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "[4/4] Права на запуск..."
chmod +x timer.py

echo ""
echo "=== Готово! ==="
echo ""
echo "Запуск:"
echo "  source .venv/bin/activate && python timer.py"
echo ""
echo "Автозапуск (добавить в ~/.config/autostart/):"
echo "  bash autostart.sh"
