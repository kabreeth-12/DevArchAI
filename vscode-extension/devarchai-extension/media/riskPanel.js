(() => {
  const rawEl = document.getElementById('devarchai-data');
  const rawText = rawEl ? rawEl.textContent || '{}' : '{}';
  let data = {};
  let risks = [];

  try {
    data = JSON.parse(rawText);
    risks = Array.isArray(data.risk_analysis)
      ? data.risk_analysis
      : Object.values(data.risk_analysis || {});
    document.getElementById('debug-status').innerHTML = '<span class="metric">Debug: payload loaded</span>';
  } catch (err) {
    document.getElementById('debug-status').innerHTML = '<span class="metric">Debug error: ' + err + '</span>';
    return;
  }

  const container = document.getElementById('risk-container');
  risks.forEach(item => {
    const level = item.predicted_risk_level;
    const label = level === 2 ? 'HIGH' : level === 1 ? 'MEDIUM' : 'LOW';
    const cls = level === 2 ? 'high' : level === 1 ? 'medium' : 'low';
    const confidence = Math.round(item.risk_confidence * 100);
    const badgeClass = level === 2 ? 'risk-high' : level === 1 ? 'risk-medium' : 'risk-low';

    const card = document.createElement('div');
    card.className = `card ${cls}`;
    card.innerHTML = `
      <h3>${item.service}</h3>
      <div style="margin:6px 0 8px 0;">
        <span class="risk-badge ${badgeClass}">${label}</span>
      </div>
      <div class="meta">
        <span class="metric">Conf: ${confidence}%</span>
        ${item.model ? `<span class="metric">Model: ${item.model}</span>` : ''}
      </div>
      <p style="margin-top:8px;color:var(--muted);font-size:12px;font-style:italic;">${item.reason}</p>
    `;
    container.appendChild(card);
  });

  const rcaPanel = document.getElementById('rca-summary');
  if (data.rca_summary) {
    const rcaConfidence = Math.round((data.rca_confidence || 0) * 100);
    const refs = (data.rca_references || []).slice(0, 5);
    const refsHtml = refs.length ? `<ul>${refs.map(r => `<li>${r}</li>`).join('')}</ul>` : '<p>No references available.</p>';
    rcaPanel.innerHTML = `
      <p><b>Summary:</b> ${data.rca_summary}</p>
      <div class="meta">
        <span class="metric">Confidence: ${rcaConfidence}%</span>
        <span class="metric">LLM Used: ${data.rca_llm_used ? 'Yes' : 'No'}</span>
      </div>
      <div><b>References:</b> ${refsHtml}</div>
    `;
  } else {
    rcaPanel.innerHTML = '<p>No RCA data available.</p>';
  }

  const top = risks && risks.length ? risks[0] : null;
  document.getElementById('hero-service').textContent = top ? top.service : '—';
  document.getElementById('hero-risk').textContent = top ? `Risk: ${top.predicted_risk_level}` : 'Risk: —';
  document.getElementById('hero-confidence').textContent = top ? `Conf: ${Math.round(top.risk_confidence * 100)}%` : 'Conf: —';
  document.getElementById('hero-model').textContent = top && top.model ? `Model: ${top.model}` : 'Model: —';
  document.getElementById('hero-count').textContent = risks ? risks.length : 0;
  document.getElementById('hero-rca').textContent = data.rca_summary ? 'Ready' : 'Unavailable';

  const graphEl = document.getElementById('dependency-graph');
  const nodes = Array.isArray(data.dependency_graph?.nodes)
    ? data.dependency_graph.nodes
    : Object.values(data.dependency_graph?.nodes || {});
  const edges = Array.isArray(data.dependency_graph?.edges)
    ? data.dependency_graph.edges
    : Object.values(data.dependency_graph?.edges || {});

  if (!nodes.length) {
    graphEl.textContent = 'No dependency edges detected.';
  } else {
    const width = graphEl.clientWidth || 800;
    const height = graphEl.clientHeight || 520;
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(width, height) * 0.32;

    const positions = {};
    nodes.forEach((node, i) => {
      const angle = (i / nodes.length) * Math.PI * 2;
      positions[node] = {
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius
      };
    });

    const svgParts = [];
    svgParts.push(`<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">`);
    svgParts.push(`<defs>
      <linearGradient id="nodeGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#4de1ff"/>
        <stop offset="100%" stop-color="#7c5cff"/>
      </linearGradient>
    </defs>`);

    edges.forEach(edge => {
      const from = positions[edge.from_service];
      const to = positions[edge.to_service];
      if (!from || !to) return;
      svgParts.push(`<line x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" stroke="#64748b" stroke-width="2" opacity="0.8" />`);
    });

    nodes.forEach(node => {
      const pos = positions[node];
      svgParts.push(`<circle cx="${pos.x}" cy="${pos.y}" r="16" fill="url(#nodeGrad)" />`);
      svgParts.push(`<text x="${pos.x}" y="${pos.y - 24}" fill="#e9edf7" font-size="10" text-anchor="middle">${node}</text>`);
    });

    svgParts.push(`</svg>`);
    graphEl.innerHTML = svgParts.join('');
  }
})();
