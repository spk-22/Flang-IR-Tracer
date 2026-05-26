import html
from typing import Dict, Any

class HTMLRenderer:
    def render(self, trace_data: Dict[str, Any]) -> str:
        stages_html = ""
        for stage, fragments in trace_data["stages"].items():
            frag_html = ""
            if not fragments:
                frag_html = "<p class='no-data'>No matching fragments found.</p>"
            else:
                for frag in fragments:
                    confidence_class = "high" if frag["confidence"] >= 0.8 else "low"
                    frag_html += f"""
                    <div class="fragment">
                        <div class="meta">Confidence: <span class="{confidence_class}">{frag["confidence"]}</span></div>
                        <pre><code>{html.escape(frag["raw_text"])}</code></pre>
                    </div>
                    """
            
            stages_html += f"""
            <div class="stage-container">
                <h2>{stage.upper()}</h2>
                {frag_html}
            </div>
            """

        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flang Trace: {trace_data['construct']}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-color: #f8fafc;
            --accent-color: #38bdf8;
            --border-color: #334155;
            --success-color: #4ade80;
            --warning-color: #fbbf24;
        }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 2rem;
            line-height: 1.5;
        }}
        .header {{
            border-bottom: 2px solid var(--accent-color);
            margin-bottom: 2rem;
            padding-bottom: 1rem;
        }}
        h1 {{ color: var(--accent-color); margin: 0; }}
        .source-info {{ font-size: 0.9rem; color: #94a3b8; margin-top: 0.5rem; }}
        .stage-container {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            margin-bottom: 1.5rem;
            padding: 1.5rem;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        }}
        h2 {{ 
            margin-top: 0; 
            font-size: 1.25rem; 
            border-left: 4px solid var(--accent-color);
            padding-left: 0.75rem;
            color: #e2e8f0;
        }}
        pre {{
            background: #000;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            border: 1px solid #334155;
        }}
        code {{ font-family: 'Fira Code', monospace; font-size: 0.9rem; }}
        .fragment {{ margin-bottom: 1rem; }}
        .meta {{ font-size: 0.8rem; margin-bottom: 0.5rem; color: #94a3b8; }}
        .high {{ color: var(--success-color); font-weight: bold; }}
        .low {{ color: var(--warning-color); font-weight: bold; }}
        .no-data {{ color: #64748b; font-style: italic; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Flang Trace: {trace_data['construct']}</h1>
        <div class="source-info">File: {trace_data['source_range']['file']} | Line: {trace_data['source_range']['start_line']}</div>
    </div>
    {stages_html}
</body>
</html>
        """
        return html_template
