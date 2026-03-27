import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


SUPPORTED_OPEN_EXTENSIONS = (".html", ".htm", ".txt")
DEFAULT_SAVE_EXTENSION = ".html"


@dataclass(frozen=True)
class DocumentPaths:
    project_root: Path
    documents_dir: Path


def get_paths(project_root: Optional[Path] = None) -> DocumentPaths:
    if project_root is None:
        project_root = Path(__file__).resolve().parents[1]
    documents_dir = project_root / "documents"
    return DocumentPaths(project_root=project_root, documents_dir=documents_dir)


def ensure_documents_dir(project_root: Optional[Path] = None) -> Path:
    paths = get_paths(project_root)
    paths.documents_dir.mkdir(parents=True, exist_ok=True)
    return paths.documents_dir


def normalize_to_documents_dir(path: Path, project_root: Optional[Path] = None) -> Path:
    paths = get_paths(project_root)
    try:
        path = path.resolve()
    except OSError:
        path = Path(os.path.abspath(str(path)))

    docs = paths.documents_dir.resolve()

    # If file is already under documents/, keep it. Otherwise, store a copy path under documents/.
    try:
        path.relative_to(docs)
        return path
    except ValueError:
        return docs / path.name


def read_document(file_path: Path) -> Tuple[str, bool]:
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_OPEN_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    if suffix in (".html", ".htm"):
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return text, True

    text = file_path.read_text(encoding="utf-8", errors="replace")
    return text, False


def write_document_html(file_path: Path, html: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(html, encoding="utf-8")
