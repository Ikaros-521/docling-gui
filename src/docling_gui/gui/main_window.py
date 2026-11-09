"""主窗口：转换页 + 设置页（FluentWindow 双页导航，支持中英文热切换）。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget
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

from .. import APP_NAME, ORG_NAME, REPO_URL, __version__
from ..core import OUTPUT_FORMATS, extensions_of_formats, input_format_groups, is_supported_file
from ..i18n import LANGUAGES, get_language, set_language, t
from .settings_page import SettingsPage
from .workers import ConvertWorker, FormatListLoader, UpdateChecker, version_tuple

_ROUTE_HOME = "home"
_ROUTE_SETTINGS = "settings"


class MainWindow(FluentWindow):
    def __init__(self, initial_path: str = "") -> None:
        super().__init__()
        self.settings = QSettings(ORG_NAME, "docling-gui")
        set_language(self.settings.value("language") or _system_language())

        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(900, 700)
        self.setAcceptDrops(True)
        self.worker: ConvertWorker | None = None
        self.format_loader: FormatListLoader | None = None
        self.update_checker: UpdateChecker | None = None
        self._format_groups: list[tuple[str, str, frozenset[str]]] = []
        self.format_checks: dict[str, CheckBox] = {}

        self._build_home_page()
        self.settings_page = SettingsPage()
        self.settings_page.setObjectName("settings")
        self.settings_page.languageChanged.connect(self._on_language_changed)
        self.settings_page.checkUpdateRequested.connect(self._start_update_check)

        self.addSubInterface(self.home, FluentIcon.HOME, t("nav_convert"))
        self.addSubInterface(self.settings_page, FluentIcon.SETTING, t("nav_settings"))

        self._restore_settings(initial_path)
        self._retranslate()
        QTimer.singleShot(10, self._load_formats)

    # ================================================================ 构建UI
    def _build_home_page(self) -> None:
        self.home = QWidget()
        self.home.setObjectName(_ROUTE_HOME)
        layout = QVBoxLayout(self.home)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)

        self.title_label = TitleLabel()
        self.subtitle_label = CaptionLabel()
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addSpacing(2)

        # --- 输入/输出卡片 ---
        card = CardWidget(self.home)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        row_in = QHBoxLayout()
        self.input_label = BodyLabel()
        self.path_edit = LineEdit()
        row_in.addWidget(self.input_label)
        row_in.addWidget(self.path_edit, 1)
        self.browse_dir_btn = PushButton(FluentIcon.FOLDER, "")
        self.browse_dir_btn.clicked.connect(self._browse_folder)
        row_in.addWidget(self.browse_dir_btn)
        self.browse_file_btn = PushButton(FluentIcon.DOCUMENT, "")
        self.browse_file_btn.clicked.connect(self._browse_file)
        row_in.addWidget(self.browse_file_btn)
        card_layout.addLayout(row_in)

        row_out = QHBoxLayout()
        self.output_label = BodyLabel()
        self.out_edit = LineEdit()
        row_out.addWidget(self.output_label)
        row_out.addWidget(self.out_edit, 1)
        self.out_browse_btn = PushButton(FluentIcon.FOLDER_ADD, "")
        self.out_browse_btn.clicked.connect(self._browse_out)
        row_out.addWidget(self.out_browse_btn)
        card_layout.addLayout(row_out)

        row_opt = QHBoxLayout()
        self.out_format_label = BodyLabel()
        self.format_combo = ComboBox()
        self._format_keys = list(OUTPUT_FORMATS.keys())
        for _ in self._format_keys:
            self.format_combo.addItem("")
        row_opt.addWidget(self.out_format_label)
        row_opt.addWidget(self.format_combo)
        row_opt.addSpacing(16)
        self.recursive_cb = CheckBox()
        self.overwrite_cb = CheckBox()
        self.images_cb = CheckBox()
        row_opt.addWidget(self.recursive_cb)
        row_opt.addWidget(self.overwrite_cb)
        row_opt.addWidget(self.images_cb)
        row_opt.addStretch(1)
        card_layout.addLayout(row_opt)

        # --- 输入格式勾选面板 ---
        fmt_header = QHBoxLayout()
        self.formats_header = BodyLabel()
        fmt_header.addWidget(self.formats_header)
        fmt_header.addStretch(1)
        self.select_all_btn = PushButton()
        self.select_all_btn.setFixedHeight(28)
        self.select_all_btn.clicked.connect(lambda: self._set_all_formats(True))
        self.select_none_btn = PushButton()
        self.select_none_btn.setFixedHeight(28)
        self.select_none_btn.clicked.connect(lambda: self._set_all_formats(False))
        fmt_header.addWidget(self.select_all_btn)
        fmt_header.addWidget(self.select_none_btn)
        card_layout.addLayout(fmt_header)

        self.fmt_scroll = ScrollArea()
        self.fmt_scroll.setWidgetResizable(True)
        self.fmt_scroll.setFixedHeight(130)
        self.fmt_scroll.setStyleSheet(
            "QScrollArea{border:1px solid rgba(0,0,0,0.06); border-radius:8px; background:transparent;}"
        )
        fmt_container = QWidget()
        self.fmt_flow = FlowLayout(fmt_container, needAni=False)
        self.fmt_flow.setContentsMargins(8, 4, 8, 4)
        self.fmt_flow.setHorizontalSpacing(10)
        self.fmt_flow.setVerticalSpacing(4)
        self.fmt_hint = CaptionLabel()
        self.fmt_hint.setAlignment(Qt.AlignCenter)
        self.fmt_flow.addWidget(self.fmt_hint)
        self.fmt_scroll.setWidget(fmt_container)
        card_layout.addWidget(self.fmt_scroll)
        layout.addWidget(card)

        # --- 操作按钮 ---
        btn_row = QHBoxLayout()
        self.start_btn = PrimaryPushButton(FluentIcon.PLAY, "")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = PushButton(FluentIcon.PAUSE, "")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # --- 进度 ---
        self.busy_bar = IndeterminateProgressBar(self.home)
        self.busy_bar.hide()
        self.progress_bar = ProgressBar(self.home)
        self.progress_bar.hide()
        self.status_label = BodyLabel()
        layout.addWidget(self.busy_bar)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        # --- 日志 ---
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        layout.addWidget(self.log_view, 1)

    # ================================================================ 多语言
    def _retranslate(self) -> None:
        """按当前语言刷新全部静态文案（含导航与设置页）。"""
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.title_label.setText(APP_NAME)
        self.subtitle_label.setText(t("app_subtitle"))
        self._set_nav_text(_ROUTE_HOME, t("nav_convert"))
        self._set_nav_text(_ROUTE_SETTINGS, t("nav_settings"))

        self.input_label.setText(t("input_path"))
        self.path_edit.setPlaceholderText(t("input_placeholder"))
        self.browse_dir_btn.setText(t("browse_folder"))
        self.browse_file_btn.setText(t("browse_file"))
        self.output_label.setText(t("output_dir"))
        self.out_edit.setPlaceholderText(t("output_placeholder"))
        self.out_browse_btn.setText(t("out_browse"))
        self.out_format_label.setText(t("out_format"))
        for i, key in enumerate(self._format_keys):
            self.format_combo.setItemText(i, t(f"out_{key}"))
        self.recursive_cb.setText(t("opt_recursive"))
        self.overwrite_cb.setText(t("opt_overwrite"))
        self.images_cb.setText(t("opt_images"))
        self.formats_header.setText(t("formats_header"))
        self.select_all_btn.setText(t("select_all"))
        self.select_none_btn.setText(t("clear"))
        if self.fmt_hint is not None:
            self.fmt_hint.setText(t("formats_loading"))
        self.start_btn.setText(t("start"))
        self.stop_btn.setText(t("stop"))
        self.status_label.setText(t("idle"))
        self.log_view.setPlaceholderText("…")

        self.settings_page._retranslate()

    def _set_nav_text(self, route_key: str, text: str) -> None:
        """更新导航项文本（防御式：不同版本 qfluentwidgets 的 panel API 可能不同）。"""
        panel = getattr(self.navigationInterface, "panel", None)
        widget = panel.widget(route_key) if panel is not None and hasattr(panel, "widget") else None
        if widget is not None and hasattr(widget, "setText"):
            widget.setText(text)

    def _on_language_changed(self, _lang: str) -> None:
        self._retranslate()

    # ================================================================ 格式面板
    def _load_formats(self) -> None:
        self.format_loader = FormatListLoader()
        self.format_loader.loaded.connect(self._populate_formats)
        self.format_loader.finished.connect(self.format_loader.deleteLater)
        self.format_loader.start()

    def _populate_formats(self, groups: list) -> None:
        self._format_groups = groups
        if self.fmt_hint is not None:
            self.fmt_flow.removeWidget(self.fmt_hint)
            self.fmt_hint.deleteLater()
            self.fmt_hint = None
        if self.format_checks:  # 幂等：重复加载（异步回调 + 测试直调）时先清空
            for cb in self.format_checks.values():
                self.fmt_flow.removeWidget(cb)
                cb.deleteLater()
            self.format_checks.clear()

        saved = self.settings.value("formats")
        saved_set = set(saved) if saved else None

        for name, _disp, exts in groups:
            cb = CheckBox(t(f"fmt_{name}"))
            cb.setToolTip("、".join(sorted(exts)))
            cb.setChecked(True if saved_set is None else name in saved_set)
            self.fmt_flow.addWidget(cb)
            self.format_checks[name] = cb

    def _set_all_formats(self, checked: bool) -> None:
        for cb in self.format_checks.values():
            cb.setChecked(checked)

    def _checked_formats(self) -> set[str]:
        return {name for name, cb in self.format_checks.items() if cb.isChecked()}

    # ================================================================ 拖拽/浏览
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir() or path.is_file():
                self.path_edit.setText(str(path))
                return

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("browse_folder"), self._browse_start())
        if folder:
            self.path_edit.setText(folder)

    def _browse_file(self) -> None:
        exts = sorted({e for _, _, group_exts in self._format_groups for e in group_exts})
        pattern = " ".join(f"*.{e}" for e in exts) or "*"
        file, _ = QFileDialog.getOpenFileName(
            self, t("browse_file"), self._browse_start(), f"* ({pattern});;All files (*)"
        )
        if file:
            self.path_edit.setText(file)

    def _browse_out(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, t("output_dir"), self.out_edit.text() or self._browse_start()
        )
        if folder:
            self.out_edit.setText(folder)

    def _browse_start(self) -> str:
        return self.path_edit.text() or self.settings.value("last_path", "") or str(Path.home())

    # ================================================================ 转换
    def _start(self) -> None:
        path_text = self.path_edit.text().strip().strip('"')
        path = Path(path_text) if path_text else None
        if path is None or not (path.is_dir() or path.is_file()):
            InfoBar.warning(title=APP_NAME, content=t("warn_no_input"), parent=self, duration=3000)
            return

        out_dir = self.out_edit.text().strip().strip('"')
        if out_dir and Path(out_dir).is_file():
            InfoBar.warning(title=APP_NAME, content=t("warn_out_is_file"), parent=self, duration=3000)
            return

        checked = self._checked_formats()
        if not checked:
            InfoBar.warning(title=APP_NAME, content=t("warn_no_formats"), parent=self, duration=3000)
            return

        # 校验单文件时扩展名是否被勾选的格式覆盖
        if path.is_file() and self._format_groups:
            exts_union = set().union(
                *(exts for name, _, exts in self._format_groups if name in checked)
            )
            if not is_supported_file(path, exts_union):
                InfoBar.warning(title=APP_NAME, content=t("warn_fmt_unmatched"), parent=self, duration=4000)
                return

        self._save_settings(path, checked)

        self.log_view.clear()
        self._log(t("log_input", path=path))
        self._log(t("log_output_dir", dir=out_dir) if out_dir else t("log_output_same"))

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
            self._log(t("stopping"))
            self.worker.stop()

    def _save_settings(self, path: Path, checked: set[str]) -> None:
        self.settings.setValue("last_path", str(path))
        self.settings.setValue("out_format_index", self.format_combo.currentIndex())
        self.settings.setValue("overwrite", self.overwrite_cb.isChecked())
        self.settings.setValue("images", self.images_cb.isChecked())
        self.settings.setValue("recursive", self.recursive_cb.isChecked())
        self.settings.setValue("formats", sorted(checked))

    def _restore_settings(self, initial_path: str) -> None:
        last_path = self.settings.value("last_path", "")
        if not initial_path and last_path:
            initial_path = str(last_path)
        if initial_path:
            self.path_edit.setText(initial_path)
        self.format_combo.setCurrentIndex(int(self.settings.value("out_format_index", 0)))
        self.overwrite_cb.setChecked(self.settings.value("overwrite", False, type=bool))
        self.images_cb.setChecked(self.settings.value("images", True, type=bool))
        self.recursive_cb.setChecked(self.settings.value("recursive", True, type=bool))

    # ================================================================ 更新检查
    def _start_update_check(self) -> None:
        if self.update_checker is not None and self.update_checker.isRunning():
            return
        self.status_label.setText(t("update_checking"))
        self.update_checker = UpdateChecker(REPO_URL.removeprefix("https://github.com/"), __version__)
        self.update_checker.done.connect(self._on_update_checked)
        self.update_checker.finished.connect(self.update_checker.deleteLater)
        self.update_checker.start()

    def _on_update_checked(self, latest: str, current: str, err: str) -> None:
        self.status_label.setText(t("idle"))
        if err and not latest:
            InfoBar.warning(title=APP_NAME, content=t("update_failed"), parent=self, duration=4000)
            return
        if version_tuple(latest) > version_tuple(current):
            InfoBar.success(title=APP_NAME, content=t("update_available", tag=latest), parent=self, duration=6000)
            self.settings_page.set_update_status(t("update_available", tag=latest))
        else:
            InfoBar.info(title=APP_NAME, content=t("update_latest", version=current), parent=self, duration=4000)
            self.settings_page.set_update_status(t("update_latest", version=current))

    # ================================================================ 状态
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
        self.status_label.setText(t("progress_label", done=done, total=total))

    def _on_done(self, ok: int, skipped: int, failed: int, stopped: bool) -> None:
        self._set_running(False)
        self.worker = None
        msg = t("summary_msg", ok=ok, skipped=skipped, failed=failed)
        self.status_label.setText((t("stopped_title") if stopped else t("done_title")) + "：" + msg)
        if stopped:
            InfoBar.warning(title=t("stopped_title"), content=msg, parent=self, duration=4000)
        elif failed:
            InfoBar.error(title=t("partial_fail_title"), content=msg, parent=self, duration=6000)
        else:
            InfoBar.success(title=t("done_title"), content=msg, parent=self, duration=4000)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None and self.worker.isRunning():
            from PySide6.QtWidgets import QMessageBox

            ret = QMessageBox.question(
                self, APP_NAME, t("stop_confirm"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.stop()
            self.worker.wait(5000)
        event.accept()


def _system_language() -> str:
    from PySide6.QtCore import QLocale

    return "zh" if QLocale.system().name().lower().startswith("zh") else "en"


def run_gui(initial_path: str = "") -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationName(APP_NAME)
    window = MainWindow(initial_path)
    window.show()
    return app.exec()
