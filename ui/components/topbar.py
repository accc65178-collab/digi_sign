from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget


class TopBar(QWidget):
    logout_requested = pyqtSignal()
    admin_requested = pyqtSignal()
    search_changed = pyqtSignal(str)

    def __init__(self, user_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setObjectName("TopBar")

        self._title = QLabel("Document Workflow", self)
        self._title.setObjectName("TopBarTitle")

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search documents...")
        self._search.setObjectName("TopBarSearch")
        self._search.textChanged.connect(self.search_changed.emit)

        self._user = QLabel(user_name, self)
        self._user.setObjectName("TopBarUser")

        self._admin = QPushButton("Admin", self)
        self._admin.setObjectName("ButtonSecondary")
        self._admin.clicked.connect(self.admin_requested.emit)
        self._admin.setVisible(False)

        self._logout = QPushButton("Logout", self)
        self._logout.setObjectName("ButtonSecondary")
        self._logout.clicked.connect(self.logout_requested.emit)

        layout = QHBoxLayout()
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)
        layout.addWidget(self._title)
        layout.addStretch(1)
        layout.addWidget(self._search)
        layout.addWidget(self._user)
        layout.addWidget(self._admin)
        layout.addWidget(self._logout)
        self.setLayout(layout)

    def set_user_name(self, user_name: str) -> None:
        self._user.setText(user_name)

    def set_search_visible(self, visible: bool) -> None:
        self._search.setVisible(visible)

    def set_admin_visible(self, visible: bool) -> None:
        self._admin.setVisible(visible)
