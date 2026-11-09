"""跨平台 GUI（PySide6 + QFluentWidgets）。"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    FluentIcon,
    FluentWindow,
    FlowLayout,
    InfoBar,
    IndeterminateProgressBar,
    LineEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    ScrollArea,
    TitleLabel,
)

from . import APP_NAME, ORG_NAME, __version__
from .core import OUTPUT_FORMATS


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
        from .core import BatchConverter

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
        from .core import input_format_groups

        self.loaded.emit(input_format_groups())


class MainWindow(FluentWindow):
    def __init__(self, initial_path: str = "") -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(900, 700)
        self.setAcceptDrops(True)
        self.worker: ConvertWorker | None = None
        self.format_loader: FormatListLoader | None = None
        self._format_groups: list[tuple[str, str, frozenset[str]]] = []
        self.format_checks: dict[str, CheckBox] = {}
        self.settings = QSettings(ORG_NAME, "docling-gui")

        # ---------------- 主页面 ----------------
        home = QWidget()
        home.setObjectName("home")
        layout = QVBoxLayout(home)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)

        title = TitleLabel(APP_NAME)
        subtitle = CaptionLabel(
            "递归批量转换 docling 支持的全部格式，跟随已安装 docling 的能力"
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(2)

        # --- 输入/输出卡片 ---
        card = CardWidget(home)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        row_in = QHBoxLayout()
        row_in.addWidget(BodyLabel("输入路径"))
        self.path_edit = LineEdit()
        self.path_edit.setPlaceholderText("文件夹（递归处理）或单个文件；也可直接拖入窗口")
        row_in.addWidget(self.path_edit, 1)
        self.browse_dir_btn = PushButton(FluentIcon.FOLDER, "文件夹…")
        self.browse_dir_btn.clicked.connect(self._browse_folder)
        row_in.addWidget(self.browse_dir_btn)
        self.browse_file_btn = PushButton(FluentIcon.DOCUMENT, "选择文件…")
        self.browse_file_btn.clicked.connect(self._browse_file)
        row_in.addWidget(self.browse_file_btn)
        card_layout.addLayout(row_in)

        row_out = QHBoxLayout()
        row_out.addWidget(BodyLabel("输出目录"))
        self.out_edit = LineEdit()
        self.out_edit.setPlaceholderText("留空 = 与源文件同路径；填写后按原目录结构镜像输出")
        row_out.addWidget(self.out_edit, 1)
        self.out_browse_btn = PushButton(FluentIcon.FOLDER_ADD, "浏览…")
        self.out_browse_btn.clicked.connect(self._browse_out)
        row_out.addWidget(self.out_browse_btn)
        card_layout.addLayout(row_out)

        row_opt = QHBoxLayout()
        row_opt.addWidget(BodyLabel("输出格式"))
        self.format_combo = ComboBox()
        self._format_keys = list(OUTPUT_FORMATS.keys())
        for key in self._format_keys:
            self.format_combo.addItem(OUTPUT_FORMATS[key][1], userData=key)
        row_opt.addWidget(self.format_combo)
        row_opt.addSpacing(16)
        self.recursive_cb = CheckBox("包含子文件夹")
        self.recursive_cb.setChecked(True)
        self.overwrite_cb = CheckBox("覆盖已有输出（默认跳过，可断点续转）")
        self.images_cb = CheckBox("导出图片")
        self.images_cb.setChecked(True)
        row_opt.addWidget(self.recursive_cb)
        row_opt.addWidget(self.overwrite_cb)
        row_opt.addWidget(self.images_cb)
        row_opt.addStretch(1)
        card_layout.addLayout(row_opt)

        # --- 输入格式勾选面板 ---
        fmt_header = QHBoxLayout()
        fmt_header.addWidget(BodyLabel("转换以下输入格式"))
        fmt_header.addStretch(1)
        self.select_all_btn = PushButton("全选")
        self.select_all_btn.setFixedHeight(28)
        self.select_all_btn.clicked.connect(lambda: self._set_all_formats(True))
        self.select_none_btn = PushButton("清空")
        self.select_none_btn.setFixedHeight(28)
        self.select_none_btn.clicked.connect(lambda: self._set_all_formats(False))
        fmt_header.addWidget(self.select_all_btn)
        fmt_header.addWidget(self.select_none_btn)
        card_layout.addLayout(fmt_header)

        self.fmt_scroll = ScrollArea()
        self.fmt_scroll.setWidgetResizable(True)
        self.fmt_scroll.setFixedHeight(130)
        self.fmt_scroll.setStyleSheet("QScrollArea{border:1px solid rgba(0,0,0,0.06); border-radius:8px; background:transparent;}")
        fmt_container = QWidget()
        self.fmt_flow = FlowLayout(fmt_container, needAni=False)
        self.fmt_flow.setContentsMargins(8, 4, 8, 4)
        self.fmt_flow.setHorizontalSpacing(10)
        self.fmt_flow.setVerticalSpacing(4)
        self.fmt_hint = CaptionLabel("正在加载格式列表…")
        self.fmt_hint.setAlignment(Qt.AlignCenter)
        self.fmt_flow.addWidget(self.fmt_hint)
        self.fmt_scroll.setWidget(fmt_container)
        card_layout.addWidget(self.fmt_scroll)
        layout.addWidget(card)

        # --- 操作按钮 ---
        btn_row = QHBoxLayout()
        self.start_btn = PrimaryPushButton(FluentIcon.PLAY, "开始转换")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = PushButton(FluentIcon.PAUSE, "停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # --- 进度 ---
        self.busy_bar = IndeterminateProgressBar(home)
        self.busy_bar.hide()
        self.progress_bar = ProgressBar(home)
        self.progress_bar.hide()
        self.status_label = BodyLabel("待机中")
        layout.addWidget(self.busy_bar)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        # --- 日志 ---
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setPlaceholderText("转换日志…")
        layout.addWidget(self.log_view, 1)

        self.addSubInterface(home, FluentIcon.HOME, "转换")

        # --- 恢复上次设置 ---
        last_path = self.settings.value("last_path", "")
        if not initial_path and last_path:
            initial_path = str(last_path)
        if initial_path:
            self.path_edit.setText(initial_path)
        self.format_combo.setCurrentIndex(int(self.settings.value("out_format_index", 0)))
        self.overwrite_cb.setChecked(self.settings.value("overwrite", False, type=bool))
        self.images_cb.setChecked(self.settings.value("images", True, type=bool))
        self.recursive_cb.setChecked(self.settings.value("recursive", True, type=bool))

        # 异步加载格式列表
        QTimer.singleShot(10, self._load_formats)

    # ------------------------------------------------------- 格式勾选面板
    def _load_formats(self) -> None:
        self.format_loader = FormatListLoader()
        self.format_loader.loaded.connect(self._populate_formats)
        self.format_loader.finished.connect(self.format_loader.deleteLater)
        self.format_loader.start()

    def _populate_formats(self, groups: list) -> None:
        self._format_groups = groups
        self.fmt_flow.removeWidget(self.fmt_hint)
        self.fmt_hint.deleteLater()

        saved: list | None = self.settings.value("formats")
        saved_set = set(saved) if saved else None

        for name, disp, exts in groups:
            cb = CheckBox(disp)
            cb.setToolTip("、".join(sorted(exts)))
            cb.setChecked(True if saved_set is None else name in saved_set)
            self.fmt_flow.addWidget(cb)
            self.format_checks[name] = cb

    def _set_all_formats(self, checked: bool) -> None:
        for cb in self.format_checks.values():
            cb.setChecked(checked)

    def _checked_formats(self) -> set[str]:
        return {name for name, cb in self.format_checks.items() if cb.isChecked()}

    # ------------------------------------------------------------------ 拖拽
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir() or path.is_file():
                self.path_edit.setText(str(path))
                return

    # ------------------------------------------------------------------ 动作
    def _browse_folder(self) -> None:
        start = self._browse_start()
        folder = QFileDialog.getExistingDirectory(self, "选择根文件夹", start)
        if folder:
            self.path_edit.setText(folder)

    def _browse_file(self) -> None:
        start = self._browse_start()
        exts = sorted(
            {e for _, _, group_exts in self._format_groups for e in group_exts}
        )
        pattern = " ".join(f"*.{e}" for e in exts) or "*"
        file, _ = QFileDialog.getOpenFileName(
            self, "选择文件", start, f"支持的格式 ({pattern});;所有文件 (*)"
        )
        if file:
            self.path_edit.setText(file)

    def _browse_out(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "选择输出目录", self.out_edit.text() or self._browse_start()
        )
        if folder:
            self.out_edit.setText(folder)

    def _browse_start(self) -> str:
        return (
            self.path_edit.text()
            or self.settings.value("last_path", "")
            or str(Path.home())
        )

    def _start(self) -> None:
        path_text = self.path_edit.text().strip().strip('"')
        path = Path(path_text) if path_text else None
        if path is None or not (path.is_dir() or path.is_file()):
            InfoBar.warning(
                title=APP_NAME, content="请先选择存在的文件或文件夹", parent=self, duration=3000
            )
            return

        out_dir = self.out_edit.text().strip().strip('"')
        if out_dir and Path(out_dir).is_file():
            InfoBar.warning(
                title=APP_NAME, content="输出目录不能是一个文件路径", parent=self, duration=3000
            )
            return

        checked = self._checked_formats()
        if not checked:
            InfoBar.warning(
                title=APP_NAME, content="请至少勾选一种要转换的输入格式", parent=self, duration=3000
            )
            return

        # 校验单文件时扩展名是否被勾选的格式覆盖
        if path.is_file() and self._format_groups:
            from .core import _is_supported

            exts_union = set().union(
                *(exts for name, _, exts in self._format_groups if name in checked)
            )
            if not _is_supported(path, exts_union):
                InfoBar.warning(
                    title=APP_NAME,
                    content="所选文件的格式未被勾选（请勾选对应格式或换文件）",
                    parent=self,
                    duration=4000,
                )
                return

        self.settings.setValue("last_path", str(path))
        self.settings.setValue("out_format_index", self.format_combo.currentIndex())
        self.settings.setValue("overwrite", self.overwrite_cb.isChecked())
        self.settings.setValue("images", self.images_cb.isChecked())
        self.settings.setValue("recursive", self.recursive_cb.isChecked())
        self.settings.setValue("formats", sorted(checked))

        self.log_view.clear()
        self._log(f"输入：{path}")
        self._log(f"输出：{out_dir if out_dir else '与源文件同路径'}")

        from .core import extensions_of_formats

        self.worker = ConvertWorker(
            path=str(path),
            out_format=self._format_keys[self.format_combo.currentIndex()],
            overwrite=self.overwrite_cb.isChecked(),
            export_images=self.images_cb.isChecked(),
            recursive=self.recursive_cb.isChecked(),
            allowed_exts=frozenset(extensions_of_formats(checked)) if self._format_groups else None,
            out_dir=out_dir,
        )
        self.worker.log_line.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_done)
        self.worker.finished.connect(self.worker.deleteLater)
        self._set_running(True)
        self.worker.start()

    def _stop(self) -> None:
        if self.worker is not None:
            self._log("正在停止…（当前文件处理完后退出）")
            self.worker.stop()

    # ------------------------------------------------------------------ 状态
    def _set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.path_edit.setEnabled(not running)
        self.out_edit.setEnabled(not running)
        self.browse_dir_btn.setEnabled(not running)
        self.browse_file_btn.setEnabled(not running)
        self.out_browse_btn.setEnabled(not running)
        self.select_all_btn.setEnabled(not running)
        self.select_none_btn.setEnabled(not running)
        self.progress_bar.hide()
        self.busy_bar.setVisible(running)

    def _log(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    def _on_progress(self, done: int, total: int) -> None:
        self.busy_bar.hide()
        self.progress_bar.show()
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.status_label.setText(f"进度：{done} / {total}")

    def _on_done(self, ok: int, skipped: int, failed: int, stopped: bool) -> None:
        self._set_running(False)
        self.worker = None
        msg = f"成功 {ok}，跳过 {skipped}，失败 {failed}"
        self.status_label.setText(("已停止" if stopped else "转换完成") + "：" + msg)
        if stopped:
            InfoBar.warning(title="已停止", content=msg, parent=self, duration=4000)
        elif failed:
            InfoBar.error(title="转换完成（有失败项）", content=msg, parent=self, duration=6000)
        else:
            InfoBar.success(title="转换完成", content=msg, parent=self, duration=4000)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None and self.worker.isRunning():
            from PySide6.QtWidgets import QMessageBox

            ret = QMessageBox.question(
                self,
                APP_NAME,
                "转换仍在进行，确定退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.stop()
            self.worker.wait(5000)
        event.accept()


def run_gui(initial_path: str = "") -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow(initial_path)
    window.show()
    return app.exec()
