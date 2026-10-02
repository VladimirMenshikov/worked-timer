#!/bin/bash
set -e

echo "=== Work Timer — установка ==="
echo ""

echo "[1/4] Системные зависимости..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3-pip \
    python3-gi \
    python3-gi-cairo \
    libnotify-bin \
    zenity \
    gir1.2-ayatanaappindicator3-0.1 \
    libayatana-appindicator3-1 2>/dev/null || \
sudo apt-get install -y \
    gir1.2-appindicator3-0.1 2>/dev/null || true

echo "[2/4] Виртуальное окружение..."
# Явно системный /usr/bin/python3 (а не то, что резолвится через PATH/pyenv) —
# только он видит apt-пакеты python3-gi/gir1.2-ayatanaappindicator3, нужные pystray
# для иконки в трее. --system-site-packages обязателен по той же причине.
# --without-pip: не полагаемся на ensurepip (пакет python3.X-venv может отсутствовать
# или конфликтовать со сторонними PPA) — pip берём из уже установленного python3-pip
# через тот же --system-site-packages, ставит он всё равно в сам venv.
# --clear гарантирует чистое окружение при каждом запуске install.sh.
/usr/bin/python3 -m venv --clear --system-site-packages --without-pip .venv

echo "[3/4] Python зависимости..."
.venv/bin/python -m pip install --quiet -r requirements.txt

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
