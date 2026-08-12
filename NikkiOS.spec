from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


root = Path(SPEC).resolve().parent
datas = [
    (str(root / "assets"), "assets"),
    (str(root / ".env.example"), "."),
]
datas += collect_data_files("dashscope")

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=["PyQt6.QtWebEngineWidgets", "PyQt6.QtWebChannel", "pyaudio", "pygetwindow"],
    hookspath=[],
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
    name="NikkiOS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="NikkiOS",
)
