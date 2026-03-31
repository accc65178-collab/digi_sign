from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from models.user import User
from services.workflow_service import WorkflowService
from ui.signup import SignupDialog


class ForgotPasswordDialog(QDialog):
    def __init__(self, workflow: WorkflowService, parent=None) -> None:
        super().__init__(parent)
        self._workflow = workflow

        self.setWindowTitle("Forgot Password")
        self.setModal(True)
        self.setObjectName("LoginDialog")
        self.resize(420, 300)

        bg = QWidget(self)
        bg.setObjectName("LoginBackground")

        card = QWidget(bg)
        card.setObjectName("LoginGlassCard")
        card.setMinimumWidth(340)

        title = QLabel("Forgot Password", card)
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignHCenter)

        subtitle = QLabel("Enter your employee name", card)
        subtitle.setObjectName("LoginSubtitle")
        subtitle.setAlignment(Qt.AlignHCenter)

        self._input_field = QLineEdit(card)
        self._input_field.setPlaceholderText("Employee name")
        self._input_field.setObjectName("LoginInput")

        btn_cancel = QPushButton("Cancel", card)
        btn_cancel.setObjectName("ButtonSecondary")
        btn_cancel.clicked.connect(self.reject)

        btn_submit = QPushButton("Submit", card)
        btn_submit.setObjectName("LoginButton")
        btn_submit.clicked.connect(self.accept)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(10)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_submit)

        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(34, 34, 34, 28)
        card_layout.setSpacing(16)
        card_layout.addWidget(title)
        card_layout.addSpacing(4)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(8)
        card_layout.addWidget(self._input_field)
        card_layout.addSpacing(12)
        card_layout.addLayout(btn_row)
        card.setLayout(card_layout)

        bg_layout = QVBoxLayout()
        bg_layout.setContentsMargins(24, 24, 24, 24)
        bg_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        bg_layout.addWidget(card, 0, Qt.AlignHCenter)
        bg_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        bg.setLayout(bg_layout)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(bg)
        self.setLayout(root)

        self._input_field.setFocus(Qt.OtherFocusReason)

    def get_username(self) -> Optional[str]:
        if self.exec_() == QDialog.Accepted:
            name = self._input_field.text().strip()
            return name if name else None
        return None


