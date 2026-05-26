import os
import re
from typing import Dict, List, Set, Optional
from flang_tracer import SourceRange

class MLIRParser:
    def __init__(self, raw_text: str):
        self.raw_text = raw_text
        self.loc_map: Dict[str, SourceRange] = self._parse_loc_map()

    def _parse_loc_map(self) -> Dict[str, SourceRange]:
        # Example: #loc2 = loc("/path/to/file.f90":10:3) or #loc3 = loc("demo.f90":10:3)
        loc_map = {}
        pattern = re.compile(r'(#loc\d+) = loc\("([^"]+)":(\d+):(\d+)\)')
        for match in pattern.finditer(self.raw_text):
            loc_id, file_path, line, col = match.groups()
            loc_map[loc_id] = SourceRange(
                file=file_path,
                start_line=int(line),
                end_line=int(line),
                start_col=int(col),
                end_col=int(col)
            )
        return loc_map

    def get_ops_for_range(self, source_range: SourceRange) -> str:
        # Find all loc IDs that overlap with the source range using basename-based comparison
        matching_loc_ids: Set[str] = {
            loc_id for loc_id, r in self.loc_map.items()
            if source_range.overlaps(r)
        }

        target_base = os.path.basename(source_range.file.replace('\\', '/')).lower()
        lines = self.raw_text.splitlines()
        extracted_lines = []
        
        # Regex to match inline loc attribute: loc("filename":line:col)
        inline_pattern = re.compile(r'loc\("([^"]+)":(\d+):(\d+)\)')
        # Regex to match aliased loc attribute: loc(#loc\d+)
        alias_pattern = re.compile(r'loc\((#loc\d+)\)')

        for line in lines:
            # Check for aliased location reference
            alias_match = alias_pattern.search(line)
            if alias_match:
                loc_id = alias_match.group(1)
                if loc_id in matching_loc_ids:
                    extracted_lines.append(line)
                    continue

            # Check for inline location reference
            inline_match = inline_pattern.search(line)
            if inline_match:
                file_path, line_num, _ = inline_match.groups()
                file_base = os.path.basename(file_path.replace('\\', '/')).lower()
                if file_base == target_base and source_range.contains(int(line_num)):
                    extracted_lines.append(line)
        
        return "\n".join(extracted_lines)

