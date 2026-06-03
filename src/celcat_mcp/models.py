from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Room:
    id: str
    name: str
    department: Optional[str] = None
    campus: Optional[str] = None


@dataclass
class TimetableEvent:
    id: str
    name: str
    start: datetime
    end: datetime
    category: Optional[str] = None
    modules: list[str] = field(default_factory=list)
    rooms: list[str] = field(default_factory=list)
    staff: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)


RESOURCE_TYPES = {
    100: "Modules",
    101: "Staff",
    102: "Room",
    103: "Groups",
    104: "Students",
    105: "Teams",
    106: "Equipment",
    107: "Programmes",
}

PUBLIC_RESOURCE_TYPES = {102: "Room"}