class LoginDialog(QDialog):
    def __init__(self, workflow: WorkflowService, parent=None) -> None:
        super().__init__(parent)

        self._workflow = workflow
        self._selected_user: Optional[User] = None

        self.setWindowTitle("Login")
        self.setModal(True)
        self.resize(520, 640)

        self.setObjectName("LoginDialog")

        self._bg = QWidget(self)
        self._bg.setObjectName("LoginBackground")

        self._card = QWidget(self._bg)
        self._card.setObjectName("LoginGlassCard")
        self._card.setMinimumWidth(420)

        title = QLabel("login", self._card)
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignHCenter)

        self._username = QLineEdit(self._card)
        self._username.setPlaceholderText("Employee name")
        self._username.setObjectName("LoginInput")

        self._password = QLineEdit(self._card)
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setObjectName("LoginInput")

        self._remember = QCheckBox("Remember me", self._card)
        self._remember.setObjectName("RememberMe")

        forgot_btn = QPushButton("Forgot Password?", self._card)
        forgot_btn.setObjectName("ForgotLink")
        forgot_btn.setFlat(True)
        forgot_btn.setAutoDefault(False)   # prevent Enter from triggering
        forgot_btn.setDefault(False)
        forgot_btn.clicked.connect(self._open_forgot_password)
        self._forgot_btn = forgot_btn  # store reference for guard

        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.addWidget(self._remember)
        options_row.addStretch(1)
        options_row.addWidget(forgot_btn)

        self._login_btn = QPushButton("Login", self._card)
        self._login_btn.setObjectName("LoginButton")
        self._login_btn.clicked.connect(self._on_login)
        self._login_btn.setAutoDefault(True)   # ensure Login is the default button
        self._login_btn.setDefault(True)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(6)
        bottom_row.addStretch(1)
        bottom_row.addWidget(QLabel("Don't have an account?", self._card))
        register_btn = QPushButton("Sign up", self._card)
        register_btn.setObjectName("RegisterLink")
        register_btn.setFlat(True)
        register_btn.clicked.connect(self._open_signup)
        bottom_row.addWidget(register_btn)
        bottom_row.addStretch(1)

        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(34, 34, 34, 28)
        card_layout.setSpacing(16)
        card_layout.addWidget(title)
        card_layout.addSpacing(8)
        card_layout.addWidget(QLabel("Employee name", self._card))
        card_layout.addWidget(self._username)
        card_layout.addWidget(QLabel("Password", self._card))
        card_layout.addWidget(self._password)
        card_layout.addLayout(options_row)
        card_layout.addWidget(self._login_btn)
        card_layout.addSpacing(6)
        card_layout.addLayout(bottom_row)
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

        self._bg_layout = QVBoxLayout()
        self._bg_layout.setContentsMargins(24, 24, 24, 24)
        self._bg_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self._bg_layout.addWidget(self._card, 0, Qt.AlignHCenter)
        self._bg_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self._bg.setLayout(self._bg_layout)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._bg)
        self.setLayout(root)

        self._username.returnPressed.connect(self._on_login)
        self._password.returnPressed.connect(self._on_login)

    def _open_forgot_password(self) -> None:
        # Strict guard: only proceed if the sender is exactly the Forgot Password button
        if self.sender() is not self._forgot_btn:
            return
        dlg = ForgotPasswordDialog(self._workflow, self)
        username = dlg.get_username()
        if username is None:
            return
        normalized = username.lower().replace(" ")

        # Validate that the username exists
        u = self._workflow.get_user_by_username(normalized)
        if u is None:
            LoginDialog._styled_msg(self, "Not registered", "User not available. Please register first.", "warning")
            return

        try:
            self._workflow.create_password_reset_request(username=normalized)
        except Exception as e:
            LoginDialog._styled_msg(self, "Request failed", str(e), "critical")
            return
        LoginDialog._styled_msg(
            self,
            "Submitted",
            "Password reset request submitted. An admin must approve it before your password can be changed.",
            "information",
        )

    @staticmethod
    def _styled_msg(parent, title: str, text: str, icon_type: str = "information") -> None:
        dlg = QDialog(parent)
        dlg.setWindowTitle(title)
        dlg.setModal(True)
        dlg.setObjectName("LoginDialog")
        dlg.resize(400, 220)

        bg = QWidget(dlg)
        bg.setObjectName("LoginBackground")

        card = QWidget(bg)
        card.setObjectName("LoginGlassCard")
        card.setMinimumWidth(340)

        icon_map = {
            "warning": "⚠️",
            "critical": "❌",
            "information": "ℹ️",
        }
        icon_label = QLabel(icon_map.get(icon_type, "ℹ️"), card)
        icon_label.setObjectName("MsgIcon")
        icon_label.setAlignment(Qt.AlignTop)

        msg_label = QLabel(text, card)
        msg_label.setObjectName("MsgText")
        msg_label.setWordWrap(True)

        ok_btn = QPushButton("OK", card)
        ok_btn.setObjectName("LoginButton")
        ok_btn.clicked.connect(dlg.accept)
        ok_btn.setAutoDefault(False)  # prevent Enter from triggering

        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        row.addWidget(icon_label)
        row.addWidget(msg_label, 1)
        card_layout.addLayout(row)
        card_layout.addWidget(ok_btn, 0, Qt.AlignCenter)
        card.setLayout(card_layout)

        bg_layout = QVBoxLayout()
        bg_layout.setContentsMargins(24, 24, 24, 24)
        bg_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        bg_layout.addWidget(card, 0, Qt.AlignHCenter)
        bg_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        bg.setLayout(bg_layout)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(bg)
        dlg.setLayout(root)

        dlg.exec_()


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

        self._username.setFocus(Qt.OtherFocusReason)

    def _on_login(self) -> None:
        raw = self._username.text().strip()
        username = raw.lower().replace(" ", "")
        password = self._password.text()
        if not username or not password:
            LoginDialog._styled_msg(self, "Missing", "Employee name and password are required", "warning")
            return

        try:
            user = self._workflow.authenticate(username=username, password=password)
        except Exception as e:
            LoginDialog._styled_msg(self, "Login failed", str(e), "critical")
            return

        if user is None:
            LoginDialog._styled_msg(self, "Login failed", "Invalid credentials or account not approved", "warning")
            return

        self._selected_user = user
        self.accept()

    def _open_signup(self) -> None:
        dlg = SignupDialog(self._workflow, self)
        dlg.exec_()

    def selected_user(self) -> Optional[User]:
        return self._selected_user
