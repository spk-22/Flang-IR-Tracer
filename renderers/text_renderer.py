from typing import Dict, Any

class TextRenderer:
    def render(self, trace_data: Dict[str, Any]):
        print("=" * 60)
        print(f"TRACING CONSTRUCT: {trace_data['construct']}")
        print(f"SOURCE RANGE: {trace_data['source_range']['file']}:{trace_data['source_range']['start_line']}")
        print("=" * 60)

        for stage, fragments in trace_data["stages"].items():
            print(f"\n[ STAGE: {stage.upper()} ]")
            if not fragments:
                print("  (No matching fragments found)")
                continue
            
            for frag in fragments:
                print(f"  Confidence: {frag['confidence']}")
                print("-" * 20)
                # Indent the raw text
                indented_text = "\n".join("    " + line for line in frag["raw_text"].splitlines())
                print(indented_text)
                print("-" * 20)
        
        print("\n" + "=" * 60)
        print("TRACE COMPLETE")
        print("=" * 60)
