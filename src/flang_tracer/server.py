import os
import json
import asyncio
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
    # Return available examples
    # Search in ../demos and ../ (workspace root)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    examples = []
    
    # Check demos dir
    demos_dir = os.path.join(base_dir, "flang-tracer", "demos")
    if os.path.exists(demos_dir):
        for root, _, files in os.walk(demos_dir):
            for file in files:
                if file.endswith(".f90"):
                    examples.append(os.path.relpath(os.path.join(root, file), base_dir).replace('\\', '/'))
                    
    # Check root dir for sample.f90
    for file in os.listdir(base_dir):
        if file.endswith(".f90"):
             examples.append(file)
             
    return {"examples": examples}

def parse_ast_to_json(ast_text: str) -> dict:
    lines = ast_text.strip().split('\n')
    if not lines or not lines[0].strip():
        return {"name": "Empty", "children": []}
        
    root = {"name": "Parse Tree", "children": []}
    stack = [(-1, root)] # (depth, node)
    
    for line in lines:
        if not line.strip(): continue
        # Count leading '| ' or spaces
        depth = 0
        stripped = line.lstrip()
        diff = len(line) - len(stripped)
        
        # Approximate depth by counting '|' and spaces
        depth = line[:diff].count('|') + (line[:diff].count(' ') // 2)
        
        node = {"name": stripped, "children": []}
        
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
        opt_level = req.get("opt_level", "O0")
        diff_opt = req.get("diff_opt", False)
        line = req.get("line", 1)
        end_line = req.get("end_line", line)
        flang_path = req.get("flang", "flang-new")
        
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        abs_file_path = os.path.join(base_dir, file_path)
        
        if not os.path.exists(abs_file_path):
            await websocket.send_json({"type": "error", "message": f"File {file_path} not found"})
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
            lines = f.readlines()
            source_lines = "".join(lines[line-1:end_line])
        
        await websocket.send_json({
            "type": "init",
            "source": source_lines,
            "stages": [s[0] for s in stages]
        })
        
        matcher = FuzzyMatcher()
        
        for stage_name, flags, ExtractorClass in stages:
            await websocket.send_json({"type": "progress", "stage": stage_name, "status": "running"})
            
            content, duration, memory_kb = driver.run_stage(abs_file_path, flags)
            extractor = ExtractorClass(content)
            
            try:
                frag = extractor.extract_fragment(target_range)
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
                    payload["ast_json"] = parse_ast_to_json(frag.raw_text)
                    
                await websocket.send_json(payload)
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "stage": stage_name,
                    "message": str(e)
                })
                
            await asyncio.sleep(0.1) # Small delay for smooth UI update
            
        if diff_opt:
            stage_name = "llvm_ir_o3"
            await websocket.send_json({"type": "progress", "stage": stage_name, "status": "running"})
            driver_o3 = FlangDriver(flang_path, opt_level="O3")
            content, duration, memory_kb = driver_o3.run_stage(abs_file_path, ["-S", "-emit-llvm", "-g", "-O3", "-o", "-"])
            extractor = LLVMIRHook(content)
            try:
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
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "stage": stage_name,
                    "message": str(e)
                })
                
        await websocket.send_json({"type": "complete"})
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
