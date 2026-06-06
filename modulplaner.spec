# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für den FHNW Modulplaner.

Baut plattformabhängig:
  macOS   -> dist/Modulplaner.app   (windowed, Quit via Dock/Cmd-Q)
  Windows -> dist/Modulplaner.exe   (Konsolenfenster, Schließen beendet die App)

Bauen:  pyinstaller --noconfirm modulplaner.spec
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_all

# certifi-Zertifikate mitnehmen (TLS für requests gegen die FHNW-API)
datas = [("templates", "templates")]
binaries = []
hiddenimports = ["certifi"]
datas += collect_data_files("certifi")

# pywebview (natives Fenster) vollständig einbinden inkl. plattformspezifischer
# Backends (macOS: Cocoa/WebKit via pyobjc; Windows: EdgeChromium via pythonnet)
_wv_datas, _wv_binaries, _wv_hidden = collect_all("webview")
datas += _wv_datas
binaries += _wv_binaries
hiddenimports += _wv_hidden

# Optionales App-Icon: lege icon.icns (macOS) bzw. icon.ico (Windows) neben diese
# Spec, dann werden sie automatisch verwendet.
import os
_icon_mac = "icon.icns" if os.path.exists("icon.icns") else None
_icon_win = "icon.ico" if os.path.exists("icon.ico") else None

block_cipher = None

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == "darwin":
    # macOS: windowed Bundle, kein Konsolenfenster
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="Modulplaner",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        icon=_icon_mac,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        name="Modulplaner",
    )
    app = BUNDLE(
        coll,
        name="Modulplaner.app",
        icon=_icon_mac,
        bundle_identifier="ch.fhnw.modulplaner",
    )
else:
    # Windows/Linux: onefile-EXE, windowed (kein Konsolenfenster) — das pywebview-
    # Fenster ist die App; Schließen beendet sie. Bei fehlendem Fenster-Backend
    # greift der Browser-Fallback in app.py, daher kein „stummer" Start.
    # (Für Debugging vorübergehend console=True setzen, um Logs zu sehen.)
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="Modulplaner",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        icon=_icon_win,
    )
