import json
from dataclasses import asdict
from typing import List, Dict, Any
from flang_tracer import SourceRange, Fragment

class TraceGraph:
    def __init__(self, construct_name: str, source_range: SourceRange):
        self.construct_name = construct_name
        self.source_range = source_range
        self.stages: Dict[str, List[Dict[str, Any]]] = {}
        self.telemetry: Dict[str, Dict[str, Any]] = {}

    def add_fragment(self, stage: str, fragment: Fragment, confidence: float, duration_ms: float = 0.0):
        if stage not in self.stages:
            self.stages[stage] = []
        
        # Calculate op count (lines of IR)
        op_count = len([l for l in fragment.raw_text.splitlines() if l.strip()])
        
        # Convert fragment to serializable dict
        f_dict = {
            "source_range": {
                "start_line": fragment.source_range.start_line,
                "end_line": fragment.source_range.end_line,
            },
            "raw_text": fragment.raw_text,
            "confidence": confidence,
            "metrics": {
                "op_count": op_count,
                "duration_ms": duration_ms
            }
        }
        self.stages[stage].append(f_dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "construct": self.construct_name,
            "source_range": {
                "file": self.source_range.file,
                "start_line": self.source_range.start_line,
                "end_line": self.source_range.end_line
            },
            "stages": self.stages
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
