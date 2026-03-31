import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from database.db_manager import DbConfig, DbManager
from services.comment_service import CommentService
from services.session import Session
from services.workflow_service import WorkflowService
import ui.dashboard as dashboard_ui
from ui.login import LoginDialog


def main() -> int:
    app = QApplication(sys.argv)

    qss_path = Path(__file__).resolve().parent / "ui" / "styles.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    db_path = Path(__file__).resolve().parent / "documents" / "app.db"
    db = DbManager(DbConfig(db_path=db_path))
    db.init_db()

    workflow = WorkflowService(db)
    comments = CommentService(db)

    while True:
        login = LoginDialog(workflow)
        if login.exec_() != login.Accepted:
            break  # User closed login; exit app

        user = login.selected_user()
        if user is None:
            break

        Session.current_user = user
        dashboard_ui._should_exit = False
        dashboard = dashboard_ui.DashboardWindow(workflow, comments, user)
        dashboard.show()

        # Run the app; if dashboard closes (logout), loop back to login.
        # If the window X was clicked, _should_exit will be True; break the loop.
        if app.exec_() != 0 or dashboard_ui._should_exit:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
