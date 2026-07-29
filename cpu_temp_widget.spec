# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：CPU/GPU 温度悬浮窗。

生成单文件 exe，内置：
- LibreHardwareMonitor/ 目录（LHM 库 + 依赖 dll）
- app.ico 图标
- 通过 --uac-admin 让 exe 自动请求管理员权限
"""
import os

block_cipher = None
HERE = os.path.abspath(".")

a = Analysis(
    ['cpu_temp_widget.py'],
    pathex=[HERE],
    binaries=[],
    datas=[
        # (源目录, 打包内目标目录) - 把整个 LibreHardwareMonitor 目录打进去
        (os.path.join(HERE, 'LibreHardwareMonitor'), 'LibreHardwareMonitor'),
    ],
    hiddenimports=[
        # pythonnet 相关，确保被收集
        'clr',
        'clr_loader',
        'pythonnet',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 只排除确定不需要的，标准库之间互相依赖，不能乱排
        'tkinter',
        'unittest',
        'pydoc_data',
    ],
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
    name='CPU温度悬浮窗',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # 不用 UPX（避免 dll 被压缩后 .NET 加载失败）
    runtime_tmpdir=None,
    console=False,       # 无控制台窗口
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,      # ★ exe 自动请求管理员权限（弹 UAC）
    icon=os.path.join(HERE, 'app.ico'),
)
