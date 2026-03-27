from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from models.user import User
from services.workflow_service import WorkflowService


class LoginDialog(QDialog):
    def __init__(self, workflow: WorkflowService, parent=None) -> None:
        super().__init__(parent)

        self._workflow = workflow
        self._selected_user: Optional[User] = None

        self.setWindowTitle("Login")
        self.setModal(True)
        self.resize(360, 140)

        self._user_combo = QComboBox(self)

        users = self._workflow.list_users()
        for u in users:
            self._user_combo.addItem(f"{u.name} ({u.role})", u)

        form = QFormLayout()
        form.addRow(QLabel("Select user:"), self._user_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_login)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _on_login(self) -> None:
        user = self._user_combo.currentData()
        if user is None:
            return
        self._selected_user = user
        self.accept()

    def selected_user(self) -> Optional[User]:
        return self._selected_user
