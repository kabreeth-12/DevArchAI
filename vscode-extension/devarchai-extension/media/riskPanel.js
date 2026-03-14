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
    const refsHtml = refs.length ? `<ul>${refs.map(r => {
      const base = r.split(/[\\/]/).pop();
      return `<li title="${r}">${base}</li>`;
    }).join('')}</ul>` : '<p>No references available.</p>';
    const summaryHtml = String(data.rca_summary).replace(/\n/g, '<br>');
    rcaPanel.innerHTML = `
      <p><b>Summary:</b></p>
      <div class="rca-text">${summaryHtml}</div>
      <div class="meta">
        <span class="metric">Confidence: ${rcaConfidence}%</span>
        <span class="metric">LLM Used: ${data.rca_llm_used ? 'Yes' : 'No'}</span>
      </div>
      <div><b>References:</b> ${refsHtml}</div>
    `;
  } else {
    rcaPanel.innerHTML = '<p>No RCA data available.</p>';
  }

  const telemetryPanel = document.getElementById('telemetry-panel');
  const telemetry = data.telemetry_debug || {};
  const telemetryKeys = Object.keys(telemetry);

  if (!telemetryKeys.length) {
    telemetryPanel.innerHTML = '<p>No telemetry data available.</p>';
  } else {
    const rows = telemetryKeys.map(service => {
      const t = telemetry[service] || {};
      const reqRate = t.req_rate !== undefined ? t.req_rate.toFixed(3) : 'n/a';
      const avgRt = t.avg_rt !== undefined ? t.avg_rt.toFixed(2) : 'n/a';
      const p95 = t.perc95_rt !== undefined ? t.perc95_rt.toFixed(2) : 'n/a';
      const spanCount = t.span_count !== undefined ? t.span_count : 'n/a';
      const traceErr = t.trace_error_rate !== undefined ? t.trace_error_rate.toFixed(3) : 'n/a';
      const p95Trace = t.p95_trace_ms !== undefined ? t.p95_trace_ms.toFixed(2) : 'n/a';

      return `
        <div class="card" style="margin-bottom:10px;">
          <div style="font-weight:600;">${service}</div>
          <div class="meta" style="margin-top:6px;">
            <span class="metric">req_rate: ${reqRate}</span>
            <span class="metric">avg_rt: ${avgRt}ms</span>
            <span class="metric">p95_rt: ${p95}ms</span>
            <span class="metric">span_count: ${spanCount}</span>
            <span class="metric">trace_err: ${traceErr}</span>
            <span class="metric">p95_trace: ${p95Trace}ms</span>
          </div>
        </div>
      `;
    }).join('');

    telemetryPanel.innerHTML = rows;
  }

  const cicdPanel = document.getElementById('cicd-optimization');
  const cicd = data.cicd_optimization;
  if (!cicd || !Array.isArray(cicd.suggestions) || !cicd.suggestions.length) {
    cicdPanel.innerHTML = '<p>No CI/CD optimization suggestions available.</p>';
  } else {
    const cards = cicd.suggestions.map(s => `
      <div class="card" style="margin-bottom:10px;">
        <div style="font-weight:600;">${s.title}</div>
        <div class="meta" style="margin-top:6px;">
          <span class="metric">Impact: ${s.impact}</span>
        </div>
        <p style="margin:6px 0 4px 0;color:var(--muted);font-size:12px;">${s.rationale}</p>
        <p style="margin:0;color:#cbd5f5;font-size:12px;"><b>Action:</b> ${s.action}</p>
      </div>
    `).join('');
    cicdPanel.innerHTML = cards;
  }

  const top = risks && risks.length ? risks[0] : null;
  document.getElementById('hero-service').textContent = top ? top.service : '--';
  document.getElementById('hero-risk').textContent = top ? `Risk: ${top.predicted_risk_level}` : 'Risk: --';
  document.getElementById('hero-confidence').textContent = top ? `Conf: ${Math.round(top.risk_confidence * 100)}%` : 'Conf: --';
  document.getElementById('hero-model').textContent = top && top.model ? `Model: ${top.model}` : 'Model: --';
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

    const riskMap = new Map();
    risks.forEach(r => {
      if (r && r.service) riskMap.set(r.service, r.predicted_risk_level);
    });

    const degree = new Map();
    nodes.forEach(n => degree.set(n, 0));
    edges.forEach(e => {
      degree.set(e.from_service, (degree.get(e.from_service) || 0) + 1);
      degree.set(e.to_service, (degree.get(e.to_service) || 0) + 1);
    });

    const nodeData = nodes.map((id, i) => ({
      id,
      x: width / 2 + Math.cos(i) * 20,
      y: height / 2 + Math.sin(i) * 20,
      vx: 0,
      vy: 0,
      risk: riskMap.has(id) ? riskMap.get(id) : -1,
      degree: degree.get(id) || 0
    }));

    const nodeIndex = new Map();
    nodeData.forEach((n, i) => nodeIndex.set(n.id, i));

    const edgeData = edges
      .map(e => ({
        source: nodeIndex.get(e.from_service),
        target: nodeIndex.get(e.to_service)
      }))
      .filter(e => e.source !== undefined && e.target !== undefined);

    const clamp = (val, min, max) => Math.max(min, Math.min(max, val));
    const iters = Math.min(680, Math.max(260, nodes.length * 12));
    const k = Math.sqrt((width * height) / (nodes.length + 1));
    const repulse = 1.1;
    const attract = 0.035;

    for (let iter = 0; iter < iters; iter++) {
      for (let i = 0; i < nodeData.length; i++) {
        for (let j = i + 1; j < nodeData.length; j++) {
          const a = nodeData[i];
          const b = nodeData[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
          const minDist = (12 + Math.min(10, a.degree)) + (12 + Math.min(10, b.degree)) + 14;
          const collision = dist < minDist ? (minDist - dist) * 1.4 : 0;
          const force = (k * k) / dist + collision * 6;
          const fx = (dx / dist) * force * repulse;
          const fy = (dy / dist) * force * repulse;
          a.vx += fx; a.vy += fy;
          b.vx -= fx; b.vy -= fy;
        }
      }

      edgeData.forEach(e => {
        const a = nodeData[e.source];
        const b = nodeData[e.target];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
        const force = (dist * dist) / k;
        const fx = (dx / dist) * force * attract;
        const fy = (dy / dist) * force * attract;
        a.vx += fx; a.vy += fy;
        b.vx -= fx; b.vy -= fy;
      });

      nodeData.forEach(n => {
        n.vx *= 0.5;
        n.vy *= 0.5;
        n.x = clamp(n.x + n.vx, 30, width - 30);
        n.y = clamp(n.y + n.vy, 30, height - 30);
      });
    }

    const riskColor = (risk) => {
      if (risk === 2) return '#ff6b6b';
      if (risk === 1) return '#ffb347';
      if (risk === 0) return '#3ddc97';
      return '#7c5cff';
    };

    const riskGlow = (risk) => {
      if (risk === 2) return 'rgba(255,107,107,0.45)';
      if (risk === 1) return 'rgba(255,179,71,0.45)';
      if (risk === 0) return 'rgba(61,220,151,0.45)';
      return 'rgba(124,92,255,0.45)';
    };

    const radiusFor = (n) => {
      const base = 12 + Math.min(10, n.degree);
      if (n.risk === 2) return base + 6;
      if (n.risk === 1) return base + 3;
      if (n.risk === 0) return base + 1;
      return base;
    };

    const svgParts = [];
    svgParts.push(`<svg id="dep-svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">`);
    svgParts.push(`<defs>
      <filter id="softGlow" x="-40%" y="-40%" width="180%" height="180%">
        <feGaussianBlur stdDeviation="6" result="coloredBlur"/>
        <feMerge>
          <feMergeNode in="coloredBlur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
      <pattern id="graphGrid" width="40" height="40" patternUnits="userSpaceOnUse">
        <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="1"/>
      </pattern>
      <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#556075"></path>
      </marker>
    </defs>`);

    svgParts.push(`<rect width="${width}" height="${height}" fill="url(#graphGrid)" opacity="0.6"/>`);
    svgParts.push(`<g id="dep-viewport">`);

    edgeData.forEach(e => {
      const a = nodeData[e.source];
      const b = nodeData[e.target];
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const bend = Math.max(20, Math.min(80, Math.sqrt(dx * dx + dy * dy) * 0.12));
      const cx = mx - dy * 0.15;
      const cy = my + dx * 0.15;
      svgParts.push(`<path d="M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}" stroke="#4b556a" stroke-width="1.4" opacity="0.55" fill="none" marker-end="url(#arrow)"/>`);
    });

    nodeData.forEach((n, idx) => {
      const r = radiusFor(n);
      const label = n.id.length > 26 ? n.id.slice(0, 23) + '...' : n.id;
      const labelWidth = Math.max(60, label.length * 6.2);
      const labelOffset = (idx % 3 === 0 ? -1 : 1) * (r + 16);
      const labelY = n.y + labelOffset;
      svgParts.push(`<g class="node" data-id="${n.id}">
        <circle cx="${n.x}" cy="${n.y}" r="${r + 8}" fill="${riskGlow(n.risk)}" opacity="0.25" filter="url(#softGlow)"></circle>
        <circle cx="${n.x}" cy="${n.y}" r="${r}" fill="${riskColor(n.risk)}" opacity="0.98"></circle>
        <circle cx="${n.x}" cy="${n.y}" r="${r + 3}" fill="none" stroke="rgba(255,255,255,0.12)"></circle>
        <rect x="${n.x - (labelWidth / 2)}" y="${labelY - 10}" rx="7" ry="7" width="${labelWidth}" height="16" fill="rgba(12,16,26,0.92)" stroke="rgba(255,255,255,0.12)"></rect>
        <text x="${n.x}" y="${labelY + 2}" fill="#e9edf7" font-size="10" text-anchor="middle">${label}</text>
      </g>`);
    });

    svgParts.push(`</g>`);
    svgParts.push(`</svg>`);
    graphEl.innerHTML = svgParts.join('');

    const svg = document.getElementById('dep-svg');
    const viewport = document.getElementById('dep-viewport');
    const tooltip = document.getElementById('graph-tooltip');
    let scale = 1;
    let panX = 0;
    let panY = 0;
    let isPanning = false;
    let startX = 0;
    let startY = 0;

    const updateTransform = () => {
      viewport.setAttribute('transform', `translate(${panX}, ${panY}) scale(${scale})`);
    };
    updateTransform();

    svg.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = Math.sign(e.deltaY) * -0.08;
      scale = Math.max(0.6, Math.min(2.2, scale + delta));
      updateTransform();
    });

    svg.addEventListener('mousedown', (e) => {
      isPanning = true;
      startX = e.clientX - panX;
      startY = e.clientY - panY;
    });

    svg.addEventListener('mousemove', (e) => {
      if (!isPanning) return;
      panX = e.clientX - startX;
      panY = e.clientY - startY;
      updateTransform();
    });

    svg.addEventListener('mouseup', () => { isPanning = false; });
    svg.addEventListener('mouseleave', () => { isPanning = false; });

    svg.addEventListener('mousemove', (e) => {
      if (!tooltip) return;
      const target = e.target.closest ? e.target.closest('.node') : null;
      if (!target) {
        tooltip.style.opacity = '0';
        return;
      }
      const id = target.getAttribute('data-id');
      if (!id) return;
      const risk = riskMap.has(id) ? riskMap.get(id) : -1;
      const riskLabel = risk === 2 ? 'High' : risk === 1 ? 'Medium' : risk === 0 ? 'Low' : 'Unknown';
      tooltip.innerHTML = `<div><b>${id}</b></div><div class="muted">Risk: ${riskLabel}</div><div class="muted">Degree: ${degree.get(id) || 0}</div>`;
      const rect = svg.getBoundingClientRect();
      tooltip.style.left = `${e.clientX - rect.left}px`;
      tooltip.style.top = `${e.clientY - rect.top}px`;
      tooltip.style.opacity = '1';
    });
  }
})();

