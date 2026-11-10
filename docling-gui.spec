# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（docling-gui，全格式版）。

支持 docling 官方全部输入格式，因此 PDF/图片/音频所需的深度学习栈
（torch/transformers/easyocr 等）必须随包携带，不能排除——产物体积为数 GB 级。
GitHub Actions 三平台均使用本 spec；Linux/Windows 的 torch 走 CPU 轮子以避免
拉入 CUDA 依赖。
"""

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    copy_metadata,
)

datas = []
binaries = []
hiddenimports = [
    "docling.document_converter",
    "docling.backend.msword_backend",
    # entry_points 动态加载的默认插件模块，静态分析不可见
    "docling.models.plugins.defaults",
    # torchvision 的 C++ 算子扩展（注册 torchvision::nms 等）。0.29 起 stable-abi
    # 轮子把模块从 _C 改名为 _C_stable，hooks-contrib 的 hook 只声明旧名导致
    # 落空；缺库时 transformers 加载 image processor 报
    # "operator torchvision::nms does not exist"。旧名不存在时 PyInstaller 仅告警
    "torchvision._C",
    "torchvision._C_stable",
]

# "docx"（python-docx）的页眉/页脚模板是包内数据文件（docx/templates/*.xml），
# 静态分析不会自动携带；冻结后 docx 后端首次处理页眉会 FileNotFoundError，
# 最终表现为 docling 抛 "Pipeline SimplePipeline failed"
# docling_parse 的 pdf_resources（fonts/glyphs/cmap，约 25MB）是 C++ 解析器打开
# PDF 的必需资源；rapidocr 的 ONNX 模型同理。均为包内数据目录，静态分析不会
# 收集，缺失时冻结产物打开 PDF 直接 RuntimeError
for pkg in (
    "docling_core",
    "filetype",
    "latex2mathml",
    "docx2python",
    "easyocr",
    "docling_ibm_models",
    "docx",
    "docling_parse",
    "rapidocr",
):
    datas += collect_data_files(pkg)

# torchvision 的 C++ 算子库（_C_stable.so/.pyd 等）注册 torchvision::nms 等算子，
# transformers 的 fast image processor 依赖它；hooks-contrib 对 0.29 的 stable-abi
# 命名收集有缺口，缺库时报 "operator torchvision::nms does not exist"
binaries += collect_dynamic_libs("torchvision")

# qfluentwidgets：qss/图片/字体等资源 + 动态导入
qfw_datas, qfw_binaries, qfw_hiddenimports = collect_all("qfluentwidgets")
datas += qfw_datas
binaries += qfw_binaries
hiddenimports += qfw_hiddenimports

# docling 的插件注册依赖 importlib.metadata.entry_points（发行名为 docling_slim），
# PyInstaller 默认不带 dist-info 元数据，冻结后注册表会变空导致转换失败
for dist in ("docling_slim", "docling_core"):
    datas += copy_metadata(dist)

# 打包 docling 模型工件（布局 + 表格），运行时实现 PDF/图片离线转换。
# CI 先经 snapshot_download 生成 models/ 目录（布局 docling-project--<repo>）；
# 本地无该目录时跳过（转换器会回退到按需在线下载）。运行时由
# docling_gui.core.models.bundled_artifacts_path() 定位并注入 artifacts_path
import os

from pathlib import Path as _Path

_models_dir = os.environ.get("DOCLING_MODELS_DIR") or "models"
if (_Path(_models_dir) / "docling-project--docling-layout-heron").is_dir():
    _root = _Path(_models_dir)
    for _p in sorted(_root.rglob("*")):
        if _p.is_file() and ".cache" not in _p.parts:
            datas.append(
                (str(_p), str(_Path("docling-models") / _p.relative_to(_root).parent))
            )
    print(f"spec: bundling docling models from {_root}")

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
    # python-docx 用 __file__ 相对路径访问模板（docx/parts/../templates/*.xml）。
    # 纯 py 模块默认进 PYZ 归档，磁盘上没有 docx/parts 目录：POSIX 内核逐级
    # 解析路径要求中间目录真实存在，冻结后 Linux/macOS 会 FileNotFoundError
    # （Windows 的 Win32 对 .. 做词法规范化所以侥幸能过）。改为实体 .py 落盘。
    # transformers 的入口类（AutoImageProcessor 等）走 _LazyModule 动态
    # import，静态分析收不齐子模块，冻结后加载布局模型即失败；整包实体
    # 落盘让所有惰性导入按正常文件机制解析（hooks-contrib 的 hook 对
    # transformers 5.x 不够）。
    module_collection_mode={"docx": "py", "transformers": "py"},
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
