# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

核心思路：docx→md 只需要 docling 的 MSWord 后端（纯 Python + lxml + PIL），
用不到 torch/transformers/OCR 栈。这些包在 docling 里都是受保护的可选导入
（try/except ImportError），因此可以安全排除，让产物从 ~1.5GB 降到 ~100MB 级。
GitHub Actions 三平台均使用本 spec。
"""

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

datas = []
for pkg in ("docling_core", "filetype", "latex2mathml", "docx2python"):
    datas += collect_data_files(pkg)
# docling 的插件注册依赖 importlib.metadata.entry_points（发行名为 docling_slim），
# PyInstaller 默认不带 dist-info 元数据，冻结后注册表会变空导致转换失败
datas += copy_metadata("docling_slim")

a = Analysis(
    ["launcher.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "docling.document_converter",
        "docling.backend.msword_backend",
        # entry_points 动态加载的默认插件模块，静态分析不可见
        "docling.models.plugins.defaults",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ---- 深度学习栈（docx 转换用不到）----
        "torch",
        "torchvision",
        "torchaudio",
        "transformers",
        "tokenizers",
        "safetensors",
        "accelerate",
        "huggingface_hub",
        "easyocr",
        "onnxruntime",
        "cv2",
        "scipy",
        "skimage",
        "matplotlib",
        "docling_ibm_models",
        # ---- 未使用的其他 GUI 框架 ----
        "PyQt5",
        "PyQt6",
        "tkinter",
        # ---- 交互环境 ----
        "IPython",
        "jupyter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="docx2md",
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
    name="docx2md",
)
