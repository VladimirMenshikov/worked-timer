#!/bin/bash
# Собирает work-timer_<version>_all.deb из исходников проекта.
#
# Собирает во временном каталоге на обычной файловой системе, а не прямо в
# репозитории: dpkg-deb требует реальных unix-прав (0755/0644) на файлы
# пакета, а если репозиторий лежит на смонтированном Windows-разделе (NTFS/
# exFAT/9p), права там не сохраняются и сборка падает с ошибкой прав доступа.
set -e

VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$(mktemp -d)"
PKG="$BUILD_DIR/pkgroot"

trap 'rm -rf "$BUILD_DIR"' EXIT

mkdir -p "$PKG/DEBIAN" "$PKG/opt/work-timer/sql/migrations" "$PKG/usr/share/applications"

cp "$ROOT_DIR/timer.py" "$PKG/opt/work-timer/timer.py"
cp "$ROOT_DIR/requirements.txt" "$PKG/opt/work-timer/requirements.txt"
cp "$ROOT_DIR/.env.example" "$PKG/opt/work-timer/.env.example"
cp "$ROOT_DIR/create_table.sql" "$PKG/opt/work-timer/create_table.sql"
cp "$ROOT_DIR/README.md" "$PKG/opt/work-timer/README.md"
cp "$ROOT_DIR/GUIDE.md" "$PKG/opt/work-timer/GUIDE.md"
cp "$ROOT_DIR"/sql/migrations/*.sql "$PKG/opt/work-timer/sql/migrations/"
cp "$SCRIPT_DIR/pkg-src/autostart.sh" "$PKG/opt/work-timer/autostart.sh"
cp "$SCRIPT_DIR/pkg-src/control" "$PKG/DEBIAN/control"
cp "$SCRIPT_DIR/pkg-src/postinst" "$PKG/DEBIAN/postinst"
cp "$SCRIPT_DIR/pkg-src/postrm" "$PKG/DEBIAN/postrm"
cp "$SCRIPT_DIR/pkg-src/work-timer.desktop" "$PKG/usr/share/applications/work-timer.desktop"

sed -i "s/^Version: .*/Version: $VERSION/" "$PKG/DEBIAN/control"

find "$PKG" -type d -exec chmod 0755 {} \;
find "$PKG" -type f -exec chmod 0644 {} \;
chmod 0755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"
chmod 0755 "$PKG/opt/work-timer/timer.py" "$PKG/opt/work-timer/autostart.sh"

OUT="$SCRIPT_DIR/work-timer_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$PKG" "$OUT"

echo "Собрано: $OUT"
