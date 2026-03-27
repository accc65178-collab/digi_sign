from dataclasses import dataclass
from typing import Optional


@dataclass
class Document:
    id: Optional[int]
    title: str
    content: str
    created_by: int
    status: str
    assigned_to: Optional[int]
    current_step: int
