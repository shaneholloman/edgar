from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple


@dataclass
class Education:
    degree: str
    field: str
    university: str
    year: Optional[int] = None

@dataclass
class Executive:
    name: str
    age: Optional[int]
    current_role: str
    past_roles: List[str]
    education: List[Education]
    compensation_salary: float
    compensation_stock: float
    compensation_bonus: float
    compensation_other: float
    compensation_total: float
    compensation_year: int
    start_date: Optional[str]
    board_member: bool
    committee_memberships: List[str]
    other_board_memberships: List[str]
    notable_achievements: Optional[str]
