const COLORS = [
  "#58c6a4",
  "#e7c66b",
  "#df7d58",
  "#7aa6ff",
  "#d77adf",
  "#8fd36a",
  "#ef8fa3",
  "#68d4d8",
  "#bda2ff",
  "#f0a95a",
  "#b8d45d",
  "#ff7c7c",
];

const canvas = document.getElementById("mapCanvas");
const ctx = canvas.getContext("2d");

const state = {
  viewMode: "flights",
  nodes: [],
  edges: [],
  clusters: [],
  land: null,
  summary: null,
  nodeById: new Map(),
  hoveredNode: null,
  selectedCluster: null,
  edgeLimit: 1000,
  showIntercluster: true,
  width: 0,
  height: 0,
  dpr: 1,
  projection: null,
  mouse: { x: -1000, y: -1000 },
  corpus: {
    nodes: [],
    edges: [],
    summary: null,
    nodeById: new Map(),
    layout: null,
    hoveredNode: null,
    selectedNode: null,
  },
  benchmark: {
    points: [],
    labelMode: "true", // "true", "hodge", or "rbl"
    hoveredPoint: null,
  },
};

const els = {
  datasetLabel: document.getElementById("datasetLabel"),
  flightViewButton: document.getElementById("flightViewButton"),
  corpusViewButton: document.getElementById("corpusViewButton"),
  metricOneLabel: document.getElementById("metricOneLabel"),
  metricOneValue: document.getElementById("metricOneValue"),
  metricTwoLabel: document.getElementById("metricTwoLabel"),
  metricTwoValue: document.getElementById("metricTwoValue"),
  metricThreeLabel: document.getElementById("metricThreeLabel"),
  metricThreeValue: document.getElementById("metricThreeValue"),
  metricFourLabel: document.getElementById("metricFourLabel"),
  metricFourValue: document.getElementById("metricFourValue"),
  mainControls: document.getElementById("mainControls"),
  edgeLimitLabel: document.getElementById("edgeLimitLabel"),
  edgeLimit: document.getElementById("edgeLimit"),
  interClusterControl: document.getElementById("interClusterControl"),
  interClusterToggle: document.getElementById("interClusterToggle"),
  clusterList: document.getElementById("clusterList"),
  detailCode: document.getElementById("detailCode"),
  detailName: document.getElementById("detailName"),
  detailLocation: document.getElementById("detailLocation"),
  detailTotalLabel: document.getElementById("detailTotalLabel"),
  detailTotal: document.getElementById("detailTotal"),
  detailInboundLabel: document.getElementById("detailInboundLabel"),
  detailInbound: document.getElementById("detailInbound"),
  detailOutboundLabel: document.getElementById("detailOutboundLabel"),
  detailOutbound: document.getElementById("detailOutbound"),
  detailPotentialLabel: document.getElementById("detailPotentialLabel"),
  detailPotential: document.getElementById("detailPotential"),
  gradientLabel: document.getElementById("gradientLabel"),
  gradientMeter: document.getElementById("gradientMeter"),
  curlLabel: document.getElementById("curlLabel"),
  curlMeter: document.getElementById("curlMeter"),
  harmonicLabel: document.getElementById("harmonicLabel"),
  harmonicMeter: document.getElementById("harmonicMeter"),
  sourceLine: document.getElementById("sourceLine"),
  benchmarkViewButton: document.getElementById("benchmarkViewButton"),
  benchmarkControls: document.getElementById("benchmarkControls"),
  showTrueLabelsButton: document.getElementById("showTrueLabelsButton"),
  showPredLabelsButton: document.getElementById("showPredLabelsButton"),
  showRblLabelsButton: document.getElementById("showRblLabelsButton"),
};

function clusterColor(clusterId) {
  if (clusterId < 0) return "#8a867d";
  return COLORS[clusterId % COLORS.length];
}

function fmt(value) {
  return Number(value || 0).toLocaleString();
}

const LAMBERT = (() => {
  const phi1 = (33 * Math.PI) / 180;
  const phi2 = (55 * Math.PI) / 180;
  const lat0 = (23 * Math.PI) / 180;
  const lon0 = (-20 * Math.PI) / 180;
  const n =
    Math.log(Math.cos(phi1) / Math.cos(phi2)) /
    Math.log(Math.tan(Math.PI / 4 + phi2 / 2) / Math.tan(Math.PI / 4 + phi1 / 2));
  const factor = (Math.cos(phi1) * Math.tan(Math.PI / 4 + phi1 / 2) ** n) / n;
  const rho0 = factor / Math.tan(Math.PI / 4 + lat0 / 2) ** n;
  return { n, factor, rho0, lon0 };
})();

function chartBox() {
  const leftPad = state.width > 900 ? 430 : 40;
  const rightPad = state.width > 900 ? 420 : 40;
  const topPad = state.width > 900 ? 40 : 260;
  const bottomPad = state.width > 900 ? 40 : 220;
  return {
    x: leftPad,
    y: topPad,
    width: Math.max(280, state.width - leftPad - rightPad),
    height: Math.max(260, state.height - topPad - bottomPad),
  };
}

function rawLambert(lon, lat) {
  const clampedLat = Math.max(-67, Math.min(84, lat));
  const phi = (clampedLat * Math.PI) / 180;
  const lambda = (lon * Math.PI) / 180;
  const rho = LAMBERT.factor / Math.tan(Math.PI / 4 + phi / 2) ** LAMBERT.n;
  const theta = LAMBERT.n * (lambda - LAMBERT.lon0);
  return {
    x: rho * Math.sin(theta),
    y: LAMBERT.rho0 - rho * Math.cos(theta),
  };
}

