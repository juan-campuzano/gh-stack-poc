from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    email: str  # unique, required (v2+v3 note)
