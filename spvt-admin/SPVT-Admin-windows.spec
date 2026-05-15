# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Windows (no macOS BUNDLE block).
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

# PyInstaller подставляет SPEC — путь к этому файлу.
_spec_dir = Path(os.path.abspath(SPEC)).parent
_icon_path = _spec_dir / "assets" / "spvt-admin.ico"
_APP_ICON = str(_icon_path) if _icon_path.is_file() else None
_datas = []
if _icon_path.is_file():
    _datas.append((str(_icon_path), "assets"))
# Корневые сертификаты для HTTPS (requests/ssl на «чужих» ПК).
_datas += collect_data_files("certifi")

block_cipher = None

a = Analysis(
    ["spvt_admin/__main__.py"],
    pathex=[],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "certifi",
        "urllib3",
        "ssl",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_exe_kw = dict(
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
if _APP_ICON is not None:
    _exe_kw["icon"] = _APP_ICON

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SPVT_Admin",
    **_exe_kw,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SPVT_Admin",
)
