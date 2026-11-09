"""GUI 后台线程任务：转换、格式列表加载、更新检查。"""

from __future__ import annotations

import json
import threading
import urllib.request

from PySide6.QtCore import QThread, Signal


class ConvertWorker(QThread):
    """后台转换线程，通过信号把日志/进度/结果发回 UI 线程。"""

    log_line = Signal(str)
    progress = Signal(int, int)  # 当前序号, 总数
    done = Signal(int, int, int, bool)  # 成功, 跳过, 失败, 是否被手动停止

    def __init__(
        self,
        path: str,
        out_format: str,
        overwrite: bool,
        export_images: bool,
        recursive: bool,
        allowed_exts: frozenset[str] | None,
        out_dir: str,
    ):
        super().__init__()
        self.path = path
        self.out_format = out_format
        self.overwrite = overwrite
        self.export_images = export_images
        self.recursive = recursive
        self.allowed_exts = allowed_exts
        self.out_dir = out_dir
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        from ..core import BatchConverter

        converter = BatchConverter(
            out_format=self.out_format,
            overwrite=self.overwrite,
            export_images=self.export_images,
            recursive=self.recursive,
            allowed_exts=self.allowed_exts,
            out_dir=self.out_dir or None,
            log=self.log_line.emit,
            progress=self.progress.emit,
            should_stop=self._stop_event.is_set,
        )
        try:
            summary = converter.convert_tree(self.path)
            self.done.emit(summary.ok, summary.skipped, summary.failed, summary.stopped)
        except Exception as exc:  # 致命错误也要反馈到界面
            self.log_line.emit(f"[错误] {type(exc).__name__}: {exc}")
            self.done.emit(0, 0, 1, False)


class FormatListLoader(QThread):
    """后台加载 docling 支持的输入格式列表（导入 docling 较重，避免卡 UI）。"""

    loaded = Signal(list)  # [(InputFormat名, 显示名, {扩展名}), ...]

    def run(self) -> None:
        from ..core import input_format_groups

        self.loaded.emit(input_format_groups())


class UpdateChecker(QThread):
    """从 GitHub Releases 查询最新版本。"""

    done = Signal(str, str, str)  # latest_tag（失败为空串）, 当前版本, 错误信息

    def __init__(self, repo: str, current_version: str):
        super().__init__()
        self.repo = repo
        self.current_version = current_version

    def run(self) -> None:
        url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "docling-gui", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.load(resp)
            tag = str(data.get("tag_name", "")).strip()
            self.done.emit(tag, self.current_version, "" if tag else "no release")
        except Exception as exc:
            self.done.emit("", self.current_version, f"{type(exc).__name__}: {exc}")


def version_tuple(version: str) -> tuple[int, ...]:
    """'v0.3.1' / '0.3.1' -> (0, 3, 1)，供版本比较。"""
    parts = version.strip().lstrip("vV").split(".")
    nums: list[int] = []
    for part in parts:
        digits = "".join(ch for ch in part if ch.isdigit())
        nums.append(int(digits) if digits else 0)
    return tuple(nums)
