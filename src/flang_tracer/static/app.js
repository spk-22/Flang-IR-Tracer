let ws = null;
let metricsChart = null;
let stageData = {};

let parseTreeRoot = null;
let parseTreeZoom = null;
let parseTreeSvg = null;
let tokenIdCounter = 1;

document.addEventListener('DOMContentLoaded', () => {
    initChart();
    fetchExamples();
    initTabs();
    
    document.getElementById('run-btn').addEventListener('click', startTrace);
    document.getElementById('export-json').addEventListener('click', exportJSON);
    document.getElementById('export-html').addEventListener('click', exportHTML);
    
    // AST Search Input
    document.getElementById('parse-tree-search').addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        if (parseTreeRoot) {
            parseTreeRoot.descendants().forEach(d => {
                d.matched = query && d.data.name.toLowerCase().includes(query);
                if (d.matched) {
                    let p = d.parent;
                    while (p) {
                        if (p._children) {
                            p.children = p._children;
                            p._children = null;
                        }
                        p = p.parent;
                    }
                }
            });
            renderParseTreeGraph();
        }
    });
    
    // Setup parse tree action buttons
    document.getElementById('btn-parse-tree-zoom-fit').addEventListener('click', () => {
        if (parseTreeRoot && parseTreeZoom) {
            const svg = d3.select('#parse-tree-container svg');
            const container = document.getElementById('parse-tree-container');
            const height = container.clientHeight || 600;
            svg.transition().duration(500).call(
                parseTreeZoom.transform, 
                d3.zoomIdentity.translate(80, height / 2 - 50).scale(0.8)
            );
        }
    });

    document.getElementById('btn-parse-tree-expand').addEventListener('click', () => {
        if (parseTreeRoot) {
            function expand(d) {
                if (d._children) {
                    d.children = d._children;
                    d._children = null;
                }
                if (d.children) {
                    d.children.forEach(expand);
                }
            }
            expand(parseTreeRoot);
            renderParseTreeGraph();
        }
    });

    document.getElementById('btn-parse-tree-collapse').addEventListener('click', () => {
        if (parseTreeRoot) {
            function collapse(d) {
                if (d.children) {
                    d._children = d.children;
                    d.children = null;
                }
                if (d._children) {
                    d._children.forEach(collapse);
                }
            }
            parseTreeRoot.children.forEach(collapse);
            renderParseTreeGraph();
        }
    });
});

/* ── Tab Switching ── */
function initTabs() {
    const buttons = document.querySelectorAll('.tab-btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            
            // Hide all tab panels
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
            // Show active
            document.getElementById(tabId).classList.remove('hidden');
            
            // Toggle active class on buttons
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Handle specialized rendering for active tabs
            if (tabId === 'tab-performance') {
                renderLoweringGraph();
                if (metricsChart) {
                    metricsChart.resize();
                }
            } else if (tabId === 'tab-comparison') {
                renderDynamicMappingTable();
            } else if (tabId === 'tab-parsetree') {
                renderParseTreeGraph();
            }
        });
    });
}

