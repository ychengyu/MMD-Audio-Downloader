# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:/MMD Audio Downloader/main.py'],
    pathex=[],
    binaries=[],
    datas=[('E:/MMD Audio Downloader/assets', 'assets')],
    hiddenimports=['PySide6.QtCore', 'PySide6.QtWidgets', 'PySide6.QtGui', 'PySide6.QtMultimedia', 'yt_dlp', 'yt_dlp.extractor', 'yt_dlp.extractor._extractors', 'yt_dlp.downloader', 'yt_dlp.postprocessor'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MMD_Audio_Downloader',
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
    icon=['E:/MMD Audio Downloader/assets/app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MMD_Audio_Downloader',
)
