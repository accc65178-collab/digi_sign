from typing import Optional

from models.user import User


class Session:
    current_user: Optional[User] = None
