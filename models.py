from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any

@dataclass
class Subtitle:
    text: str
    end: float
    start: float
    style: Dict[str, Any]
    is_locked: bool = False

@dataclass
class Edit:
    type: str
    end: float
    speed: float
    start: float
    anchor_x: float
    anchor_y: float
    zoom: Union[str, float]
    is_locked: bool = False

@dataclass
class Segment:
    end: float
    start: float
    can_copy: bool = False
    is_original: bool = False
    edit: Optional[Edit] = None
    needs_processing: bool = True
    subtitles: List[Subtitle] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start
