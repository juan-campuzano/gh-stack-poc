from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    email: str  # must be unique (v2 note)
