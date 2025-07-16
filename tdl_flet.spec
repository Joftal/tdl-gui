# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['tdl_flet.py'],
    pathex=[],
    binaries=[],
    datas=[('tdl.exe', '.')],  # 添加tdl.exe作为数据文件
    hiddenimports=[
        'flet',
        'flet_core',
        'httpx',
        'PIL',
        'psutil',
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TDL下载器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ico.ico',  # 更新为正确的图标文件名
    version='file_version_info.txt',
) 