import sys
from pathlib import Path
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from database.db_manager import DbConfig, DbManager
from services.comment_service import CommentService
from services.session import Session
from services.workflow_service import WorkflowService
import ui.dashboard as dashboard_ui
from ui.login import LoginDialog


def get_database_path() -> Path:
    """Get persistent database path for the application"""
    # Check if running from exe
    if getattr(sys, 'frozen', False):
        # Running from exe - use data folder within the exe directory for shared network access
        exe_dir = Path(sys.executable).parent
        db_dir = exe_dir / "data"
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "app.db"
    else:
        # Running from source - use local documents folder
        return Path(__file__).resolve().parent / "documents" / "app.db"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Signix")
    
    icon_path = Path(__file__).resolve().parent / "ui" / "images" / "logo.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    qss_path = Path(__file__).resolve().parent / "ui" / "styles.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    # Use persistent database path
    db_path = get_database_path()
    print(f"Database path: {db_path}")  # Debug line to see where database is stored
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
