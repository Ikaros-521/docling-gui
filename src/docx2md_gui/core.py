"""核心转换逻辑：递归扫描 .docx，用 docling 转成同名 .md（输出到源文件同目录）。

本模块不依赖任何 GUI 框架，GUI 与 CLI 共用。
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

DOCX_SUFFIXES = {".docx"}

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]
StopFn = Callable[[], bool]


@dataclass
class Summary:
    total: int = 0
    ok: int = 0
    skipped: int = 0
    failed: int = 0
    stopped: bool = False
    failed_files: list[str] = field(default_factory=list)


def collect_docx_files(root: str | Path, recursive: bool = True) -> Iterator[Path]:
    """收集 root 下（含子文件夹）的所有 .docx 文件，跳过 Office 临时锁文件（~$ 开头）。"""
    root = Path(root)
    iterator = root.rglob("*") if recursive else root.glob("*")
    for path in sorted(iterator):
        if (
            path.is_file()
            and path.suffix.lower() in DOCX_SUFFIXES
            and not path.name.startswith("~$")
        ):
            yield path


class BatchConverter:
    """批量转换器。log/progress/should_stop 由调用方注入（GUI 或 CLI 各自实现）。"""

    def __init__(
        self,
        overwrite: bool = False,
        export_images: bool = True,
        recursive: bool = True,
        log: LogFn | None = None,
        progress: ProgressFn | None = None,
        should_stop: StopFn | None = None,
    ) -> None:
        self.overwrite = overwrite
        self.export_images = export_images
        self.recursive = recursive
        self._log = log if log is not None else (lambda _msg: None)
        self._progress = progress
        self._should_stop = should_stop

    # ------------------------------------------------------------------ out
    def log(self, msg: str) -> None:
        self._log(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def convert_tree(self, root: str | Path) -> Summary:
        files = sorted(collect_docx_files(root, self.recursive))
        summary = Summary(total=len(files))
        self.log(f"扫描完成：共找到 {len(files)} 个 .docx 文件（根目录：{root}）")
        if not files:
            return summary

        self.log("正在初始化 docling 引擎（首次加载可能需要几秒）…")
        converter = self._make_converter()

        for index, src in enumerate(files, 1):
            if self._should_stop is not None and self._should_stop():
                summary.stopped = True
                self.log("已手动停止，剩余文件未处理")
                break
            if self._progress is not None:
                self._progress(index, summary.total)

            dst = src.with_suffix(".md")
            if dst.exists() and not self.overwrite:
                summary.skipped += 1
                self.log(f"跳过（md 已存在）: {src}")
                continue
            try:
                self._convert_one(converter, src, dst)
                summary.ok += 1
                self.log(f"转换成功: {src} -> {dst.name}")
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
    def _make_converter(self):
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter

        # 只允许 docx：不走 PDF/OCR 管线，无需下载任何模型
        return DocumentConverter(allowed_formats=[InputFormat.DOCX])

    def _convert_one(self, converter, src: Path, dst: Path) -> None:
        from docling.datamodel.base_models import ConversionStatus
        from docling_core.types.doc import ImageRefMode

        result = converter.convert(str(src))
        if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
            detail = "; ".join(str(e) for e in result.errors) or str(result.status)
            raise RuntimeError(detail)
        if result.status == ConversionStatus.PARTIAL_SUCCESS and result.errors:
            self.log(f"（警告）部分内容可能丢失: {src} — {'; '.join(str(e) for e in result.errors)}")

        document = result.document
        images_dir = src.parent / f"{src.stem}_images"

        if self.export_images and document.pictures:
            # 官方导出机制：图片存到 <同名>_images/，md 内为相对链接
            if images_dir.exists():
                shutil.rmtree(images_dir, ignore_errors=True)
            md = document.export_to_markdown(
                image_mode=ImageRefMode.REFERENCED,
                image_dir=images_dir,
                image_uri_prefix=f"{images_dir.name}/",
            )
        else:
            md = document.export_to_markdown()

        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(md, encoding="utf-8", newline="\n")