/* ── Export ── */
function exportJSON() {
    const blob = new Blob([JSON.stringify(stageData, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'flang_trace_results.json';
    a.click();
    URL.revokeObjectURL(url);
}

function exportHTML() {
    const mappingTable = document.getElementById('ir-mapping-table').innerHTML || '<p>No data</p>';
    const refTable = document.getElementById('ir-static-reference-table').innerHTML || '<p>No data</p>';
    
    let html = `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Flang Trace Export</title>
<style>
body { background: #0b0f19; color: #f8fafc; font-family: 'Inter', sans-serif; padding: 2rem; }
h2, h3 { color: #60a5fa; }
pre { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; padding: 1rem; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; overflow-x: auto; }
.ir-mapping { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 0.5rem; margin-bottom: 2rem; }
.ir-mapping th, .ir-mapping td { border: 1px solid rgba(255,255,255,0.1); padding: 0.6rem 0.8rem; text-align: left; color: #f8fafc; }
.ir-mapping th { background: rgba(255,255,255,0.05); color: #94a3b8; font-weight: 600; }
.ir-mapping tbody tr:hover { background: rgba(59,130,246,0.1); }
</style>
</head>
<body>
<h2>Flang Multi-Stage Trace Export</h2>
<h3>Cross-Stage Mapping Table</h3>
${mappingTable}
<h3>Static IR Comparison Reference Table</h3>
${refTable}
</body>
</html>`;

    const blob = new Blob([html], {type: 'text/html'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'flang_trace_export.html';
    a.click();
    URL.revokeObjectURL(url);
}

/* ── Performance Chart ── */
function initChart() {
    const ctx = document.getElementById('metrics-chart').getContext('2d');
    metricsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Time (ms)',
                    data: [],
                    backgroundColor: 'rgba(59, 130, 246, 0.5)',
                    borderColor: 'rgba(59, 130, 246, 1)',
                    borderWidth: 1
                },
                {
                    label: 'IR Ops',
                    data: [],
                    backgroundColor: 'rgba(167, 139, 250, 0.5)',
                    borderColor: 'rgba(167, 139, 250, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Memory (KB)',
                    data: [],
                    backgroundColor: 'rgba(255, 99, 132, 0.5)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            },
            plugins: {
                legend: { labels: { color: '#f8fafc' } }
            }
        }
    });
}

function updateMetricsChart() {
    if (!metricsChart) return;
    
    const stages = ['parse_tree', 'semantic', 'hlfir', 'fir', 'llvm_ir'];
    const labels = [];
    const times = [];
    const ops = [];
    const memories = [];
    
    stages.forEach(stage => {
        if (stageData[stage]) {
            labels.push(stage.toUpperCase());
            times.push(stageData[stage].duration_ms || 0);
            ops.push(stageData[stage].op_count || 0);
            memories.push(stageData[stage].memory_kb || 0);
        }
    });
    
    metricsChart.data.labels = labels;
    metricsChart.data.datasets[0].data = times;
    metricsChart.data.datasets[1].data = ops;
    metricsChart.data.datasets[2].data = memories;
    metricsChart.update();
}

/* ── Available Examples ── */
async function fetchExamples() {
    try {
        const res = await fetch('/api/examples');
        const data = await res.json();
        const select = document.getElementById('example-select');
        select.innerHTML = '';
        data.examples.forEach(ex => {
            const opt = document.createElement('option');
            opt.value = ex;
            opt.textContent = ex;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error("Failed to load examples", e);
    }
}

/* ── Reset UI State ── */
function resetUI() {
    ['parse_tree', 'semantic', 'hlfir', 'fir', 'llvm_ir', 'llvm_ir_o3'].forEach(stage => {
        const codeEl = document.getElementById(`code-${stage}`);
        if (codeEl) codeEl.innerHTML = '';
        const badge = document.getElementById(`badge-${stage}`);
        if (badge) {
            badge.textContent = 'Pending';
            badge.className = 'status-badge';
        }
    });
    const srcEl = document.getElementById('code-source');
    if (srcEl) srcEl.innerHTML = '';
    
    stageData = {};
    tokenIdCounter = 1;
    parseTreeRoot = null;
    
    metricsChart.data.labels = [];
    metricsChart.data.datasets[0].data = [];
    metricsChart.data.datasets[1].data = [];
    metricsChart.data.datasets[2].data = [];
    metricsChart.update();
    
    const mappingContainer = document.getElementById('ir-mapping-table');
    if (mappingContainer) mappingContainer.innerHTML = '';
    
    const staticContainer = document.getElementById('ir-static-reference-table');
    if (staticContainer) {
        staticContainer.innerHTML = '<p style="color: #64748b; padding: 1rem; text-align: center;">No reference data available yet. Please click Trace.</p>';
    }
    
    const parseTreeContainer = document.getElementById('parse-tree-container');
    if (parseTreeContainer) {
        parseTreeContainer.innerHTML = '<p style="color: #64748b; padding: 2rem; text-align: center;">No Parse Tree data available yet. Please click Trace.</p>';
    }
    
    const searchInput = document.getElementById('parse-tree-search');
    if (searchInput) searchInput.value = '';
}

/* ── Start Tracer WebSocket ── */
function startTrace() {
    if (ws) {
        ws.close();
    }
    
    resetUI();
    
    const file = document.getElementById('example-select').value;
    const lineRange = document.getElementById('line-input').value.split('-');
    const line = parseInt(lineRange[0]);
    const endLine = lineRange.length > 1 ? parseInt(lineRange[1]) : line;
    const optLevel = document.getElementById('opt-select').value;
    const diffOpt = document.getElementById('diff-opt').checked;
    const flangPath = document.getElementById('flang-input').value;
    
    if (diffOpt) {
        document.getElementById('col-llvm_ir_o3').classList.remove('hidden');
    } else {
        document.getElementById('col-llvm_ir_o3').classList.add('hidden');
    }

    const wsUrl = `ws://${window.location.host}/ws/trace`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        ws.send(JSON.stringify({
            file, line, end_line: endLine, opt_level: optLevel, diff_opt: diffOpt, flang: flangPath
        }));
    };
    
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'init') {
            document.getElementById('code-source').textContent = msg.source;
            applyHighlighting();
        } 
        else if (msg.type === 'progress') {
            const badge = document.getElementById(`badge-${msg.stage}`);
            if (badge) {
                badge.textContent = 'Running';
                badge.className = 'status-badge running';
            }
        }
        else if (msg.type === 'result') {
            stageData[msg.stage] = msg;
            
            // Update code view
            const codeEl = document.getElementById(`code-${msg.stage}`);
            if (codeEl) {
                codeEl.textContent = msg.fragment;
            }
            
            // Update badge
            const badge = document.getElementById(`badge-${msg.stage}`);
            if (badge) {
                badge.textContent = `${msg.duration_ms}ms`;
                badge.className = 'status-badge done';
            }
            
            // Update Performance/Lowering graphics
            renderLoweringGraph();
            updateMetricsChart();
            
            // Render Parse Tree immediately if we are currently on the parse tree tab
            if (msg.stage === 'parse_tree') {
                const parseTreeTab = document.getElementById('tab-parsetree');
                if (parseTreeTab && !parseTreeTab.classList.contains('hidden')) {
                    renderParseTreeGraph();
                }
            }
            
            applyHighlighting();
        }
        else if (msg.type === 'mapping') {
            stageData.mapping = msg;
            
            // Auto-render if currently on Comparison Tab
            const comparisonTab = document.getElementById('tab-comparison');
            if (comparisonTab && !comparisonTab.classList.contains('hidden')) {
                renderDynamicMappingTable();
            }
        }
        else if (msg.type === 'error') {
            console.error("Stage error:", msg);
            if (msg.stage) {
                const badge = document.getElementById(`badge-${msg.stage}`);
                if (badge) {
                    badge.textContent = 'Error';
                    badge.className = 'status-badge error';
                }
                const codeEl = document.getElementById(`code-${msg.stage}`);
                if (codeEl) {
                    codeEl.textContent = `⚠ ${msg.message}`;
                }
            } else {
                alert(`Error: ${msg.message}`);
            }
        }
        else if (msg.type === 'complete') {
            console.log('Trace complete');
        }
    };
    
    ws.onerror = (err) => {
        console.error('WebSocket error', err);
    };
}

/* ── Dynamic Tables Rendering ── */
function renderDynamicMappingTable() {
    const mappingContainer = document.getElementById('ir-mapping-table');
    const staticContainer = document.getElementById('ir-static-reference-table');
    
    if (!mappingContainer || !staticContainer) return;
    
    if (!stageData.mapping) {
        mappingContainer.innerHTML = '<p style="color: #64748b; padding: 1.5rem; text-align: center;">No stage trace data available yet. Please run the trace.</p>';
        staticContainer.innerHTML = '<p style="color: #64748b; padding: 1.5rem; text-align: center;">No stage trace data available yet. Please run the trace.</p>';
        return;
    }
    
    const mapping = stageData.mapping.cross_stage_mapping || [];
    const staticRef = stageData.mapping.static_comparison_reference || [];
    
    // 1. Render Cross-Stage Mapping Table
    if (mapping.length === 0) {
        mappingContainer.innerHTML = '<p style="color: #64748b; padding: 1.5rem; text-align: center;">No constructs detected in this source code range.</p>';
    } else {
        let html = `<table class="ir-mapping">
            <thead>
                <tr>
                    <th>Construct Element</th>
                    <th>Source Code</th>
                    <th>HLFIR</th>
                    <th>FIR</th>
                    <th>LLVM IR</th>
                    <th>Transformation Explanation</th>
                </tr>
            </thead>
            <tbody>`;
            
        mapping.forEach(row => {
            const hlfirDisplay = row.hlfir !== "-" ? escapeHTML(row.hlfir) : "-";
            const firDisplay = row.fir !== "-" ? escapeHTML(row.fir) : "-";
            const llvmDisplay = row.llvm_ir !== "-" ? escapeHTML(row.llvm_ir) : "-";
            
            html += `<tr>
                <td style="white-space: nowrap; font-weight:600; color:#60a5fa;">${row.construct_element}</td>
                <td><code style="font-family:'JetBrains Mono',monospace; font-size:0.75rem;">${escapeHTML(row.source_code)}</code></td>
                <td><pre style="margin:0; font-family:'JetBrains Mono',monospace; font-size:0.75rem; white-space:pre-wrap; word-break:break-all; color:#93c5fd;">${hlfirDisplay}</pre></td>
                <td><pre style="margin:0; font-family:'JetBrains Mono',monospace; font-size:0.75rem; white-space:pre-wrap; word-break:break-all; color:#a78bfa;">${firDisplay}</pre></td>
                <td><pre style="margin:0; font-family:'JetBrains Mono',monospace; font-size:0.75rem; white-space:pre-wrap; word-break:break-all; color:#34d399;">${llvmDisplay}</pre></td>
                <td style="font-size:0.8rem; line-height:1.4; color:#cbd5e1; min-width: 250px;">${row.explanation}</td>
            </tr>`;
        });
        
        html += `</tbody></table>`;
        mappingContainer.innerHTML = html;
    }
    
    // 2. Render Static IR Comparison Reference Table (Dynamic!)
    if (staticRef.length === 0) {
        staticContainer.innerHTML = '<p style="color: #64748b; padding: 1.5rem; text-align: center;">No matching reference construct mappings found for this program.</p>';
    } else {
        let html = `<table class="ir-mapping">
            <thead>
                <tr>
                    <th>Fortran Construct</th>
                    <th>HLFIR</th>
                    <th>FIR</th>
                    <th>LLVM IR</th>
                </tr>
            </thead>
            <tbody>`;
            
        staticRef.forEach(row => {
            html += `<tr>
                <td style="font-weight:600; color:#60a5fa;">${row.fortran_construct}</td>
                <td><code>${escapeHTML(row.hlfir)}</code></td>
                <td><code>${escapeHTML(row.fir)}</code></td>
                <td><code>${escapeHTML(row.llvm_ir)}</code></td>
            </tr>`;
        });
        
        html += `</tbody></table>`;
        staticContainer.innerHTML = html;
    }
}

/* ── Interactive collapsible D3.js Parse Tree Graph with OOP Color Coding ── */
function renderParseTreeGraph() {
    const container = document.getElementById('parse-tree-container');
    if (!container) return;
    
    if (!stageData.parse_tree || !stageData.parse_tree.ast_json) {
        container.innerHTML = '<p style="color: #64748b; padding: 2rem; text-align: center;">No Parse Tree data available yet. Please click Trace.</p>';
        return;
    }
    
    container.innerHTML = '';
    
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;
    
    const data = stageData.parse_tree.ast_json;
    
    // Create hierarchy
    parseTreeRoot = d3.hierarchy(data);
    parseTreeRoot.x0 = height / 2;
    parseTreeRoot.y0 = 0;
    
    // Collapse children by default for deep levels to keep it readable initially!
    function collapseDeep(d) {
        if (d.depth >= 3 && d.children) {
            d._children = d.children;
            d.children = null;
        }
        if (d.children) {
            d.children.forEach(collapseDeep);
        }
        if (d._children) {
            d._children.forEach(collapseDeep);
        }
    }
    if (parseTreeRoot.children) {
        parseTreeRoot.children.forEach(collapseDeep);
    }
    
    // Initialize tooltip
    let tooltip = document.getElementById('parse-tree-tooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'parse-tree-tooltip';
        tooltip.style.position = 'absolute';
        tooltip.style.background = 'rgba(15, 23, 42, 0.95)';
        tooltip.style.color = '#f8fafc';
        tooltip.style.padding = '0.5rem 0.75rem';
        tooltip.style.borderRadius = '6px';
        tooltip.style.border = '1px solid rgba(255,255,255,0.1)';
        tooltip.style.fontSize = '0.75rem';
        tooltip.style.pointerEvents = 'none';
        tooltip.style.opacity = '0';
        tooltip.style.transition = 'opacity 0.2s';
        tooltip.style.zIndex = '100';
        tooltip.style.fontFamily = 'Inter, sans-serif';
        container.appendChild(tooltip);
    }
    
    const svg = d3.select('#parse-tree-container').append('svg')
        .attr('width', '100%')
        .attr('height', '100%')
        .style('cursor', 'grab');
        
    const g = svg.append('g');
    parseTreeSvg = g;
        
    parseTreeZoom = d3.zoom()
        .scaleExtent([0.05, 5])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });
        
    svg.call(parseTreeZoom);
    svg.call(parseTreeZoom.transform, d3.zoomIdentity.translate(80, height / 2 - 50).scale(0.8));
    
    const treeLayout = d3.tree().nodeSize([35, 220]);
    
    function update(source) {
        const nodes = parseTreeRoot.descendants();
        const links = parseTreeRoot.links();
        
        treeLayout(parseTreeRoot);
        
        nodes.forEach(d => { d.y = d.depth * 200; });
        
        // ── NODES ──
        const node = g.selectAll('g.node')
            .data(nodes, d => d.id || (d.id = ++tokenIdCounter));
            
        const nodeEnter = node.enter().append('g')
            .attr('class', 'node')
            .attr('transform', d => `translate(${source.y0},${source.x0})`)
            .on('click', (event, d) => {
                if (d.children) {
                    d._children = d.children;
                    d.children = null;
                } else {
                    d.children = d._children;
                    d._children = null;
                }
                update(d);
            })
            .style('cursor', 'pointer');
            
        nodeEnter.append('circle')
            .attr('r', d => d.matched ? 10 : 6)
            .style('fill', d => d.matched ? '#f59e0b' : (d._children ? getNodeColor(d.data.name) : '#1e293b'))
            .style('stroke', d => d.matched ? '#fbbf24' : getNodeColor(d.data.name))
            .style('stroke-width', d => d.matched ? '3px' : '2px')
            .style('filter', d => d.matched ? 'drop-shadow(0 0 8px rgba(245, 158, 11, 0.8))' : `drop-shadow(0 0 4px ${getNodeColor(d.data.name)}66)`);
            
        nodeEnter.append('text')
            .attr('dy', '.35em')
            .attr('x', d => d.children || d._children ? -12 : 12)
            .attr('text-anchor', d => d.children || d._children ? 'end' : 'start')
            .text(d => d.data.name)
            .style('fill', d => d.matched ? '#fbbf24' : '#cbd5e1')
            .style('font-family', "'JetBrains Mono', monospace")
            .style('font-size', '0.75rem')
            .style('text-shadow', '0 1px 3px rgba(0,0,0,0.8)');
            
        // Tooltip binds
        nodeEnter.on('mouseover', (event, d) => {
            tooltip.style.opacity = '1';
            tooltip.innerHTML = `<strong>Node:</strong> ${escapeHTML(d.data.name)}<br>
                                 <strong>Depth:</strong> ${d.depth}<br>
                                 <strong>Category:</strong> ${getNodeCategory(d.data.name)}`;
        })
        .on('mousemove', (event) => {
            const containerRect = container.getBoundingClientRect();
            tooltip.style.left = (event.clientX - containerRect.left + 15) + 'px';
            tooltip.style.top = (event.clientY - containerRect.top + 15) + 'px';
        })
        .on('mouseout', () => {
            tooltip.style.opacity = '0';
        });
            
        const nodeUpdate = node.merge(nodeEnter).transition()
            .duration(350)
            .attr('transform', d => `translate(${d.y},${d.x})`);
            
        nodeUpdate.select('circle')
            .attr('r', d => d.matched ? 10 : 6)
            .style('fill', d => d.matched ? '#f59e0b' : (d._children ? getNodeColor(d.data.name) : '#1e293b'))
            .style('stroke', d => d.matched ? '#fbbf24' : getNodeColor(d.data.name))
            .style('stroke-width', d => d.matched ? '3px' : '2px')
            .style('filter', d => d.matched ? 'drop-shadow(0 0 8px rgba(245, 158, 11, 0.8))' : `drop-shadow(0 0 4px ${getNodeColor(d.data.name)}66)`);
            
        nodeUpdate.select('text')
            .style('fill', d => d.matched ? '#fbbf24' : '#cbd5e1')
            .style('font-weight', d => d.matched ? 'bold' : 'normal');
            
        const nodeExit = node.exit().transition()
            .duration(350)
            .attr('transform', d => `translate(${source.y},${source.x})`)
            .remove();
            
        nodeExit.select('circle')
            .attr('r', 1e-6);
            
        nodeExit.select('text')
            .style('fill-opacity', 1e-6);
            
        // ── LINKS ──
        const link = g.selectAll('path.link')
            .data(links, d => d.target.id);
            
        const linkEnter = link.enter().insert('path', 'g')
            .attr('class', 'link')
            .attr('d', d => {
                const o = { x: source.x0, y: source.y0 };
                return diagonal(o, o);
            })
            .style('fill', 'none')
            .style('stroke', 'rgba(148, 163, 184, 0.25)')
            .style('stroke-width', '1.5px');
            
        link.merge(linkEnter).transition()
            .duration(350)
            .attr('d', d => diagonal(d.source, d.target));
            
        link.exit().transition()
            .duration(350)
            .attr('d', d => {
                const o = { x: source.x, y: source.y };
                return diagonal(o, o);
            })
            .remove();
            
        nodes.forEach(d => {
            d.x0 = d.x;
            d.y0 = d.y;
        });
    }
    
    function diagonal(s, d) {
        return `M ${s.y} ${s.x}
                C ${(s.y + d.y) / 2} ${s.x},
                  ${(s.y + d.y) / 2} ${d.x},
                  ${d.y} ${d.x}`;
    }
    
    update(parseTreeRoot);
}

