from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("src") + ["obsws_python", "NDIlib"]

a = Analysis(
    ["../src/main.py"],
    pathex=[".."],
    binaries=[
    ("/opt/anaconda3/envs/CamComposite/lib/libpython3.10.dylib", "Frameworks"),
    ],
    datas=[
        ("../assets", "assets"),
        ("../src/helpers", "src/helpers"),
        ("../src/prototypes", "src/prototypes"),
        ("../src/services", "src/services"),
        ("../src/ui", "src/ui"),
        ("../src/utils", "src/utils"),
        ("../assets/bin/macos/ffmpeg", "assets/bin/macos"),
        ("../packaging/mac/resources/CamComposite-OBS.json", "."),
        ("../packaging/mac/resources/mac-first-run-setup.sh", "."),
        ("../packaging/mac/resources/obs-studio-32.0.4-macos-apple.dmg", "."),
        ("../packaging/mac/resources/distroav-6.1.1-macos-universal.pkg", "."),
        ("../packaging/mac/resources/libNDI_for_Mac.pkg", "."),
    ],
    hiddenimports=hiddenimports,
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
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CamComposite",
)

app = BUNDLE(
    coll,
    name="CamComposite.app",
    icon="../assets/icons/CamComposite.icns",
    bundle_identifier="com.camcomposite.app",
    info_plist={
        "CFBundleName": "CamComposite",
        "CFBundleDisplayName": "CamComposite",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSCameraUsageDescription": "CamComposite needs camera access to detect and preview connected cameras.",
    },
)