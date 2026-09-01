# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import shutil
from PyInstaller.utils.hooks import collect_submodules

project_dir = Path(SPECPATH)
src_dir = project_dir / "src"
icon_path = project_dir / "assets" / "app_icon.ico"

# Qt6Core.dll is loaded by PySide6.QtCore.pyd from the PySide6 directory.
# Keep the MSVC runtime DLLs beside the Qt binaries in the one-file bundle;
# PyInstaller may otherwise deduplicate them under shiboken6, where the
# Windows DLL loader cannot find them when QtCore is imported.
pyside6_dir = Path(__import__("PySide6").__file__).parent
shiboken6_dir = Path(__import__("shiboken6").__file__).parent
qt_runtime_dlls = [
    (str(pyside6_dir / name), "PySide6")
    for name in (
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "msvcp140_codecvt_ids.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
    )
    if (pyside6_dir / name).exists()
]
shiboken_runtime_dlls = [
    (str(shiboken6_dir / name), "PySide6")
    for name in ("shiboken6.abi3.dll",)
    if (shiboken6_dir / name).exists()
]

# Qt6Core dynamically loads ICU on Windows.  The Python distribution used to
# build this application does not ship ICU itself, so include the available
# ICU runtime DLLs in the bundle when present (for example from the bundled
# Poppler runtime used by the workspace).
icu_runtime_dlls = []
icu_dirs = [
    Path(os.environ.get("QT_ICU_DIR", "")),
    Path(shutil.which("icuuc.dll") or "").parent,
    Path(r"C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin"),
]
for icu_dir in icu_dirs:
    if icu_dir.is_dir():
        icu_runtime_dlls.extend(
            (str(path), "PySide6")
            for path in icu_dir.glob("icu*.dll")
        )
        if icu_runtime_dlls:
            break

# 打包图标文件到 exe 内部
datas = [
    (str(icon_path), "assets"),
]

# 收集所有需要的子模块
openpyxl_imports = collect_submodules("openpyxl")
borehole_imports = collect_submodules("borehole")

excludes = [
    "tkinter",
    "matplotlib",
    "numpy",
    "scipy",
    "pandas",
    "PIL",
    "chardet",
    "charset_normalizer",
    # PySide6 不需要的模块
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtConcurrent",
    "PySide6.QtDataVisualization",
    "PySide6.QtDBus",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtHttpServer",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtPrintSupport",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtXml",
    "PySide6.QtXmlPatterns",
    # shiboken
    "shiboken6.shiboken6",
]

a = Analysis(
    [str(project_dir / "run.py")],
    pathex=[str(src_dir)],
    binaries=qt_runtime_dlls + shiboken_runtime_dlls + icu_runtime_dlls,
    datas=datas,
    hiddenimports=openpyxl_imports + borehole_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure, optimize=2)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="钻孔数据编辑工具v3",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)
