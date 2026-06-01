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
    "torch",
    "torchvision",
    "ultralytics",
    "ultralytics.engine.results",
    "ultralytics.utils.ops",
    "anomalib.models.image.efficient_ad.torch_model",
    "seat_defect_core",
    "seat_defect_core.api",
    "seat_defect_core.service.core",
    "seat_defect_core.yolo.detection",
    "seat_defect_core.efficientad.engine",
    "seat_defect_core.classifier.engine",
    "seat_defect_core.calibration.registry",
    "seat_defect_core.rule_engine",
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

production_config = Analysis(
    ["app/production_config.py"],
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
production_config_pyz = PYZ(production_config.pure)
production_config_exe = EXE(
    production_config_pyz,
    production_config.scripts,
    [],
    exclude_binaries=True,
    name="OnlineDetectionConfigWizard",
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

model_check = Analysis(
    ["app/model_check.py"],
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
model_check_pyz = PYZ(model_check.pure)
model_check_exe = EXE(
    model_check_pyz,
    model_check.scripts,
    [],
    exclude_binaries=True,
    name="OnlineDetectionModelCheck",
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

site_report = Analysis(
    ["app/site_report.py"],
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
site_report_pyz = PYZ(site_report.pure)
site_report_exe = EXE(
    site_report_pyz,
    site_report.scripts,
    [],
    exclude_binaries=True,
    name="OnlineDetectionSiteReport",
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
    production_config_exe,
    camera_check_exe,
    model_check_exe,
    line_check_exe,
    mvs_list_exe,
    site_report_exe,
    gui.binaries,
    gui.datas,
    diagnostics.binaries,
    diagnostics.datas,
    production_config.binaries,
    production_config.datas,
    camera_check.binaries,
    camera_check.datas,
    model_check.binaries,
    model_check.datas,
    line_check.binaries,
    line_check.datas,
    mvs_list.binaries,
    mvs_list.datas,
    site_report.binaries,
    site_report.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OnlineDetectionApp",
)
