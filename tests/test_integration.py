import os
import pytest
from flang_tracer.driver import FlangDriver
from flang_tracer import SourceRange
from flang_tracer.hooks.fir_hook import FIRExtractor
from flang_tracer.hooks.hlfir_hook import HLFIRExtractor
from flang_tracer.hooks.sema_hook import SemaExtractor
from flang_tracer.hooks.llvmir_hook import LLVMIRHook

FLANG_PATH = "/home/siya/llvm-project/build/bin/flang-new"
DEMO_F90 = "/mnt/d/cd lab el/flang-tracer/tests/fixtures/demo.f90"

def test_driver_and_extractors():
    # Only run if in WSL and flang-new exists
    if not os.path.exists(FLANG_PATH):
        pytest.skip("flang-new not found at expected path")

    driver = FlangDriver(FLANG_PATH)
    dumps = driver.get_all_dumps(DEMO_F90)

    assert dumps["parse_tree"] != ""
    assert dumps["symbols"] != ""
    assert dumps["fir"] != ""
    assert dumps["hlfir"] != ""
    assert dumps["llvm_ir"] != ""

    # Test FIR Extraction for 'sum = 0' at line 10
    target_range = SourceRange(DEMO_F90, 10, 10)
    fir_extractor = FIRExtractor(dumps["fir"]["content"])
    fir_fragment = fir_extractor.extract_fragment(target_range)
    assert "fir.store" in fir_fragment.raw_text

    # Test Semantic Extraction
    sema_extractor = SemaExtractor(dumps["symbols"]["content"])
    sema_fragment = sema_extractor.extract_fragment(target_range)
    # Line 10 has 'sum', which is defined on line 6
    # Wait, overlapping range... if I look for line 6
    sum_range = SourceRange(DEMO_F90, 6, 6)
    sema_fragment_sum = sema_extractor.extract_fragment(sum_range)
    assert "sum" in sema_fragment_sum.raw_text

    # Test LLVM IR Extraction
    llvm_hook = LLVMIRHook(dumps["llvm_ir"]["content"])
    llvm_fragment = llvm_hook.extract_fragment(target_range)
    assert "store" in llvm_fragment.raw_text

