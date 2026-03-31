from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int
    name: str
    full_name: str
    employee_id: str
    department: str
    lab: str
    username: str
    password_hash: str
    designation: str
    role: str
    status: str
    enabled: bool

    def display_label(self) -> str:
        d = (self.designation or "").strip()
        if d:
            return f"{self.full_name} ({d})"
        return self.full_name
