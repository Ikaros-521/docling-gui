# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（docling-gui，全格式版）。

支持 docling 官方全部输入格式，因此 PDF/图片/音频所需的深度学习栈
（torch/transformers/easyocr 等）必须随包携带，不能排除——产物体积为数 GB 级。
GitHub Actions 三平台均使用本 spec；Linux/Windows 的 torch 走 CPU 轮子以避免
拉入 CUDA 依赖。
"""

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

datas = []
binaries = []
hiddenimports = [
    "docling.document_converter",
    "docling.backend.msword_backend",
    # entry_points 动态加载的默认插件模块，静态分析不可见
    "docling.models.plugins.defaults",
]

for pkg in ("docling_core", "filetype", "latex2mathml", "docx2python", "easyocr", "docling_ibm_models"):
    datas += collect_data_files(pkg)

# qfluentwidgets：qss/图片/字体等资源 + 动态导入
qfw_datas, qfw_binaries, qfw_hiddenimports = collect_all("qfluentwidgets")
datas += qfw_datas
binaries += qfw_binaries
hiddenimports += qfw_hiddenimports

# docling 的插件注册依赖 importlib.metadata.entry_points（发行名为 docling_slim），
# PyInstaller 默认不带 dist-info 元数据，冻结后注册表会变空导致转换失败
for dist in ("docling_slim", "docling_core"):
    datas += copy_metadata(dist)

a = Analysis(
    ["launcher.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5",
        "PyQt6",
        "tkinter",
        "IPython",
        "jupyter",
        "pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="docling-gui",
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
    name="docling-gui",
)
