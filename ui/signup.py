from __future__ import annotations

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from services.workflow_service import WorkflowService


class SignupDialog(QDialog):
    def __init__(self, workflow: WorkflowService, parent=None) -> None:
        super().__init__(parent)

        self._workflow = workflow

        self.setWindowTitle("Sign up")
        self.setModal(True)
        self.resize(360, 210)

        self._username = QLineEdit(self)
        self._password = QLineEdit(self)
        self._password.setEchoMode(QLineEdit.Password)
        self._role = QComboBox(self)
        self._role.addItems(["Normal", "Admin"])

        form = QFormLayout()
        form.addRow("Username:", self._username)
        form.addRow("Password:", self._password)
        form.addRow("Role:", self._role)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _on_submit(self) -> None:
        username = self._username.text().strip().lower()
        password = self._password.text()
        role = self._role.currentText().strip() or "Normal"
        if not username:
            QMessageBox.warning(self, "Missing", "Username is required")
            return
        if not password:
            QMessageBox.warning(self, "Missing", "Password is required")
            return

        try:
            self._workflow.signup_user(username=username, password=password, role=role)
        except Exception as e:
            QMessageBox.warning(self, "Signup failed", str(e))
            return
        QMessageBox.information(
            self,
            "Submitted",
            "Signup submitted. An admin must approve your account before you can log in.",
        )
        self.accept()
