import re
from typing import Dict, Set
from flang_tracer import SourceRange, Fragment

class LLVMIRParser:
    def __init__(self, raw_text: str):
        self.raw_text = raw_text
        self.loc_map: Dict[str, int] = self._parse_loc_map()

    def _parse_loc_map(self) -> Dict[str, int]:
        # Example: !56 = !DILocation(line: 27, column: 1, scope: !53)
        loc_map = {}
        pattern = re.compile(r'^\s*(!\d+)\s*=\s*!DILocation\(line:\s*(\d+)')
        for line in self.raw_text.splitlines():
            match = pattern.match(line)
            if match:
                loc_id, line_num = match.groups()
                loc_map[loc_id] = int(line_num)
        return loc_map

    def get_instructions_for_range(self, source_range: SourceRange) -> str:
        matching_loc_ids: Set[str] = {
            loc_id for loc_id, line in self.loc_map.items()
            if source_range.contains(line)
        }

        if not matching_loc_ids:
            return ""

        extracted_lines = []
        for line in self.raw_text.splitlines():
            # Instructions end with , !dbg !15
            if any(f"!dbg {loc_id}" in line for loc_id in matching_loc_ids):
                extracted_lines.append(line)
        
        return "\n".join(extracted_lines)

class LLVMIRHook:
    def __init__(self, raw_text: str):
        self.parser = LLVMIRParser(raw_text)

    def extract_fragment(self, source_range: SourceRange) -> Fragment:
        instr_text = self.parser.get_instructions_for_range(source_range)
        return Fragment(
            stage="llvm_ir",
            source_range=source_range,
            raw_text=instr_text
        )
