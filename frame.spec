# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Frame browser — optimized for size."""
from pathlib import Path

block_cipher = None

project_root = Path(SPECPATH)
frame_dir = project_root / "frame"

# ── Data files ────────────────────────────────────────────────────
frame_data = [
    (str(frame_dir / "data" / "adblock_hosts.txt"), "frame/data"),
    (str(frame_dir / "data" / "id.json"), "frame/data"),
    (str(frame_dir / "data" / "ikon.png"), "frame/data"),
]

# ── Hidden imports — HANYA yang benar-benar dipakai ───────────────
hidden_imports = [
    # Qt core
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtNetwork",
    "PyQt6.QtSvg",
    "PyQt6.QtSvgWidgets",
    # QtWebEngine + dependency wajibnya
    # CATATAN: QtWebEngineWidgets ternyata butuh QtQuick/QtQml secara
    # internal, jadi jangan di-exclude meski kita pakai widget mode.
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebChannel",
    "PyQt6.QtQml",
    "PyQt6.QtQuick",
    "PyQt6.QtOpenGL",
    "PyQt6.QtOpenGLWidgets",
    "PyQt6.QtPrintSupport",
    # SIP
    "PyQt6.sip",
]

# ── Excludes — buang Qt module & Python package yang tidak dipakai ─
excludes = [
    # QtWebEngineQuick — pakai widget mode, bukan QML WebView
    "PyQt6.QtWebEngineQuick",
    # QtQuick3D — tidak dipakai QtWebEngine
    "PyQt6.QtQuick3D",
    # Qt3D (tidak dipakai)
    "PyQt6.Qt3DAnimation", "PyQt6.Qt3DCore", "PyQt6.Qt3DExtras",
    "PyQt6.Qt3DInput", "PyQt6.Qt3DLogic", "PyQt6.Qt3DRender",
    # Qt miscellaneous (tidak dipakai)
    "PyQt6.QtBluetooth", "PyQt6.QtCharts", "PyQt6.QtDataVisualization",
    "PyQt6.QtDesigner", "PyQt6.QtHelp",
    "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtNetworkAuth", "PyQt6.QtNfc", "PyQt6.QtPositioning",
    "PyQt6.QtRemoteObjects", "PyQt6.QtSensors", "PyQt6.QtSerialPort",
    "PyQt6.QtSpatialAudio", "PyQt6.QtSql",
    "PyQt6.QtStateMachine", "PyQt6.QtTest",
    "PyQt6.QtTextToSpeech", "PyQt6.QtWebSockets", "PyQt6.QtXml",
    "PyQt6.QAxContainer", "PyQt6.QtDBus",
    "PyQt6.lupdate", "PyQt6.uic",
    # Python package yang tidak dipakai
    "tkinter", "matplotlib", "numpy", "scipy", "PIL", "pandas",
    "IPython", "jupyter", "pytest", "pygame", "setuptools",
]

# ── Analysis ──────────────────────────────────────────────────────
a = Analysis(
    ["run_frame.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=frame_data,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Frame",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="frame/data/ikon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Frame",
)

# ══════════════════════════════════════════════════════════════════
#  Post-build cleanup
# ══════════════════════════════════════════════════════════════════
import shutil

dist_root = project_root / "dist" / "Frame" / "_internal"
qt6_root = dist_root / "PyQt6" / "Qt6"
bin_dir = qt6_root / "bin"
plugins_root = qt6_root / "plugins"

# 1. Hapus file debug (tidak dipakai di produksi)
for pattern in ("*.debug.pak", "*.debug.bin"):
    for p in qt6_root.rglob(pattern):
        try:
            p.unlink()
        except OSError:
            pass

# 2. Hapus Qt plugins yang tidak dipakai
unused_plugin_dirs = [
    "sqldrivers",       # Frame tidak pakai database
    "multimedia",       # QtMultimedia di-exclude
    "mediaservice",
    "audio",
    "bearer",           # network bearer (usang)
    "playlistformats",
    "position",
    "sensors",
    "nfc",
    "qmltooling",
    "renderers",
    "sceneparsers",
    "texttospeech",
    "virtualkeyboard",
    "webview",          # QtWebView (beda dari QtWebEngine)
]
for name in unused_plugin_dirs:
    target = plugins_root / name
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)

# 3. Hapus imageformat plugins yang tidak dipakai
#    (keep: gif, ico, jpeg, svg, webp)
keep_imageformats = {"qgif.dll", "qico.dll", "qjpeg.dll", "qsvg.dll", "qwebp.dll"}
imageformats = plugins_root / "imageformats"
if imageformats.exists():
    for f in imageformats.iterdir():
        if f.is_file() and f.name not in keep_imageformats:
            try:
                f.unlink()
            except OSError:
                pass

# 4. Hapus translations Qt (keep hanya en + id)
keep_translations = {"qtbase_en.qm", "qtbase_id.qm",
                     "qt_en.qm", "qt_id.qm"}
translations = qt6_root / "translations"
if translations.exists():
    for f in translations.iterdir():
        if f.is_file() and f.name not in keep_translations:
            try:
                f.unlink()
            except OSError:
                pass

# 5. Hapus folder qml HANYA yang 3D-related.
#    QtWebEngineWidgets butuh sisa folder qml (QtQuick base).
qml_dir = qt6_root / "qml"
if qml_dir.exists():
    quick3d_qml = qml_dir / "QtQuick3D"
    if quick3d_qml.exists():
        shutil.rmtree(quick3d_qml, ignore_errors=True)

# 6. Hapus DLL QtQuick3D saja.
#    JANGAN hapus Qt6Quick.dll / Qt6Qml.dll / Qt6QuickControls2* —
#    QtWebEngineWidgets import-nya akan gagal kalau dihapus.
quick3d_dlls = [
    "Qt6Quick3D.dll", "Qt6Quick3DAssetImport.dll",
    "Qt6Quick3DAssetUtils.dll", "Qt6Quick3DEffects.dll",
    "Qt6Quick3DHelpers.dll", "Qt6Quick3DHelpersImpl.dll",
    "Qt6Quick3DIblBaker.dll", "Qt6Quick3DParticleEffects.dll",
    "Qt6Quick3DParticles.dll", "Qt6Quick3DPhysics.dll",
    "Qt6Quick3DPhysicsHelpers.dll", "Qt6Quick3DRuntimeRender.dll",
    "Qt6Quick3DUtils.dll",
    "Qt6ShaderTools.dll",
]
for name in quick3d_dlls:
    target = bin_dir / name
    if target.exists():
        try:
            target.unlink()
        except OSError:
            pass

# 7. Hapus DevTools UI resources (Ctrl+Shift+I DevTools akan disable).
#    Comment dua baris di bawah kalau mau DevTools tetap bisa dipakai.
devtools_pak = qt6_root / "resources" / "qtwebengine_devtools_resources.pak"
if devtools_pak.exists():
    try:
        devtools_pak.unlink()
    except OSError:
        pass

# 8. Sisakan hanya locale English + Indonesia (buang ~30 bahasa lain)
locales_dir = qt6_root / "translations" / "qtwebengine_locales"
if locales_dir.exists():
    keep = {"en-US.pak", "en-GB.pak", "id.pak"}
    for f in locales_dir.iterdir():
        if f.is_file() and f.name not in keep:
            try:
                f.unlink()
            except OSError:
                pass