/* ── Dynamic AST Node Category Helpers for OOP Fortran Demos ── */
function getNodeColor(name) {
    const text = name.toLowerCase();
    if (text.includes('abstract') || text.includes('deferred') || text.includes('shape')) return '#c084fc'; // Purple
    if (text.includes('extends') || text.includes('extends(') || text.includes('inheritance') || text.includes('square')) return '#4ade80'; // Green
    if (text.includes('procedure') || text.includes('=>') || text.includes('tbp')) return '#60a5fa'; // Blue
    if (text.includes('dispatch') || text.includes('select type') || text.includes('class(') || text.includes('area')) return '#f87171'; // Red
    return '#3b82f6'; // Default Accent Blue
}

function getNodeCategory(name) {
    const text = name.toLowerCase();
    if (text.includes('abstract') || text.includes('deferred') || text.includes('shape')) return '<span style="color:#c084fc;font-weight:bold;">Abstract Type / Interface</span>';
    if (text.includes('extends') || text.includes('extends(') || text.includes('inheritance') || text.includes('square')) return '<span style="color:#4ade80;font-weight:bold;">Inheritance / Extends</span>';
    if (text.includes('procedure') || text.includes('=>') || text.includes('tbp')) return '<span style="color:#60a5fa;font-weight:bold;">Type-Bound Procedure (TBP)</span>';
    if (text.includes('dispatch') || text.includes('select type') || text.includes('class(') || text.includes('area')) return '<span style="color:#f87171;font-weight:bold;">Dynamic Dispatch / Polymorphic Op</span>';
    return '<span style="color:#94a3b8;">AST Structure Node</span>';
}

