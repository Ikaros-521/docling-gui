"""批量转换器：扫描 → docling 解析 → 输出（同路径或镜像目录）。"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .formats import OUTPUT_FORMATS
from .scanner import collect_supported_files

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]
StopFn = Callable[[], bool]


@dataclass
class Summary:
    """一次批量转换的结果汇总。"""

    total: int = 0
    ok: int = 0
    skipped: int = 0
    failed: int = 0
    stopped: bool = False
    failed_files: list[str] = field(default_factory=list)


class BatchConverter:
    """批量转换器。log/progress/should_stop 由调用方注入（GUI 或 CLI 各自实现）。"""

    def __init__(
        self,
        out_format: str = "md",
        overwrite: bool = False,
        export_images: bool = True,
        recursive: bool = True,
        allowed_exts: set[str] | frozenset[str] | None = None,
        out_dir: str | Path | None = None,
        log: LogFn | None = None,
        progress: ProgressFn | None = None,
        should_stop: StopFn | None = None,
    ) -> None:
        if out_format not in OUTPUT_FORMATS:
            raise ValueError(f"不支持的输出格式：{out_format}")
        self.out_format = out_format
        self.overwrite = overwrite
        self.export_images = export_images
        self.recursive = recursive
        self.allowed_exts = frozenset(allowed_exts) if allowed_exts is not None else None
        self.out_dir = Path(out_dir) if out_dir else None
        self._log = log if log is not None else (lambda _msg: None)
        self._progress = progress
        self._should_stop = should_stop

    # ------------------------------------------------------------------ out
    def log(self, msg: str) -> None:
        self._log(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def convert_tree(self, root: str | Path) -> Summary:
        root_path = Path(root)
        files = sorted(collect_supported_files(root_path, self.recursive, self.allowed_exts))
        # 原始格式优先：md/html/json/doctags/txt 既是输入也是输出格式，
        # 否则上一轮的输出可能先被转换，"抢走"原始文件的转换名额
        out_suffixes = {suffix for suffix, _ in OUTPUT_FORMATS.values()}
        files.sort(key=lambda p: (p.suffix.lower() in out_suffixes, str(p).lower()))

        summary = Summary(total=len(files))
        mode = "同路径" if self.out_dir is None else str(self.out_dir)
        self.log(
            f"扫描完成：共找到 {len(files)} 个受支持的文件"
            f"（输入：{root_path} | 输出：{mode}）"
        )
        if not files:
            return summary

        self.log("正在初始化 docling 引擎（首次可能较慢；PDF/图片/音频需模型，会自动下载）…")
        converter = self._make_converter()
        out_suffix = OUTPUT_FORMATS[self.out_format][0]

        for src in files:
            if self._should_stop is not None and self._should_stop():
                summary.stopped = True
                self.log("已手动停止，剩余文件未处理")
                break
            if self._progress is not None:
                self._progress(summary.ok + summary.skipped + summary.failed + 1, summary.total)

            if src.suffix.lower() == out_suffix:
                # 输入与输出同后缀：转换无意义，且 --overwrite 时会覆盖源文件
                summary.skipped += 1
                self.log(f"跳过（输入与输出格式相同）: {src}")
                continue

            dst = self._resolve_dst(root_path, src, out_suffix)
            if dst.exists() and not self.overwrite:
                summary.skipped += 1
                self.log(f"跳过（输出已存在）: {src}")
                continue
            try:
                self._convert_one(converter, src, dst)
                summary.ok += 1
                self.log(f"转换成功: {src} -> {dst}")
            except Exception as exc:
                summary.failed += 1
                summary.failed_files.append(str(src))
                self.log(f"转换失败: {src} - {type(exc).__name__}: {exc}")

        self.log(
            f"转换结束：成功 {summary.ok}，跳过 {summary.skipped}，"
            f"失败 {summary.failed}，共 {summary.total}"
        )
        return summary

    # ------------------------------------------------------------- internal
    def _resolve_dst(self, root_path: Path, src: Path, out_suffix: str) -> Path:
        """计算输出路径：默认同路径；指定 out_dir 时按相对根的目录结构镜像。"""
        if self.out_dir is None:
            return src.with_suffix(out_suffix)
        if root_path.is_file() or root_path == src:  # 单文件输入
            return (self.out_dir / src.name).with_suffix(out_suffix)
        return (self.out_dir / src.relative_to(root_path)).with_suffix(out_suffix)

    def _make_converter(self):
        from docling.document_converter import DocumentConverter

        # 不限制 allowed_formats：支持已安装 docling 的全部输入格式
        # （输入格式过滤在扫描阶段已完成，这里交给 docling 自行嗅探）
        return DocumentConverter()

    def _convert_one(self, converter, src: Path, dst: Path) -> None:
        from docling.datamodel.base_models import ConversionStatus
        from docling_core.types.doc import ImageRefMode

        result = converter.convert(str(src))
        if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
            detail = "; ".join(str(e) for e in result.errors) or str(result.status)
            raise RuntimeError(detail)
        if result.status == ConversionStatus.PARTIAL_SUCCESS and result.errors:
            self.log(f"（警告）部分内容可能丢失: {src} - {'; '.join(str(e) for e in result.errors)}")

        document = result.document
        # 必须用绝对路径：docling-core 对 image_dir 的相对路径解释不统一
        # （md 相对 CWD，html/json 相对输出文件目录），绝对路径可消除歧义。
        # 图片目录跟随输出文件所在目录（自定义输出目录时与输出文件放在一起）
        images_dir = (dst.parent / f"{src.stem}_images").resolve()
        use_images = self.export_images and bool(document.pictures)
        if use_images and images_dir.exists():
            shutil.rmtree(images_dir, ignore_errors=True)

        if self.out_format == "md":
            if use_images:
                text = document.export_to_markdown(
                    image_mode=ImageRefMode.REFERENCED,
                    image_dir=images_dir,
                    image_uri_prefix=f"{images_dir.name}/",
                )
            else:
                text = document.export_to_markdown()
            self._write_text(dst, text)
        elif self.out_format == "html":
            if use_images:
                text = document.export_to_html(
                    image_mode=ImageRefMode.REFERENCED,
                    image_dir=images_dir,
                    image_uri_prefix=f"{images_dir.name}/",
                )
            else:
                text = document.export_to_html()
            self._write_text(dst, text)
        elif self.out_format == "json":
            if use_images:
                document.save_as_json(
                    dst, image_mode=ImageRefMode.REFERENCED, artifacts_dir=images_dir
                )
            else:
                document.save_as_json(dst, image_mode=ImageRefMode.PLACEHOLDER)
        elif self.out_format == "doctags":
            self._write_text(dst, document.export_to_doctags())
        elif self.out_format == "txt":
            self._write_text(dst, document.export_to_text())
        else:  # pragma: no cover
            raise ValueError(f"不支持的输出格式：{self.out_format}")

    @staticmethod
    def _write_text(dst: Path, text: str) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8", newline="\n")
