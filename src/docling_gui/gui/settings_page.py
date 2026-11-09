"""设置页：通用（语言切换）+ 关于（版本/仓库/链接/检查更新）。"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (
    ComboBox,
    FluentIcon,
    PrimaryPushSettingCard,
    PushSettingCard,
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    BodyLabel,
)

from .. import (
    DOCLING_URL,
    ISSUES_URL,
    LICENSE_NAME,
    ORG_NAME,
    QFLUENTWIDGETS_URL,
    REPO_URL,
    __version__,
)
from ..i18n import LANGUAGES, get_language, t


class SettingsPage(ScrollArea):
    """设置页。语言变更通过 languageChanged 信号通知主窗口整体重翻译。"""

    languageChanged = Signal(str)
    checkUpdateRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scroll_widget = None
        self._lang_combo_initializing = True
        self._build_ui()
        self._retranslate()

    def _build_ui(self) -> None:
        self.setWidgetResizable(True)
        self.setViewportMargins(0, 0, 0, 0)
        self.setStyleSheet("QScrollArea{background: transparent; border: none;}")

        self.scroll_widget = _Widget()
        self.scroll_widget.setStyleSheet("QWidget{background: transparent;}")
        self.setWidget(self.scroll_widget)
        from qfluentwidgets import ExpandLayout

        layout = ExpandLayout(self.scroll_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ---- 通用组 ----
        self.general_group = SettingCardGroup("", self.scroll_widget)
        self.language_card = SettingCard(FluentIcon.LANGUAGE, "")
        self.lang_combo = ComboBox()
        for _code, label in LANGUAGES:
            self.lang_combo.addItem(label)
        self.lang_combo.setCurrentIndex([c for c, _ in LANGUAGES].index(get_language()))
        self._lang_combo_initializing = False
        self.lang_combo.setFixedWidth(150)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        self.language_card.hBoxLayout.addWidget(self.lang_combo, 0, Qt.AlignRight)
        self.language_card.hBoxLayout.addSpacing(16)
        self.general_group.addSettingCard(self.language_card)

        # ---- 关于组 ----
        self.about_group = SettingCardGroup("", self.scroll_widget)
        self.version_card = SettingCard(FluentIcon.INFO, "")
        self.repo_card = PushSettingCard("", FluentIcon.GITHUB, "", REPO_URL)
        self.repo_card.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        self.issues_card = PushSettingCard("", FluentIcon.EDIT, "", ISSUES_URL)
        self.issues_card.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(ISSUES_URL)))
        self.docling_card = PushSettingCard("", FluentIcon.ROBOT, "", DOCLING_URL)
        self.docling_card.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DOCLING_URL)))
        self.qfw_card = PushSettingCard("", FluentIcon.PALETTE, "", QFLUENTWIDGETS_URL)
        self.qfw_card.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(QFLUENTWIDGETS_URL)))
        self.license_card = SettingCard(FluentIcon.CERTIFICATE, "")
        self.update_card = PrimaryPushSettingCard("", FluentIcon.SYNC, "", REPO_URL)
        self.update_card.clicked.connect(self.checkUpdateRequested.emit)
        for card in (
            self.version_card,
            self.repo_card,
            self.issues_card,
            self.docling_card,
            self.qfw_card,
            self.license_card,
            self.update_card,
        ):
            self.about_group.addSettingCard(card)

        layout.addWidget(self.general_group)
        layout.addWidget(self.about_group)

    # ---------------------------------------------------------------- 语言
    def _on_language_changed(self, index: int) -> None:
        if self._lang_combo_initializing:
            return
        from ..i18n import set_language

        lang = LANGUAGES[index][0]
        set_language(lang)
        QSettings(ORG_NAME, "docling-gui").setValue("language", lang)
        self.languageChanged.emit(lang)

    # ---------------------------------------------------------------- 文案
    def _retranslate(self) -> None:
        self.general_group.titleLabel.setText(t("settings_group_general"))
        self.general_group.titleLabel.adjustSize()
        self.about_group.titleLabel.setText(t("settings_group_about"))
        self.about_group.titleLabel.adjustSize()

        self.language_card.setTitle(t("settings_language"))
        self.language_card.setContent(t("settings_language_desc"))

        self.version_card.setTitle(t("settings_version"))
        self.version_card.setContent(f"v{__version__}")
        self.repo_card.setTitle(t("settings_repo"))
        self.repo_card.setContent(t("settings_repo_desc"))
        self.repo_card.button.setText(t("settings_open_btn"))
        self.issues_card.setTitle(t("settings_issues"))
        self.issues_card.setContent(t("settings_issues_desc"))
        self.issues_card.button.setText(t("settings_open_btn"))
        self.docling_card.setTitle(t("settings_docling"))
        self.docling_card.setContent(t("settings_docling_desc"))
        self.docling_card.button.setText(t("settings_open_btn"))
        self.qfw_card.setTitle(t("settings_qfw"))
        self.qfw_card.setContent(t("settings_qfw_desc"))
        self.qfw_card.button.setText(t("settings_open_btn"))
        self.license_card.setTitle(t("settings_license"))
        self.license_card.setContent(LICENSE_NAME)
        self.update_card.setTitle(t("settings_check_update"))
        self.update_card.setContent(t("settings_check_update_desc"))
        self.update_card.button.setText(t("settings_check_update"))

    def set_update_status(self, text: str) -> None:
        """检查更新后把结果写回卡片说明。"""
        self.update_card.setContent(text)


class _Widget(QWidget):
    """ScrollArea 内容容器（透明背景）。"""
