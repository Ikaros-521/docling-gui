"""跨平台 GUI（PySide6）。"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, ORG_NAME, __version__


class ConvertWorker(QThread):
    """后台转换线程，通过信号把日志/进度/结果发回 UI 线程。"""

    log_line = Signal(str)
    progress = Signal(int, int)  # 当前序号, 总数
    done = Signal(int, int, int, bool)  # 成功, 跳过, 失败, 是否被手动停止

    def __init__(self, folder: str, overwrite: bool, export_images: bool, recursive: bool):
        super().__init__()
        self.folder = folder
        self.overwrite = overwrite
        self.export_images = export_images
        self.recursive = recursive
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        from .core import BatchConverter

        converter = BatchConverter(
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


class MainWindow(QMainWindow):
    def __init__(self, initial_folder: str = "") -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(780, 540)
        self.setAcceptDrops(True)
        self.worker: ConvertWorker | None = None

        from PySide6.QtCore import QSettings

        self.settings = QSettings(ORG_NAME, "docx2md")

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # --- 目录选择行 ---
        row = QHBoxLayout()
        row.addWidget(QLabel("根目录:"))
        self.path_edit = QLineEdit(initial_folder or "")
        self.path_edit.setPlaceholderText("选择或直接拖入一个文件夹，将递归转换其中所有 .docx")
        row.addWidget(self.path_edit, 1)
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._browse)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        # --- 选项行 ---
        opt_row = QHBoxLayout()
        self.overwrite_cb = QCheckBox("覆盖已存在的 .md（不勾选则跳过，可断点续转）")
        self.images_cb = QCheckBox("导出图片")
        self.images_cb.setChecked(True)
        self.recursive_cb = QCheckBox("包含子文件夹")
        self.recursive_cb.setChecked(True)
        opt_row.addWidget(self.overwrite_cb)
        opt_row.addWidget(self.images_cb)
        opt_row.addWidget(self.recursive_cb)
        opt_row.addStretch(1)
        layout.addLayout(opt_row)

        # --- 按钮行 ---
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("开始转换")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # --- 进度条 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("待机中")
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)

        # --- 日志区 ---
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        layout.addWidget(self.log_view, 1)

        self.setCentralWidget(central)

        last_dir = self.settings.value("last_dir", "")
        if not self.path_edit.text() and last_dir:
            self.path_edit.setText(str(last_dir))

    # ------------------------------------------------------------------ 拖拽
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).is_dir():
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                self.path_edit.setText(str(path))
                return

    # ------------------------------------------------------------------ 动作
    def _browse(self) -> None:
        start = self.path_edit.text() or self.settings.value("last_dir", "") or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "选择根目录", str(start))
        if folder:
            self.path_edit.setText(folder)

    def _start(self) -> None:
        folder = self.path_edit.text().strip().strip('"')
        if not folder or not Path(folder).is_dir():
            QMessageBox.warning(self, APP_NAME, "请先选择一个存在的文件夹")
            return
        self.settings.setValue("last_dir", folder)

        self.log_view.clear()
        self._log(f"根目录：{folder}")
        self.worker = ConvertWorker(
            folder=folder,
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
        if not running:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(1)
        else:
            self.progress_bar.setRange(0, 0)  # 忙碌态，等扫描完成后再设为确定值
            self.progress_bar.setValue(0)

    def _log(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    def _on_progress(self, done: int, total: int) -> None:
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.progress_label.setText(f"进度：{done} / {total}")

    def _on_done(self, ok: int, skipped: int, failed: int, stopped: bool) -> None:
        self._set_running(False)
        self.worker = None
        title = "已停止" if stopped else "转换完成"
        msg = f"成功 {ok}，跳过 {skipped}，失败 {failed}"
        self.progress_label.setText(f"{title}：{msg}")
        QMessageBox.information(self, title, msg)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None and self.worker.isRunning():
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


def run_gui(initial_folder: str = "") -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow(initial_folder)
    window.show()
    return app.exec()