function projectionLayout() {
  if (state.projection && state.projection.width === state.width && state.projection.height === state.height) {
    return state.projection;
  }

  let samples = [];
  if (state.nodes.length > 0) {
    samples = state.nodes.map((node) => rawLambert(node.lon, node.lat));
  } else {
    for (let lon = -180; lon <= 180; lon += 10) {
      for (const lat of [-60, -30, 0, 30, 60, 82]) {
        samples.push(rawLambert(lon, lat));
      }
    }
  }

  let minX = Math.min(...samples.map((point) => point.x));
  let maxX = Math.max(...samples.map((point) => point.x));
  let minY = Math.min(...samples.map((point) => point.y));
  let maxY = Math.max(...samples.map((point) => point.y));
  const padX = Math.max(0.12, (maxX - minX) * 0.11);
  const padY = Math.max(0.12, (maxY - minY) * 0.11);
  minX -= padX;
  maxX += padX;
  minY -= padY;
  maxY += padY;
  const box = chartBox();
  const scale = Math.min(box.width / (maxX - minX), box.height / (maxY - minY)) * 0.98;
  const projectedWidth = (maxX - minX) * scale;
  const projectedHeight = (maxY - minY) * scale;

  state.projection = {
    width: state.width,
    height: state.height,
    minX,
    minY,
    scale,
    offsetX: box.x + (box.width - projectedWidth) / 2,
    offsetY: box.y + (box.height - projectedHeight) / 2,
    box,
  };
  return state.projection;
}

function project(lon, lat) {
  const layout = projectionLayout();
  const raw = rawLambert(lon, lat);
  return {
    x: layout.offsetX + (raw.x - layout.minX) * layout.scale,
    y: layout.offsetY + (raw.y - layout.minY) * layout.scale,
  };
}

function resizeCanvas() {
  state.dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
  state.width = window.innerWidth;
  state.height = window.innerHeight;
  canvas.width = Math.floor(state.width * state.dpr);
  canvas.height = Math.floor(state.height * state.dpr);
  canvas.style.width = `${state.width}px`;
  canvas.style.height = `${state.height}px`;
  ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
  state.projection = null;
  state.corpus.layout = null;
  draw();
}

function traceRing(ring) {
  let started = false;
  let previousLon = null;
  for (const coordinate of ring) {
    const lon = coordinate[0];
    const lat = coordinate[1];
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
    const point = project(lon, lat);
    if (!started || (previousLon !== null && Math.abs(lon - previousLon) > 180)) {
      ctx.moveTo(point.x, point.y);
      started = true;
    } else {
      ctx.lineTo(point.x, point.y);
    }
    previousLon = lon;
  }
}

function drawLandPolygon(polygon) {
  for (const ring of polygon) {
    ctx.beginPath();
    traceRing(ring);
    ctx.stroke();
  }
}

function drawAeronauticalChartMap() {
  const { box } = projectionLayout();
  ctx.save();
  ctx.beginPath();
  ctx.rect(box.x, box.y, box.width, box.height);
  ctx.clip();

  const ocean = ctx.createLinearGradient(box.x, box.y, box.x, box.y + box.height);
  ocean.addColorStop(0, "rgba(27, 40, 40, 0.42)");
  ocean.addColorStop(0.48, "rgba(18, 30, 29, 0.26)");
  ocean.addColorStop(1, "rgba(34, 31, 24, 0.36)");
  ctx.fillStyle = ocean;
  ctx.fillRect(box.x, box.y, box.width, box.height);

  if (state.land) {
    ctx.strokeStyle = "rgba(244, 233, 196, 0.26)";
    ctx.lineWidth = 0.8;
    for (const feature of state.land.features || []) {
      const geometry = feature.geometry;
      if (!geometry) continue;
      if (geometry.type === "Polygon") {
        drawLandPolygon(geometry.coordinates);
      } else if (geometry.type === "MultiPolygon") {
        geometry.coordinates.forEach(drawLandPolygon);
      }
    }
  }

  ctx.restore();
  ctx.save();
  ctx.strokeStyle = "rgba(243, 239, 226, 0.18)";
  ctx.lineWidth = 1;
  ctx.strokeRect(box.x, box.y, box.width, box.height);
  ctx.restore();
}

function drawProjectedLine(points) {
  ctx.beginPath();
  let started = false;
  let previous = null;
  for (const point of points) {
    const projected = project(point.lon, point.lat);
    if (!started || (previous && Math.hypot(projected.x - previous.x, projected.y - previous.y) > state.width * 0.5)) {
      ctx.moveTo(projected.x, projected.y);
      started = true;
    } else {
      ctx.lineTo(projected.x, projected.y);
    }
    previous = projected;
  }
  ctx.stroke();
}

function drawGraticule() {
  ctx.save();
  ctx.strokeStyle = "rgba(243, 239, 226, 0.11)";
  ctx.lineWidth = 1;
  for (let lon = -180; lon <= 180; lon += 30) {
    const points = [];
    for (let lat = -60; lat <= 82; lat += 3) {
      points.push({ lon, lat });
    }
    drawProjectedLine(points);
  }
  for (let lat = -60; lat <= 75; lat += 15) {
    const points = [];
    for (let lon = -180; lon <= 180; lon += 4) {
      points.push({ lon, lat });
    }
    drawProjectedLine(points);
  }
  ctx.restore();
}

function toVector(lon, lat) {
  const phi = (lat * Math.PI) / 180;
  const lambda = (lon * Math.PI) / 180;
  const cosPhi = Math.cos(phi);
  return {
    x: cosPhi * Math.cos(lambda),
    y: cosPhi * Math.sin(lambda),
    z: Math.sin(phi),
  };
}

function fromVector(vector) {
  const hyp = Math.hypot(vector.x, vector.y);
  return {
    lon: (Math.atan2(vector.y, vector.x) * 180) / Math.PI,
    lat: (Math.atan2(vector.z, hyp) * 180) / Math.PI,
  };
}

function greatCirclePoints(source, target) {
  const a = toVector(source.lon, source.lat);
  const b = toVector(target.lon, target.lat);
  const dot = Math.max(-1, Math.min(1, a.x * b.x + a.y * b.y + a.z * b.z));
  const omega = Math.acos(dot);
  const steps = Math.max(10, Math.min(42, Math.ceil((omega * 180) / Math.PI / 4)));
  const points = [];

  if (omega < 1e-6) {
    return [
      { lon: source.lon, lat: source.lat },
      { lon: target.lon, lat: target.lat },
    ];
  }

  const sinOmega = Math.sin(omega);
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const weightA = Math.sin((1 - t) * omega) / sinOmega;
    const weightB = Math.sin(t * omega) / sinOmega;
    points.push(
      fromVector({
        x: weightA * a.x + weightB * b.x,
        y: weightA * a.y + weightB * b.y,
        z: weightA * a.z + weightB * b.z,
      }),
    );
  }
  return points;
}

