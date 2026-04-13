from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
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

        self.setWindowTitle("Signix - Admin Panel")
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
        self._refresh_settings()

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

        self._btn_promote_admin = QPushButton("Make Admin", w)
        self._btn_promote_admin.setObjectName("ButtonSecondary")
        self._btn_promote_admin.clicked.connect(self._promote_admin_selected_user)

        self._btn_make_user = QPushButton("Make User", w)
        self._btn_make_user.setObjectName("ButtonSecondary")
        self._btn_make_user.clicked.connect(self._make_user_selected)

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
        actions.addWidget(self._btn_promote_admin)
        actions.addWidget(self._btn_make_user)
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
        self._docs_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._docs_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._btn_docs_delete = QPushButton("Delete document", w)
        self._btn_docs_delete.setObjectName("ButtonSecondary")
        self._btn_docs_refresh = QPushButton("Refresh", w)
        self._btn_docs_refresh.setObjectName("ButtonSecondary")
        
        self._btn_docs_delete.clicked.connect(self._delete_selected_document)
        self._btn_docs_refresh.clicked.connect(self.refresh)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        actions.addWidget(self._btn_docs_delete)
        actions.addStretch(1)
        actions.addWidget(self._btn_docs_refresh)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("All Documents", w))
        layout.addWidget(self._docs_table, 1)
        layout.addLayout(actions)
        w.setLayout(layout)
        return w

    def _build_settings_tab(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(16)

        # General Settings Group
        gen_group = QGroupBox("General Configuration", w)
        gen_form = QFormLayout()
        
        self._set_org_name = QLineEdit(w)
        self._set_ref_prefix = QLineEdit(w)
        self._set_default_font = QLineEdit(w)
        
        gen_form.addRow("Organization Name:", self._set_org_name)
        gen_form.addRow("Reference Number Prefix:", self._set_ref_prefix)
        gen_form.addRow("Default Export Font:", self._set_default_font)
        
        self._btn_save_settings = QPushButton("Save Settings", w)
        self._btn_save_settings.setObjectName("ButtonPrimary")
        self._btn_save_settings.clicked.connect(self._save_general_settings)
        
        gen_layout = QVBoxLayout()
        gen_layout.addLayout(gen_form)
        gen_layout.addWidget(self._btn_save_settings, 0, Qt.AlignRight)
        gen_group.setLayout(gen_layout)

        # Template Management Group
        tmpl_group = QGroupBox("Document Template (REF.docx)", w)
        tmpl_info = QLabel("The template defines the letterhead, logo, and footer for all exported documents.", w)
        tmpl_info.setWordWrap(True)
        
        self._btn_choose_tmpl = QPushButton("Choose New Template File...", w)
        self._btn_choose_tmpl.setObjectName("ButtonSecondary")
        self._btn_choose_tmpl.clicked.connect(self._upload_new_template)
        
        tmpl_layout = QVBoxLayout()
        tmpl_layout.addWidget(tmpl_info)
        tmpl_layout.addWidget(self._btn_choose_tmpl, 0, Qt.AlignLeft)
        tmpl_group.setLayout(tmpl_layout)

        layout.addWidget(gen_group)
        layout.addWidget(tmpl_group)
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

    def _selected_document_id(self) -> Optional[int]:
        row = self._docs_table.currentRow()
        if row < 0:
            return None
        item = self._docs_table.item(row, 0)
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

    def _delete_selected_document(self) -> None:
        selected_items = self._docs_table.selectedItems()
        if not selected_items:
            return

        # Get unique row indices from selected items
        rows = sorted(list(set(item.row() for item in selected_items)), reverse=True)
        doc_ids = []
        titles = []
        for r in rows:
            id_item = self._docs_table.item(r, 0)
            title_item = self._docs_table.item(r, 1)
            if id_item and title_item:
                doc_ids.append(int(id_item.text()))
                titles.append(title_item.text())

        if not doc_ids:
            return

        if len(doc_ids) == 1:
            msg = f"Delete document '{titles[0]}' (ID: {doc_ids[0]})?"
        else:
            msg = f"Delete {len(doc_ids)} selected documents?\n\nTitles include: {', '.join(titles[:5])}{'...' if len(titles) > 5 else ''}"

        full_msg = f"{msg}\n\nThis will permanently remove the documents, their approval history, and all comments. This cannot be undone."
        
        res = QMessageBox.question(
            self,
            "Delete documents",
            full_msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return
            
        success_count = 0
        error_count = 0
        for did in doc_ids:
            try:
                self._workflow.delete_document(did)
                success_count += 1
            except Exception:
                error_count += 1
        
        if error_count == 0:
            LoginDialog._styled_msg(self, "Deleted", f"Successfully removed {success_count} document(s).", "information")
        else:
            LoginDialog._styled_msg(self, "Partial Success", f"Removed {success_count} documents, but {error_count} failed.", "warning")
            
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
            self._users_table.setItem(row, 5, QTableWidgetItem("Enabled" if u.enabled else "Disabled"))
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

    def _refresh_settings(self) -> None:
        self._set_org_name.setText(self._workflow.get_setting("org_name", "Organization Name"))
        self._set_ref_prefix.setText(self._workflow.get_setting("ref_prefix", "SIGNIX/"))
        self._set_default_font.setText(self._workflow.get_setting("default_font", "Times New Roman"))

    def _save_general_settings(self) -> None:
        org = self._set_org_name.text().strip()
        prefix = self._set_ref_prefix.text().strip()
        font = self._set_default_font.text().strip()
        
        if not org or not prefix:
            LoginDialog._styled_msg(self, "Invalid", "Organization Name and Prefix cannot be empty.", "warning")
            return
            
        self._workflow.update_setting("org_name", org)
        self._workflow.update_setting("ref_prefix", prefix)
        self._workflow.update_setting("default_font", font)
        
        LoginDialog._styled_msg(self, "Saved", "General settings updated successfully.", "information")

    def _upload_new_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select REF.docx", "", "Word Documents (*.docx)")
        if not path:
            return
            
        try:
            self._workflow.upload_template(path)
            LoginDialog._styled_msg(self, "Success", "Document template (REF.docx) has been updated.", "information")
        except Exception as e:
            LoginDialog._styled_msg(self, "Failed", f"Could not update template: {str(e)}", "critical")

    def _promote_admin_selected_user(self) -> None:
        row = self._users_table.currentRow()
        if row < 0:
            return
        
        username_item = self._users_table.item(row, 1)
        if not username_item:
            return
            
        username = username_item.text()
        user = self._workflow.get_user_by_username(username)
        if not user:
            return
            
        if user.role == "Admin":
            LoginDialog._styled_msg(self, "Info", f"User '{username}' is already an admin.", "information")
            return
            
        res = QMessageBox.question(
            self, "Confirm Promotion", 
            f"Are you sure you want to promote '{username}' to Administrator role?\nThis cannot be undone easily.",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            self._workflow.update_user_role(user.id, "Admin")
            LoginDialog._styled_msg(self, "Success", f"User '{username}' has been promoted to Admin.", "information")
            self.refresh()

    def _make_user_selected(self) -> None:
        row = self._users_table.currentRow()
        if row < 0:
            return
        
        username_item = self._users_table.item(row, 1)
        if not username_item:
            return
            
        username = username_item.text()
        user = self._workflow.get_user_by_username(username)
        if not user:
            return
            
        if user.id == self._current_user.id:
            LoginDialog._styled_msg(self, "Action Denied", "You cannot demote yourself.", "warning")
            return
            
        if user.role != "Admin":
            return
            
        res = QMessageBox.question(
            self, "Confirm Demotion", 
            f"Are you sure you want to demote '{username}' to regular User role?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            self._workflow.update_user_role(user.id, "User")
            LoginDialog._styled_msg(self, "Success", f"User '{username}' has been demoted to User.", "information")
            self.refresh()
