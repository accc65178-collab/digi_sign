from __future__ import annotations

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt5.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from services.workflow_service import WorkflowService


class SignupDialog(QDialog):
    def __init__(self, workflow: WorkflowService, parent=None) -> None:
        super().__init__(parent)

        self._workflow = workflow

        self.setWindowTitle("Signix - Sign up")
        self.setModal(True)
        self.resize(520, 640)

        self.setObjectName("SignupDialog")

        self._bg = QWidget(self)
        self._bg.setObjectName("LoginBackground")

        self._card = QWidget(self._bg)
        self._card.setObjectName("LoginGlassCard")
        self._card.setMinimumWidth(420)

        title = QLabel("sign up", self._card)
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignHCenter)

        self._full_name = QLineEdit(self._card)
        self._full_name.setPlaceholderText("Full name")
        self._full_name.setObjectName("LoginInput")

        self._employee_id = QLineEdit(self._card)
        self._employee_id.setPlaceholderText("Employee ID")
        self._employee_id.setObjectName("LoginInput")

        self._department = QLineEdit(self._card)
        self._department.setPlaceholderText("Directorate")
        self._department.setObjectName("LoginInput")

        self._lab = QLineEdit(self._card)
        self._lab.setPlaceholderText("Lab")
        self._lab.setObjectName("LoginInput")

        self._designation = QLineEdit(self._card)
        self._designation.setPlaceholderText("Designation")
        self._designation.setObjectName("LoginInput")

        self._password = QLineEdit(self._card)
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.Password)
        self._password.setObjectName("LoginInput")

        self._confirm_password = QLineEdit(self._card)
        self._confirm_password.setPlaceholderText("Confirm password")
        self._confirm_password.setEchoMode(QLineEdit.Password)
        self._confirm_password.setObjectName("LoginInput")

        self._submit = QPushButton("Sign up", self._card)
        self._submit.setObjectName("LoginButton")
        self._submit.clicked.connect(self._on_submit)

        self._cancel = QPushButton("Cancel", self._card)
        self._cancel.setObjectName("ButtonSecondary")
        self._cancel.clicked.connect(self.reject)

        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(34, 34, 34, 28)
        card_layout.setSpacing(16)
        card_layout.addWidget(title)
        card_layout.addSpacing(8)
        card_layout.addWidget(QLabel("Full name", self._card))
        card_layout.addWidget(self._full_name)
        card_layout.addWidget(QLabel("Employee ID", self._card))
        card_layout.addWidget(self._employee_id)
        card_layout.addWidget(QLabel("Directorate", self._card))
        card_layout.addWidget(self._department)
        card_layout.addWidget(QLabel("Lab", self._card))
        card_layout.addWidget(self._lab)
        card_layout.addWidget(QLabel("Designation", self._card))
        card_layout.addWidget(self._designation)
        card_layout.addWidget(QLabel("Password", self._card))
        card_layout.addWidget(self._password)
        card_layout.addWidget(QLabel("Confirm Password", self._card))
        card_layout.addWidget(self._confirm_password)
        card_layout.addWidget(self._submit)
        card_layout.addWidget(self._cancel)
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

        bg_layout = QVBoxLayout()
        bg_layout.setContentsMargins(24, 24, 24, 24)
        bg_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        bg_layout.addWidget(self._card, 0, Qt.AlignHCenter)
        bg_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self._bg.setLayout(bg_layout)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._bg)
        self.setLayout(root)

        self._full_name.returnPressed.connect(self._on_submit)
        self._employee_id.returnPressed.connect(self._on_submit)
        self._department.returnPressed.connect(self._on_submit)
        self._lab.returnPressed.connect(self._on_submit)
        self._designation.returnPressed.connect(self._on_submit)
        self._password.returnPressed.connect(self._on_submit)
        self._confirm_password.returnPressed.connect(self._on_submit)

    def showEvent(self, event) -> None:
        super().showEvent(event)

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

        self._full_name.setFocus(Qt.OtherFocusReason)

    def _on_submit(self) -> None:
        full_name = self._full_name.text().strip()
        employee_id = self._employee_id.text().strip()
        department = self._department.text().strip()
        lab = self._lab.text().strip()
        designation = self._designation.text().strip()
        password = self._password.text()
        confirm_password = self._confirm_password.text()
        if not full_name:
            QMessageBox.warning(self, "Missing", "Full name is required")
            return
        if not employee_id:
            QMessageBox.warning(self, "Missing", "Employee ID is required")
            return
        if not department:
            QMessageBox.warning(self, "Missing", "Directorate is required")
            return
        if not lab:
            QMessageBox.warning(self, "Missing", "Lab is required")
            return
        if not designation:
            QMessageBox.warning(self, "Missing", "Designation is required")
            return
        if not password:
            QMessageBox.warning(self, "Missing", "Password is required")
            return

        if password != confirm_password:
            QMessageBox.warning(self, "Mismatch", "Password and Confirm Password do not match")
            return

        try:
            self._workflow.signup_user(full_name=full_name, employee_id=employee_id, department=department, lab=lab, designation=designation, password=password)
        except Exception as e:
            QMessageBox.warning(self, "Signup failed", str(e))
            return
        QMessageBox.information(
            self,
            "Submitted",
            "Signup submitted. An admin must approve your account before you can log in.",
        )
        self.accept()
