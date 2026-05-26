import html
import json
import re
from typing import Dict, Any, List

class DashboardRenderer:
    def render(self, trace_data: Dict[str, Any]) -> str:
        # 1. Identify Key Variables
        source_text = trace_data.get('raw_source', trace_data['construct'])
        vars_found = list(set(re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]*\b', source_text)))
        keywords = {'program', 'integer', 'real', 'implicit', 'none', 'do', 'end', 'forall', 'where', 'print', 'parameter', 'float', 'sqrt', 'associate', 'critical'}
        variables = [v for v in vars_found if v.lower() not in keywords and len(v) > 0]
        
        # 2. Build a Map of Variable -> Color Class
        var_color_map = {v: f"var-color-{i % 5}" for i, v in enumerate(variables)}

        def apply_smart_highlighting(text: str, stage: str) -> str:
            escaped = html.escape(text)
            
            # Map to store temporary SSA register associations for this fragment
            # e.g., {"%7": "var-color-0"}
            ssa_map = {}
            
            # First Pass: Discover SSA associations in MLIR (HLFIR/FIR)
            if stage in ["hlfir", "fir"]:
                # Look for: %7 = ... {uniq_name = "_QFEsum"}
                for v, color in var_color_map.items():
                    # Matches: %7 = hlfir.declare ... uniq_name = "...sum"
                    match = re.search(rf'(%[0-9a-zA-Z_]+)\s*=.*uniq_name\s*=\s*".*{v}"', escaped, re.IGNORECASE)
                    if match:
                        ssa_map[match.group(1)] = color

            # Second Pass: Discover SSA associations in LLVM IR
            if stage == "llvm_ir":
                # Look for: %3 = alloca ... !dbg !23 (where !23 maps to the line)
                # For simplicity, we'll look for identifiers in comments or metadata if present
                pass

            # Final Pass: Apply Highlighting
            # 1. Highlight original variable names (even if part of a longer ID like %_QFEsum)
            for v, color in var_color_map.items():
                escaped = re.sub(rf'([%@_]?[a-zA-Z0-9_]*{v}[a-zA-Z0-9_]*)', rf'<span class="var-tag {color}">\1</span>', escaped, flags=re.IGNORECASE)
            
            # 2. Highlight discovered SSA registers
            for reg, color in ssa_map.items():
                # Avoid re-highlighting if already tagged
                escaped = re.sub(rf'(?<!>)\b({re.escape(reg)})\b', rf'<span class="var-tag {color}">\1</span>', escaped)
                
            return escaped

        # Metrics calculation
        total_ops = 0
        total_time = 0.0
        stage_metrics = {}
        for stage, fragments in trace_data["stages"].items():
            s_ops = sum(f["metrics"]["op_count"] for f in fragments)
            s_time = sum(f["metrics"]["duration_ms"] for f in fragments)
            total_ops += s_ops
            total_time += s_time
            s_mem = sum(len(f["raw_text"]) for f in fragments) / 1024.0
            stage_metrics[stage] = {"ops": s_ops, "time": s_time, "mem": round(s_mem, 2)}
        
        num_source_lines = max(1, (trace_data["source_range"]["end_line"] - trace_data["source_range"]["start_line"] + 1))
        expansion_factor = round(total_ops / num_source_lines, 1)

        # Build columns
        source_col = f"<div class='source-snippet'><pre><code>{apply_smart_highlighting(source_text, 'source')}</code></pre></div>"
        
        def get_col(stage_name: str) -> str:
            frags = trace_data["stages"].get(stage_name, [])
            if not frags: return "<div class='empty-cell'>No Mapping</div>"
            return "".join(f"<pre><code>{apply_smart_highlighting(f['raw_text'], stage_name)}</code></pre>" for f in frags)

        hlfir_col = get_col("hlfir")
        fir_col = get_col("fir")
        llvm_col = get_col("llvm_ir")
        
        has_o3 = "llvm_ir_o3" in trace_data["stages"]
        llvm_o3_col = get_col("llvm_ir_o3") if has_o3 else ""
        grid_cols = "300px 1fr 1fr 1fr 1fr" if has_o3 else "300px 1fr 1fr 1fr"
        o3_header = '<div class="th">LLVM IR (O3)</div>' if has_o3 else ""
        o3_cell = f'<div class="td"><div class="scroll-container">{llvm_o3_col}</div></div>' if has_o3 else ""

        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Semantic Evolution Map</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #030712; --panel: #111827; --border: #1f2937; --accent: #60a5fa; --text: #f3f4f6; --text-dim: #9ca3af;
            --v0: #60a5fa; --v1: #34d399; --v2: #f472b6; --v3: #fbbf24; --v4: #a78bfa;
        }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}
        header {{ padding: 1rem 2rem; background: rgba(17, 24, 39, 0.8); backdrop-filter: blur(8px); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }}
        .metrics-grid {{ display: flex; gap: 2rem; }}
        .metric-card {{ display: flex; flex-direction: column; }}
        .m-label {{ font-size: 0.6rem; text-transform: uppercase; color: var(--text-dim); font-weight: 700; letter-spacing: 0.05em; }}
        .m-value {{ font-size: 1.1rem; font-weight: 800; color: var(--accent); }}
        .evolution-table {{ flex: 1; display: grid; grid-template-columns: {grid_cols}; grid-template-rows: 40px 1fr; padding: 1rem; gap: 1px; background: var(--border); overflow: hidden; }}
        .th {{ background: #1f2937; padding: 0.5rem 1rem; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: var(--accent); display: flex; align-items: center; }}
        .td {{ background: var(--panel); padding: 0; overflow: hidden; display: flex; flex-direction: column; }}
        .scroll-container {{ flex: 1; overflow: auto; padding: 1rem; }}
        .source-snippet {{ font-family: 'JetBrains Mono', monospace; background: #000; border-radius: 4px; border-left: 4px solid var(--accent); }}
        pre {{ margin: 0 0 1.5rem 0; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; line-height: 1.5; white-space: pre; }}
        .var-tag {{ font-weight: 700; padding: 0 2px; border-radius: 2px; }}
        .var-color-0 {{ color: var(--v0); background: rgba(96, 165, 250, 0.2); }}
        .var-color-1 {{ color: var(--v1); background: rgba(52, 211, 153, 0.2); }}
        .var-color-2 {{ color: var(--v2); background: rgba(244, 114, 182, 0.2); }}
        .var-color-3 {{ color: var(--v3); background: rgba(251, 191, 36, 0.2); }}
        .var-color-4 {{ color: var(--v4); background: rgba(167, 139, 250, 0.2); }}
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-thumb {{ background: #374151; border-radius: 4px; }}
    </style>
</head>
<body>
    <header>
        <div class="info"><h2 style="margin:0; font-size: 1.2rem;">Semantic Lowering Map</h2><div style="font-size: 0.7rem; color: var(--text-dim);">{trace_data['construct']}</div></div>
        <div class="metrics-grid">
            <div class="metric-card"><span class="m-label">Aggregate Time</span><span class="m-value">{round(total_time, 2)}ms</span></div>
            <div class="metric-card"><span class="m-label">IR Volume</span><span class="m-value">{max(m['mem'] for m in stage_metrics.values())} KB</span></div>
            <div class="metric-card"><span class="m-label">Expansion Rate</span><span class="m-value">{expansion_factor}x</span></div>
        </div>
    </header>
    <div class="evolution-table">
        <div class="th">Source Snippet</div><div class="th">HLFIR Evolution</div><div class="th">FIR Translation</div><div class="th">LLVM IR Generation</div>{o3_header}
        <div class="td"><div class="scroll-container">{source_col}</div></div>
        <div class="td"><div class="scroll-container">{hlfir_col}</div></div>
        <div class="td"><div class="scroll-container">{fir_col}</div></div>
        <div class="td"><div class="scroll-container">{llvm_col}</div></div>{o3_cell}
    </div>
</body>
</html>
        """
        return html_template
