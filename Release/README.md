# Work Timer — релизы

| Платформа | Готово сейчас | Инструкция |
|---|---|---|
| Linux (Mint / Ubuntu / Debian) | `.deb`-пакет — ставится сразу | [`linux/README.md`](linux/README.md) |
| Windows | скрипты сборки `.exe` / `Setup.exe` (запускать на Windows) | [`windows/README.md`](windows/README.md) |

## Linux

```bash
sudo apt install ./Release/linux/work-timer_1.1.0_all.deb
```

## Windows

Готового бинарника нет — PyInstaller не кросс-компилирует Windows-exe из Linux. В [`windows/`](windows) лежат все скрипты сборки: `build_exe.bat` (→ `WorkTimer.exe`) и `build_installer.bat` (→ `WorkTimerSetup-1.1.0.exe`). Запустите их на Windows-машине, см. подробности в [`windows/README.md`](windows/README.md). Исходники Windows-версии приложения — в [`../Win`](../Win).
