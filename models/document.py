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


def _load_ref_body_html() -> str:
    template_path = Path(__file__).resolve().parent.parent / "documents" / "REF.docx"
    if not template_path.exists():
        return ""
    if DocxDocument is None:
        return ""
    try:
        doc = DocxDocument(str(template_path))
        body_parts = ["<div style='font-family: Arial, sans-serif;'>"]
        for para in doc.paragraphs:
            txt = para.text.strip()
            if not txt:
                body_parts.append("<br/>")
            else:
                style = ""
                for run in para.runs:
                    if run.bold:
                        style += "font-weight:bold; "
                    if run.italic:
                        style += "font-style:italic; "
                if style:
                    body_parts.append(f"<p style='{style}'>{txt}</p>")
                else:
                    body_parts.append(f"<p>{txt}</p>")
        body_parts.append("</div>")
        return "\n".join(body_parts)
    except Exception:
        return ""
