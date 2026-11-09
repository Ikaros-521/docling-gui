"""格式元数据：输出格式清单 + 输入格式动态发现（跟随已安装 docling 的能力）。"""

from __future__ import annotations

# 输出格式 -> (文件后缀, 显示名)。API 见 DoclingDocument.export_to_* / save_as_json
OUTPUT_FORMATS: dict[str, tuple[str, str]] = {
    "md": (".md", "Markdown"),
    "html": (".html", "HTML"),
    "json": (".json", "JSON（DoclingDocument 无损）"),
    "doctags": (".doctags", "DocTags XML"),
    "txt": (".txt", "纯文本"),
}

# docling InputFormat 名称 -> 中文显示名（GUI 的英文界面用 i18n 的 fmt_* 键覆盖）
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


def is_supported_file(path, exts: set[str] | frozenset[str]) -> bool:
    """判断文件扩展名是否在给定集合内（处理 .tar.gz 双扩展名）。"""
    from pathlib import Path

    p = Path(path)
    if p.name.lower().endswith(".tar.gz"):  # METS_GBS 双扩展名
        return True
    return p.suffix.lower().lstrip(".") in exts
