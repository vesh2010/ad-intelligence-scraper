# PyInstaller spec for the portable Windows desktop launcher.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(__file__).resolve().parents[1]
PLAYWRIGHT_DATA = Path(__import__('os').environ.get('PLAYWRIGHT_BROWSERS_PATH', ''))

hiddenimports = collect_submodules('playwright') + collect_submodules('uvicorn')
datas = collect_data_files('playwright')

# The build workflow places Chromium beside the bundled application resources.
# Keeping the browser external to the one-file extraction directory avoids PyInstaller
# attempting to execute a browser from an archive. The final artifact is still a single EXE.

analysis = Analysis(
    [str(ROOT / 'desktop_launcher.py')],
    pathex=[str(ROOT), str(ROOT / 'backend')],
    binaries=[],
    datas=datas + [(str(ROOT / 'backend' / 'app'), 'app')],
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
    name='AdIntelligenceScraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
