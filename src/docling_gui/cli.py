"""命令行入口（argparse）。

界面语言跟随 GUI 设置；CLI 自身输出保持中文。
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
    except Exception:  # windowed 打包里 sys.stdout 可能为 None
        pass


def _fix_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def _setup_logging(to_file: bool) -> None:
    """把根 logger 接到可见出口。

    docling 等三方库把真实异常只记进 logging（`_log.exception`），应用若不接
    handler，冻结 GUI 里这些根因会静默丢失。CLI 模式输出到 stderr（WARNING+
    即可，ERROR 级会带堆栈）；GUI 模式写轮转日志文件供事后排查。
    """
    import logging
    from logging.handlers import RotatingFileHandler

    root = logging.getLogger()
    if to_file:
        root.setLevel(logging.INFO)
        try:
            log_dir = Path.home() / ".docling-gui"
            log_dir.mkdir(parents=True, exist_ok=True)
            handler: logging.Handler = RotatingFileHandler(
                log_dir / "docling-gui.log",
                maxBytes=1_000_000,
                backupCount=2,
                encoding="utf-8",
            )
        except OSError:
            return  # 日志写不了也不能挡住转换主流程
    else:
        root.setLevel(logging.WARNING)
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(handler)


def _resolve_formats(spec: str) -> frozenset[str] | None:
    """把 'pdf,docx,image' 这样的 InputFormat 名单解析为扩展名集合。"""
    from .core import input_format_groups

    valid = {name.lower(): (name, exts) for name, _, exts in input_format_groups()}
    allowed: set[str] = set()
    for token in spec.split(","):
        t = token.strip().lower()
        if not t:
            continue
        if t not in valid:
            _safe_print(f"错误：未知输入格式 {token!r}。可用值：")
            _safe_print("  " + "  ".join(sorted(valid)))
            raise SystemExit(2)
        allowed.update(valid[t][1])
    return frozenset(allowed) if allowed else None


def build_parser() -> argparse.ArgumentParser:
    from . import __version__
    from .core import OUTPUT_FORMATS

    parser = argparse.ArgumentParser(
        prog="docling-gui",
        description="递归把文件夹（或单个文件）内 docling 支持的文件转为指定格式；"
        "默认输出到源文件同路径，可用 --out 指定输出目录（镜像目录结构）",
    )
    parser.add_argument("path", nargs="?", default="", help="要处理的文件或根文件夹（不传则启动 GUI）")
    parser.add_argument(
        "--to",
        choices=list(OUTPUT_FORMATS.keys()),
        default="md",
        help="输出格式：md/html/json/doctags/txt（默认 md）",
    )
    parser.add_argument("--out", default="", help="输出目录（留空 = 与源文件同路径；按原目录结构镜像）")
    parser.add_argument(
        "--formats", default="", help="只转换指定格式，逗号分隔 InputFormat 名（如 pdf,docx,image；留空 = 全部）"
    )
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的输出（默认跳过）")
    parser.add_argument("--no-images", action="store_true", help="不导出内嵌图片")
    parser.add_argument("--flat", action="store_true", help="不递归子文件夹")
    parser.add_argument("--gui", action="store_true", help="强制启动 GUI")
    parser.add_argument("--cli", action="store_true", help="强制命令行模式")
    parser.add_argument("--list-formats", action="store_true", help="列出当前 docling 支持的输入格式后退出")
    parser.add_argument("--version", action="store_true", help="显示版本号后退出")
    return parser


def main(argv: list[str] | None = None) -> int:
    from . import __version__

    args = build_parser().parse_args(argv)

    if args.version:
        _safe_print(f"docling-gui {__version__}")
        return 0

    if args.list_formats:
        from .core import input_format_groups, supported_extensions

        _fix_console_encoding()
        _safe_print("支持的输入格式（来自已安装的 docling）：")
        for name, disp, exts in input_format_groups():
            _safe_print(f"  {name:<14} {disp}  [{' '.join(sorted(exts))}]")
        _safe_print("\n全部扩展名：")
        _safe_print("  " + "  ".join(sorted(supported_extensions())))
        return 0

    path = args.path
    # windowed 打包下拖拽文件/文件夹启动：没有控制台，CLI 输出无处显示，进 GUI
    run_as_gui = args.gui or not path or (getattr(sys, "frozen", False) and not args.cli)
    _setup_logging(to_file=run_as_gui)
    if run_as_gui:
        return _run_gui(path)

    # ---------------- CLI 模式 ----------------
    _fix_console_encoding()
    root = Path(path)
    if not root.is_dir() and not root.is_file():
        _safe_print(f"错误：路径不存在：{root}")
        return 2

    allowed_exts = _resolve_formats(args.formats) if args.formats.strip() else None

    from .core import BatchConverter

    converter = BatchConverter(
        out_format=args.to,
        overwrite=args.overwrite,
        export_images=not args.no_images,
        recursive=not args.flat,
        allowed_exts=allowed_exts,
        out_dir=args.out or None,
        log=_safe_print,
    )
    summary = converter.convert_tree(root)
    return 0 if (summary.failed == 0 and not summary.stopped) else 1


def _run_gui(path: str) -> int:
    from .gui import run_gui

    return run_gui(path)
