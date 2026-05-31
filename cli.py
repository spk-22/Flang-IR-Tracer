import argparse
import os
import sys
from flang_tracer import SourceRange, Fragment
from flang_tracer.driver import FlangDriver
from flang_tracer.hooks.parse_hook import ParseTreeParser
from flang_tracer.hooks.sema_hook import SemaExtractor
from flang_tracer.hooks.fir_hook import FIRExtractor
from flang_tracer.hooks.hlfir_hook import HLFIRExtractor
from flang_tracer.hooks.llvmir_hook import LLVMIRHook
from flang_tracer.correlator.loc_index import LocationIndex
from flang_tracer.correlator.matcher import FuzzyMatcher
from flang_tracer.correlator.graph import TraceGraph
from flang_tracer.correlator.ir_stats import IRStats
from flang_tracer.renderers.text_renderer import TextRenderer
from flang_tracer.renderers.json_renderer import JSONRenderer
from flang_tracer.renderers.html_renderer import HTMLRenderer
from flang_tracer.renderers.dashboard_renderer import DashboardRenderer

def main():
    parser = argparse.ArgumentParser(description="Flang-Tracer: Trace Fortran constructs across compilation stages.")
    parser.add_argument("input", nargs="?", help="Fortran source file (.f90)")
    parser.add_argument("--line", type=int, help="Start line to trace")
    parser.add_argument("--end-line", type=int, help="End line to trace (optional)")
    parser.add_argument("--output", choices=["text", "json", "html", "dashboard"], default="text", help="Output format")
    parser.add_argument("--flang", default="flang-new", help="Path to flang-new binary")
    parser.add_argument("--out-file", help="File to save the output (for json and html)")
    parser.add_argument("--opt-level", choices=["O0", "O1", "O2", "O3"], default="O0", help="Optimization level for flang (default: O0)")
    parser.add_argument("--diff-opt", action="store_true", help="Trace at both O0 and O3, and output side-by-side diff")
    parser.add_argument("--serve", action="store_true", help="Launch the interactive real-time web dashboard")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the web server on (default: 8000)")

    args = parser.parse_args()

    if args.serve:
        print(f"[*] Starting interactive dashboard on http://localhost:{args.port}")
        import uvicorn
        uvicorn.run("flang_tracer.server:app", host="0.0.0.0", port=args.port, reload=False)
        return

    if not args.input:
        parser.error("the following arguments are required: input (unless --serve is used)")
    
    input_file = os.path.abspath(args.input)
    if not os.path.exists(input_file):
        print(f"Error: File {input_file} not found.")
        sys.exit(1)
        
    if args.line is None:
        parser.error("the following arguments are required: --line (unless --serve is used)")

    end_line = args.end_line if args.end_line else args.line
    target_range = SourceRange(input_file, args.line, end_line)

    print(f"[*] Tracing {args.input} lines {args.line}-{end_line}...")

    # 1. Run Driver
    driver = FlangDriver(args.flang, opt_level=args.opt_level)
    dumps = driver.get_all_dumps(input_file)

    dumps_o3 = None
    if args.diff_opt:
        driver_o3 = FlangDriver(args.flang, opt_level="O3")
        dumps_o3 = driver_o3.get_all_dumps(input_file)

    # 2. Extract and Index
    index = LocationIndex()
    
    # Hooks mapping
    hooks = [
        ("parse_tree", ParseTreeParser(dumps["parse_tree"]["content"])),
        ("semantic", SemaExtractor(dumps["symbols"]["content"])),
        ("fir", FIRExtractor(dumps["fir"]["content"])),
        ("hlfir", HLFIRExtractor(dumps["hlfir"]["content"])),
        ("llvm_ir", LLVMIRHook(dumps["llvm_ir"]["content"]))
    ]

    if args.diff_opt:
        hooks.append(("llvm_ir_o3", LLVMIRHook(dumps_o3["llvm_ir"]["content"])))

    for stage, extractor in hooks:
        try:
            if stage == "llvm_ir_o3":
                duration = dumps_o3.get("llvm_ir", {}).get("duration_ms", 0.0)
            else:
                duration = dumps.get(stage, {}).get("duration_ms", 0.0)
                
            frag = extractor.extract_fragment(target_range)
            if stage == "llvm_ir_o3":
                frag = Fragment(stage="llvm_ir_o3", source_range=frag.source_range, raw_text=frag.raw_text, metadata=frag.metadata)
            
            if frag.metadata is None:
                frag.metadata = {}
            frag.metadata["ir_stats"] = IRStats.count_ops(frag.raw_text, stage)
                
            index.add_fragment(frag)
            # Store duration in index or metadata if needed, 
            # but for now we'll fetch it from dumps when adding to graph
        except Exception as e:
            print(f"[!] Error extracting {stage}: {e}")

    # 3. Correlate
    graph = TraceGraph(f"Trace of {os.path.basename(input_file)}:{args.line}", target_range)
    matcher = FuzzyMatcher()
    
    for stage, _ in hooks:
        stage_frags = index.get_by_stage(stage)
        best_matches = matcher.find_best_matches(target_range, stage_frags)
        
        if stage == "llvm_ir_o3":
            duration = dumps_o3.get("llvm_ir", {}).get("duration_ms", 0.0)
        else:
            duration = dumps.get(stage, {}).get("duration_ms", 0.0)
            
        for frag, score in best_matches:
            if score > 0:
                graph.add_fragment(stage, frag, score, duration_ms=duration)

    # 4. Render
    trace_data = graph.to_dict()
    if args.output == "text":
        TextRenderer().render(trace_data)
    elif args.output == "json":
        result = JSONRenderer().render(trace_data)
        if args.out_file:
            with open(args.out_file, "w") as f:
                f.write(result)
            print(f"[*] JSON output saved to {args.out_file}")
        else:
            print(result)
    elif args.output == "html":
        result = HTMLRenderer().render(trace_data)
        out_file = args.out_file if args.out_file else "trace.html"
        with open(out_file, "w") as f:
            f.write(result)
        print(f"[*] HTML report generated: {out_file}")
    elif args.output == "dashboard":
        result = DashboardRenderer().render(trace_data)
        out_file = args.out_file if args.out_file else "dashboard.html"
        with open(out_file, "w") as f:
            f.write(result)
        print(f"[*] Premium Dashboard generated: {out_file}")

if __name__ == "__main__":
    main()
