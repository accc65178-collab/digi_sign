from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QTextCharFormat
from PyQt5.QtWidgets import (
    QAction,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTextEdit,
    QToolBar,
)

from utils.file_handler import (
    DEFAULT_SAVE_EXTENSION,
    ensure_documents_dir,
    normalize_to_documents_dir,
    read_document,
    write_document_html,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Offline Document Editor")
        self.resize(1000, 650)

        self._current_file: Optional[Path] = None
        self._dirty: bool = False

        self._documents_dir = ensure_documents_dir()

        self._editor = QTextEdit(self)
        self._editor.setAcceptRichText(True)
        self.setCentralWidget(self._editor)

        self._editor.textChanged.connect(self._on_text_changed)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self.statusBar()
        self._update_status()

    def _create_actions(self) -> None:
        self._new_action = QAction("New", self)
        self._new_action.setShortcut("Ctrl+N")
        self._new_action.triggered.connect(self.new_document)

        self._open_action = QAction("Open", self)
        self._open_action.setShortcut("Ctrl+O")
        self._open_action.triggered.connect(self.open_document)

        self._save_action = QAction("Save", self)
        self._save_action.setShortcut("Ctrl+S")
        self._save_action.triggered.connect(self.save_document)

        self._exit_action = QAction("Exit", self)
        self._exit_action.setShortcut("Alt+F4")
        self._exit_action.triggered.connect(self.close)

        self._bold_action = QAction("Bold", self)
        self._bold_action.setShortcut("Ctrl+B")
        self._bold_action.setCheckable(True)
        self._bold_action.triggered.connect(self.toggle_bold)

        self._italic_action = QAction("Italic", self)
        self._italic_action.setShortcut("Ctrl+I")
        self._italic_action.setCheckable(True)
        self._italic_action.triggered.connect(self.toggle_italic)

        self._underline_action = QAction("Underline", self)
        self._underline_action.setShortcut("Ctrl+U")
        self._underline_action.setCheckable(True)
        self._underline_action.triggered.connect(self.toggle_underline)

    def _create_menus(self) -> None:
        menu = self.menuBar().addMenu("File")
        menu.addAction(self._new_action)
        menu.addAction(self._open_action)
        menu.addAction(self._save_action)
        menu.addSeparator()
        menu.addAction(self._exit_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Formatting", self)
        toolbar.setMovable(True)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(toolbar)

        toolbar.addAction(self._bold_action)
        toolbar.addAction(self._italic_action)
        toolbar.addAction(self._underline_action)

    def _on_text_changed(self) -> None:
        if not self._dirty:
            self._dirty = True
            self._update_status()

    def _update_status(self) -> None:
        name = self._current_file.name if self._current_file else "Untitled"
        state = "Unsaved" if self._dirty else "Saved"
        self.statusBar().showMessage(f"File: {name}   |   {state}")

    def _maybe_save_before_destructive_action(self) -> bool:
        if not self._dirty:
            return True

        result = QMessageBox.question(
            self,
            "Unsaved changes",
            "You have unsaved changes. Save before continuing?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )

        if result == QMessageBox.Cancel:
            return False

        if result == QMessageBox.Yes:
            return self.save_document()

        return True

    def new_document(self) -> None:
        if not self._maybe_save_before_destructive_action():
            return

        self._editor.blockSignals(True)
        self._editor.clear()
        self._editor.blockSignals(False)

        self._current_file = None
        self._dirty = False
        self._update_status()

    def open_document(self) -> None:
        if not self._maybe_save_before_destructive_action():
            return

        file_path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Document",
            str(self._documents_dir),
            "Documents (*.html *.htm *.txt);;All Files (*)",
        )
        if not file_path_str:
            return

        file_path = Path(file_path_str)
        try:
            content, is_html = read_document(file_path)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return

        self._editor.blockSignals(True)
        if is_html:
            self._editor.setHtml(content)
        else:
            self._editor.setPlainText(content)
        self._editor.blockSignals(False)

        self._current_file = file_path
        self._dirty = False
        self._update_status()

    def save_document(self) -> bool:
        if self._current_file is None:
            return self.save_document_as()

        try:
            html = self._editor.toHtml()
            write_document_html(self._current_file, html)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False

        self._dirty = False
        self._update_status()
        return True

    def save_document_as(self) -> bool:
        default_name = "untitled" + DEFAULT_SAVE_EXTENSION
        file_path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save Document",
            str(self._documents_dir / default_name),
            "HTML (*.html);;Text (*.txt)",
        )
        if not file_path_str:
            return False

        path = Path(file_path_str)
        if path.suffix.lower() == "":
            path = path.with_suffix(DEFAULT_SAVE_EXTENSION)

        path = normalize_to_documents_dir(path)
        self._current_file = path

        return self.save_document()

    def closeEvent(self, event) -> None:
        if self._maybe_save_before_destructive_action():
            event.accept()
        else:
            event.ignore()

    def _merge_char_format(self, fmt: QTextCharFormat) -> None:
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(cursor.WordUnderCursor)

        cursor.mergeCharFormat(fmt)
        self._editor.mergeCurrentCharFormat(fmt)

    def toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold if self._bold_action.isChecked() else QFont.Normal)
        self._merge_char_format(fmt)

    def toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(self._italic_action.isChecked())
        self._merge_char_format(fmt)

    def toggle_underline(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(self._underline_action.isChecked())
        self._merge_char_format(fmt)
