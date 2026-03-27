from dataclasses import dataclass
from typing import Optional


@dataclass
class Comment:
    id: Optional[int]
    document_id: int
    user_id: int
    comment: str
    timestamp: str