/* ── Highlight Variables/Mangled Matching ── */
function applyHighlighting() {
    const sourceText = document.getElementById('code-source').textContent;
    if (!sourceText) return;
    
    // Find variables in source
    const varsFound = sourceText.match(/\b[a-zA-Z][a-zA-Z0-9_]*\b/g) || [];
    const keywords = ['program', 'integer', 'real', 'implicit', 'none', 'do', 'end', 'forall', 'where', 'print', 'parameter', 'float', 'sqrt', 'associate', 'critical', 'module', 'subroutine', 'function', 'call', 'use', 'type', 'class', 'contains', 'allocate', 'deallocate', 'if', 'then', 'else', 'select', 'case'];
    const variables = [...new Set(varsFound)].filter(v => !keywords.includes(v.toLowerCase()));
    
    const varColorMap = {};
    variables.forEach((v, i) => { varColorMap[v] = `var-color-${i % 5}`; });
    
    // Highlight all visible code blocks
    ['source', 'parse_tree', 'semantic', 'hlfir', 'fir', 'llvm_ir', 'llvm_ir_o3'].forEach(stage => {
        const el = document.getElementById(`code-${stage}`);
        if (!el || !el.textContent || el.textContent.startsWith('⚠')) return;
        
        let html = el.textContent.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        variables.forEach(v => {
            const regex = new RegExp(`\\b${v}\\b`, 'gi');
            html = html.replace(regex, `<span class="var-tag ${varColorMap[v]}">$&</span>`);
        });
        
        el.innerHTML = html;
    });
}

