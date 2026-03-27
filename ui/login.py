from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGraphicsOpacityEffect,
    QLabel,
    QPushButton,
    QLineEdit,
    QMessageBox,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from models.user import User
from services.workflow_service import WorkflowService
from ui.signup import SignupDialog


class LoginDialog(QDialog):
    def __init__(self, workflow: WorkflowService, parent=None) -> None:
        super().__init__(parent)

        self._workflow = workflow
        self._selected_user: Optional[User] = None

        self.setWindowTitle("Login")
        self.setModal(True)
        self.resize(420, 260)

        self._card = QWidget(self)
        self._card.setObjectName("LoginCard")

        title = QLabel("Sign in", self)
        title.setObjectName("PageTitle")

        self._username = QLineEdit(self)
        self._username.setPlaceholderText("Username")

        self._password = QLineEdit(self)
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.Password)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Login")
        buttons.accepted.connect(self._on_login)
        buttons.rejected.connect(self.reject)

        signup_btn = QPushButton("Sign up", self)
        signup_btn.setObjectName("ButtonSecondary")
        signup_btn.clicked.connect(self._open_signup)
        buttons.addButton(signup_btn, QDialogButtonBox.ActionRole)

        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)
        card_layout.addWidget(title)
        card_layout.addWidget(QLabel("Username", self))
        card_layout.addWidget(self._username)
        card_layout.addWidget(QLabel("Password", self))
        card_layout.addWidget(self._password)
        card_layout.addWidget(buttons)
        self._card.setLayout(card_layout)

        self._opacity = QGraphicsOpacityEffect(self._card)
        self._opacity.setOpacity(0.0)
        self._card.setGraphicsEffect(self._opacity)

        self._fade_anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_anim.setDuration(220)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._slide_anim = QPropertyAnimation(self._card, b"pos", self)
        self._slide_anim.setDuration(240)
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)

        root = QVBoxLayout()
        root.setContentsMargins(24, 24, 24, 24)
        root.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        root.addWidget(self._card)
        root.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.setLayout(root)

    def showEvent(self, event) -> None:
        super().showEvent(event)

        # Recalculate after layout has run.
        self._fade_anim.stop()
        self._slide_anim.stop()

        end_pos = self._card.pos()
        start_pos = end_pos + end_pos.__class__(0, 10)
        self._card.move(start_pos)

        self._opacity.setOpacity(0.0)
        self._fade_anim.start()

        self._slide_anim.setStartValue(start_pos)
        self._slide_anim.setEndValue(end_pos)
        self._slide_anim.start()

    def _on_login(self) -> None:
        username = self._username.text().strip().lower()
        password = self._password.text()
        if not username or not password:
            QMessageBox.warning(self, "Missing", "Username and password are required")
            return

        try:
            user = self._workflow.authenticate(username=username, password=password)
        except Exception as e:
            QMessageBox.critical(self, "Login failed", str(e))
            return

        if user is None:
            QMessageBox.warning(self, "Login failed", "Invalid credentials or account not approved")
            return

        self._selected_user = user
        self.accept()

    def _open_signup(self) -> None:
        dlg = SignupDialog(self._workflow, self)
        dlg.exec_()

    def selected_user(self) -> Optional[User]:
        return self._selected_user
