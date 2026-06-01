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

gui = Analysis(
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
gui_pyz = PYZ(gui.pure)

gui_exe = EXE(
    gui_pyz,
    gui.scripts,
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

diagnostics = Analysis(
    ["app/diagnostics.py"],
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
diagnostics_pyz = PYZ(diagnostics.pure)
diagnostics_exe = EXE(
    diagnostics_pyz,
    diagnostics.scripts,
    [],
    exclude_binaries=True,
    name="OnlineDetectionDiagnostics",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

camera_check = Analysis(
    ["app/camera_check.py"],
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
camera_check_pyz = PYZ(camera_check.pure)
camera_check_exe = EXE(
    camera_check_pyz,
    camera_check.scripts,
    [],
    exclude_binaries=True,
    name="OnlineDetectionCameraCheck",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

line_check = Analysis(
    ["app/line_check.py"],
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
line_check_pyz = PYZ(line_check.pure)
line_check_exe = EXE(
    line_check_pyz,
    line_check.scripts,
    [],
    exclude_binaries=True,
    name="OnlineDetectionLineCheck",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

mvs_list = Analysis(
    ["app/mvs_list.py"],
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
mvs_list_pyz = PYZ(mvs_list.pure)
mvs_list_exe = EXE(
    mvs_list_pyz,
    mvs_list.scripts,
    [],
    exclude_binaries=True,
    name="OnlineDetectionMvsList",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    gui_exe,
    diagnostics_exe,
    camera_check_exe,
    line_check_exe,
    mvs_list_exe,
    gui.binaries,
    gui.datas,
    diagnostics.binaries,
    diagnostics.datas,
    camera_check.binaries,
    camera_check.datas,
    line_check.binaries,
    line_check.datas,
    mvs_list.binaries,
    mvs_list.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OnlineDetectionApp",
)
