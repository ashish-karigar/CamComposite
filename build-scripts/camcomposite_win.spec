# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

SPEC_DIR = Path(SPEC).resolve().parent
PROJECT_ROOT = SPEC_DIR.parent

a = Analysis(
    [str(PROJECT_ROOT / "src" / "main.py")],
    pathex=[
        str(PROJECT_ROOT),
        str(PROJECT_ROOT / "src"),
    ],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / "assets"), "assets"),
        (str(PROJECT_ROOT / "packaging" / "win"), "packaging/win"),
    ],
    hiddenimports=[
        "pyvirtualcam",
        "cv2",
        "PIL",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CamComposite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    icon=str(PROJECT_ROOT / "assets" / "icons" / "CamComposite.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CamComposite",
)