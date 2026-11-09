"""核心转换逻辑：递归扫描 docling 支持的输入文件，转换为指定输出格式。

- 输入：文件夹（递归/平铺）或单个文件；可按 InputFormat 勾选过滤
- 输出：与源文件同路径（默认），或镜像目录结构输出到自定义目录
支持的格式动态取自已安装的 docling，天然跟随官方能力。
本模块不依赖任何 GUI 框架，GUI 与 CLI 共用。
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]
StopFn = Callable[[], bool]

# 输出格式 -> (文件后缀, 显示名)。API 见 DoclingDocument.export_to_* / save_as_json
OUTPUT_FORMATS: dict[str, tuple[str, str]] = {
    "md": (".md", "Markdown"),
    "html": (".html", "HTML"),
    "json": (".json", "JSON（DoclingDocument 无损）"),
    "doctags": (".doctags", "DocTags XML"),
    "txt": (".txt", "纯文本"),
}

# docling InputFormat 名称 -> 界面显示名（未列出的回退为英文名）
INPUT_FORMAT_DISPLAY: dict[str, str] = {
    "PDF": "PDF",
    "DOCX": "Word 新版（docx）",
    "DOC": "Word 旧版（doc，需 LibreOffice）",
    "RTF": "RTF（需 LibreOffice）",
    "PPTX": "PowerPoint 新版",
    "PPT": "PowerPoint 旧版（需 LibreOffice）",
    "HTML": "HTML/XHTML",
    "MHTML": "MHTML/MHT",
    "IMAGE": "图片",
    "ASCIIDOC": "AsciiDoc",
    "MD": "Markdown/文本",
    "CSV": "CSV",
    "XLSX": "Excel 新版",
    "XLS": "Excel 旧版（需 LibreOffice）",
    "ODT": "OpenDocument 文字",
    "ODS": "OpenDocument 表格",
    "ODP": "OpenDocument 演示",
    "XML_USPTO": "XML（USPTO 专利）",
    "XML_JATS": "XML（JATS 学术）",
    "XML_XBRL": "XML（XBRL 财报）",
    "XML_DOCLANG": "DocLang XML",
    "DCLX": "DocLang 归档",
    "METS_GBS": "METS（Google Books）",
    "JSON_DOCLING": "Docling JSON",
    "AUDIO": "音频",
    "VIDEO": "视频（仅取音轨，需 ffmpeg）",
    "VTT": "WebVTT 字幕",
    "LATEX": "LaTeX",
    "EMAIL": "Email（eml/msg）",
    "EPUB": "EPUB",
    "BOXNOTE": "BoxNote",
    "IWORK_PAGES": "iWork Pages（需扩展）",
    "IWORK_KEYNOTE": "iWork Keynote（需扩展）",
    "IWORK_NUMBERS": "iWork Numbers（需扩展）",
    "EBCDIC": "EBCDIC",
    "AFP": "AFP/MO:DCA",
    "CALENDAR": "iCalendar",
}


@dataclass
class Summary:
    total: int = 0
    ok: int = 0
    skipped: int = 0
    failed: int = 0
    stopped: bool = False
    failed_files: list[str] = field(default_factory=list)


def supported_extensions() -> set[str]:
    """从已安装的 docling 动态获取全部支持的输入扩展名（小写，不含点）。"""
    from docling.datamodel.base_models import FormatToExtensions

    exts: set[str] = set()
    for values in FormatToExtensions.values():
        exts.update(str(v).lower().lstrip(".") for v in values)
    return exts


def input_format_groups() -> list[tuple[str, str, frozenset[str]]]:
    """返回 [(InputFormat名, 显示名, {扩展名}), ...]，用于界面勾选与过滤。"""
    from docling.datamodel.base_models import FormatToExtensions, InputFormat

    groups: list[tuple[str, str, frozenset[str]]] = []
    for fmt in InputFormat:
        exts = frozenset(
            str(e).lower().lstrip(".") for e in FormatToExtensions.get(fmt, [])
        )
        if exts:
            groups.append((fmt.name, INPUT_FORMAT_DISPLAY.get(fmt.name, fmt.name), exts))
    return groups


def extensions_of_formats(names: set[str]) -> frozenset[str]:
    """给定 InputFormat 名称集合，返回其全部扩展名的并集。"""
    exts: set[str] = set()
    for name, _, group_exts in input_format_groups():
        if name in names:
            exts.update(group_exts)
    return frozenset(exts)


def _is_supported(path: Path, exts: set[str]) -> bool:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in exts:
        return True
    return path.name.lower().endswith(".tar.gz")  # METS_GBS 双扩展名


def collect_supported_files(
    root: str | Path,
    recursive: bool = True,
    allowed_exts: set[str] | frozenset[str] | None = None,
) -> Iterator[Path]:
    """收集 root 下所有 docling 支持的文件。

    root 可以是文件夹（递归或平铺）或单个文件。
    allowed_exts 为 None 时不过滤（全部支持格式）；否则只保留扩展名命中的文件。
    跳过：隐藏目录/文件（. 开头）、Office 临时锁文件（~$ 开头）、
    本工具自身导出的 <名称>_images 目录（避免上一轮产物被再次当作输入）。
    """
    root = Path(root)
    exts = allowed_exts if allowed_exts is not None else supported_extensions()

    if root.is_file():
        if _is_supported(root, exts):
            yield root
        return

    iterator = root.rglob("*") if recursive else root.glob("*")
    for path in sorted(iterator):
        if not path.is_file():
            continue
        name = path.name
        if name.startswith("~$") or name.startswith("."):
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts[:-1]):
            continue
        if "_images" in path.parent.name:
            continue
        if _is_supported(path, exts):
            yield path


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
        if root_path.is_file():
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
        # 图片目录跟随输出文件所在目录（自定义输出目录时与 .md 放在一起）
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
