let ws = null;
let metricsChart = null;
let stageData = {};
let tokenIdCounter = 1;
let tokenMap = {};

document.addEventListener('DOMContentLoaded', () => {
    initChart();
    fetchExamples();
    
    document.getElementById('run-btn').addEventListener('click', startTrace);
});

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

function resetUI() {
    ['hlfir', 'fir', 'llvm_ir', 'llvm_ir_o3'].forEach(stage => {
        document.getElementById(`code-${stage}`).innerHTML = '';
        const badge = document.getElementById(`badge-${stage}`);
        if (badge) {
            badge.textContent = 'Pending';
            badge.className = 'status-badge';
        }
    });
    const srcEl = document.getElementById('code-source');
    if (srcEl) srcEl.innerHTML = '';
    const treeContainer = document.getElementById('tree-container');
    if (treeContainer) treeContainer.innerHTML = '';
    const treeStatus = document.getElementById('tree-status');
    if (treeStatus) {
        treeStatus.textContent = 'Pending';
        treeStatus.className = 'status-badge pending';
    }
    
    metricsChart.data.labels = [];
    metricsChart.data.datasets[0].data = [];
    metricsChart.data.datasets[1].data = [];
    metricsChart.data.datasets[2].data = [];
    metricsChart.update();
    // Clear token map and reset counter
    Object.keys(tokenMap).forEach(k => delete tokenMap[k]);
    tokenIdCounter = 1;
}

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
            if (msg.stage === 'parse_tree') {
                document.getElementById('tree-status').textContent = 'Running';
                document.getElementById('tree-status').className = 'status-badge running';
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
            
            // Update token map for this stage
            updateTokenMap(msg.stage, msg.fragment);
            console.log('Token map updated', tokenMap);
            
            // Render Parse Tree if available
            if (msg.stage === 'parse_tree' && msg.ast_json) {
                renderTree(msg.ast_json);
                document.getElementById('tree-status').textContent = 'Done';
                document.getElementById('tree-status').className = 'status-badge done';
            }
            
            // Update Chart
            if (msg.stage !== 'parse_tree' && msg.stage !== 'semantic') {
                metricsChart.data.labels.push(msg.stage.toUpperCase());
                metricsChart.data.datasets[0].data.push(msg.duration_ms);
                metricsChart.data.datasets[1].data.push(msg.op_count);
                metricsChart.data.datasets[2].data.push(msg.memory_kb || 0);
                
                // Redraw lowering graph whenever we get IR stats
                renderLoweringGraph();
            }
            
            // Render the token mapping table
            renderTokenTable();
            
            applyHighlighting();
        }
        else if (msg.type === 'error') {
            console.error("Trace Error", msg);
            if (msg.stage) {
                const badge = document.getElementById(`badge-${msg.stage}`);
                if (badge) {
                    badge.textContent = 'Error';
                    badge.className = 'status-badge error';
                }
            } else {
                alert(`Error: ${msg.message}`);
            }
        }
    };
}



function updateTokenMap(stage, rawText) {
    const tokens = rawText.match(/\b[a-zA-Z][a-zA-Z0-9_]*\b/g) || [];
    tokens.forEach(tok => {
        if (!tokenMap[tok]) {
            tokenMap[tok] = { id: tokenIdCounter++, occurrences: {} };
        }
        tokenMap[tok].occurrences[stage] = (tokenMap[tok].occurrences[stage] || 0) + 1;
    });
}