function drawRoute(edge) {
  const source = state.nodeById.get(edge.source);
  const target = state.nodeById.get(edge.target);
  if (!source || !target) return;
  if (!state.showIntercluster && !edge.sameCluster) return;
  if (state.selectedCluster !== null && source.cluster !== state.selectedCluster && target.cluster !== state.selectedCluster) {
    return;
  }

  const color = edge.sameCluster ? clusterColor(source.cluster) : "rgba(243, 239, 226, 0.58)";
  const alpha = edge.sameCluster ? 0.18 : 0.12;
  const points = greatCirclePoints(source, target);

  ctx.save();
  ctx.globalAlpha = alpha + Math.min(0.28, edge.count / 95);
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(0.35, Math.min(2.8, Math.sqrt(edge.count) * 0.34));
  drawProjectedLine(points);
  ctx.restore();
}

function drawNode(node) {
  const point = project(node.lon, node.lat);
  const activeCluster = state.selectedCluster === null || state.selectedCluster === node.cluster;
  const isHovered = state.hoveredNode && state.hoveredNode.id === node.id;
  const radius = Math.max(2.2, Math.min(12, Math.sqrt(node.totalRoutes) * 0.36));
  const potential = node.potentialNorm ?? 0.35;
  const color = clusterColor(node.cluster);

  ctx.save();
  ctx.globalAlpha = activeCluster ? 1 : 0.18;
  ctx.beginPath();
  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = isHovered ? 24 : 8 + potential * 10;
  ctx.arc(point.x, point.y, isHovered ? radius + 4 : radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.lineWidth = isHovered ? 2 : 1;
  ctx.strokeStyle = isHovered ? "#f3efe2" : "rgba(16, 18, 17, 0.78)";
  ctx.stroke();
  ctx.restore();
}

function drawTooltip() {
  const node = state.hoveredNode;
  if (!node) return;
  const point = project(node.lon, node.lat);
  const text = `${node.code}  ${node.city || node.name}`;
  ctx.save();
  ctx.font = "650 12px Inter, system-ui, sans-serif";
  const width = Math.min(260, ctx.measureText(text).width + 22);
  const x = Math.min(state.width - width - 18, point.x + 14);
  const y = Math.max(18, point.y - 36);
  ctx.fillStyle = "rgba(20, 23, 22, 0.94)";
  ctx.strokeStyle = "rgba(243, 239, 226, 0.24)";
  ctx.lineWidth = 1;
  ctx.fillRect(x, y, width, 30);
  ctx.strokeRect(x, y, width, 30);
  ctx.fillStyle = "#f3efe2";
  ctx.fillText(text, x + 11, y + 19);
  ctx.restore();
}

function corpusColor(index) {
  return COLORS[index % COLORS.length];
}

function termAbbreviation(label) {
  const words = label.split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words
    .slice(0, 3)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

function buildCorpusLayout() {
  const box = chartBox();
  const centerX = box.x + box.width / 2;
  const centerY = box.y + box.height / 2;
  const radiusX = box.width * 0.39;
  const radiusY = box.height * 0.38;
  const nodes = state.corpus.nodes.map((node, index) => {
    const angle = (index / Math.max(1, state.corpus.nodes.length)) * Math.PI * 2 - Math.PI / 2;
    return {
      ...node,
      index,
      x: centerX + Math.cos(angle) * radiusX,
      y: centerY + Math.sin(angle) * radiusY,
      vx: 0,
      vy: 0,
      radius: Math.max(6, Math.min(22, Math.sqrt(node.documentCount) * 1.7)),
    };
  });
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const edges = state.corpus.edges
    .map((edge) => ({
      ...edge,
      sourceNode: nodeById.get(edge.source),
      targetNode: nodeById.get(edge.target),
    }))
    .filter((edge) => edge.sourceNode && edge.targetNode);

  for (let step = 0; step < 260; step += 1) {
    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j += 1) {
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const force = 1600 / (distance * distance);
        const fx = (dx / distance) * force;
        const fy = (dy / distance) * force;
        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }

    for (const edge of edges) {
      const a = edge.sourceNode;
      const b = edge.targetNode;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const distance = Math.max(1, Math.hypot(dx, dy));
      const desired = Math.max(68, 168 - Math.min(92, edge.documentCount * 1.7));
      const strength = 0.003 * Math.min(4, Math.sqrt(edge.documentCount));
      const force = (distance - desired) * strength;
      const fx = (dx / distance) * force;
      const fy = (dy / distance) * force;
      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }

    for (const node of nodes) {
      node.vx += (centerX - node.x) * 0.002;
      node.vy += (centerY - node.y) * 0.002;
      node.vx *= 0.78;
      node.vy *= 0.78;
      node.x = Math.max(box.x + 28, Math.min(box.x + box.width - 28, node.x + node.vx));
      node.y = Math.max(box.y + 28, Math.min(box.y + box.height - 28, node.y + node.vy));
    }
  }

  state.corpus.layout = {
    width: state.width,
    height: state.height,
    box,
    nodes,
    edges,
    nodeById,
  };
  return state.corpus.layout;
}

function corpusLayout() {
  if (
    state.corpus.layout &&
    state.corpus.layout.width === state.width &&
    state.corpus.layout.height === state.height
  ) {
    return state.corpus.layout;
  }
  return buildCorpusLayout();
}

function drawCorpusGraph() {
  const layout = corpusLayout();
  const { box } = layout;
  const selectedId = state.corpus.selectedNode;
  const hoveredId = state.corpus.hoveredNode ? state.corpus.hoveredNode.id : null;

  ctx.save();
  ctx.beginPath();
  ctx.rect(box.x, box.y, box.width, box.height);
  ctx.clip();

  const networkGradient = ctx.createLinearGradient(box.x, box.y, box.x + box.width, box.y + box.height);
  networkGradient.addColorStop(0, "rgba(37, 49, 47, 0.52)");
  networkGradient.addColorStop(0.55, "rgba(19, 26, 25, 0.32)");
  networkGradient.addColorStop(1, "rgba(40, 34, 27, 0.44)");
  ctx.fillStyle = networkGradient;
  ctx.fillRect(box.x, box.y, box.width, box.height);

  ctx.strokeStyle = "rgba(243, 239, 226, 0.07)";
  ctx.lineWidth = 1;
  for (let x = box.x + 60; x < box.x + box.width; x += 60) {
    ctx.beginPath();
    ctx.moveTo(x, box.y);
    ctx.lineTo(x, box.y + box.height);
    ctx.stroke();
  }
  for (let y = box.y + 60; y < box.y + box.height; y += 60) {
    ctx.beginPath();
    ctx.moveTo(box.x, y);
    ctx.lineTo(box.x + box.width, y);
    ctx.stroke();
  }

  const visibleEdges = layout.edges
    .filter((edge) => !selectedId || edge.source === selectedId || edge.target === selectedId)
    .slice(0, state.edgeLimit);
  for (const edge of visibleEdges) {
    const active = edge.source === selectedId || edge.target === selectedId || edge.source === hoveredId || edge.target === hoveredId;
    const source = edge.sourceNode;
    const target = edge.targetNode;
    ctx.beginPath();
    ctx.moveTo(source.x, source.y);
    const midX = (source.x + target.x) / 2;
    const midY = (source.y + target.y) / 2;
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const distance = Math.max(1, Math.hypot(dx, dy));
    const bend = Math.min(38, Math.max(8, distance * 0.08));
    ctx.quadraticCurveTo(midX - (dy / distance) * bend, midY + (dx / distance) * bend, target.x, target.y);
    ctx.strokeStyle = active ? "rgba(231, 198, 107, 0.68)" : "rgba(243, 239, 226, 0.14)";
    ctx.globalAlpha = active ? 1 : 0.48;
    ctx.lineWidth = Math.max(0.7, Math.min(5, Math.sqrt(edge.documentCount) * 0.42));
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  const sortedNodes = [...layout.nodes].sort((a, b) => a.documentCount - b.documentCount);
  for (const node of sortedNodes) {
    const active = !selectedId || node.id === selectedId || visibleEdges.some((edge) => edge.source === node.id || edge.target === node.id);
    const highlighted = node.id === selectedId || node.id === hoveredId;
    const color = corpusColor(node.index);
    ctx.save();
    ctx.globalAlpha = active ? 1 : 0.18;
    ctx.beginPath();
    ctx.fillStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = highlighted ? 24 : 9;
    ctx.arc(node.x, node.y, highlighted ? node.radius + 4 : node.radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.lineWidth = highlighted ? 2 : 1;
    ctx.strokeStyle = highlighted ? "#f3efe2" : "rgba(12, 14, 13, 0.82)";
    ctx.stroke();
    ctx.restore();
  }

  ctx.font = "700 11px Inter, system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (const node of layout.nodes) {
    const highlighted = node.id === selectedId || node.id === hoveredId;
    if (!highlighted && node.documentCount < 20) continue;
    ctx.fillStyle = highlighted ? "#f3efe2" : "rgba(243, 239, 226, 0.76)";
    ctx.fillText(node.label, node.x, node.y + node.radius + 8);
  }

  ctx.restore();
}

function nearestCorpusNode(x, y) {
  const layout = corpusLayout();
  let best = null;
  let bestDistance = Infinity;
  for (const node of layout.nodes) {
    const distance = Math.hypot(node.x - x, node.y - y);
    const threshold = node.radius + 8;
    if (distance < threshold && distance < bestDistance) {
      best = node;
      bestDistance = distance;
    }
  }
  return best;
}

function draw() {
  if (!ctx) return;
  ctx.clearRect(0, 0, state.width, state.height);
  const gradient = ctx.createLinearGradient(0, 0, state.width, state.height);
  gradient.addColorStop(0, "#121615");
  gradient.addColorStop(0.52, "#0c100f");
  gradient.addColorStop(1, "#171412");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, state.width, state.height);

  if (state.viewMode === "corpus") {
    drawCorpusGraph();
    return;
  }
  if (state.viewMode === "benchmark") {
    drawBenchmarkPlot();
    return;
  }

  drawAeronauticalChartMap();
  drawGraticule();

  const visibleEdges = state.edges.slice(0, state.edgeLimit);
  visibleEdges.forEach(drawRoute);

  const sortedNodes = [...state.nodes].sort((a, b) => a.totalRoutes - b.totalRoutes);
  sortedNodes.forEach(drawNode);
  drawTooltip();
}

function projectBenchmark(bx, by) {
  const box = chartBox();
  const size = Math.min(box.width, box.height) * 0.82;
  const scale = size / 16.0;
  const centerX = box.x + box.width / 2;
  const centerY = box.y + box.height / 2;
  return {
    x: centerX + bx * scale,
    y: centerY - by * scale
  };
}

function nearestBenchmarkPoint(x, y) {
  if (!state.benchmark.points) return null;
  let best = null;
  let bestDistance = Infinity;
  for (const point of state.benchmark.points) {
    const proj = projectBenchmark(point.x, point.y);
    const distance = Math.hypot(proj.x - x, proj.y - y);
    if (distance < 12 && distance < bestDistance) {
      best = point;
      bestDistance = distance;
    }
  }
  return best;
}

function drawBenchmarkPlot() {
  const box = chartBox();
  ctx.save();
  ctx.beginPath();
  ctx.rect(box.x, box.y, box.width, box.height);
  ctx.clip();

  const networkGradient = ctx.createLinearGradient(box.x, box.y, box.x + box.width, box.y + box.height);
  networkGradient.addColorStop(0, "rgba(22, 28, 27, 0.52)");
  networkGradient.addColorStop(0.55, "rgba(12, 17, 16, 0.32)");
  networkGradient.addColorStop(1, "rgba(28, 24, 18, 0.44)");
  ctx.fillStyle = networkGradient;
  ctx.fillRect(box.x, box.y, box.width, box.height);

  ctx.strokeStyle = "rgba(243, 239, 226, 0.04)";
  ctx.lineWidth = 1;
  for (let val = -8; val <= 8; val += 2) {
    const p1 = projectBenchmark(val, -8);
    const p2 = projectBenchmark(val, 8);
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();

    const p3 = projectBenchmark(-8, val);
    const p4 = projectBenchmark(8, val);
    ctx.beginPath();
    ctx.moveTo(p3.x, p3.y);
    ctx.lineTo(p4.x, p4.y);
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(243, 239, 226, 0.15)";
  const originX1 = projectBenchmark(0, -8);
  const originX2 = projectBenchmark(0, 8);
  ctx.beginPath();
  ctx.moveTo(originX1.x, originX1.y);
  ctx.lineTo(originX2.x, originX2.y);
  ctx.stroke();

  const originY1 = projectBenchmark(-8, 0);
  const originY2 = projectBenchmark(8, 0);
  ctx.beginPath();
  ctx.moveTo(originY1.x, originY1.y);
  ctx.lineTo(originY2.x, originY2.y);
  ctx.stroke();

  const centers = [
    { name: "City 0 (5, 5)", x: 5, y: 5 },
    { name: "City 1 (-5, 5)", x: -5, y: 5 },
    { name: "City 2 (5, -5)", x: 5, y: -5 },
    { name: "City 3 (-5, -5)", x: -5, y: -5 }
  ];
  ctx.font = "italic 600 11px Inter, system-ui, sans-serif";
  ctx.fillStyle = "rgba(243, 239, 226, 0.3)";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const c of centers) {
    const proj = projectBenchmark(c.x, c.y);
    ctx.beginPath();
    ctx.arc(proj.x, proj.y, 45, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(243, 239, 226, 0.08)";
    ctx.stroke();
    ctx.fillText(c.name, proj.x, proj.y);
  }

  if (!state.benchmark.points || state.benchmark.points.length === 0) {
    ctx.restore();
    return;
  }

  const hovered = state.benchmark.hoveredPoint;
  for (const point of state.benchmark.points) {
    const proj = projectBenchmark(point.x, point.y);
    const isHovered = hovered && hovered.id === point.id;
    const mode = state.benchmark.labelMode;
    const label = mode === "true" ? point.trueLabel : (mode === "rbl" ? (point.rblLabel !== undefined ? point.rblLabel : -1) : point.predLabel);
    
    let color;
    if (label === -1) {
      color = "#ff4d4d";
    } else {
      color = clusterColor(label);
    }

    ctx.save();
    ctx.beginPath();
    ctx.fillStyle = color;
    if (isHovered) {
      ctx.shadowColor = color;
      ctx.shadowBlur = 15;
      ctx.arc(proj.x, proj.y, 6.5, 0, Math.PI * 2);
    } else {
      ctx.globalAlpha = 0.8;
      ctx.arc(proj.x, proj.y, 4.0, 0, Math.PI * 2);
    }
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.lineWidth = isHovered ? 2 : 0.8;
    ctx.strokeStyle = isHovered ? "#f3efe2" : "rgba(12, 14, 13, 0.6)";
    ctx.stroke();
    ctx.restore();
  }

  ctx.restore();
}

function nearestNode(x, y) {
  if (state.viewMode === "corpus") {
    return nearestCorpusNode(x, y);
  }
  if (state.viewMode === "benchmark") {
    return nearestBenchmarkPoint(x, y);
  }
  let best = null;
  let bestDistance = Infinity;
  for (const node of state.nodes) {
    const point = project(node.lon, node.lat);
    const distance = Math.hypot(point.x - x, point.y - y);
    const threshold = Math.max(8, Math.min(18, Math.sqrt(node.totalRoutes) * 0.48));
    if (distance < threshold && distance < bestDistance) {
      best = node;
      bestDistance = distance;
    }
  }
  return best;
}

function updateFlightLabels() {
  els.detailTotalLabel.textContent = "Total routes";
  els.detailInboundLabel.textContent = "Inbound";
  els.detailOutboundLabel.textContent = "Outbound";
  els.detailPotentialLabel.textContent = "Potential";
}

function updateCorpusLabels() {
  els.detailTotalLabel.textContent = "Documents";
  els.detailInboundLabel.textContent = "Mentions";
  els.detailOutboundLabel.textContent = "Sources";
  els.detailPotentialLabel.textContent = "Edges";
}

function updateBenchmarkLabels() {
  els.detailTotalLabel.textContent = "True Passport";
  els.detailInboundLabel.textContent = "Mapmaker Group";
  els.detailOutboundLabel.textContent = "Closeness to City";
  els.detailPotentialLabel.textContent = "Generalization";
}

function updateBenchmarkDetails(node) {
  updateBenchmarkLabels();
  if (!node) {
    els.detailCode.textContent = "C&T";
    els.detailName.textContent = "Cities & Tourists";
    els.detailLocation.textContent = "Hover a point in the scatter plot to inspect its status.";
    els.detailTotal.textContent = "--";
    els.detailInbound.textContent = "--";
    els.detailOutbound.textContent = "--";
    els.detailPotential.textContent = "--";
    return;
  }
  const isTourist = node.trueLabel === -1;
  const mode = state.benchmark.labelMode;
  const label = mode === "true" ? node.trueLabel : (mode === "rbl" ? (node.rblLabel !== undefined ? node.rblLabel : -1) : node.predLabel);
  const isGrouped = label !== -1;
  els.detailCode.textContent = isTourist ? "NOISE" : "CORE";
  els.detailName.textContent = isTourist ? "Wandering Tourist" : "City Resident";
  els.detailLocation.textContent = `Coordinates: (${node.x.toFixed(2)}, ${node.y.toFixed(2)})`;
  els.detailTotal.textContent = isTourist ? "Tourist (Noise)" : `City ${node.trueLabel} Resident`;
  els.detailInbound.textContent = !isGrouped ? "Tourist (Noise)" : `City ${label} Member`;

  const centers = [[5, 5], [-5, 5], [5, -5], [-5, -5]];
  const dist = Math.min(...centers.map(c => Math.hypot(node.x - c[0], node.y - c[1])));
  els.detailOutbound.textContent = `${dist.toFixed(2)} units`;

  if (isTourist && isGrouped) {
    els.detailPotential.textContent = "Blended In (Error)";
  } else if (!isTourist && !isGrouped) {
    els.detailPotential.textContent = "Outlier (Error)";
  } else {
    els.detailPotential.textContent = "Correctly Filtered";
  }
}

function updateDetails(node) {
  if (state.viewMode === "corpus") {
    updateCorpusDetails(node);
    return;
  }
  if (state.viewMode === "benchmark") {
    updateBenchmarkDetails(node);
    return;
  }
  updateFlightLabels();
  if (!node) {
    els.detailCode.textContent = "---";
    els.detailName.textContent = "Hover an airport";
    els.detailLocation.textContent = "Route structure and Hodge potential appear here.";
    els.detailTotal.textContent = "--";
    els.detailInbound.textContent = "--";
    els.detailOutbound.textContent = "--";
    els.detailPotential.textContent = "--";
    return;
  }
  els.detailCode.textContent = node.code;
  els.detailName.textContent = node.name;
  els.detailLocation.textContent = [node.city, node.country].filter(Boolean).join(", ");
  els.detailTotal.textContent = fmt(node.totalRoutes);
  els.detailInbound.textContent = fmt(node.inboundRoutes);
  els.detailOutbound.textContent = fmt(node.outboundRoutes);
  els.detailPotential.textContent = node.potentialNorm === null ? "n/a" : `${Math.round(node.potentialNorm * 100)}%`;
}

function updateCorpusDetails(node) {
  updateCorpusLabels();
  const summary = state.corpus.summary;
  const counts = summary ? summary.counts : null;
  if (!node) {
    els.detailCode.textContent = "DOJ";
    els.detailName.textContent = "Hover a term";
    els.detailLocation.textContent = "Co-mention graph built from official DOJ disclosure PDFs.";
    els.detailTotal.textContent = counts ? fmt(counts.processedDocuments) : "--";
    els.detailInbound.textContent = counts ? fmt(counts.distinctTermsWithMentions) : "--";
    els.detailOutbound.textContent = counts ? fmt(counts.documentsWithMentions) : "--";
    els.detailPotential.textContent = counts ? fmt(counts.graphEdges) : "--";
    return;
  }
  const connectedEdges = state.corpus.edges.filter((edge) => edge.source === node.id || edge.target === node.id);
  const source = node.sampleSources && node.sampleSources[0] ? node.sampleSources[0] : null;
  els.detailCode.textContent = termAbbreviation(node.label);
  els.detailName.textContent = node.label;
  els.detailLocation.textContent = source ? `Sample source: ${source.fileName}` : "Source-text term from DOJ disclosure PDFs.";
  els.detailTotal.textContent = fmt(node.documentCount);
  els.detailInbound.textContent = fmt(node.mentionCount);
  els.detailOutbound.textContent = fmt(node.sampleSources ? node.sampleSources.length : 0);
  els.detailPotential.textContent = fmt(connectedEdges.length);
}

function updateBenchmarkMeters() {
  els.gradientLabel.textContent = "Correct Cities";
  els.curlLabel.textContent = "Filtered Noise";
  els.harmonicLabel.textContent = "Clustering ARI";
  els.gradientMeter.value = 0.994;
  els.curlMeter.value = 0.267;
  els.harmonicMeter.value = 0.875;
}

function updateMeters() {
  if (state.viewMode === "corpus") {
    updateCorpusMeters();
    return;
  }
  if (state.viewMode === "benchmark") {
    updateBenchmarkMeters();
    return;
  }
  if (!state.summary) return;
  const hodge = state.summary.hodge;
  const total = Math.max(1, hodge.gradientNorm + hodge.curlNorm + hodge.harmonicNorm);
  els.gradientLabel.textContent = "Gradient";
  els.curlLabel.textContent = "Curl";
  els.harmonicLabel.textContent = "Harmonic";
  els.gradientMeter.value = hodge.gradientNorm / total;
  els.curlMeter.value = hodge.curlNorm / total;
  els.harmonicMeter.value = hodge.harmonicNorm / total;
}

function updateCorpusMeters() {
  const summary = state.corpus.summary;
  if (!summary) return;
  const statuses = summary.counts.statusCounts || {};
  const total = Math.max(1, summary.counts.processedDocuments || 0);
  els.gradientLabel.textContent = "Processed";
  els.curlLabel.textContent = "Needs OCR";
  els.harmonicLabel.textContent = "Mentioned";
  els.gradientMeter.value = (statuses.processed || 0) / total;
  els.curlMeter.value = (statuses.needs_ocr || 0) / total;
  els.harmonicMeter.value = (summary.counts.documentsWithMentions || 0) / total;
}

function renderBenchmarkClusters() {
  els.clusterList.innerHTML = "";
  const mode = state.benchmark.labelMode;
  const counts = {};
  for (const point of state.benchmark.points) {
    const label = mode === "true" ? point.trueLabel : (mode === "rbl" ? (point.rblLabel !== undefined ? point.rblLabel : -1) : point.predLabel);
    counts[label] = (counts[label] || 0) + 1;
  }
  
  const sortedLabels = Object.keys(counts).map(Number).sort((a, b) => a - b);
  const labelsToRender = sortedLabels.filter(l => l !== -1);
  if (sortedLabels.includes(-1)) {
    labelsToRender.push(-1);
  }
  
  const items = [];
  for (const label of labelsToRender) {
    let name, desc;
    if (label === -1) {
      name = "Wilderness Noise";
      desc = mode === "true" ? "60 Wandering Tourists" : (mode === "rbl" ? "13 Tourists" : "19 Tourists");
    } else {
      name = `City ${label}`;
      desc = mode === "true" ? "135 Citizens" : `Grouped Cluster Member`;
    }
    items.push({ id: label, name: name, desc: desc, count: counts[label] || 0 });
  }

  for (const item of items) {
    const button = document.createElement("button");
    button.className = "cluster-button";
    button.type = "button";
    const color = item.id === -1 ? "#ff4d4d" : clusterColor(item.id);
    button.innerHTML = `
      <span class="cluster-swatch" style="background:${color}"></span>
      <span class="cluster-copy">
        <strong>${item.name}</strong>
        <p>${item.desc}</p>
      </span>
      <span class="cluster-count">${item.count}</span>
    `;
    els.clusterList.appendChild(button);
  }
}

function renderClusters() {
  if (state.viewMode === "corpus") {
    renderCorpusTerms();
    return;
  }
  if (state.viewMode === "benchmark") {
    renderBenchmarkClusters();
    return;
  }
  els.clusterList.innerHTML = "";
  state.clusters
    .filter((cluster) => cluster.id >= 0)
    .sort((a, b) => b.routeTotal - a.routeTotal)
    .forEach((cluster) => {
      const button = document.createElement("button");
      button.className = "cluster-button";
      button.type = "button";
      button.dataset.cluster = cluster.id;
      button.innerHTML = `
        <span class="cluster-swatch" style="background:${clusterColor(cluster.id)}"></span>
        <span class="cluster-copy">
          <strong>${cluster.label}</strong>
          <p>${cluster.topAirports.slice(0, 3).map((airport) => airport.code).join(" / ")}</p>
        </span>
        <span class="cluster-count">${cluster.nodeCount}</span>
      `;
      button.addEventListener("click", () => {
        state.selectedCluster = state.selectedCluster === cluster.id ? null : cluster.id;
        document.querySelectorAll(".cluster-button").forEach((item) => item.classList.remove("active"));
        if (state.selectedCluster !== null) button.classList.add("active");
        draw();
      });
      els.clusterList.appendChild(button);
    });
}

function renderCorpusTerms() {
  els.clusterList.innerHTML = "";
  state.corpus.nodes
    .slice()
    .sort((a, b) => b.documentCount - a.documentCount || b.mentionCount - a.mentionCount)
    .forEach((node, index) => {
      const button = document.createElement("button");
      button.className = "cluster-button corpus-term";
      button.type = "button";
      button.dataset.node = node.id;
      button.innerHTML = `
        <span class="cluster-swatch" style="background:${corpusColor(index)}"></span>
        <span class="cluster-copy">
          <strong>${node.label}</strong>
          <p>${fmt(node.mentionCount)} mentions</p>
        </span>
        <span class="cluster-count">${fmt(node.documentCount)}</span>
      `;
      button.addEventListener("click", () => {
        state.corpus.selectedNode = state.corpus.selectedNode === node.id ? null : node.id;
        document.querySelectorAll(".cluster-button").forEach((item) => item.classList.remove("active"));
        if (state.corpus.selectedNode !== null) button.classList.add("active");
        const selectedNode = state.corpus.selectedNode ? state.corpus.nodeById.get(state.corpus.selectedNode) : null;
        updateDetails(selectedNode);
        draw();
      });
      els.clusterList.appendChild(button);
    });
}

function renderFlightSummary() {
  els.datasetLabel.textContent = state.summary.dataset;
  els.metricOneLabel.textContent = "Airports";
  els.metricOneValue.textContent = fmt(state.summary.counts.selectedAirports);
  els.metricTwoLabel.textContent = "Routes";
  els.metricTwoValue.textContent = fmt(state.summary.counts.visualEdges);
  els.metricThreeLabel.textContent = "Clusters";
  els.metricThreeValue.textContent = fmt(state.summary.counts.clusters);
  els.metricFourLabel.textContent = "Triangles";
  els.metricFourValue.textContent = fmt(state.summary.counts.triangles);
  els.edgeLimitLabel.textContent = "Route density";
  els.edgeLimit.min = "200";
  els.edgeLimit.step = "50";
  els.edgeLimit.max = String(Math.max(200, state.edges.length));
  els.edgeLimit.value = String(Math.min(Math.max(state.edgeLimit, 200), state.edges.length));
  state.edgeLimit = Number(els.edgeLimit.value);
  els.interClusterControl.hidden = false;
  els.sourceLine.textContent = `Source: OpenFlights routes and Natural Earth land. Generated ${new Date(state.summary.generatedAt).toLocaleString()}.`;
}

function renderCorpusSummary() {
  const summary = state.corpus.summary;
  const counts = summary.counts;
  const statuses = counts.statusCounts || {};
  els.datasetLabel.textContent = summary.dataset;
  els.metricOneLabel.textContent = "PDFs";
  els.metricOneValue.textContent = fmt(counts.manifestDocuments);
  els.metricTwoLabel.textContent = "Text PDFs";
  els.metricTwoValue.textContent = fmt(statuses.processed || 0);
  els.metricThreeLabel.textContent = "Needs OCR";
  els.metricThreeValue.textContent = fmt(statuses.needs_ocr || 0);
  els.metricFourLabel.textContent = "Graph edges";
  els.metricFourValue.textContent = fmt(counts.graphEdges);
  els.edgeLimitLabel.textContent = "Graph density";
  els.edgeLimit.min = "25";
  els.edgeLimit.step = "5";
  els.edgeLimit.max = String(Math.max(25, state.corpus.edges.length));
  els.edgeLimit.value = String(Math.min(Math.max(state.edgeLimit, 25), state.corpus.edges.length));
  state.edgeLimit = Number(els.edgeLimit.value);
  els.interClusterControl.hidden = true;
  els.sourceLine.textContent = "Source: DOJ Epstein Library. Graph edges are same-file co-mentions only.";
}

function renderBenchmarkSummary() {
  els.datasetLabel.textContent = "Cities & Tourists Analogy";
  els.metricOneLabel.textContent = "Citizens";
  els.metricOneValue.textContent = "540";
  els.metricTwoLabel.textContent = "Tourists";
  els.metricTwoValue.textContent = "60";
  els.metricThreeLabel.textContent = "Correct";
  els.metricThreeValue.textContent = "553";
  els.metricFourLabel.textContent = "Errors";
  els.metricFourValue.textContent = "47";
  els.sourceLine.textContent = "Visual representation of the 600-sample benchmark dataset, exploring the Bayes error limit.";
}

function setViewMode(viewMode) {
  if (viewMode === "corpus" && !state.corpus.summary) return;
  if (viewMode === "benchmark" && !state.benchmark.points.length) return;
  state.viewMode = viewMode;
  state.hoveredNode = null;
  state.corpus.hoveredNode = null;
  state.benchmark.hoveredPoint = null;
  els.flightViewButton.classList.toggle("active", viewMode === "flights");
  els.corpusViewButton.classList.toggle("active", viewMode === "corpus");
  els.benchmarkViewButton.classList.toggle("active", viewMode === "benchmark");
  els.mainControls.style.display = viewMode === "benchmark" ? "none" : "block";
  els.benchmarkControls.style.display = viewMode === "benchmark" ? "block" : "none";
  if (viewMode === "corpus") {
    renderCorpusSummary();
  } else if (viewMode === "benchmark") {
    renderBenchmarkSummary();
  } else {
    renderFlightSummary();
  }
  renderClusters();
  updateMeters();
  updateDetails(null);
  draw();
}

async function loadData() {
  const [nodes, edges, clusters, summary, land, corpusNodes, corpusEdges, corpusSummary, benchmarkPoints] = await Promise.all([
    fetch("data/openflights/nodes.json").then((response) => response.json()),
    fetch("data/openflights/edges.json").then((response) => response.json()),
    fetch("data/openflights/clusters.json").then((response) => response.json()),
    fetch("data/openflights/summary.json").then((response) => response.json()),
    fetch("data/world/land.geojson").then((response) => response.json()),
    fetch("data/epstein/mention_nodes.json").then((response) => response.json()),
    fetch("data/epstein/mention_edges.json").then((response) => response.json()),
    fetch("data/epstein/summary.json").then((response) => response.json()),
    fetch("data/benchmark.json").then((response) => response.json()),
  ]);

  state.nodes = nodes;
  state.edges = edges.sort((a, b) => b.count - a.count);
  state.clusters = clusters;
  state.summary = summary;
  state.land = land;
  state.nodeById = new Map(nodes.map((node) => [node.id, node]));
  state.corpus.nodes = corpusNodes;
  state.corpus.edges = corpusEdges.sort((a, b) => b.documentCount - a.documentCount);
  state.corpus.summary = corpusSummary;
  state.corpus.nodeById = new Map(corpusNodes.map((node) => [node.id, node]));
  state.benchmark.points = benchmarkPoints;

  resizeCanvas();
  setViewMode("flights");
}

els.edgeLimit.addEventListener("input", (event) => {
  state.edgeLimit = Number(event.target.value);
  draw();
});

els.flightViewButton.addEventListener("click", () => {
  setViewMode("flights");
});

els.corpusViewButton.addEventListener("click", () => {
  setViewMode("corpus");
});

els.benchmarkViewButton.addEventListener("click", () => {
  setViewMode("benchmark");
});

els.showTrueLabelsButton.addEventListener("click", () => {
  state.benchmark.labelMode = "true";
  els.showTrueLabelsButton.classList.add("active");
  els.showPredLabelsButton.classList.remove("active");
  els.showRblLabelsButton.classList.remove("active");
  renderClusters();
  updateDetails(state.benchmark.hoveredPoint);
  draw();
});

els.showPredLabelsButton.addEventListener("click", () => {
  state.benchmark.labelMode = "hodge";
  els.showPredLabelsButton.classList.add("active");
  els.showTrueLabelsButton.classList.remove("active");
  els.showRblLabelsButton.classList.remove("active");
  renderClusters();
  updateDetails(state.benchmark.hoveredPoint);
  draw();
});

els.showRblLabelsButton.addEventListener("click", () => {
  state.benchmark.labelMode = "rbl";
  els.showRblLabelsButton.classList.add("active");
  els.showTrueLabelsButton.classList.remove("active");
  els.showPredLabelsButton.classList.remove("active");
  renderClusters();
  updateDetails(state.benchmark.hoveredPoint);
  draw();
});

els.interClusterToggle.addEventListener("change", (event) => {
  state.showIntercluster = event.target.checked;
  draw();
});

canvas.addEventListener("mousemove", (event) => {
  const rect = canvas.getBoundingClientRect();
  state.mouse.x = event.clientX - rect.left;
  state.mouse.y = event.clientY - rect.top;
  const hovered = nearestNode(state.mouse.x, state.mouse.y);
  
  let currentHovered;
  if (state.viewMode === "corpus") {
    currentHovered = state.corpus.hoveredNode;
  } else if (state.viewMode === "benchmark") {
    currentHovered = state.benchmark.hoveredPoint;
  } else {
    currentHovered = state.hoveredNode;
  }

  if ((hovered && !currentHovered) || (!hovered && currentHovered) || (hovered && currentHovered.id !== hovered.id)) {
    if (state.viewMode === "corpus") {
      state.corpus.hoveredNode = hovered;
    } else if (state.viewMode === "benchmark") {
      state.benchmark.hoveredPoint = hovered;
    } else {
      state.hoveredNode = hovered;
    }
    updateDetails(hovered);
    draw();
  }
});

canvas.addEventListener("mouseleave", () => {
  state.hoveredNode = null;
  state.corpus.hoveredNode = null;
  state.benchmark.hoveredPoint = null;
  updateDetails(null);
  draw();
});

window.addEventListener("resize", resizeCanvas);

loadData().catch((error) => {
  console.error(error);
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="load-error">Failed to load generated atlas artifacts: ${error.message}</div>`,
  );
});
