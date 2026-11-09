"""文件扫描：收集 docling 支持的待转换文件，支持文件夹递归与格式过滤。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from .formats import is_supported_file, supported_extensions


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
        if is_supported_file(root, exts):
            yield root
        return

    iterator = root.rglob("*") if recursive else root.glob("*")
    for path in sorted(iterator):
        if not _is_convertible(path, root, exts):
            continue
        yield path


def _is_convertible(path: Path, root: Path, exts: set[str] | frozenset[str]) -> bool:
    if not path.is_file():
        return False
    name = path.name
    if name.startswith("~$") or name.startswith("."):
        return False
    if any(part.startswith(".") for part in path.relative_to(root).parts[:-1]):
        return False
    if "_images" in path.parent.name:
        return False
    return is_supported_file(path, exts)