function renderTokenTable() {
    const container = document.getElementById('ir-mapping-table');
    if (!container) return;
    const tokenCount = Object.keys(tokenMap).length;
    console.log('renderTokenTable called, token count:', tokenCount);
    if (tokenCount === 0) {
        container.innerHTML = '<p>No token data yet.</p>';
        return;
    }
    // Determine which stages have data
    const stages = Object.keys(stageData).sort();
    console.log('Stages for table:', stages);
    if (stages.length === 0) {
        container.innerHTML = '<p>No stage data available.</p>';
        return;
    }
    let html = '<table class="ir-mapping"><thead><tr><th>Token</th><th>ID</th>';
    stages.forEach(s => { html += `<th>${s}</th>`; });
    html += '</tr></thead><tbody>';
    Object.entries(tokenMap).forEach(([tok, info]) => {
        html += `<tr><td>${tok}</td><td>${info.id}</td>`;
        stages.forEach(s => {
            const cnt = info.occurrences[s] || 0;
            html += `<td>${cnt}</td>`;
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
    console.log('Rendered token table with', tokenCount, 'tokens');
}

// Extend existing message handling to update token map and render table

function applyHighlighting() {
    const sourceText = document.getElementById('code-source').textContent;
    if (!sourceText) return;
    
    // Find variables in source
    const varsFound = sourceText.match(/\b[a-zA-Z][a-zA-Z0-9_]*\b/g) || [];
    const keywords = ['program', 'integer', 'real', 'implicit', 'none', 'do', 'end', 'forall', 'where', 'print', 'parameter', 'float', 'sqrt', 'associate', 'critical'];
    const variables = [...new Set(varsFound)].filter(v => !keywords.includes(v.toLowerCase()));
    
    const varColorMap = {};
    variables.forEach((v, i) => { varColorMap[v] = `var-color-${i % 5}`; });
    
    // Highlight all visible code blocks
    ['source', 'hlfir', 'fir', 'llvm_ir', 'llvm_ir_o3'].forEach(stage => {
        const el = document.getElementById(`code-${stage}`);
        if (!el || !el.textContent) return;
        
        let html = el.textContent.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        variables.forEach(v => {
            // Highlight exact matches
            const regex = new RegExp(`\\b${v}\\b`, 'gi');
            html = html.replace(regex, `<span class="var-tag ${varColorMap[v]}">$&</span>`);
            // Also try to highlight mangled names (like _QFEsum)
            const mangled = new RegExp(`([%@_]?[a-zA-Z0-9_]*${v}[a-zA-Z0-9_]*)`, 'gi');
            html = html.replace(mangled, (match, p1) => {
                if (match.toLowerCase() === v.toLowerCase()) return match; // already handled
                return `<span class="var-tag ${varColorMap[v]}">${match}</span>`;
            });
        });
        
        el.innerHTML = html;
    });
}

function renderTree(treeData) {
    const container = document.getElementById('tree-container');
    container.innerHTML = ''; // clear
    
    const width = container.clientWidth || 400;
    const height = container.clientHeight || 300;
    
    const svg = d3.select('#tree-container').append('svg')
        .attr('width', '100%')
        .attr('height', '100%')
        .append('g')
        .attr('transform', 'translate(40, 20)');
        
    const root = d3.hierarchy(treeData);
    
    const treeLayout = d3.tree().size([height - 40, width - 160]);
    treeLayout(root);
    
    // Links
    svg.selectAll('.link')
        .data(root.links())
        .enter().append('path')
        .attr('class', 'link')
        .attr('d', d3.linkHorizontal()
            .x(d => d.y)
            .y(d => d.x)
        );
        
    // Nodes
    const node = svg.selectAll('.node')
        .data(root.descendants())
        .enter().append('g')
        .attr('class', d => 'node' + (d.children ? ' node--internal' : ' node--leaf'))
        .attr('transform', d => `translate(${d.y},${d.x})`);
        
    node.append('circle').attr('r', 4);
    
    node.append('text')
        .attr('dy', 3)
        .attr('x', d => d.children ? -8 : 8)
        .style('text-anchor', d => d.children ? 'end' : 'start')
        .text(d => d.data.name);
}

function renderLoweringGraph() {
    const container = document.getElementById('lowering-container');
    if (!container) return;
    container.innerHTML = '';
    
    // Build data array for nodes
    const stages = ['source', 'hlfir', 'fir', 'llvm_ir'];
    const nodes = [];
    const links = [];
    
    // Add Source Node
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
        
    // Simple force layout for a pipeline flow
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
