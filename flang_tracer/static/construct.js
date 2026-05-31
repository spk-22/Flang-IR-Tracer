// construct.js - UI logic for Flang Construct Trace
// Load examples list
async function loadExamples() {
  const resp = await fetch('/api/examples');
  const data = await resp.json();
  const select = document.getElementById('example-select');
  data.examples.forEach(ex => {
    const opt = document.createElement('option');
    opt.value = ex;
    opt.textContent = ex;
    select.appendChild(opt);
  });
}

// Helper to parse line range input
function parseLineRange(str) {
  const parts = str.split('-').map(s => parseInt(s.trim(), 10));
  if (parts.length === 1) return [parts[0], parts[0]];
  return [parts[0], parts[1] || parts[0]];
}

let ws = null;
let results = {};

function initTabs() {
  const tabs = document.getElementById('tabs');
  const contents = document.getElementById('tab-contents');
  const tabNames = ['Performance', 'IR Code', 'Comparison'];
  tabNames.forEach(name => {
    const btn = document.createElement('button');
    btn.className = 'tab-btn';
    btn.textContent = name;
    btn.dataset.tab = name.toLowerCase().replace(' ', '-');
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    tabs.appendChild(btn);
  });
  // create containers
  const perfDiv = document.createElement('div');
  perfDiv.id = 'performance';
  perfDiv.className = 'panel hidden';
  const irDiv = document.createElement('div');
  irDiv.id = 'ir-code';
  irDiv.className = 'panel hidden';
  const compDiv = document.createElement('div');
  compDiv.id = 'comparison';
  compDiv.className = 'panel hidden';
  contents.appendChild(perfDiv);
  contents.appendChild(irDiv);
  contents.appendChild(compDiv);
  // default tab
  switchTab('performance');
}

function switchTab(tabId) {
  document.querySelectorAll('.panel').forEach(p => p.classList.add('hidden'));
  document.getElementById(tabId).classList.remove('hidden');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  const activeBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  if (activeBtn) activeBtn.classList.add('active');
}

function createPerformanceChart(data) {
  const ctx = document.getElementById('perf-canvas');
  if (!ctx) {
    const canvas = document.createElement('canvas');
    canvas.id = 'perf-canvas';
    document.getElementById('performance').appendChild(canvas);
  }
  const labels = data.map(d => d.stage);
  const durations = data.map(d => d.duration_ms);
  new Chart(document.getElementById('perf-canvas'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Duration (ms)', data: durations, backgroundColor: 'var(--accent)' }] },
    options: { responsive: true, plugins: { legend: { labels: { color: 'var(--text-primary)' } } }, scales: { y: { beginAtZero: true, ticks: { color: 'var(--text-primary)' } }, x: { ticks: { color: 'var(--text-primary)' } } }
  });
}

function renderIrCode() {
  const container = document.getElementById('ir-code');
  container.innerHTML = '';
  Object.entries(results).forEach(([stage, payload]) => {
    const div = document.createElement('div');
    div.className = 'stage-col';
    const header = document.createElement('h3');
    header.textContent = stage;
    div.appendChild(header);
    const pre = document.createElement('pre');
    pre.textContent = payload.fragment || '';
    div.appendChild(pre);
    container.appendChild(div);
  });
}

function renderComparison() {
  const container = document.getElementById('comparison');
  container.innerHTML = '';
  // Build table mapping source ops to stage ops (simplified)
  const table = document.createElement('table');
  table.className = 'ir-mapping';
  const thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>Stage</th><th>Ops</th><th>Score</th></tr>';
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  Object.entries(results).forEach(([stage, payload]) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${stage}</td><td>${payload.op_count || 0}</td><td>${(payload.score*100).toFixed(1)}%</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.appendChild(table);
}

function exportJSON() {
  const blob = new Blob([JSON.stringify(results, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'trace_results.json';
  a.click();
  URL.revokeObjectURL(url);
}

function exportHTML() {
  // Capture the current comparison table HTML
  const comparisonDiv = document.getElementById('comparison').innerHTML;
  const htmlContent = `<!DOCTYPE html>
<html>
<head>
<meta charset='UTF-8'>
<title>Flang Trace Export</title>
<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css'/>
<style>
  body { background: #0b0f19; color: #f8fafc; font-family: 'Inter', sans-serif; }
  .ir-mapping { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  .ir-mapping th, .ir-mapping td { border: 1px solid rgba(255,255,255,0.1); padding: 0.4rem 0.6rem; }
  .ir-mapping th { background: rgba(255,255,255,0.05); color: #94a3b8; }
</style>
</head>
<body>
<h2>Flang Trace Results</h2>
<div>${comparisonDiv}</div>
</body>
</html>`;
  const blob = new Blob([htmlContent], {type: 'text/html'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'flang_trace_export.html';
  a.click();
  URL.revokeObjectURL(url);
}

document.getElementById('trace-btn').addEventListener('click', async () => {
  const file = document.getElementById('example-select').value;
  const lineRange = parseLineRange(document.getElementById('line-input').value);
  const opt = document.getElementById('opt-select').value;
  if (!file) { alert('Select an example'); return; }
  ws = new WebSocket(`ws://${location.host}/ws/trace`);
  ws.onopen = () => {
    ws.send(JSON.stringify({file, line: lineRange[0], end_line: lineRange[1], opt_level: opt}));
  };
  ws.onmessage = (msg) => {
    const data = JSON.parse(msg.data);
    if (data.type === 'init') { results = {}; }
    else if (data.type === 'result') {
      results[data.stage] = data;
    } else if (data.type === 'error') {
      console.error('Stage error', data);
    } else if (data.type === 'complete') {
      ws.close();
      // Render UI components
      renderIrCode();
      renderComparison();
      // performance chart data
      const perfData = Object.values(results).map(r => ({stage: r.stage, duration_ms: r.duration_ms}));
      createPerformanceChart(perfData);
    }
  };
});

document.getElementById('export-json').addEventListener('click', exportJSON);
document.getElementById('export-html').addEventListener('click', exportHTML);

// Initialise
loadExamples();
initTabs();
