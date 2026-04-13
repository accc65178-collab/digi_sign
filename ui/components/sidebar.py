from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QButtonGroup, QLabel, QPushButton, QStyle, QVBoxLayout, QWidget


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    icon: Optional[int] = None


class Sidebar(QWidget):
    nav_changed = pyqtSignal(str)

    def __init__(self, items: list[NavItem], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setObjectName("Sidebar")
        self.setFixedWidth(240)

        self._title = QLabel("Workflow", self)
        self._title.setObjectName("SidebarTitle")

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.buttonClicked.connect(self._on_button_clicked)

        self._buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        layout.addWidget(self._title)
        layout.addSpacing(8)

        for item in items:
            btn = QPushButton(item.label, self)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("navKey", item.key)
            btn.setObjectName("NavButton")

            if item.icon is not None:
                btn.setIcon(self.style().standardIcon(item.icon))

            self._group.addButton(btn)
            self._buttons[item.key] = btn
            layout.addWidget(btn)

        layout.addStretch(1)
        self.setLayout(layout)

    def set_active(self, key: str) -> None:
        btn = self._buttons.get(key)
        if btn is None:
            return
        btn.setChecked(True)
        self.nav_changed.emit(key)

    def set_badge(self, key: str, count: int) -> None:
        btn = self._buttons.get(key)
        if btn is None:
            return
        base = btn.text().split("  [")[0]
        if count > 0:
            btn.setText(f"{base}  [{count}]")
            btn.setProperty("hasBadge", True)
        else:
            btn.setText(base)
            btn.setProperty("hasBadge", False)
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def _on_button_clicked(self, btn: QPushButton) -> None:
        key = btn.property("navKey")
        if isinstance(key, str):
            self.nav_changed.emit(key)


def default_nav_items() -> list[NavItem]:
    return [
        NavItem("dashboard", "Dashboard", QStyle.SP_ComputerIcon),
        NavItem("my_docs", "My Documents", QStyle.SP_FileIcon),
        NavItem("my_approved", "My Approved Letters", QStyle.SP_DialogYesButton),
        NavItem("pending", "Pending Approvals", QStyle.SP_MessageBoxInformation),
        NavItem("approved_by_me", "Approved by Me", QStyle.SP_DialogApplyButton),
    ]
