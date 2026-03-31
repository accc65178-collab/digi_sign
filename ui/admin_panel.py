from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.user import User
from services.workflow_service import WorkflowService
from ui.login import LoginDialog


class AdminPanelDialog(QDialog):
    def __init__(self, workflow: WorkflowService, current_user: User, parent=None) -> None:
        super().__init__(parent)

        self._workflow = workflow
        self._current_user = current_user

        if self._current_user.role != "Admin":
            raise PermissionError("Admin access required")

        self.setWindowTitle("Admin Panel")
        self.setModal(True)
        self.resize(980, 640)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_dashboard_tab(), "Dashboard")
        self._tabs.addTab(self._build_users_tab(), "Users")
        self._tabs.addTab(self._build_password_resets_tab(), "Password Resets")
        self._tabs.addTab(self._build_documents_tab(), "Documents")
        self._tabs.addTab(self._build_settings_tab(), "Settings")

        root = QVBoxLayout()
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        root.addWidget(self._tabs, 1)
        self.setLayout(root)

        self.refresh()

    def refresh(self) -> None:
        self._refresh_dashboard()
        self._refresh_users()
        self._refresh_password_resets()
        self._refresh_documents()

    def _build_dashboard_tab(self) -> QWidget:
        w = QWidget(self)
        self._stats_total_users = QLabel("0", w)
        self._stats_active_users = QLabel("0", w)
        self._stats_pending_approvals = QLabel("0", w)
        self._stats_total_docs = QLabel("0", w)

        grid = QHBoxLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        grid.addWidget(self._stat_card("Total users", self._stats_total_users))
        grid.addWidget(self._stat_card("Active users", self._stats_active_users))
        grid.addWidget(self._stat_card("Pending approvals", self._stats_pending_approvals))
        grid.addWidget(self._stat_card("Total documents", self._stats_total_docs))

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Admin Dashboard", w))
        layout.addLayout(grid)
        layout.addStretch(1)
        w.setLayout(layout)
        return w

    def _stat_card(self, title: str, value_label: QLabel) -> QWidget:
        card = QWidget(self)
        card.setObjectName("LoginCard")
        t = QLabel(title, card)
        t.setObjectName("CardTitle")
        value_label.setObjectName("CardValue")
        box = QVBoxLayout()
        box.setContentsMargins(14, 12, 14, 12)
        box.setSpacing(6)
        box.addWidget(t)
        box.addWidget(value_label)
        card.setLayout(box)
        return card

    def _build_users_tab(self) -> QWidget:
        w = QWidget(self)

        self._users_table = QTableWidget(0, 6, w)
        self._users_table.setHorizontalHeaderLabels(["Name", "Username", "Designation", "Role", "Status", "Enabled"])
        self._users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._users_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._btn_approve = QPushButton("Approve", w)
        self._btn_approve.setObjectName("ButtonPrimary")
        self._btn_reject = QPushButton("Reject", w)
        self._btn_reject.setObjectName("ButtonSecondary")
        self._btn_enable = QPushButton("Enable", w)
        self._btn_enable.setObjectName("ButtonSecondary")
        self._btn_disable = QPushButton("Disable", w)
        self._btn_disable.setObjectName("ButtonSecondary")
        self._btn_reset_pw = QPushButton("Reset password", w)
        self._btn_reset_pw.setObjectName("ButtonSecondary")
        self._btn_delete = QPushButton("Delete", w)
        self._btn_delete.setObjectName("ButtonSecondary")
        self._btn_refresh_users = QPushButton("Refresh", w)
        self._btn_refresh_users.setObjectName("ButtonSecondary")

        self._btn_approve.clicked.connect(self._approve_selected_user)
        self._btn_reject.clicked.connect(self._reject_selected_user)
        self._btn_enable.clicked.connect(lambda: self._set_selected_user_enabled(True))
        self._btn_disable.clicked.connect(lambda: self._set_selected_user_enabled(False))
        self._btn_reset_pw.clicked.connect(self._reset_selected_user_password)
        self._btn_delete.clicked.connect(self._delete_selected_user)
        self._btn_refresh_users.clicked.connect(self.refresh)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        actions.addWidget(self._btn_approve)
        actions.addWidget(self._btn_reject)
        actions.addWidget(self._btn_enable)
        actions.addWidget(self._btn_disable)
        actions.addWidget(self._btn_reset_pw)
        actions.addWidget(self._btn_delete)
        actions.addStretch(1)
        actions.addWidget(self._btn_refresh_users)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("User Management", w))
        layout.addWidget(self._users_table, 1)
        layout.addLayout(actions)
        w.setLayout(layout)
        return w

    def _build_password_resets_tab(self) -> QWidget:
        w = QWidget(self)

        self._resets_table = QTableWidget(0, 5, w)
        self._resets_table.setHorizontalHeaderLabels(["ID", "Username", "Requested at", "Status", "Handled by"])
        self._resets_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._resets_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._btn_reset_approve = QPushButton("Approve + Set Password", w)
        self._btn_reset_approve.setObjectName("ButtonPrimary")
        self._btn_reset_reject = QPushButton("Reject", w)
        self._btn_reset_reject.setObjectName("ButtonSecondary")
        self._btn_reset_refresh = QPushButton("Refresh", w)
        self._btn_reset_refresh.setObjectName("ButtonSecondary")

        self._btn_reset_approve.clicked.connect(self._approve_selected_reset)
        self._btn_reset_reject.clicked.connect(self._reject_selected_reset)
        self._btn_reset_refresh.clicked.connect(self.refresh)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        actions.addWidget(self._btn_reset_approve)
        actions.addWidget(self._btn_reset_reject)
        actions.addStretch(1)
        actions.addWidget(self._btn_reset_refresh)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Password Reset Requests", w))
        layout.addWidget(self._resets_table, 1)
        layout.addLayout(actions)
        w.setLayout(layout)
        return w

    def _build_documents_tab(self) -> QWidget:
        w = QWidget(self)

        self._docs_table = QTableWidget(0, 5, w)
        self._docs_table.setHorizontalHeaderLabels(["ID", "Title", "Status", "Created by", "Assigned to"])
        self._docs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._docs_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._btn_docs_refresh = QPushButton("Refresh", w)
        self._btn_docs_refresh.setObjectName("ButtonSecondary")
        self._btn_docs_refresh.clicked.connect(self.refresh)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self._btn_docs_refresh)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("All Documents (read-only)", w))
        layout.addWidget(self._docs_table, 1)
        layout.addLayout(actions)
        w.setLayout(layout)
        return w

    def _build_settings_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Settings", w))
        layout.addWidget(QLabel("Template editing is not available yet in this build.", w))
        layout.addStretch(1)
        w.setLayout(layout)
        return w

    def _selected_user_id(self) -> Optional[int]:
        row = self._users_table.currentRow()
        if row < 0:
            return None
        item = self._users_table.item(row, 1)
        if item is None:
            return None
        username = item.text().strip()
        u = self._workflow.get_user_by_username(username)
        return None if u is None else u.id

    def _selected_reset_request_id(self) -> Optional[int]:
        row = self._resets_table.currentRow()
        if row < 0:
            return None
        item = self._resets_table.item(row, 0)
        if item is None:
            return None
        try:
            return int(item.text())
        except Exception:
            return None

    def _approve_selected_user(self) -> None:
        uid = self._selected_user_id()
        if uid is None:
            return
        self._workflow.approve_user(uid)
        self.refresh()

    def _reject_selected_user(self) -> None:
        uid = self._selected_user_id()
        if uid is None:
            return
        self._workflow.reject_user(uid)
        self.refresh()

    def _set_selected_user_enabled(self, enabled: bool) -> None:
        uid = self._selected_user_id()
        if uid is None:
            return
        if uid == self._current_user.id and not enabled:
            LoginDialog._styled_msg(self, "Not allowed", "You cannot disable your own admin account.", "warning")
            return
        self._workflow.set_user_enabled(user_id=uid, enabled=enabled)
        self.refresh()

    def _reset_selected_user_password(self) -> None:
        uid = self._selected_user_id()
        if uid is None:
            return
        pw, ok = QInputDialog.getText(self, "Reset password", "New password:", echo=QLineEdit.Password)
        if not ok:
            return
        try:
            self._workflow.reset_user_password(user_id=uid, new_password=pw)
        except Exception as e:
            LoginDialog._styled_msg(self, "Failed", str(e), "critical")
            return
        LoginDialog._styled_msg(self, "Updated", "Password updated.", "information")

    def _delete_selected_user(self) -> None:
        uid = self._selected_user_id()
        if uid is None:
            return
        if uid == self._current_user.id:
            LoginDialog._styled_msg(self, "Not allowed", "You cannot delete yourself.", "warning")
            return
        u = self._workflow.get_user(uid)
        label = str(uid) if u is None else u.display_label()

        res = QMessageBox.question(
            self,
            "Delete user",
            f"Delete user '{label}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return
        if not self._workflow.can_delete_user(uid):
            LoginDialog._styled_msg(
                self,
                "Cannot delete",
                "This user is referenced by documents/approvals/comments and cannot be safely deleted.",
                "warning",
            )
            return
        self._workflow.delete_user(uid)
        self.refresh()

    def _approve_selected_reset(self) -> None:
        rid = self._selected_reset_request_id()
        if rid is None:
            return
        row = self._resets_table.currentRow()
        username_item = self._resets_table.item(row, 1) if row >= 0 else None
        if username_item is None:
            return
        username = username_item.text().strip()
        u = self._workflow.get_user_by_username(username)
        if u is None:
            LoginDialog._styled_msg(self, "Not found", "User no longer exists.", "warning")
            return
        pw, ok = QInputDialog.getText(self, "Set new password", f"New password for {u.display_label()}:", echo=QLineEdit.Password)
        if not ok:
            return

        try:
            self._workflow.reset_user_password(user_id=u.id, new_password=pw)
            self._workflow.handle_password_reset_request(request_id=rid, status="Approved", handled_by=self._current_user.id)
        except Exception as e:
            LoginDialog._styled_msg(self, "Failed", str(e), "critical")
            return
        LoginDialog._styled_msg(self, "Done", "Password reset approved and applied.", "information")
        self.refresh()

    def _reject_selected_reset(self) -> None:
        rid = self._selected_reset_request_id()
        if rid is None:
            return
        try:
            self._workflow.handle_password_reset_request(request_id=rid, status="Rejected", handled_by=self._current_user.id)
        except Exception as e:
            LoginDialog._styled_msg(self, "Failed", str(e), "critical")
            return
        self.refresh()

    def _refresh_dashboard(self) -> None:
        users = self._workflow.list_users()
        pending = self._workflow.list_pending_users()
        docs = self._workflow.list_all_documents()

        self._stats_total_users.setText(str(len(users)))
        self._stats_active_users.setText(str(sum(1 for u in users if u.enabled)))
        self._stats_pending_approvals.setText(str(len(pending)))
        self._stats_total_docs.setText(str(len(docs)))

    def _refresh_users(self) -> None:
        users = self._workflow.list_users()
        self._users_table.setRowCount(0)
        for u in users:
            row = self._users_table.rowCount()
            self._users_table.insertRow(row)
            self._users_table.setItem(row, 0, QTableWidgetItem(u.name))
            self._users_table.setItem(row, 1, QTableWidgetItem(u.username))
            self._users_table.setItem(row, 2, QTableWidgetItem(u.designation))
            self._users_table.setItem(row, 3, QTableWidgetItem(u.role))
            self._users_table.setItem(row, 4, QTableWidgetItem(u.status))
            self._users_table.setItem(row, 5, QTableWidgetItem("Yes" if u.enabled else "No"))
        self._users_table.resizeColumnsToContents()

    def _refresh_password_resets(self) -> None:
        rows = self._workflow.list_password_reset_requests()
        self._resets_table.setRowCount(0)
        for r in rows:
            row = self._resets_table.rowCount()
            self._resets_table.insertRow(row)

            handled_by = ""
            if r["handled_by"] is not None:
                u = self._workflow.get_user(int(r["handled_by"]))
                handled_by = "" if u is None else u.display_label()

            self._resets_table.setItem(row, 0, QTableWidgetItem(str(r["id"])))
            self._resets_table.setItem(row, 1, QTableWidgetItem(str(r["username"])))
            self._resets_table.setItem(row, 2, QTableWidgetItem(str(r["requested_at"])))
            self._resets_table.setItem(row, 3, QTableWidgetItem(str(r["status"])))
            self._resets_table.setItem(row, 4, QTableWidgetItem(handled_by))
        self._resets_table.resizeColumnsToContents()

    def _refresh_documents(self) -> None:
        docs = self._workflow.list_all_documents()
        self._docs_table.setRowCount(0)
        for d in docs:
            row = self._docs_table.rowCount()
            self._docs_table.insertRow(row)
            created_by = self._workflow.get_user(d.created_by)
            created_label = str(d.created_by) if created_by is None else created_by.display_label()
            assigned_label = ""
            if d.assigned_to is not None:
                assigned = self._workflow.get_user(int(d.assigned_to))
                assigned_label = str(d.assigned_to) if assigned is None else assigned.display_label()

            self._docs_table.setItem(row, 0, QTableWidgetItem(str(d.id)))
            self._docs_table.setItem(row, 1, QTableWidgetItem(d.title))
            self._docs_table.setItem(row, 2, QTableWidgetItem(d.status))
            self._docs_table.setItem(row, 3, QTableWidgetItem(created_label))
            self._docs_table.setItem(row, 4, QTableWidgetItem(assigned_label))
        self._docs_table.resizeColumnsToContents()