/* ── Lowering Graph Force Layout ── */
function renderLoweringGraph() {
    const container = document.getElementById('lowering-container');
    if (!container) return;
    container.innerHTML = '';
    
    const stages = ['source', 'parse_tree', 'semantic', 'hlfir', 'fir', 'llvm_ir'];
    const nodes = [];
    const links = [];
    
    nodes.push({ id: 'source', name: 'Fortran Source', group: 0, val: 1 });
    
    let prevId = 'source';
    let gIndex = 1;
    
    stages.forEach((stg) => {
        if (stg === 'source') return;
        if (stageData[stg]) {
            const ops = stageData[stg].op_count || 1;
            nodes.push({ id: stg, name: stg.toUpperCase() + ' (' + ops + ' ops)', group: gIndex, val: Math.max(5, ops) });
            links.push({ source: prevId, target: stg, value: ops });
            prevId = stg;
            gIndex++;
        }
    });
    
    if (nodes.length <= 1) return;
    
    const width = container.clientWidth || 400;
    const height = container.clientHeight || 250;
    
    const svg = d3.select('#lowering-container').append('svg')
        .attr('width', width)
        .attr('height', height);
        
    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('x', d3.forceX(d => (d.group * (width / (nodes.length + 1)))).strength(1))
        .force('y', d3.forceY(height / 2).strength(0.1));
        
    const link = svg.append('g')
        .attr('stroke', '#4b5563')
        .attr('stroke-opacity', 0.6)
        .selectAll('line')
        .data(links)
        .join('line')
        .attr('stroke-width', d => Math.min(10, Math.max(2, Math.sqrt(d.value))));
        
    const color = d3.scaleOrdinal(d3.schemeCategory10);
    
    const node = svg.append('g')
        .attr('stroke', '#fff')
        .attr('stroke-width', 1.5)
        .selectAll('circle')
        .data(nodes)
        .join('circle')
        .attr('r', d => Math.min(30, Math.max(10, Math.sqrt(d.val) * 3)))
        .attr('fill', d => color(d.group))
        .call(drag(simulation));
        
    node.append('title').text(d => d.name);
    
    const labels = svg.append('g')
        .selectAll('text')
        .data(nodes)
        .join('text')
        .attr('dy', -15)
        .attr('text-anchor', 'middle')
        .style('fill', '#f3f4f6')
        .style('font-size', '12px')
        .style('pointer-events', 'none')
        .text(d => d.name);

    simulation.on('tick', () => {
        link.attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
            
        node.attr('cx', d => d.x).attr('cy', d => d.y);
        labels.attr('x', d => d.x).attr('y', d => d.y - (Math.min(30, Math.max(10, Math.sqrt(d.val) * 3)) + 5));
    });
    
    function drag(simulation) {
        function dragstarted(event) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }
        function dragged(event) {
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }
        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }
        return d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended);
    }
}

/* ── HTML Escaper Helper ── */
function escapeHTML(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
