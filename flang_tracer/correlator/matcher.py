from typing import List, Tuple
from flang_tracer import SourceRange, Fragment

class FuzzyMatcher:
    def __init__(self, tolerance: int = 1):
        self.tolerance = tolerance

    def match(self, target: SourceRange, candidate: SourceRange) -> Tuple[bool, float]:
        """
        Check if target and candidate match with a confidence score.
        1.0 for exact match.
        0.8 for overlap.
        0.5 for within tolerance lines.
        0.0 for no match.
        """
        if target.file != candidate.file:
            return False, 0.0

        # Exact match
        if (target.start_line == candidate.start_line and 
            target.end_line == candidate.end_line):
            return True, 1.0

        # Overlap match
        if target.overlaps(candidate):
            return True, 0.8

        # Tolerance match (nearby lines)
        start_diff = abs(target.start_line - candidate.start_line)
        end_diff = abs(target.end_line - candidate.end_line)
        
        if start_diff <= self.tolerance and end_diff <= self.tolerance:
            return True, 0.5

        return False, 0.0

    def find_best_matches(self, target: SourceRange, fragments: List[Fragment]) -> List[Tuple[Fragment, float]]:
        matches = []
        for f in fragments:
            is_match, score = self.match(target, f.source_range)
            if is_match:
                matches.append((f, score))
        
        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def score_match(self, source_text: str, candidate_text: str) -> float:
        """Calculate a similarity score between source text and candidate text."""
        if not source_text or not candidate_text:
            return 0.0
        # Normalize and tokenize
        import re
        s_tokens = set(re.findall(r'\b\w+\b', source_text.lower()))
        c_tokens = set(re.findall(r'\b\w+\b', candidate_text.lower()))
        if not s_tokens or not c_tokens:
            return 0.0
        # Calculate overlap (Jaccard similarity)
        intersection = s_tokens.intersection(c_tokens)
        union = s_tokens.union(c_tokens)
        return round(len(intersection) / len(union), 2)

