from flang_tracer import SourceRange, Fragment
from flang_tracer.hooks.mlir_utils import MLIRParser

class FIRExtractor:
    def __init__(self, raw_text: str):
        self.parser = MLIRParser(raw_text)

    def extract_fragment(self, source_range: SourceRange) -> Fragment:
        ops_text = self.parser.get_ops_for_range(source_range)
        return Fragment(
            stage="fir",
            source_range=source_range,
            raw_text=ops_text
        )
