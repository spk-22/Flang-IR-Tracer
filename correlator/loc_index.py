from typing import List, Dict
from flang_tracer import SourceRange, Fragment

class LocationIndex:
    def __init__(self):
        self.fragments: List[Fragment] = []

    def add_fragment(self, fragment: Fragment):
        self.fragments.append(fragment)

    def query(self, target_range: SourceRange) -> List[Fragment]:
        """Return all fragments that overlap with the target range."""
        return [
            f for f in self.fragments
            if target_range.overlaps(f.source_range)
        ]

    def get_by_stage(self, stage: str) -> List[Fragment]:
        return [f for f in self.fragments if f.stage == stage]
