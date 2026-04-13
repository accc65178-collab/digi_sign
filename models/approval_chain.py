from dataclasses import dataclass
from typing import Optional


@dataclass
class ApprovalChainStep:
    id: Optional[int]
    document_id: int
    user_id: int
    step_order: int
    status: str
    signature_png: Optional[bytes] = None
    approval_date: str = ""
