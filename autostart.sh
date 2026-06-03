#!/bin/bash
# Создаёт .desktop файл для автозапуска при входе в систему

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/work-timer.desktop"

mkdir -p "$AUTOSTART_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Work Timer
Comment=Трекер рабочего времени
Exec=$SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/timer.py
Icon=appointment-soon
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

echo "Автозапуск настроен: $DESKTOP_FILE"
