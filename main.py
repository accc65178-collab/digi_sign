import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from database.db_manager import DbConfig, DbManager
from services.comment_service import CommentService
from services.session import Session
from services.workflow_service import WorkflowService
from ui.dashboard import DashboardWindow
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

    login = LoginDialog(workflow)
    if login.exec_() != login.Accepted:
        return 0

    user = login.selected_user()
    if user is None:
        return 0

    Session.current_user = user
    dashboard = DashboardWindow(workflow, comments, user)
    dashboard.show()

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
