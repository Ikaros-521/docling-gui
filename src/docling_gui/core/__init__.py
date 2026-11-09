"""核心域逻辑：格式发现、文件扫描、批量转换。

本包不依赖任何 GUI 框架，GUI 与 CLI 共用。
公开 API 见各模块；常用入口在此统一再导出。
"""

from .formats import (
    INPUT_FORMAT_DISPLAY,
    OUTPUT_FORMATS,
    extensions_of_formats,
    input_format_groups,
    is_supported_file,
    supported_extensions,
)
from .scanner import collect_supported_files
from .converter import BatchConverter, Summary

__all__ = [
    "INPUT_FORMAT_DISPLAY",
    "OUTPUT_FORMATS",
    "BatchConverter",
    "Summary",
    "collect_supported_files",
    "extensions_of_formats",
    "input_format_groups",
    "is_supported_file",
    "supported_extensions",
]
