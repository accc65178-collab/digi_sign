from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from models.user import User
from services.workflow_service import WorkflowService


class AdminPanelDialog(QDialog):
    def __init__(self, workflow: WorkflowService, parent=None) -> None:
        super().__init__(parent)

        self._workflow = workflow

        self.setWindowTitle("Admin Panel - User Approvals")
        self.setModal(True)
        self.resize(520, 360)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SingleSelection)

        self._approve = QPushButton("Approve", self)
        self._approve.setObjectName("ButtonPrimary")
        self._reject = QPushButton("Reject", self)
        self._reject.setObjectName("ButtonSecondary")
        self._remove = QPushButton("Remove", self)
        self._remove.setObjectName("ButtonSecondary")
        self._refresh = QPushButton("Refresh", self)
        self._refresh.setObjectName("ButtonSecondary")

        self._approve.clicked.connect(self._approve_selected)
        self._reject.clicked.connect(self._reject_selected)
        self._remove.clicked.connect(self._remove_selected)
        self._refresh.clicked.connect(self.refresh)

        btns = QHBoxLayout()
        btns.addWidget(self._approve)
        btns.addWidget(self._reject)
        btns.addWidget(self._remove)
        btns.addStretch(1)
        btns.addWidget(self._refresh)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Pending Users", self))
        layout.addWidget(self._list, 1)
        layout.addLayout(btns)
        self.setLayout(layout)

        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        pending = self._workflow.list_pending_users()
        if not pending:
            item = QListWidgetItem("No pending users")
            item.setFlags(Qt.NoItemFlags)
            self._list.addItem(item)
            self._approve.setEnabled(False)
            self._reject.setEnabled(False)
            self._remove.setEnabled(False)
            return

        self._approve.setEnabled(True)
        self._reject.setEnabled(True)
        self._remove.setEnabled(True)
        for u in pending:
            item = QListWidgetItem(f"{u.username}")
            item.setData(Qt.UserRole, u)
            self._list.addItem(item)

    def _selected_user(self) -> Optional[User]:
        item = self._list.currentItem()
        if item is None:
            return None
        u = item.data(Qt.UserRole)
        if isinstance(u, User):
            return u
        return None

    def _approve_selected(self) -> None:
        u = self._selected_user()
        if u is None:
            return
        self._workflow.approve_user(u.id)
        QMessageBox.information(self, "Approved", f"Approved {u.username}.")
        self.refresh()

    def _reject_selected(self) -> None:
        u = self._selected_user()
        if u is None:
            return
        self._workflow.reject_user(u.id)
        QMessageBox.information(self, "Rejected", f"Rejected {u.username}.")
        self.refresh()

    def _remove_selected(self) -> None:
        u = self._selected_user()
        if u is None:
            return

        if u.role == "Admin":
            QMessageBox.warning(self, "Not allowed", "Admin users cannot be removed.")
            return

        res = QMessageBox.question(
            self,
            "Remove user",
            f"Remove user '{u.username}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return

        if not self._workflow.can_delete_user(u.id):
            QMessageBox.warning(
                self,
                "Cannot remove",
                "This user is referenced by documents/approvals/comments and cannot be safely removed.",
            )
            return

        self._workflow.delete_user(u.id)
        QMessageBox.information(self, "Removed", f"Removed {u.username}.")
        self.refresh()
