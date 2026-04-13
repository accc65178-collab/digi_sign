from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.document import Document
from models.user import User
from services.comment_service import CommentService
from services.workflow_service import WorkflowService
from ui.admin_panel import AdminPanelDialog
from ui.editor import EditorWindow, _SignatureDialog
from ui.components.card_widget import CardWidget
from ui.components.sidebar import Sidebar, default_nav_items
from ui.components.table_widget import TableWidget
from ui.components.topbar import TopBar

# Global flag to indicate the app should exit
_should_exit = False


@dataclass(frozen=True)
class _RowRef:
    doc_id: int


class DashboardWindow(QMainWindow):
    def __init__(self, workflow: WorkflowService, comment_service: CommentService, current_user: User) -> None:
        super().__init__()

        self._workflow = workflow
        self._comments = comment_service
        self._current_user = current_user
        self._logout_requested = False

        self.setWindowTitle(f"Signix - Dashboard ({current_user.display_label()})")
        self.resize(1100, 700)
        self.setWindowState(Qt.WindowMaximized)

        root = QWidget(self)
        root.setObjectName("AppShell")
        self.setCentralWidget(root)

        self._sidebar = Sidebar(default_nav_items(), self)
        self._sidebar.nav_changed.connect(self._on_nav_changed)

        self._topbar = TopBar(current_user.display_label(), self)
        self._topbar.logout_requested.connect(self._logout)
        self._topbar.admin_requested.connect(self._open_admin)
        self._topbar.search_changed.connect(self._on_search_changed)
        self._topbar.set_admin_visible(current_user.role == "Admin")

        self._create_menus()

        self._stack = QStackedWidget(self)

        self._dashboard_page = self._build_dashboard_page()
        self._my_docs_page = self._build_table_page("My Documents")
        self._my_approved_page = self._build_table_page("My Approved Letters")
        self._pending_page = self._build_table_page("Pending Approvals")
        self._approved_by_me_page = self._build_table_page("Approved by Me")

        self._stack.addWidget(self._dashboard_page)
        self._stack.addWidget(self._my_docs_page)
        self._stack.addWidget(self._my_approved_page)
        self._stack.addWidget(self._pending_page)
        self._stack.addWidget(self._approved_by_me_page)

        right = QWidget(self)
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._topbar)
        right_layout.addWidget(self._stack, 1)
        right.setLayout(right_layout)

        shell = QHBoxLayout()
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._sidebar)
        shell.addWidget(right, 1)
        root.setLayout(shell)

        self._my_docs_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._my_docs_table))
        self._my_approved_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._my_approved_table))
        self._pending_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._pending_table))
        self._approved_by_me_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._approved_by_me_table))
        self._recent_table.itemDoubleClicked.connect(lambda _: self._open_selected(self._recent_table))

        self._sidebar.set_active("dashboard")
        self.refresh()

    def _create_menus(self) -> None:
        mb = self.menuBar()
        profile_menu = mb.addMenu("Profile")
        act_change_sig = profile_menu.addAction("Change Signature")
        act_change_sig.triggered.connect(self._change_signature)

    def _change_signature(self) -> None:
        dlg = _SignatureDialog(self)
        if dlg.exec_() != dlg.Accepted:
            return
        sig_png = dlg.signature_png_bytes()
        if not sig_png:
            return
        try:
            self._workflow.set_user_signature_png(user_id=self._current_user.id, signature_png=sig_png)
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))

    def _make_table(self) -> QTableWidget:
        return TableWidget(["Title", "Subject", "Status", "Initiator", "Created", "Approval Chain", "Approved"], self)

    def _build_table_page(self, title: str) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        header = QWidget(self)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(QLabel(title))
        header_layout.addStretch(1)
        if title == "My Documents":
            btn = QPushButton("New Document", self)
            btn.setObjectName("ButtonPrimary")
            btn.clicked.connect(self._new_document)
            header_layout.addWidget(btn)
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.setObjectName("ButtonSecondary")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        header.setLayout(header_layout)

        table = self._make_table()
        empty = QLabel("", self)
        empty.setObjectName("EmptyState")
        empty.setAlignment(Qt.AlignCenter)

        layout.addWidget(header)
        layout.addWidget(table, 1)
        layout.addWidget(empty)
        page.setLayout(layout)

        if title == "My Documents":
            self._my_docs_table = table
            self._my_docs_empty = empty
        elif title == "My Approved Letters":
            self._my_approved_table = table
            self._my_approved_empty = empty
        elif title == "Pending Approvals":
            self._pending_table = table
            self._pending_empty = empty
        elif title == "Approved by Me":
            self._approved_by_me_table = table
            self._approved_by_me_empty = empty

        return page

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Dashboard", self)
        title.setObjectName("PageTitle")

        cards = QWidget(self)
        cards_layout = QHBoxLayout()
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)
        self._total_card = CardWidget("Total Documents", "0", self)
        self._pending_card = CardWidget("Pending Approvals", "0", self)
        self._approved_card = CardWidget("Approved", "0", self)
        cards_layout.addWidget(self._total_card)
        cards_layout.addWidget(self._pending_card)
        cards_layout.addWidget(self._approved_card)
        cards.setLayout(cards_layout)

        recent_header = QWidget(self)
        recent_header_layout = QHBoxLayout()
        recent_header_layout.setContentsMargins(0, 0, 0, 0)
        recent_header_layout.addWidget(QLabel("Recent Activity"))
        recent_header_layout.addStretch(1)
        refresh_btn = QPushButton("Refresh", self)
        refresh_btn.setObjectName("ButtonSecondary")
        refresh_btn.clicked.connect(self.refresh)
        recent_header_layout.addWidget(refresh_btn)
        recent_header.setLayout(recent_header_layout)

        self._recent_table = self._make_table()
        self._recent_empty = QLabel("", self)
        self._recent_empty.setObjectName("EmptyState")
        self._recent_empty.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(cards)
        layout.addSpacing(6)
        layout.addWidget(recent_header)
        layout.addWidget(self._recent_table, 1)
        layout.addWidget(self._recent_empty)
        page.setLayout(layout)
        return page

    def _set_empty_state(self, table: QTableWidget, label: QLabel, message: str) -> None:
        has_rows = table.rowCount() > 0
        label.setVisible(not has_rows)
        if not has_rows:
            label.setText(message)

    def refresh(self) -> None:
        created = self._workflow.my_created_documents(self._current_user.id)
        pending = self._workflow.pending_for_me(self._current_user.id)
        approved_by_me = self._workflow.documents_approved_by_me(self._current_user.id)

        # 1. My Documents (Drafts/Pending creation)
        my_docs = [d for d in created if d.status not in ("Approved", "Rejected")]
        
        # 2. My Approved Letters (Created by me, now approved)
        my_approved = [d for d in created if d.status == "Approved"]
        
        # 3. Pending Approvals (Assigned to me)
        # (already in 'pending' variable)
        
        # 4. Approved by Me (Created by others, approved by me)
        # (already in 'approved_by_me' variable)

        pending_count = sum(1 for d in pending if d.status == "Pending")
        self._sidebar.set_badge("pending", pending_count)

        all_docs = created + pending + approved_by_me
        total = len({d.id for d in all_docs if d.id is not None})
        approved_total = sum(1 for d in all_docs if d.status == "Approved")

        self._total_card.set_value(str(total))
        self._pending_card.set_value(str(pending_count))
        self._approved_card.set_value(str(approved_total))

        self._fill_table(self._my_docs_table, my_docs)
        self._fill_table(self._my_approved_table, my_approved)
        self._fill_table(self._pending_table, pending, highlight_pending=True)
        self._fill_table(self._approved_by_me_table, approved_by_me)

        recent = (pending + created + approved_by_me)[:]
        recent.sort(key=lambda d: (d.id or 0), reverse=True)
        self._fill_table(self._recent_table, recent[:10], highlight_pending=True)

        self._set_empty_state(self._my_docs_table, self._my_docs_empty, "No documents found")
        self._set_empty_state(self._my_approved_table, self._my_approved_empty, "No approved letters")
        self._set_empty_state(self._pending_table, self._pending_empty, "No pending approvals")
        self._set_empty_state(self._approved_by_me_table, self._approved_by_me_empty, "No letters approved by you")
        self._set_empty_state(self._recent_table, self._recent_empty, "No recent activity")

    def _assignee_label(self, assigned_to: Optional[int]) -> str:
        if assigned_to is None:
            return ""

        user = self._workflow.get_user(assigned_to)
        if user is None:
            return str(assigned_to)
        return user.display_label()

    def _fill_table(self, table: QTableWidget, docs: list[Document], *, highlight_pending: bool = False) -> None:
        was_sorting = table.isSortingEnabled()
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for doc in docs:
            row = table.rowCount()
            table.insertRow(row)

            title_item = QTableWidgetItem(doc.title)
            title_item.setData(Qt.UserRole, _RowRef(doc_id=int(doc.id)))
            
            # Get initiator info
            initiator_name = "Unknown"
            initiator = self._workflow.get_user(doc.created_by)
            if initiator:
                initiator_name = initiator.display_label()

            # Format creation date
            created_date = ""
            if doc.created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(doc.created_at)
                    created_date = dt.strftime("%d-%m-%Y")
                except Exception:
                    created_date = doc.created_at[:10] if len(doc.created_at) > 10 else doc.created_at

            # Get approval chain info
            approval_chain = ""
            approved_date = ""
            if doc.id:
                try:
                    chain = self._workflow.get_approval_chain(doc.id)
                    if chain:
                        chain_names = []
                        for step in chain:
                            approver = self._workflow.get_user(step.user_id)
                            if approver:
                                name = approver.display_label()
                                if step.status == "Approved":
                                    chain_names.append(f"{name} ✓")
                                    # Get the last approval date
                                    if step.approval_date and not approved_date:
                                        try:
                                            from datetime import datetime
                                            dt = datetime.fromisoformat(step.approval_date)
                                            approved_date = dt.strftime("%d-%m-%Y")
                                        except Exception:
                                            approved_date = step.approval_date[:10] if len(step.approval_date) > 10 else step.approval_date
                                elif step.status == "Pending":
                                    chain_names.append(f"{name} (Pending)")
                                else:
                                    chain_names.append(name)
                        approval_chain = " → ".join(chain_names)
                except Exception:
                    approval_chain = "Not configured"

            # Create table items
            subject_item = QTableWidgetItem(doc.subject[:50] + "..." if len(doc.subject) > 50 else doc.subject)
            status_item = QTableWidgetItem(doc.status)
            initiator_item = QTableWidgetItem(initiator_name)
            created_item = QTableWidgetItem(created_date)
            chain_item = QTableWidgetItem(approval_chain)
            approved_item = QTableWidgetItem(approved_date if approved_date else "-")

            # Highlight pending items
            if highlight_pending and doc.status == "Pending":
                for item in (title_item, subject_item, status_item, initiator_item, created_item, chain_item, approved_item):
                    item.setBackground(QColor(255, 248, 204))

            # Set items in table
            table.setItem(row, 0, title_item)
            table.setItem(row, 1, subject_item)
            table.setItem(row, 2, status_item)
            table.setItem(row, 3, initiator_item)
            table.setItem(row, 4, created_item)
            table.setItem(row, 5, chain_item)
            table.setItem(row, 6, approved_item)

        # Resize columns for better fit
        table.setColumnWidth(0, 200)  # Title
        table.setColumnWidth(1, 200)  # Subject
        table.setColumnWidth(2, 100)  # Status
        table.setColumnWidth(3, 120)  # Initiator
        table.setColumnWidth(4, 100)  # Created
        table.setColumnWidth(5, 250)  # Approval Chain
        table.setColumnWidth(6, 100)  # Approved

        table.setSortingEnabled(was_sorting)

    def _selected_doc_id(self, table: QTableWidget) -> Optional[int]:
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        if item is None:
            return None
        ref = item.data(Qt.UserRole)
        if ref is None:
            return None
        return ref.doc_id

    def _on_nav_changed(self, key: str) -> None:
        mapping = {
            "dashboard": 0,
            "my_docs": 1,
            "my_approved": 2,
            "pending": 3,
            "approved_by_me": 4,
        }
        index = mapping.get(key)
        if index is not None:
            self._stack.setCurrentIndex(index)

    def _on_search_changed(self, text: str) -> None:
        table = self._current_table()
        if table is None:
            return
        query = text.strip().lower()
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            title = "" if item is None else item.text().lower()
            table.setRowHidden(row, bool(query) and query not in title)

    def _current_table(self) -> Optional[QTableWidget]:
        idx = self._stack.currentIndex()
        if idx == 0:
            return self._recent_table
        if idx == 1:
            return self._my_docs_table
        if idx == 2:
            return self._my_approved_table
        if idx == 3:
            return self._pending_table
        if idx == 4:
            return self._approved_by_me_table
        return None

    def _logout(self) -> None:
        self._logout_requested = True
        self.close()

    def closeEvent(self, event) -> None:
        # If the user clicked Logout, return to the login dialog.
        # If the user clicked the window's X button, exit the application.
        if not self._logout_requested:
            global _should_exit
            _should_exit = True
        event.accept()

    def _open_admin(self) -> None:
        if self._current_user.role != "Admin":
            return
        dlg = AdminPanelDialog(self._workflow, self._current_user, self)
        dlg.exec_()
        self.refresh()

    def _open_selected(self, table: QTableWidget) -> None:
        doc_id = self._selected_doc_id(table)
        if doc_id is None:
            return

        doc = self._workflow.get_document(doc_id)
        if doc is None:
            QMessageBox.warning(self, "Not found", "Document no longer exists.")
            self.refresh()
            return

        editor = EditorWindow(self._workflow, self._comments, self._current_user, doc, self)
        editor.saved.connect(self.refresh)
        editor.show()

    def _new_document(self) -> None:
        editor = EditorWindow(self._workflow, self._comments, self._current_user, None, self)
        editor.saved.connect(self.refresh)
        editor.show()
