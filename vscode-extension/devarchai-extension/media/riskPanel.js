(() => {
  const rawEl = document.getElementById('devarchai-data');
  const rawText = rawEl ? rawEl.textContent || '{}' : '{}';
  let data = {};
  let risks = [];
  let debugStage = 'init';

  try {
    data = JSON.parse(rawText);
    debugStage = 'parsed';
    risks = Array.isArray(data.risk_analysis)
      ? data.risk_analysis
      : Object.values(data.risk_analysis || {});
    const statusEl = document.getElementById('debug-status');
    if (statusEl) {
      statusEl.innerHTML = '<span class="metric">Debug: payload loaded</span>';
    }
  } catch (err) {
    const statusEl = document.getElementById('debug-status');
    if (statusEl) {
      statusEl.innerHTML = `<span class="metric">Debug parse error: ${err}</span>`;
    }
    console.error('Risk panel parse error:', err);
    return;
  }

  const resolveRiskLevel = (item) => {
    const raw = item?.predicted_risk_level;
    const asNum = Number(raw);
    if (Number.isFinite(asNum)) return asNum;
    const asStr = String(raw || '').toLowerCase();
    if (asStr === 'high') return 2;
    if (asStr === 'medium') return 1;
    if (asStr === 'low') return 0;
    return -1;
  };

  const resolveConfidencePercent = (item) => {
    const raw = item?.risk_confidence ?? item?.confidence ?? item?.risk_score ?? item?.score ?? item?.probability;
    const num = Number(raw);
    if (!Number.isFinite(num)) return null;
    const pct = num > 1 ? num : num * 100;
    return Math.max(0, Math.min(pct, 100));
  };

  const formatPercent = (value) => {
    if (value === null) return 'n/a';
    if (value < 1) return `${value.toFixed(2)}%`;
    if (value < 10) return `${value.toFixed(1)}%`;
    return `${Math.round(value)}%`;
  };

  const riskLabel = (level) => (level === 2 ? 'HIGH' : level === 1 ? 'MEDIUM' : level === 0 ? 'LOW' : 'UNKNOWN');
  const riskClass = (level) => (level === 2 ? 'high' : level === 1 ? 'medium' : level === 0 ? 'low' : 'unknown');
  const riskBadgeClass = (level) => (level === 2 ? 'risk-high' : level === 1 ? 'risk-medium' : level === 0 ? 'risk-low' : 'risk-unknown');
  const telemetryServices = new Set(Object.keys(data.telemetry_debug || {}));
  const telemetryKnown = telemetryServices.size > 0;

  const resolveTelemetryBadge = (service) => {
    if (!telemetryKnown) return { label: 'Telemetry: n/a', className: 'telemetry-na' };
    if (telemetryServices.has(service)) return { label: 'Telemetry: yes', className: 'telemetry-on' };
    return { label: 'Telemetry: none', className: 'telemetry-off' };
  };

  let riskSortOrder = 'desc'; // desc = high->low confidence
  const getConfidenceNumeric = (item) => {
    const pct = resolveConfidencePercent(item);
    return pct === null ? -1 : pct;
  };
  const sortRisks = (list) => {
    const dir = riskSortOrder === 'asc' ? 1 : -1;
    return [...list].sort((a, b) => {
      const ca = getConfidenceNumeric(a);
      const cb = getConfidenceNumeric(b);
      if (ca !== cb) return (ca - cb) * dir;
      const ra = resolveRiskLevel(a);
      const rb = resolveRiskLevel(b);
      if (ra !== rb) return rb - ra;
      return String(a?.service || '').localeCompare(String(b?.service || ''));
    });
  };
  const updateRiskSortToggle = () => {
    const btn = document.getElementById('risk-sort-toggle');
    if (!btn) return;
    const label = riskSortOrder === 'desc'
      ? 'Sort: confidence high -> low'
      : 'Sort: confidence low -> high';
    btn.textContent = label;
  };

  try {
    const container = document.getElementById('risk-container');
    debugStage = 'risk-block';
    const renderRiskCards = () => {
      if (!container) return [];
      container.innerHTML = '';
      const ordered = sortRisks(risks);
      ordered.forEach(item => {
        const level = resolveRiskLevel(item);
        const label = riskLabel(level);
        const cls = riskClass(level);
        const confidencePct = resolveConfidencePercent(item);
        const confidenceLabel = formatPercent(confidencePct);
        const badgeClass = riskBadgeClass(level);
        const telemetry = resolveTelemetryBadge(item.service);
        const reason = item.reason || 'No explanation available.';

        const card = document.createElement('div');
        card.className = `card ${cls}`;
        card.innerHTML = `
          <h3>${item.service}</h3>
          <div style="margin:6px 0 8px 0;">
            <span class="risk-badge ${badgeClass}">${label}</span>
          </div>
          <div class="meta">
            <span class="metric">Conf: ${confidenceLabel}</span>
            ${item.model ? `<span class="metric">Model: ${item.model}</span>` : ''}
            <span class="metric ${telemetry.className}">${telemetry.label}</span>
          </div>
          <p style="margin-top:8px;color:var(--muted);font-size:12px;font-style:italic;">${reason}</p>
        `;
        container.appendChild(card);
      });
      return ordered;
    };

    let orderedRisks = renderRiskCards();
    updateRiskSortToggle();

    const sortToggle = document.getElementById('risk-sort-toggle');
    if (sortToggle) {
      sortToggle.addEventListener('click', () => {
        riskSortOrder = riskSortOrder === 'desc' ? 'asc' : 'desc';
        updateRiskSortToggle();
        orderedRisks = renderRiskCards();
        updateHero(orderedRisks);
      });
    }

  debugStage = 'rca-block';
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

  debugStage = 'telemetry-block';
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

  debugStage = 'cicd-block';
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

  debugStage = 'improvements-block';
  const improvementsPanel = document.getElementById('improvements-panel');
  const improvements = Array.isArray(data.improvements) ? data.improvements : [];
  if (improvementsPanel) {
    if (!improvements.length) {
      improvementsPanel.innerHTML = '<p style="color:var(--muted);font-size:13px;">No improvement suggestions available.</p>';
    } else {
      improvementsPanel.innerHTML = improvements.map((s, i) => `
        <div class="card" style="margin-bottom:10px;display:flex;gap:12px;align-items:flex-start;">
          <span style="color:var(--accent-2);font-size:15px;font-weight:700;flex-shrink:0;line-height:1.4;">${i + 1}.</span>
          <span style="font-size:13px;color:#dde6ff;line-height:1.5;">${s}</span>
        </div>
      `).join('');
    }
  }

  function updateHero(list) {
    const top = list && list.length ? list[0] : null;
    const topLevel = top ? resolveRiskLevel(top) : -1;
    const topConfidence = top ? formatPercent(resolveConfidencePercent(top)) : '--';
    const telemetry = top ? resolveTelemetryBadge(top.service) : { label: 'Telemetry: --', className: 'telemetry-na' };
    document.getElementById('hero-service').textContent = top ? top.service : '--';
    document.getElementById('hero-risk').textContent = top ? `Risk: ${riskLabel(topLevel)}` : 'Risk: --';
    document.getElementById('hero-confidence').textContent = top ? `Conf: ${topConfidence}` : 'Conf: --';
    document.getElementById('hero-model').textContent = top && top.model ? `Model: ${top.model}` : 'Model: --';
    document.getElementById('hero-count').textContent = risks ? risks.length : 0;
    document.getElementById('hero-rca').textContent = data.rca_summary ? 'Ready' : 'Unavailable';
    const telemetryEl = document.getElementById('hero-telemetry');
    if (telemetryEl) {
      telemetryEl.textContent = telemetry.label;
      telemetryEl.className = `metric ${telemetry.className}`;
    }
  }
  updateHero(orderedRisks);

  const graphEl = document.getElementById('dependency-graph');
  const nodes = Array.isArray(data.dependency_graph?.nodes)
    ? data.dependency_graph.nodes
    : Object.values(data.dependency_graph?.nodes || {});
  const edges = Array.isArray(data.dependency_graph?.edges)
    ? data.dependency_graph.edges
    : Object.values(data.dependency_graph?.edges || {});

  try {
    if (!nodes.length) {
      graphEl.textContent = 'No dependency nodes available.';
    } else {
      const width = graphEl.clientWidth || 1000;
    const height = graphEl.clientHeight || 520;

    const riskMap = new Map();
    risks.forEach(r => {
      if (r && r.service) riskMap.set(r.service, r.predicted_risk_level);
    });

    const inMap = new Map();
    const outMap = new Map();
    nodes.forEach(n => {
      inMap.set(n, []);
      outMap.set(n, []);
    });
    edges.forEach(e => {
      if (inMap.has(e.to_service) && outMap.has(e.from_service)) {
        inMap.get(e.to_service).push(e.from_service);
        outMap.get(e.from_service).push(e.to_service);
      }
    });

    const rootNodes = nodes.filter(n => inMap.get(n)?.length === 0);
    const startNodes = rootNodes.length ? rootNodes : [...nodes];

    const levelMap = new Map();
    const visited = new Set();
    let queue = [...startNodes];
    let level = 0;

    while (queue.length) {
      const next = [];
      queue.forEach(node => {
        if (visited.has(node)) return;
        visited.add(node);
        levelMap.set(node, level);
        outMap.get(node).forEach(child => {
          if (!visited.has(child) && !next.includes(child)) next.push(child);
        });
      });
      queue = next;
      level += 1;
    }

    nodes.forEach(node => {
      if (!levelMap.has(node)) levelMap.set(node, level);
    });

    const maxLevel = Math.max(...levelMap.values());
    const levelBuckets = Array.from({ length: maxLevel + 1 }, () => []);
    nodes.forEach(node => {
      const l = levelMap.get(node) ?? maxLevel;
      levelBuckets[l].push(node);
    });

    const nodeData = nodes.map(node => ({
      id: node,
      x: 0,
      y: 0,
      risk: riskMap.has(node) ? riskMap.get(node) : -1,
      indeg: inMap.get(node)?.length || 0,
      outdeg: outMap.get(node)?.length || 0,
    }));

    const nodeIndex = new Map(nodeData.map((n, i) => [n.id, i]));

    // Radial ring layout: nodes grouped by graph depth, arranged around the center.
    const centerX = width / 2;
    const centerY = height / 2;
    const safeRadius = Math.min(width, height) * 0.52; // more space usage
    const ringSpacing = Math.max(140, safeRadius / Math.max(2, maxLevel + 1));

    levelBuckets.forEach((bucket, lvl) => {
      const baseRing = 70 + lvl * ringSpacing;
      const bucketCount = bucket.length || 1;
      const sortedBucket = bucket.slice().sort((a, b) => (outMap.get(b).length + inMap.get(b).length) - (outMap.get(a).length + inMap.get(a).length));
      const angleStep = (Math.PI * 2) / Math.max(8, bucketCount); // preserve readability even if few nodes

      sortedBucket.forEach((nodeId, idx) => {
        const adjustedIndex = idx % bucketCount;
        const angle = adjustedIndex * angleStep - Math.PI / 2;
        const radialJitter = ((adjustedIndex % 2) ? 1 : -1) * (bucketCount > 12 ? 8 : 0); // more separation for crowded rings
        const ringRadius = baseRing + radialJitter;
        const n = nodeData[nodeIndex.get(nodeId)];
        n.x = centerX + Math.cos(angle) * ringRadius;
        n.y = centerY + Math.sin(angle) * ringRadius;
      });
    });

    const edgeData = edges.map(e => {
      const s = nodeIndex.get(e.from_service);
      const t = nodeIndex.get(e.to_service);
      if (s !== undefined && t !== undefined) {
        return { from: s, to: t, fromId: e.from_service, toId: e.to_service };
      }
      return null;
    }).filter(Boolean);

    const colors = { high: '#ff6b6b', medium: '#ffb347', low: '#3ddc97', unknown: '#7c5cff' };
    const riskColor = risk => (risk === 2 ? colors.high : risk === 1 ? colors.medium : risk === 0 ? colors.low : colors.unknown);
    const riskGlow = risk => (risk === 2 ? 'rgba(255,107,107,0.35)' : risk === 1 ? 'rgba(255,179,71,0.35)' : risk === 0 ? 'rgba(61,220,151,0.35)' : 'rgba(124,92,255,0.35)');
    const riskText = risk => (risk === 2 ? 'High' : risk === 1 ? 'Medium' : risk === 0 ? 'Low' : 'Unknown');
    const radiusFor = node => Math.max(6, 7 + Math.min(8, Math.round((node.indeg + node.outdeg) * 0.9)));

    let selectedNode = null;
    let riskFilter = 'all';
    let nodeLabelMode = 'smart'; // smart | selected | all
    let searchQuery = '';
    const graphDetailsContent = document.getElementById('graph-details-content');
    const graphButtons = document.querySelectorAll('.graph-btn');
    const graphLabelToggle = document.getElementById('graph-label-toggle');
    const graphSearchInput = document.getElementById('graph-search');

    if (graphDetailsContent) {
      graphDetailsContent.innerHTML = 'Click a node to inspect risk + dependencies.';
    }

    const setGraphDetails = (nodeId) => {
      if (!graphDetailsContent) return;
      if (!nodeId) {
        graphDetailsContent.innerHTML = 'Click a node to inspect risk + dependencies.';
        return;
      }

      const nodeOut = nodeData.find(n => n.id === nodeId);
      if (!nodeOut) {
        graphDetailsContent.innerHTML = 'Node data unavailable.';
        return;
      }

      const inDeg = inMap.get(nodeId)?.length || 0;
      const outDeg = outMap.get(nodeId)?.length || 0;
      const riskLevel = nodeOut.risk >= 0 ? riskText(nodeOut.risk) : 'Unknown';

      graphDetailsContent.innerHTML = `
        <div><strong>${nodeOut.id}</strong></div>
        <div class="meta" style="margin-top:5px;"><span class="metric">Risk: ${riskLevel}</span> <span class="metric">In: ${inDeg}</span> <span class="metric">Out: ${outDeg}</span></div>
        <div class="meta" style="margin-top:4px;">Click same node to unselect.</div>
      `;
    };

    graphButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const risk = e.target.getAttribute('data-risk');
        if (risk) {
          riskFilter = risk;
          graphButtons.forEach(b => b.classList.toggle('active', b === e.target));
          renderGraph();
        }
      });
    });

    if (graphLabelToggle) {
      const updateLabelToggle = () => {
        const labelText = nodeLabelMode === 'smart' ? 'Labels: smart' : nodeLabelMode === 'selected' ? 'Labels: selected' : 'Labels: all';
        graphLabelToggle.textContent = labelText;
      };

      graphLabelToggle.addEventListener('click', () => {
        nodeLabelMode = nodeLabelMode === 'smart' ? 'selected' : nodeLabelMode === 'selected' ? 'all' : 'smart';
        updateLabelToggle();
        renderGraph();
      });

      updateLabelToggle();
    }

    if (graphSearchInput) {
      graphSearchInput.addEventListener('input', (e) => {
        searchQuery = (e.target.value || '').trim().toLowerCase();
        renderGraph();
      });
    }

    const renderGraph = () => {
      const svgParts = [];
      svgParts.push(`<svg id="dep-svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">`);
      svgParts.push(`<defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#556075" opacity="0.85" />
        </marker>
      </defs>`);

      svgParts.push(`<rect width="${width}" height="${height}" fill="rgba(19,26,41,0.85)" />`);

      for (let ring = 0; ring <= maxLevel; ring++) {
        const rr = 70 + ring * ringSpacing;
        svgParts.push(`<circle cx="${centerX}" cy="${centerY}" r="${rr}" fill="none" stroke="rgba(117, 153, 217, 0.16)" stroke-width="1" />`);
        if (ring < maxLevel) {
          svgParts.push(`<text x="${centerX + rr + 10}" y="${centerY - 6}" fill="#9fbfed" font-size="10" font-family="IBM Plex Mono,monospace" text-anchor="start">Level ${ring}</text>`);
        } else {
          svgParts.push(`<text x="${centerX + rr + 10}" y="${centerY - 6}" fill="#9fbfed" font-size="10" font-family="IBM Plex Mono,monospace" text-anchor="start">Level ${ring} (leaf)</text>`);
        }
      }

      svgParts.push(`<g id="dep-viewport">`);

      const activeNodeIds = new Set(nodeData
        .filter(node => riskFilter === 'all' || (riskFilter === 'high' && node.risk === 2) || (riskFilter === 'medium' && node.risk === 1) || (riskFilter === 'low' && node.risk === 0))
        .map(node => node.id)
      );

      const reachableOut = new Set();
      const reachableIn = new Set();
      if (selectedNode) {
        const queueOut = [selectedNode];
        const queueIn = [selectedNode];

        while (queueOut.length) {
          const current = queueOut.shift();
          (outMap.get(current) || []).forEach(child => {
            if (!reachableOut.has(child)) {
              reachableOut.add(child);
              queueOut.push(child);
            }
          });
        }

        while (queueIn.length) {
          const current = queueIn.shift();
          (inMap.get(current) || []).forEach(parent => {
            if (!reachableIn.has(parent)) {
              reachableIn.add(parent);
              queueIn.push(parent);
            }
          });
        }
      }

      const visibleEdges = edgeData.filter(edge => activeNodeIds.has(edge.fromId) && activeNodeIds.has(edge.toId));

      visibleEdges.forEach(edge => {
        const a = nodeData[edge.from];
        const b = nodeData[edge.to];
        const mx = (a.x + b.x) / 2;
        const my = (a.y + b.y) / 2;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 0.1;
        const curve = Math.min(70, Math.max(8, d * 0.12));
        const cx = mx - (dy / d) * curve;
        const cy = my + (dx / d) * curve;

        const edgePathHit = selectedNode && (
          edge.fromId === selectedNode || edge.toId === selectedNode ||
          reachableOut.has(edge.fromId) || reachableOut.has(edge.toId) ||
          reachableIn.has(edge.fromId) || reachableIn.has(edge.toId)
        );
        const opacity = selectedNode ? (edgePathHit ? 0.9 : 0.1) : 0.44;
        const sw = edgePathHit ? 2.2 : 1.1;
        const strokeColor = edgePathHit ? '#7cdfff' : '#8f9fbf';

        svgParts.push(`<path d="M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}" stroke="${strokeColor}" stroke-width="${sw}" opacity="${opacity}" fill="none" marker-end="url(#arrow)" />`);
      });

      const wrapId = (id) => {
        const words = id.split(/[-_.\/]/g).join(' ').split(' ');
        const lines = [];
        let current = '';
        words.forEach(w => {
          if (!w) return;
          if ((current + ' ' + w).trim().length <= 14) {
            current = (current + ' ' + w).trim();
          } else {
            if (current) lines.push(current);
            current = w;
          }
        });
        if (current) lines.push(current);
        return lines.slice(0, 3);
      };

      nodeData.filter(n => activeNodeIds.has(n.id)).forEach(n => {
        const r = radiusFor(n);
        const color = riskColor(n.risk);
        const glow = riskGlow(n.risk);
        const isSelected = selectedNode === n.id;
        const isNeighbor = selectedNode && (outMap.get(selectedNode)?.includes(n.id) || inMap.get(selectedNode)?.includes(n.id));
        const matchesSearch = !!searchQuery && n.id.toLowerCase().includes(searchQuery);
        const isReachable = selectedNode && (reachableOut.has(n.id) || reachableIn.has(n.id));

        const strokeColor = isSelected ? '#ffffff' : isNeighbor ? '#d6eaff' : isReachable ? '#8cd6ff' : 'rgba(255,255,255,0.18)';
        const strokeW = isSelected ? 2.2 : (isNeighbor ? 1.8 : isReachable ? 1.6 : 1.1);
        const bgOpacity = selectedNode ? (isSelected || isNeighbor || isReachable ? 0.48 : 0.10) : 0.32;
        const isDimmed = searchQuery && !matchesSearch && !isSelected && !isNeighbor;
        const nodeFill = isDimmed ? 'rgba(101, 118, 146, 0.40)' : color;
        const nodeGlow = isDimmed ? 'rgba(102,110,132,0.16)' : glow;

        const labelLines = wrapId(n.id);
        const angle = Math.atan2(n.y - centerY, n.x - centerX);
        const labelX = n.x + Math.cos(angle) * (r + 16);
        const labelY = n.y + Math.sin(angle) * (r + 16);
        const shouldShowLabel = nodeLabelMode === 'all'
          || (nodeLabelMode === 'selected' && (isSelected || isNeighbor))
          || (nodeLabelMode === 'smart' && (isSelected || isNeighbor || nodeData.length <= 24))
          || matchesSearch;

        const textElements = shouldShowLabel
          ? labelLines.map((line, li) => {
              const align = Math.abs(Math.cos(angle)) > 0.35 ? 'middle' : (Math.cos(angle) >= 0 ? 'start' : 'end');
              const yOffset = labelY + li * 12;
              const xOffset = labelX + (align === 'start' ? 10 : align === 'end' ? -10 : 0);
              return `<text x="${xOffset}" y="${yOffset}" fill="#e8f1ff" font-size="9" text-anchor="${align}" style="pointer-events:none;">${line}</text>`;
            }).join('')
          : '';

        svgParts.push(`
          <g class="node" data-id="${n.id}" style="cursor:pointer;">
            <circle cx="${n.x}" cy="${n.y}" r="${r + 12}" fill="${nodeGlow}" opacity="${bgOpacity}" />
            <circle cx="${n.x}" cy="${n.y}" r="${r}" fill="${nodeFill}" stroke="${strokeColor}" stroke-width="${strokeW}" />
            ${textElements}
          </g>
        `);
      });

      svgParts.push('</g></svg>');
      graphEl.innerHTML = svgParts.join('');

      setGraphDetails(selectedNode);

      const serviceList = document.getElementById('graph-service-list');
      if (serviceList) {
        const matches = nodeData
          .filter(n => n.id.toLowerCase().includes(searchQuery || ''))
          .map(n => ({ id: n.id, risk: n.risk, selected: n.id === selectedNode }))
          .slice(0, 50);

        if (searchQuery) {
          serviceList.innerHTML = matches.length
            ? `<div style="font-size:11px;color:#c8d4f1;">Showing ${matches.length} matching services:</div>${matches.map(m => `<div style="padding:3px 0;${m.selected ? 'font-weight:700;color:#ffffff;' : 'color:#a4b0c8;'}">${m.id}</div>`).join('')}`
            : '<div style="color:#f1adad;font-size:11px;">No matching services found.</div>';
        } else {
          const dotColor = (risk) => risk === 2 ? '#ff6b6b' : risk === 1 ? '#ffb347' : risk === 0 ? '#3ddc97' : '#7c5cff';
          serviceList.innerHTML = `<div style="font-size:11px;color:#c8d4f1;">All services (${nodeData.length}):</div>${nodeData.slice(0, 50).map(n => `<div style="padding:2px 0;display:flex;align-items:center;gap:6px;${n.id === selectedNode ? 'font-weight:700;color:#ffffff;' : 'color:#a4b0c8;'}"><span style="width:7px;height:7px;border-radius:50%;background:${dotColor(n.risk)};flex-shrink:0;display:inline-block;"></span>${n.id}</div>`).join('')}${nodeData.length > 50 ? '<div style="padding-top:4px;color:#8899b7;font-size:11px;">...more...</div>' : ''}`;
        }
      }

      debugStage = 'graph-block';
    const svg = document.getElementById('dep-svg');
      const viewport = document.getElementById('dep-viewport');
      const tooltip = document.getElementById('graph-tooltip');
      let scale = 1;
      let panX = 0;
      let panY = 0;
      let isPanning = false;
      let startX = 0;
      let startY = 0;

      const updateTransform = () => { viewport.setAttribute('transform', `translate(${panX}, ${panY}) scale(${scale})`); };
      updateTransform();

      svg.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = Math.sign(e.deltaY) * -0.08;
        scale = Math.max(0.6, Math.min(2.8, scale + delta));
        updateTransform();
      });

      svg.addEventListener('mousedown', (e) => {
        isPanning = true;
        startX = e.clientX - panX;
        startY = e.clientY - panY;
      });

      svg.addEventListener('mousemove', (e) => {
        if (isPanning) {
          panX = e.clientX - startX;
          panY = e.clientY - startY;
          updateTransform();
        }

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
        const inDeg = inMap.get(id)?.length || 0;
        const outDeg = outMap.get(id)?.length || 0;

        tooltip.innerHTML = `<div><b>${id}</b></div><div class="muted">Risk: ${riskLabel}</div><div class="muted">In: ${inDeg} Out: ${outDeg}</div>`;
        const rect = svg.getBoundingClientRect();
        tooltip.style.left = `${e.clientX - rect.left}px`;
        tooltip.style.top = `${e.clientY - rect.top - 22}px`;
        tooltip.style.opacity = '1';
      });

      svg.addEventListener('mouseup', () => { isPanning = false; });
      svg.addEventListener('mouseleave', () => { isPanning = false; tooltip.style.opacity = '0'; });

      svg.addEventListener('click', (e) => {
        const target = e.target.closest ? e.target.closest('.node') : null;
        if (!target) {
          selectedNode = null;
        } else {
          const id = target.getAttribute('data-id');
          selectedNode = selectedNode === id ? null : id;
        }
        renderGraph();
      });
    };

    renderGraph();
  }
} catch (graphError) {
    const status = document.getElementById('debug-status');
    if (status) {
      status.innerHTML = `<span class="metric">Graph error (${debugStage}): ${graphError.message || graphError}</span>`;
    }
    if (graphEl) {
      graphEl.textContent = `Graph rendering failed: ${graphError.message || graphError}`;
    }
    console.error('Graph rendering error:', graphError);
  } finally {
    const status = document.getElementById('debug-status');
    if (status && debugStage !== 'graph-block') {
      status.innerHTML = `<span class="metric">Debug: completed stage ${debugStage}. If UI is blank, check DevTools console.</span>`;
    }
  }
} catch (renderError) {
    const status = document.getElementById('debug-status');
    if (status) {
      status.innerHTML = `<span class="metric">UI render error (${debugStage}): ${renderError.message || renderError}</span>`;
    }
    console.error('RiskPanel render error:', renderError);
  }
})();

