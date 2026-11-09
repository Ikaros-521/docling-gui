"""跨平台 GUI（PySide6 + QFluentWidgets）。"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QSettings, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    FluentIcon,
    FluentWindow,
    InfoBar,
    IndeterminateProgressBar,
    LineEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
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
        folder: str,
        out_format: str,
        overwrite: bool,
        export_images: bool,
        recursive: bool,
    ):
        super().__init__()
        self.folder = folder
        self.out_format = out_format
        self.overwrite = overwrite
        self.export_images = export_images
        self.recursive = recursive
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
            log=self.log_line.emit,
            progress=self.progress.emit,
            should_stop=self._stop_event.is_set,
        )
        try:
            summary = converter.convert_tree(self.folder)
            self.done.emit(summary.ok, summary.skipped, summary.failed, summary.stopped)
        except Exception as exc:  # 致命错误也要反馈到界面
            self.log_line.emit(f"[错误] {type(exc).__name__}: {exc}")
            self.done.emit(0, 0, 1, False)


class MainWindow(FluentWindow):
    def __init__(self, initial_folder: str = "") -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(880, 640)
        self.setAcceptDrops(True)
        self.worker: ConvertWorker | None = None
        self.settings = QSettings(ORG_NAME, "docling-gui")

        # ---------------- 主页面 ----------------
        home = QWidget()
        home.setObjectName("home")
        layout = QVBoxLayout(home)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)

        title = TitleLabel(APP_NAME)
        subtitle = CaptionLabel(
            "递归批量转换 docling 支持的全部格式，输出保存在源文件同目录（跟随已安装 docling 的能力）"
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(4)

        # --- 设置卡片 ---
        card = CardWidget(home)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(BodyLabel("根目录"))
        self.path_edit = LineEdit()
        self.path_edit.setPlaceholderText("选择或直接拖入文件夹；也可把文件夹拖到程序图标上启动")
        row1.addWidget(self.path_edit, 1)
        self.browse_btn = PushButton(FluentIcon.FOLDER, "浏览…")
        self.browse_btn.clicked.connect(self._browse)
        row1.addWidget(self.browse_btn)
        card_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(BodyLabel("输出格式"))
        self.format_combo = ComboBox()
        self._format_keys = list(OUTPUT_FORMATS.keys())
        for key in self._format_keys:
            self.format_combo.addItem(OUTPUT_FORMATS[key][1], userData=key)
        row2.addWidget(self.format_combo)
        row2.addSpacing(16)
        self.recursive_cb = CheckBox("包含子文件夹")
        self.recursive_cb.setChecked(True)
        self.overwrite_cb = CheckBox("覆盖已有输出（默认跳过，可断点续转）")
        self.images_cb = CheckBox("导出图片")
        self.images_cb.setChecked(True)
        row2.addWidget(self.recursive_cb)
        row2.addWidget(self.overwrite_cb)
        row2.addWidget(self.images_cb)
        row2.addStretch(1)
        card_layout.addLayout(row2)
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
        last_dir = self.settings.value("last_dir", "")
        if not initial_folder and last_dir:
            initial_folder = str(last_dir)
        if initial_folder:
            self.path_edit.setText(initial_folder)
        self.format_combo.setCurrentIndex(int(self.settings.value("out_format_index", 0)))
        self.overwrite_cb.setChecked(self.settings.value("overwrite", False, type=bool))
        self.images_cb.setChecked(self.settings.value("images", True, type=bool))
        self.recursive_cb.setChecked(self.settings.value("recursive", True, type=bool))

    # ------------------------------------------------------------------ 拖拽
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).is_dir():
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                self.path_edit.setText(str(path))
                return

    # ------------------------------------------------------------------ 动作
    def _browse(self) -> None:
        start = self.path_edit.text() or self.settings.value("last_dir", "") or str(Path.home())
        folder = QFileDialog_getExistingDirectory(self, start)
        if folder:
            self.path_edit.setText(folder)

    def _start(self) -> None:
        folder = self.path_edit.text().strip().strip('"')
        if not folder or not Path(folder).is_dir():
            InfoBar.warning(
                title=APP_NAME,
                content="请先选择一个存在的文件夹",
                parent=self,
                duration=3000,
            )
            return
        self.settings.setValue("last_dir", folder)
        self.settings.setValue("out_format_index", self.format_combo.currentIndex())
        self.settings.setValue("overwrite", self.overwrite_cb.isChecked())
        self.settings.setValue("images", self.images_cb.isChecked())
        self.settings.setValue("recursive", self.recursive_cb.isChecked())

        self.log_view.clear()
        self._log(f"根目录：{folder}")
        self.worker = ConvertWorker(
            folder=folder,
            out_format=self._format_keys[self.format_combo.currentIndex()],
            overwrite=self.overwrite_cb.isChecked(),
            export_images=self.images_cb.isChecked(),
            recursive=self.recursive_cb.isChecked(),
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
        self.browse_btn.setEnabled(not running)
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


def QFileDialog_getExistingDirectory(parent, start: str) -> str:
    from PySide6.QtWidgets import QFileDialog

    return QFileDialog.getExistingDirectory(parent, "选择根目录", str(start))


def run_gui(initial_folder: str = "") -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow(initial_folder)
    window.show()
    return app.exec()
