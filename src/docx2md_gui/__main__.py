"""入口模块。

- 源码运行：python -m docx2md_gui [文件夹]
- 不带文件夹 / --gui：启动图形界面
- 打包后的 exe：直接拖文件夹到 exe 上也会启动 GUI；--cli 强制命令行模式
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        # 中文 Windows 控制台（GBK）可能无法编码部分字符，降级输出不丢行
        try:
            out = sys.stdout
            if out is None:
                return
            enc = getattr(out, "encoding", None) or "utf-8"
            out.buffer.write(msg.encode(enc, errors="replace") + b"\n")
            out.buffer.flush()
        except Exception:
            pass
    except Exception:  # windowed exe 里 sys.stdout 可能为 None
        pass


def _fix_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docx2md",
        description="递归把文件夹内所有 .docx 转成同路径同名 .md（基于 docling）",
    )
    parser.add_argument("folder", nargs="?", default="", help="要处理的根文件夹（不传则启动 GUI）")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的 .md（默认跳过）")
    parser.add_argument("--no-images", action="store_true", help="不导出内嵌图片")
    parser.add_argument("--flat", action="store_true", help="不递归子文件夹")
    parser.add_argument("--gui", action="store_true", help="强制启动 GUI")
    parser.add_argument("--cli", action="store_true", help="强制命令行模式（打包 exe 中使用）")
    parser.add_argument("--version", action="store_true", help="显示版本号后退出")
    args = parser.parse_args(argv)

    from . import __version__

    if args.version:
        _safe_print(f"docx2md {__version__}")
        return 0

    frozen = getattr(sys, "frozen", False)
    folder = args.folder

    # 决定走 GUI 还是 CLI
    if args.gui or not folder:
        return _run_gui(folder)
    if frozen and not args.cli:
        # windowed exe 下拖拽文件夹启动：没有控制台，CLI 输出无处显示，进 GUI
        return _run_gui(folder)

    # ---------------- CLI 模式 ----------------
    _fix_console_encoding()
    root = Path(folder)
    if not root.is_dir():
        _safe_print(f"错误：文件夹不存在：{root}")
        return 2

    from .core import BatchConverter

    converter = BatchConverter(
        overwrite=args.overwrite,
        export_images=not args.no_images,
        recursive=not args.flat,
        log=_safe_print,
    )
    summary = converter.convert_tree(root)
    return 0 if (summary.failed == 0 and not summary.stopped) else 1


def _run_gui(folder: str) -> int:
    from .app import run_gui

    return run_gui(folder)


if __name__ == "__main__":
    sys.exit(main())
