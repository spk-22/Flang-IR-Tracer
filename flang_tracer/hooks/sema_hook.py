import re
from typing import List
from flang_tracer import SourceRange, Fragment

class SemaExtractor:
    def __init__(self, raw_text: str):
        self.raw_text = raw_text

    def extract_fragment(self, source_range: SourceRange) -> Fragment:
        # Example: name: path, line, col_range
        lines = self.raw_text.splitlines()
        matching_symbols = []
        for line in lines:
            # Match symbol definition line
            match = re.match(r"^(\w+): (.+), (\d+), (\d+)-(\d+)$", line)
            if match:
                name, path, lineno, start_col, end_col = match.groups()
                symbol_range = SourceRange(
                    file=path,
                    start_line=int(lineno),
                    end_line=int(lineno),
                    start_col=int(start_col),
                    end_col=int(end_col)
                )
                if source_range.overlaps(symbol_range):
                    matching_symbols.append(line)
        
        return Fragment(
            stage="semantic",
            source_range=source_range,
            raw_text="\n".join(matching_symbols)
        )
