# -*- mode: python ; coding: utf-8 -*-
# Собирается командой build_exe.bat (PyInstaller не умеет кросс-компилировать
# Windows-exe с Linux/macOS — этот .spec нужно запускать на Windows).
import os

SRC_DIR = os.path.join(SPECPATH, "..", "..", "Win")

a = Analysis(
    [os.path.join(SRC_DIR, "timer.py")],
    pathex=[SRC_DIR],
    binaries=[],
    datas=[],
    hiddenimports=["pystray._win32"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="WorkTimer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=os.path.join(SPECPATH, "assets", "work-timer.ico"),
)
