from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None


@dataclass
class Document:
    id: Optional[int]
    title: str
    subject: str
    content: str
    created_by: int
    status: str
    assigned_to: Optional[int]
    current_step: int
    initiator_signature_png: Optional[bytes] = None
    created_at: str = ""


def _load_ref_body_html() -> str:
    return ""
