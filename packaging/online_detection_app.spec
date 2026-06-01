# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path.cwd()


def collect_tree(src: str, dst: str):
    path = ROOT / src
    if not path.exists():
        return []
    return [(str(path), dst)]


datas = []
datas += collect_tree("app/qml", "app/qml")
datas += collect_tree("app/resources", "app/resources")
datas += collect_tree("app/infrastructure/camera/mvs/MvCameraControl.dll", "app/infrastructure/camera/mvs")
datas += collect_tree("config.production.example.json", ".")
datas += collect_tree("config.example.json", ".")

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "pymodbus.client",
    "cv2",
    "numpy",
    "seat_defect_core",
]

a = Analysis(
    ["app/main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OnlineDetectionApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OnlineDetectionApp",
)
