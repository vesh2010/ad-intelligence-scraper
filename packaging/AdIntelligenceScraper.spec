from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(__file__).resolve().parents[1]
BROWSERS = ROOT / "packaging" / "browsers"
TOOLS = ROOT / "packaging" / "tools"

datas = collect_data_files("playwright") + [(str(ROOT / "backend" / "app"), "app")]
hiddenimports = collect_submodules("playwright") + collect_submodules("uvicorn")
if BROWSERS.is_dir():
    datas.append((str(BROWSERS), "browsers"))
if TOOLS.is_dir():
    datas.append((str(TOOLS), "tools"))

analysis = Analysis(
    [str(ROOT / "desktop_launcher.py")],
    pathex=[str(ROOT), str(ROOT / "backend")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="AdIntelligenceScraper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
