import os
import json
import asyncio
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from flang_tracer.driver import FlangDriver
from flang_tracer import SourceRange
from flang_tracer.hooks.parse_hook import ParseTreeParser
from flang_tracer.hooks.sema_hook import SemaExtractor
from flang_tracer.hooks.fir_hook import FIRExtractor
from flang_tracer.hooks.hlfir_hook import HLFIRExtractor
from flang_tracer.hooks.llvmir_hook import LLVMIRHook
from flang_tracer.correlator.matcher import FuzzyMatcher
from flang_tracer.correlator.ir_stats import IRStats

app = FastAPI()

# Setup static files directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def get_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)

@app.get("/api/examples")
async def get_examples():
    """Return available .f90 examples from the project workspace."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    examples = []
    for root, dirs, files in os.walk(base_dir):
        if '.venv' in dirs:
            dirs.remove('.venv')
        if '.git' in dirs:
            dirs.remove('.git')
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
            
        for file in files:
            if file.endswith('.f90'):
                rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                examples.append(rel_path.replace('\\', '/'))
    return {"examples": sorted(examples)}

def parse_ast_to_json(ast_text: str) -> dict:
    lines = ast_text.strip().split('\n')
    # Skip header lines
    lines = [l for l in lines if not l.strip().startswith("==") and not l.strip() == "Parse Tree"]
    if not lines or not lines[0].strip():
        return {"name": "Empty", "children": []}
        
    root = {"name": "Parse Tree", "children": []}
    stack = [(-1, root)] # (depth, node)
    
    for line in lines:
        if not line.strip(): continue
        
        match = re.match(r"^([ |]*)(\w+.*)$", line)
        if match:
            indent_str = match.group(1)
            content = match.group(2)
            # The depth is the length of the leading indentation string!
            depth = len(indent_str)
        else:
            depth = 0
            content = line.strip()
            
        node = {"name": content, "children": []}
        
        while stack and stack[-1][0] >= depth:
            stack.pop()
            
        if stack:
            stack[-1][1]["children"].append(node)
        stack.append((depth, node))
        
    return root

@app.websocket("/ws/trace")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        req = json.loads(data)
        
        file_path = req.get("file")
        if not file_path:
            await websocket.send_json({"type": "error", "message": "No example file selected in the dropdown."})
            return
            
        opt_level = req.get("opt_level", "O0")
        diff_opt = req.get("diff_opt", False)
        line = req.get("line", 1)
        end_line = req.get("end_line", line)
        flang_path = req.get("flang", "flang-new")
        
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        abs_file_path = os.path.join(base_dir, file_path)
        
        if not os.path.exists(abs_file_path) or os.path.isdir(abs_file_path):
            await websocket.send_json({"type": "error", "message": f"File {file_path} not found or is a directory"})
            return
            
        target_range = SourceRange(abs_file_path, line, end_line)
        driver = FlangDriver(flang_path, opt_level=opt_level)
        
        stages = [
            ("parse_tree", ["-fc1", "-fdebug-dump-parse-tree"], ParseTreeParser),
            ("semantic", ["-fc1", "-fget-symbols-sources"], SemaExtractor),
            ("fir", ["-fc1", "-emit-fir", "-mmlir", "--mlir-print-debuginfo", "-o", "-"], FIRExtractor),
            ("hlfir", ["-fc1", "-emit-hlfir", "-mmlir", "--mlir-print-debuginfo", "-o", "-"], HLFIRExtractor),
            ("llvm_ir", ["-S", "-emit-llvm", "-g", f"-{opt_level}", "-o", "-"], LLVMIRHook)
        ]
        
        # Read source code
        with open(abs_file_path, "r") as f:
            all_lines = f.readlines()
            source_lines = "".join(all_lines[line-1:end_line])
        
        await websocket.send_json({
            "type": "init",
            "source": source_lines,
            "stages": [s[0] for s in stages]
        })
        
        stageData = {}
        matcher = FuzzyMatcher()
        
        for stage_name, flags, ExtractorClass in stages:
            await websocket.send_json({"type": "progress", "stage": stage_name, "status": "running"})
            
            try:
                content, duration, memory_kb = driver.run_stage(abs_file_path, flags)
            except Exception as e:
                # Catches LLVM aborts (e.g. coarray unsupported features)
                await websocket.send_json({
                    "type": "error",
                    "stage": stage_name,
                    "message": f"Flang crashed/aborted: {str(e)}"
                })
                await asyncio.sleep(0.1)
                continue
            
            if not content:
                await websocket.send_json({
                    "type": "error",
                    "stage": stage_name,
                    "message": "No output from Flang for this stage (compilation may have failed)"
                })
                await asyncio.sleep(0.1)
                continue
            
            try:
                extractor = ExtractorClass(content)
                parser = extractor  # Keep reference for parse_tree AST
                frag = parser.extract_fragment(target_range)
                stageData[stage_name] = {"fragment": frag.raw_text}
                score = matcher.score_match(source_lines, frag.raw_text)
                payload = {
                    "type": "result",
                    "stage": stage_name,
                    "duration_ms": round(duration * 1000, 2),
                    "fragment": frag.raw_text,
                    "score": score,
                    "op_count": len(frag.raw_text.split('\n')),
                    "ir_stats": IRStats.count_ops(frag.raw_text, stage_name),
                    "memory_kb": memory_kb
                }
                if stage_name == "parse_tree":
                    # Convert parse tree to JSON for D3 visualization
                    def node_to_dict(node):
                        return {"name": node.content, "children": [node_to_dict(c) for c in node.children] if node.children else []}
                    ast_json = node_to_dict(parser.root) if parser.root else {"name": "Empty", "children": []}
                    payload["ast_json"] = ast_json
                    # Generate full tree text for IR Code tab
                    def render_tree(node, depth=0):
                        lines = ["  " * depth + node.content]
                        for child in node.children:
                            lines.extend(render_tree(child, depth + 1))
                        return lines
                    full_tree_text = "\n".join(render_tree(parser.root)) if parser.root else ""
                    payload["full_tree"] = full_tree_text
                await websocket.send_json(payload)
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "stage": stage_name,
                    "message": str(e)
                })
                
            await asyncio.sleep(0.1)  # Small delay for smooth UI update
            
        # Optional O3 diff
        if diff_opt:
            stage_name = "llvm_ir_o3"
            await websocket.send_json({"type": "progress", "stage": stage_name, "status": "running"})
            try:
                driver_o3 = FlangDriver(flang_path, opt_level="O3")
                content, duration, memory_kb = driver_o3.run_stage(abs_file_path, ["-S", "-emit-llvm", "-g", "-O3", "-o", "-"])
                if content:
                    extractor = LLVMIRHook(content)
                    frag = extractor.extract_fragment(target_range)
                    score = matcher.score_match(source_lines, frag.raw_text)
                    await websocket.send_json({
                        "type": "result",
                        "stage": stage_name,
                        "duration_ms": round(duration * 1000, 2),
                        "fragment": frag.raw_text,
                        "score": score,
                        "op_count": len(frag.raw_text.split('\n')),
                        "ir_stats": IRStats.count_ops(frag.raw_text, stage_name),
                        "memory_kb": memory_kb
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "stage": stage_name,
                        "message": "No output from Flang O3 stage"
                    })
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "stage": stage_name,
                    "message": str(e)
                })
                
        # After processing all stages, generate dynamic mapping tables
        from flang_tracer.correlator.mapping_engine import MappingEngine
        source_text = source_lines
        hlfir_text = stageData.get('hlfir', {}).get('fragment', '')
        fir_text = stageData.get('fir', {}).get('fragment', '')
        llvm_ir_text = stageData.get('llvm_ir', {}).get('fragment', '')
        mapping_engine = MappingEngine(source_text, hlfir_text, fir_text, llvm_ir_text, start_line=line)
        tables = mapping_engine.generate_tables()
        await websocket.send_json({
            "type": "mapping",
            "cross_stage_mapping": tables["cross_stage_mapping"],
            "static_comparison_reference": tables["static_comparison_reference"]
        })
        
        await websocket.send_json({"type": "complete"})
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
