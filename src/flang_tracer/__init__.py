import os
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class SourceRange:
    file: str
    start_line: int
    end_line: int
    start_col: Optional[int] = None
    end_col: Optional[int] = None

    def contains(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line

    def overlaps(self, other: 'SourceRange') -> bool:
        f1 = os.path.basename(self.file.replace('\\', '/')).lower()
        f2 = os.path.basename(other.file.replace('\\', '/')).lower()
        if f1 != f2:
            return False
        return not (self.end_line < other.start_line or self.start_line > other.end_line)

@dataclass
class Fragment:
    stage: str
    source_range: SourceRange
    raw_text: str
    metadata: Optional[dict] = None

