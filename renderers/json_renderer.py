import json
from typing import Dict, Any

class JSONRenderer:
    def render(self, trace_data: Dict[str, Any]) -> str:
        return json.dumps(trace_data, indent=2)
