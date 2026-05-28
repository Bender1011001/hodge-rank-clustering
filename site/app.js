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
  geneHuman: {
    nodes: [],
    edges: [],
    summary: null,
    nodeById: new Map(),
    layout: null,
    hoveredNode: null,
    selectedNode: null,
  },
  geneMouse: {
    nodes: [],
    edges: [],
    summary: null,
    nodeById: new Map(),
    layout: null,
    hoveredNode: null,
    selectedNode: null,
  },
  geneNet1: {
    nodes: [],
    edges: [],
    summary: null,
    nodeById: new Map(),
    layout: null,
    hoveredNode: null,
    selectedNode: null,
  },
  geneNet3: {
    nodes: [],
    edges: [],
    summary: null,
    nodeById: new Map(),
    layout: null,
    hoveredNode: null,
    selectedNode: null,
  },
  geneNet4: {
    nodes: [],
    edges: [],
    summary: null,
    nodeById: new Map(),
    layout: null,
    hoveredNode: null,
    selectedNode: null,
  },
  trade: {
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
  geneHumanViewButton: document.getElementById("geneHumanViewButton"),
  geneMouseViewButton: document.getElementById("geneMouseViewButton"),
  geneNet1ViewButton: document.getElementById("geneNet1ViewButton"),
  geneNet3ViewButton: document.getElementById("geneNet3ViewButton"),
  geneNet4ViewButton: document.getElementById("geneNet4ViewButton"),
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
  tradeViewButton: document.getElementById("tradeViewButton"),
  showTrueLabelsButton: document.getElementById("showTrueLabelsButton"),
  showPredLabelsButton: document.getElementById("showPredLabelsButton"),
  showRblLabelsButton: document.getElementById("showRblLabelsButton"),
  storyGuideToggle: document.getElementById("storyGuideToggle"),
  storyGuideBox: document.getElementById("storyGuideBox"),
  storyStepDetails: document.getElementById("storyStepDetails"),
  legendList: document.getElementById("legendList"),
  storyStep1: document.getElementById("storyStep1"),
  storyStep2: document.getElementById("storyStep2"),
  storyStep3: document.getElementById("storyStep3"),
  storyStep4: document.getElementById("storyStep4"),
  storyStep5: document.getElementById("storyStep5"),
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

function buildGraphLayout(viewKey) {
  const box = chartBox();
  const subState = state[viewKey];

  if (viewKey === "trade") {
    const nodes = subState.nodes.map((node, index) => {
      // Longitude: map -180 to 180 to box width (with 45px padding)
      const x = box.x + 45 + ((node.longitude - (-180)) / 360) * (box.width - 90);
      // Potential: map 0.0 (top/supplier) to 1.0 (bottom/consumer).
      // Since exporters have low potential, putting them at the top means we map potential directly to Y (since 0 potential = top).
      const y = box.y + 45 + node.potentialNorm * (box.height - 90);
      return {
        ...node,
        index,
        x,
        y,
        vx: 0,
        vy: 0,
        radius: Math.max(6, Math.min(22, Math.log10(Math.max(1e8, node.gdp)) * 1.5)),
      };
    });
    const nodeById = new Map(nodes.map((node) => [node.id, node]));
    const edges = subState.edges
      .map((edge) => ({
        ...edge,
        sourceNode: nodeById.get(edge.source),
        targetNode: nodeById.get(edge.target),
      }))
      .filter((edge) => edge.sourceNode && edge.targetNode);

    subState.layout = {
      width: state.width,
      height: state.height,
      box,
      nodes,
      edges,
      nodeById,
    };
    return subState.layout;
  }

  const centerX = box.x + box.width / 2;
  const centerY = box.y + box.height / 2;
  const radiusX = box.width * 0.39;
  const radiusY = box.height * 0.38;
  const nodes = subState.nodes.map((node, index) => {
    const angle = (index / Math.max(1, subState.nodes.length)) * Math.PI * 2 - Math.PI / 2;
    return {
      ...node,
      index,
      x: centerX + Math.cos(angle) * radiusX,
      y: centerY + Math.sin(angle) * radiusY,
      vx: 0,
      vy: 0,
      radius: Math.max(7, Math.min(24, Math.sqrt(node.documentCount) * 2.2)),
    };
  });
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const edges = subState.edges
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
        const force = 1800 / (distance * distance);
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
      const desired = 95;
      const strength = 0.004;
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

  subState.layout = {
    width: state.width,
    height: state.height,
    box,
    nodes,
    edges,
    nodeById,
  };
  return subState.layout;
}

function getGraphLayout(viewKey) {
  const subState = state[viewKey];
  if (
    subState.layout &&
    subState.layout.width === state.width &&
    subState.layout.height === state.height
  ) {
    return subState.layout;
  }
  return buildGraphLayout(viewKey);
}

function geneColor(potentialNorm, kind) {
  if (potentialNorm === null || potentialNorm === undefined) {
    return kind === "tf" ? "#58c6a4" : "#7aa6ff";
  }
  const hue = 110 + potentialNorm * 100;
  return `hsl(${hue}, 85%, 60%)`;
}

function drawGeneGraph(viewKey) {
  const layout = getGraphLayout(viewKey);
  const { box } = layout;
  const subState = state[viewKey];
  const selectedId = subState.selectedNode;
  const hoveredId = subState.hoveredNode ? subState.hoveredNode.id : null;

  ctx.save();
  ctx.beginPath();
  ctx.rect(box.x, box.y, box.width, box.height);
  ctx.clip();

  const networkGradient = ctx.createLinearGradient(box.x, box.y, box.x + box.width, box.y + box.height);
  networkGradient.addColorStop(0, "rgba(18, 30, 24, 0.52)");
  networkGradient.addColorStop(0.55, "rgba(10, 18, 20, 0.32)");
  networkGradient.addColorStop(1, "rgba(22, 14, 30, 0.44)");
  ctx.fillStyle = networkGradient;
  ctx.fillRect(box.x, box.y, box.width, box.height);

  ctx.strokeStyle = "rgba(243, 239, 226, 0.06)";
  ctx.lineWidth = 0.8;
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
    const bend = Math.min(30, Math.max(6, distance * 0.06));

    ctx.quadraticCurveTo(midX - (dy / distance) * bend, midY + (dx / distance) * bend, target.x, target.y);
    ctx.strokeStyle = active ? "rgba(243, 239, 226, 0.8)" : "rgba(243, 239, 226, 0.11)";
    ctx.globalAlpha = active ? 1.0 : 0.4;
    ctx.lineWidth = active ? 2.0 : 1.0;
    ctx.stroke();

    if (active && distance > 30) {
      const t = 0.5;
      const ax = (1-t)*(1-t)*source.x + 2*(1-t)*t*(midX - (dy / distance) * bend) + t*t*target.x;
      const ay = (1-t)*(1-t)*source.y + 2*(1-t)*t*(midY + (dx / distance) * bend) + t*t*target.y;
      const tx = 2*(1-t)*((midX - (dy / distance) * bend) - source.x) + 2*t*(target.x - (midX - (dy / distance) * bend));
      const ty = 2*(1-t)*((midY + (dx / distance) * bend) - source.y) + 2*t*(target.y - (midY + (dx / distance) * bend));
      const angle = Math.atan2(ty, tx);

      ctx.save();
      ctx.translate(ax, ay);
      ctx.rotate(angle);
      ctx.beginPath();
      ctx.moveTo(-6, -4);
      ctx.lineTo(2, 0);
      ctx.lineTo(-6, 4);
      ctx.closePath();
      ctx.fillStyle = "#f3efe2";
      ctx.fill();
      ctx.restore();
    }
  }
  ctx.globalAlpha = 1.0;

  const sortedNodes = [...layout.nodes].sort((a, b) => a.documentCount - b.documentCount);
  for (const node of sortedNodes) {
    const active = !selectedId || node.id === selectedId || visibleEdges.some((edge) => edge.source === node.id || edge.target === node.id);
    const highlighted = node.id === selectedId || node.id === hoveredId;
    const color = geneColor(node.potentialNorm, node.kind);

    ctx.save();
    ctx.globalAlpha = active ? 1 : 0.22;
    ctx.beginPath();
    ctx.fillStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = highlighted ? 24 : 9;

    const r = highlighted ? node.radius + 3 : node.radius;
    ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    ctx.lineWidth = highlighted ? 2 : 1;
    ctx.strokeStyle = highlighted ? "#f3efe2" : "rgba(12, 14, 13, 0.85)";
    ctx.stroke();

    if (node.kind === "tf") {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r * 0.45, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.globalAlpha = active ? 0.8 : 0.3;
      ctx.fill();
    }

    ctx.restore();
  }

  ctx.font = "italic 600 11px Inter, system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (const node of layout.nodes) {
    const highlighted = node.id === selectedId || node.id === hoveredId;
    const tf = node.kind === "tf";
    if (!highlighted && node.documentCount < 10 && !tf) continue;
    ctx.fillStyle = highlighted ? "#f3efe2" : (tf ? "rgba(243, 239, 226, 0.88)" : "rgba(243, 239, 226, 0.65)");
    ctx.fillText(node.label, node.x, node.y + node.radius + 6);
  }

  ctx.restore();
}

function nearestGeneNode(viewKey, x, y) {
  const layout = getGraphLayout(viewKey);
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
  if (state.viewMode === "geneHuman") {
    drawGeneGraph("geneHuman");
    return;
  }
  if (state.viewMode === "geneMouse") {
    drawGeneGraph("geneMouse");
    return;
  }
  if (state.viewMode === "geneNet1") {
    drawGeneGraph("geneNet1");
    return;
  }
  if (state.viewMode === "geneNet3") {
    drawGeneGraph("geneNet3");
    return;
  }
  if (state.viewMode === "geneNet4") {
    drawGeneGraph("geneNet4");
    return;
  }
  if (state.viewMode === "trade") {
    drawTradeGraph();
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
  if (state.viewMode === "geneHuman") {
    return nearestGeneNode("geneHuman", x, y);
  }
  if (state.viewMode === "geneMouse") {
    return nearestGeneNode("geneMouse", x, y);
  }
  if (state.viewMode === "geneNet1") {
    return nearestGeneNode("geneNet1", x, y);
  }
  if (state.viewMode === "geneNet3") {
    return nearestGeneNode("geneNet3", x, y);
  }
  if (state.viewMode === "geneNet4") {
    return nearestGeneNode("geneNet4", x, y);
  }
  if (state.viewMode === "trade") {
    return nearestGeneNode("trade", x, y);
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

function updateGeneLabels() {
  els.detailTotalLabel.textContent = "Connectivity";
  els.detailInboundLabel.textContent = "Type";
  els.detailOutboundLabel.textContent = "Potential Value";
  els.detailPotentialLabel.textContent = "Potential";
}

function updateGeneDetails(viewKey, node) {
  updateGeneLabels();
  const summary = state[viewKey].summary;
  let name = "";
  if (viewKey === "geneHuman") name = "Human";
  else if (viewKey === "geneMouse") name = "Mouse";
  else if (viewKey === "geneNet1") name = "Net 1 (In Silico)";
  else if (viewKey === "geneNet3") name = "Net 3 (E. coli)";
  else if (viewKey === "geneNet4") name = "Net 4 (Yeast)";

  if (!node) {
    els.detailCode.textContent = "GRN";
    els.detailName.textContent = `Hover a gene (${name})`;
    els.detailLocation.textContent = viewKey.startsWith("geneNet") ? "Gene Regulatory Network from DREAM5 Challenge." : "Transcriptional regulatory network from GRNPedia TRRUST database.";
    els.detailTotal.textContent = summary ? fmt(summary.counts.genes) : "--";
    els.detailInbound.textContent = summary ? fmt(summary.counts.interactions) : "--";
    els.detailOutbound.textContent = summary ? fmt(summary.counts.triangles) : "--";
    els.detailPotential.textContent = "--";
    return;
  }
  els.detailCode.textContent = node.kind.toUpperCase();
  els.detailName.textContent = node.label;
  els.detailLocation.textContent = node.kind === "tf" ? "Transcription Factor (Regulator)" : "Target Gene";
  els.detailTotal.textContent = `${node.documentCount} connections`;
  els.detailInbound.textContent = node.kind === "tf" ? "Master Regulator" : "Downstream Target";
  els.detailOutbound.textContent = `${Math.round(node.potentialNorm * 100)}%`;
  els.detailPotential.textContent = `${Math.round(node.potentialNorm * 100)}%`;
}

function updateDetails(node) {
  if (state.viewMode === "corpus") {
    updateCorpusDetails(node);
    return;
  }
  if (state.viewMode === "geneHuman") {
    updateGeneDetails("geneHuman", node);
    return;
  }
  if (state.viewMode === "geneMouse") {
    updateGeneDetails("geneMouse", node);
    return;
  }
  if (state.viewMode === "geneNet1") {
    updateGeneDetails("geneNet1", node);
    return;
  }
  if (state.viewMode === "geneNet3") {
    updateGeneDetails("geneNet3", node);
    return;
  }
  if (state.viewMode === "geneNet4") {
    updateGeneDetails("geneNet4", node);
    return;
  }
  if (state.viewMode === "trade") {
    updateTradeDetails(node);
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

function updateGeneMeters(viewKey) {
  const summary = state[viewKey].summary;
  if (!summary) return;
  const hodge = summary.hodge;
  const total = Math.max(1, hodge.gradientNorm + hodge.curlNorm + hodge.harmonicNorm);
  els.gradientLabel.textContent = "Gradient";
  els.curlLabel.textContent = "Curl";
  els.harmonicLabel.textContent = "Harmonic";
  els.gradientMeter.value = hodge.gradientNorm / total;
  els.curlMeter.value = hodge.curlNorm / total;
  els.harmonicMeter.value = hodge.harmonicNorm / total;
}

function updateMeters() {
  if (state.viewMode === "corpus") {
    updateCorpusMeters();
    return;
  }
  if (state.viewMode === "geneHuman") {
    updateGeneMeters("geneHuman");
    return;
  }
  if (state.viewMode === "geneMouse") {
    updateGeneMeters("geneMouse");
    return;
  }
  if (state.viewMode === "geneNet1") {
    updateGeneMeters("geneNet1");
    return;
  }
  if (state.viewMode === "geneNet3") {
    updateGeneMeters("geneNet3");
    return;
  }
  if (state.viewMode === "geneNet4") {
    updateGeneMeters("geneNet4");
    return;
  }
  if (state.viewMode === "trade") {
    updateGeneMeters("trade");
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

function renderGeneClusters(viewKey) {
  els.clusterList.innerHTML = "";
  const subState = state[viewKey];
  const summary = subState.summary;
  if (!summary) return;

  const headerReg = document.createElement("div");
  headerReg.className = "legend-header";
  headerReg.style = "font-size:0.88rem; font-weight:700; margin:10px 0 6px 0; color:#58c6a4; letter-spacing:0.5px; text-transform:uppercase;";
  headerReg.textContent = "Top Master Regulators (Basins)";
  els.clusterList.appendChild(headerReg);

  summary.top_regulators.forEach((reg) => {
    const button = document.createElement("button");
    button.className = "cluster-button gene-button";
    button.type = "button";
    const active = subState.selectedNode === reg.gene;
    if (active) button.classList.add("active");
    button.innerHTML = `
      <span class="cluster-swatch" style="background:#58c6a4"></span>
      <span class="cluster-copy">
        <strong>${reg.gene}</strong>
        <p>Rank #${reg.rank} Regulator</p>
      </span>
      <span class="cluster-count">${Math.round(reg.potential * 100)}%</span>
    `;
    button.addEventListener("click", () => {
      const layout = getGraphLayout(viewKey);
      const node = layout.nodes.find(n => n.id === reg.gene);
      if (node) {
        subState.selectedNode = subState.selectedNode === node.id ? null : node.id;
        document.querySelectorAll(".cluster-button").forEach((item) => item.classList.remove("active"));
        if (subState.selectedNode !== null) button.classList.add("active");
        updateDetails(subState.selectedNode ? node : null);
        draw();
      }
    });
    els.clusterList.appendChild(button);
  });

  const headerTgt = document.createElement("div");
  headerTgt.className = "legend-header";
  headerTgt.style = "font-size:0.88rem; font-weight:700; margin:18px 0 6px 0; color:#7aa6ff; letter-spacing:0.5px; text-transform:uppercase;";
  headerTgt.textContent = "Top Target Genes (Sinks)";
  els.clusterList.appendChild(headerTgt);

  summary.top_targets.forEach((tgt) => {
    const button = document.createElement("button");
    button.className = "cluster-button gene-button";
    button.type = "button";
    const active = subState.selectedNode === tgt.gene;
    if (active) button.classList.add("active");
    button.innerHTML = `
      <span class="cluster-swatch" style="background:#7aa6ff"></span>
      <span class="cluster-copy">
        <strong>${tgt.gene}</strong>
        <p>Rank #${tgt.rank} Target</p>
      </span>
      <span class="cluster-count">${Math.round(tgt.potential * 100)}%</span>
    `;
    button.addEventListener("click", () => {
      const layout = getGraphLayout(viewKey);
      const node = layout.nodes.find(n => n.id === tgt.gene);
      if (node) {
        subState.selectedNode = subState.selectedNode === node.id ? null : node.id;
        document.querySelectorAll(".cluster-button").forEach((item) => item.classList.remove("active"));
        if (subState.selectedNode !== null) button.classList.add("active");
        updateDetails(subState.selectedNode ? node : null);
        draw();
      }
    });
    els.clusterList.appendChild(button);
  });
}

function renderClusters() {
  if (state.viewMode === "corpus") {
    renderCorpusTerms();
    return;
  }
  if (state.viewMode === "geneHuman") {
    renderGeneClusters("geneHuman");
    return;
  }
  if (state.viewMode === "geneMouse") {
    renderGeneClusters("geneMouse");
    return;
  }
  if (state.viewMode === "geneNet1") {
    renderGeneClusters("geneNet1");
    return;
  }
  if (state.viewMode === "geneNet3") {
    renderGeneClusters("geneNet3");
    return;
  }
  if (state.viewMode === "geneNet4") {
    renderGeneClusters("geneNet4");
    return;
  }
  if (state.viewMode === "trade") {
    renderTradeClusters();
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

function updateLegend(viewMode) {
  if (!els.legendList) return;
  if (viewMode === "corpus") {
    els.legendList.innerHTML = `
      <li><strong>Gradient:</strong> <span class="analogy-label">"Core Target"</span> - central investigation topics or key entities.</li>
      <li><strong>Curl:</strong> <span class="analogy-label">"Local Gossip"</span> - tight local loops where entities are co-mentioned.</li>
      <li><strong>Harmonic:</strong> <span class="analogy-label">"Indirect Orbits"</span> - larger circular paths of documents linking nodes.</li>
    `;
  } else if (viewMode === "geneHuman" || viewMode === "geneMouse" || viewMode.startsWith("geneNet")) {
    els.legendList.innerHTML = `
      <li><strong>Gradient:</strong> <span class="analogy-label">"Regulator Waterfall"</span> - flow going from low potential basins (sources/TFs) to high potential sinks (target genes).</li>
      <li><strong>Curl:</strong> <span class="analogy-label">"Regulatory Whirlpools"</span> - circular feedback loops of regulatory interactions.</li>
      <li><strong>Harmonic:</strong> <span class="analogy-label">"Indirect Orbits"</span> - larger cycles routing through non-triangular pathways.</li>
    `;
  } else if (viewMode === "trade") {
    els.legendList.innerHTML = `
      <li><strong>Gradient:</strong> <span class="analogy-label">"Supply Chain Waterfall"</span> - flow going from low-potential upstream net exporters to high-potential downstream net importers.</li>
      <li><strong>Curl:</strong> <span class="analogy-label">"Regional Subcontracting"</span> - circular trade loops within regional trade networks (e.g. EU parts circulation).</li>
      <li><strong>Harmonic:</strong> <span class="analogy-label">"Global Balancing Loops"</span> - systemic circular trading loops traversing multiple continents.</li>
    `;
  } else if (viewMode === "benchmark") {
    els.legendList.innerHTML = `
      <li><strong>Gradient:</strong> <span class="analogy-label">"City Core"</span> - stable, dense coordinate clusters of true residents.</li>
      <li><strong>Curl:</strong> <span class="analogy-label">"Wandering Tourists"</span> - random points flagged as outliers (noise).</li>
      <li><strong>Harmonic:</strong> <span class="analogy-label">"Bayes Limit"</span> - the optimal accuracy separating noise from signal.</li>
    `;
  } else {
    els.legendList.innerHTML = `
      <li><strong>Gradient:</strong> <span class="analogy-label">"Hub Waterfall"</span> - one-way routes draining towards regional hub cities.</li>
      <li><strong>Curl:</strong> <span class="analogy-label">"Local Whirlpools"</span> - circular 3-airport loops (e.g. feeders).</li>
      <li><strong>Harmonic:</strong> <span class="analogy-label">"Global Orbits"</span> - large loops winding around the network boundaries.</li>
    `;
  }
}

function renderGeneSummary(viewKey) {
  const subState = state[viewKey];
  const summary = subState.summary;
  let name = "";
  if (viewKey === "geneHuman") name = "Human";
  else if (viewKey === "geneMouse") name = "Mouse";
  else if (viewKey === "geneNet1") name = "Net 1 (In Silico)";
  else if (viewKey === "geneNet3") name = "Net 3 (E. coli)";
  else if (viewKey === "geneNet4") name = "Net 4 (Yeast)";

  els.datasetLabel.textContent = viewKey.startsWith("geneNet") ? `DREAM5 ${name} Regulatory Network` : `TRRUST ${name} Regulatory Network`;
  els.metricOneLabel.textContent = "Genes";
  els.metricOneValue.textContent = fmt(summary.counts.genes);
  els.metricTwoLabel.textContent = "Interactions";
  els.metricTwoValue.textContent = fmt(summary.counts.interactions);
  els.metricThreeLabel.textContent = "Triangles";
  els.metricThreeValue.textContent = fmt(summary.counts.triangles);
  els.metricFourLabel.textContent = "Sub-edges";
  els.metricFourValue.textContent = fmt(subState.edges.length);
  els.edgeLimitLabel.textContent = "Graph density";
  els.edgeLimit.min = "10";
  els.edgeLimit.step = "5";
  els.edgeLimit.max = String(Math.max(10, subState.edges.length));
  els.edgeLimit.value = String(Math.min(Math.max(state.edgeLimit, 10), subState.edges.length));
  state.edgeLimit = Number(els.edgeLimit.value);
  els.interClusterControl.hidden = true;
  els.sourceLine.textContent = viewKey.startsWith("geneNet") ? `Source: DREAM5 Challenge. Top 120 nodes shown.` : `Source: GRNPedia TRRUST ${name} v2. Top 120 nodes shown.`;
}

function setViewMode(viewMode) {
  if (viewMode === "corpus" && !state.corpus.summary) return;
  if (viewMode === "benchmark" && !state.benchmark.points.length) return;
  if (viewMode === "geneHuman" && !state.geneHuman.summary) return;
  if (viewMode === "geneMouse" && !state.geneMouse.summary) return;
  if (viewMode === "geneNet1" && !state.geneNet1.summary) return;
  if (viewMode === "geneNet3" && !state.geneNet3.summary) return;
  if (viewMode === "geneNet4" && !state.geneNet4.summary) return;
  if (viewMode === "trade" && !state.trade.summary) return;
  state.viewMode = viewMode;
  state.hoveredNode = null;
  state.corpus.hoveredNode = null;
  state.benchmark.hoveredPoint = null;
  state.geneHuman.hoveredNode = null;
  state.geneMouse.hoveredNode = null;
  state.geneNet1.hoveredNode = null;
  state.geneNet3.hoveredNode = null;
  state.geneNet4.hoveredNode = null;
  state.trade.hoveredNode = null;
  els.flightViewButton.classList.toggle("active", viewMode === "flights");
  els.corpusViewButton.classList.toggle("active", viewMode === "corpus");
  els.geneHumanViewButton.classList.toggle("active", viewMode === "geneHuman");
  els.geneMouseViewButton.classList.toggle("active", viewMode === "geneMouse");
  els.geneNet1ViewButton.classList.toggle("active", viewMode === "geneNet1");
  els.geneNet3ViewButton.classList.toggle("active", viewMode === "geneNet3");
  els.geneNet4ViewButton.classList.toggle("active", viewMode === "geneNet4");
  els.benchmarkViewButton.classList.toggle("active", viewMode === "benchmark");
  els.tradeViewButton.classList.toggle("active", viewMode === "trade");
  els.mainControls.style.display = (viewMode === "benchmark" || viewMode === "trade") ? "none" : "block";
  els.benchmarkControls.style.display = viewMode === "benchmark" ? "block" : "none";
  if (viewMode === "corpus") {
    renderCorpusSummary();
  } else if (viewMode === "benchmark") {
    renderBenchmarkSummary();
  } else if (viewMode === "geneHuman") {
    renderGeneSummary("geneHuman");
  } else if (viewMode === "geneMouse") {
    renderGeneSummary("geneMouse");
  } else if (viewMode === "geneNet1") {
    renderGeneSummary("geneNet1");
  } else if (viewMode === "geneNet3") {
    renderGeneSummary("geneNet3");
  } else if (viewMode === "geneNet4") {
    renderGeneSummary("geneNet4");
  } else if (viewMode === "trade") {
    renderTradeSummary();
  } else {
    renderFlightSummary();
  }
  updateLegend(viewMode);
  renderClusters();
  updateMeters();
  updateDetails(null);
  draw();
}

async function loadData() {
  const [
    nodes, edges, clusters, summary, land,
    corpusNodes, corpusEdges, corpusSummary,
    benchmarkPoints,
    trrustHumanNodes, trrustHumanEdges, trrustMouseNodes, trrustMouseEdges, trrustSummary,
    net1Nodes, net1Edges, net3Nodes, net3Edges, net4Nodes, net4Edges, dream5Summary,
    tradeNodes, tradeEdges, tradeSummary,
  ] = await Promise.all([
    fetch("data/openflights/nodes.json").then((response) => response.json()),
    fetch("data/openflights/edges.json").then((response) => response.json()),
    fetch("data/openflights/clusters.json").then((response) => response.json()),
    fetch("data/openflights/summary.json").then((response) => response.json()),
    fetch("data/world/land.geojson").then((response) => response.json()),
    fetch("data/epstein/mention_nodes.json").then((response) => response.json()),
    fetch("data/epstein/mention_edges.json").then((response) => response.json()),
    fetch("data/epstein/summary.json").then((response) => response.json()),
    fetch("data/benchmark.json").then((response) => response.json()),
    fetch("data/trrust/human_nodes.json").then((response) => response.json()),
    fetch("data/trrust/human_edges.json").then((response) => response.json()),
    fetch("data/trrust/mouse_nodes.json").then((response) => response.json()),
    fetch("data/trrust/mouse_edges.json").then((response) => response.json()),
    fetch("data/trrust/summary.json").then((response) => response.json()),
    fetch("data/dream5/net1_nodes.json").then((response) => response.json()),
    fetch("data/dream5/net1_edges.json").then((response) => response.json()),
    fetch("data/dream5/net3_nodes.json").then((response) => response.json()),
    fetch("data/dream5/net3_edges.json").then((response) => response.json()),
    fetch("data/dream5/net4_nodes.json").then((response) => response.json()),
    fetch("data/dream5/net4_edges.json").then((response) => response.json()),
    fetch("data/dream5/summary.json").then((response) => response.json()),
    fetch("data/trade/nodes.json").then((response) => response.json()),
    fetch("data/trade/edges.json").then((response) => response.json()),
    fetch("data/trade/summary.json").then((response) => response.json()),
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

  state.geneHuman.nodes = trrustHumanNodes;
  state.geneHuman.edges = trrustHumanEdges;
  state.geneHuman.summary = trrustSummary.human;
  state.geneHuman.nodeById = new Map(trrustHumanNodes.map((node) => [node.id, node]));

  state.geneMouse.nodes = trrustMouseNodes;
  state.geneMouse.edges = trrustMouseEdges;
  state.geneMouse.summary = trrustSummary.mouse;
  state.geneMouse.nodeById = new Map(trrustMouseNodes.map((node) => [node.id, node]));

  state.geneNet1.nodes = net1Nodes;
  state.geneNet1.edges = net1Edges;
  state.geneNet1.summary = dream5Summary.net1;
  state.geneNet1.nodeById = new Map(net1Nodes.map((node) => [node.id, node]));

  state.geneNet3.nodes = net3Nodes;
  state.geneNet3.edges = net3Edges;
  state.geneNet3.summary = dream5Summary.net3;
  state.geneNet3.nodeById = new Map(net3Nodes.map((node) => [node.id, node]));

  state.geneNet4.nodes = net4Nodes;
  state.geneNet4.edges = net4Edges;
  state.geneNet4.summary = dream5Summary.net4;
  state.geneNet4.nodeById = new Map(net4Nodes.map((node) => [node.id, node]));

  state.trade.nodes = tradeNodes;
  state.trade.edges = tradeEdges;
  state.trade.summary = tradeSummary;
  state.trade.nodeById = new Map(tradeNodes.map((node) => [node.id, node]));

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

els.geneHumanViewButton.addEventListener("click", () => {
  setViewMode("geneHuman");
});

els.geneMouseViewButton.addEventListener("click", () => {
  setViewMode("geneMouse");
});

els.geneNet1ViewButton.addEventListener("click", () => {
  setViewMode("geneNet1");
});

els.geneNet3ViewButton.addEventListener("click", () => {
  setViewMode("geneNet3");
});

els.geneNet4ViewButton.addEventListener("click", () => {
  setViewMode("geneNet4");
});

els.benchmarkViewButton.addEventListener("click", () => {
  setViewMode("benchmark");
});

els.tradeViewButton.addEventListener("click", () => {
  setViewMode("trade");
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
  } else if (state.viewMode === "geneHuman") {
    currentHovered = state.geneHuman.hoveredNode;
  } else if (state.viewMode === "geneMouse") {
    currentHovered = state.geneMouse.hoveredNode;
  } else if (state.viewMode === "geneNet1") {
    currentHovered = state.geneNet1.hoveredNode;
  } else if (state.viewMode === "geneNet3") {
    currentHovered = state.geneNet3.hoveredNode;
  } else if (state.viewMode === "geneNet4") {
    currentHovered = state.geneNet4.hoveredNode;
  } else if (state.viewMode === "trade") {
    currentHovered = state.trade.hoveredNode;
  } else if (state.viewMode === "benchmark") {
    currentHovered = state.benchmark.hoveredPoint;
  } else {
    currentHovered = state.hoveredNode;
  }

  if ((hovered && !currentHovered) || (!hovered && currentHovered) || (hovered && currentHovered.id !== hovered.id)) {
    if (state.viewMode === "corpus") {
      state.corpus.hoveredNode = hovered;
    } else if (state.viewMode === "geneHuman") {
      state.geneHuman.hoveredNode = hovered;
    } else if (state.viewMode === "geneMouse") {
      state.geneMouse.hoveredNode = hovered;
    } else if (state.viewMode === "geneNet1") {
      state.geneNet1.hoveredNode = hovered;
    } else if (state.viewMode === "geneNet3") {
      state.geneNet3.hoveredNode = hovered;
    } else if (state.viewMode === "geneNet4") {
      state.geneNet4.hoveredNode = hovered;
    } else if (state.viewMode === "trade") {
      state.trade.hoveredNode = hovered;
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
  state.geneHuman.hoveredNode = null;
  state.geneMouse.hoveredNode = null;
  state.geneNet1.hoveredNode = null;
  state.geneNet3.hoveredNode = null;
  state.geneNet4.hoveredNode = null;
  state.trade.hoveredNode = null;
  state.benchmark.hoveredPoint = null;
  updateDetails(null);
  draw();
});

// --- Storyteller & Layperson Guide Logic ---
if (els.storyGuideToggle) {
  els.storyGuideToggle.addEventListener("click", () => {
    const visible = els.storyGuideBox.style.display === "flex";
    els.storyGuideBox.style.display = visible ? "none" : "flex";
    els.storyGuideToggle.classList.toggle("active", !visible);
  });
}

function clearActiveSteps() {
  const steps = [els.storyStep1, els.storyStep2, els.storyStep3, els.storyStep4, els.storyStep5];
  steps.forEach(btn => btn && btn.classList.remove("active"));
}

if (els.storyStep1) {
  els.storyStep1.addEventListener("click", () => {
    setViewMode("flights");
    clearActiveSteps();
    els.storyStep1.classList.add("active");

    const minNode = state.nodes.reduce((min, n) => {
      if (n.potentialNorm === null) return min;
      if (!min) return n;
      return n.potentialNorm < min.potentialNorm ? n : min;
    }, null) || state.nodes[0];

    if (minNode) {
      state.hoveredNode = minNode;
      state.selectedCluster = minNode.cluster;
      els.edgeLimit.value = "600";
      state.edgeLimit = 600;
      updateDetails(minNode);
      updateMeters();
      draw();
      els.storyStepDetails.innerHTML = `
        <strong>📍 Hub Waterfall (Gradient Sink)</strong><br>
        Flights naturally drain into regional hubs. We highlighted <b>${minNode.city || minNode.name} (${minNode.code})</b>, which has the lowest potential (${Math.round((minNode.potentialNorm || 0) * 100)}%). Think of it as a massive gravity well on the map.
      `;
    }
  });
}

if (els.storyStep2) {
  els.storyStep2.addEventListener("click", () => {
    setViewMode("flights");
    clearActiveSteps();
    els.storyStep2.classList.add("active");

    let maxCurlEdge = null;
    let maxCurl = -1;
    for (const edge of state.edges) {
      if (edge.hodge && edge.hodge.curl !== undefined) {
        const absCurl = Math.abs(edge.hodge.curl);
        if (absCurl > maxCurl) {
          maxCurl = absCurl;
          maxCurlEdge = edge;
        }
      }
    }

    if (maxCurlEdge) {
      const node = state.nodeById.get(maxCurlEdge.source);
      if (node) {
        state.hoveredNode = node;
        state.selectedCluster = node.cluster;
        els.edgeLimit.value = "400";
        state.edgeLimit = 400;
        updateDetails(node);
        updateMeters();
        draw();
        els.storyStepDetails.innerHTML = `
          <strong>🌀 Local Whirlpools (Curl Loops)</strong><br>
          These represent circular "rock-paper-scissors" connections between three nearby airports. We highlighted <b>${node.city} (${node.code})</b>. Part of its flow is trapped in regional loops, defying the main hub hierarchy!
        `;
      }
    } else {
      els.storyStepDetails.innerHTML = `No high-curl loops found in the current selection. Try increasing flight data density.`;
    }
  });
}

if (els.storyStep3) {
  els.storyStep3.addEventListener("click", () => {
    setViewMode("flights");
    clearActiveSteps();
    els.storyStep3.classList.add("active");

    let maxHarmEdge = null;
    let maxHarm = -1;
    for (const edge of state.edges) {
      if (edge.hodge && edge.hodge.harmonic !== undefined) {
        const absHarm = Math.abs(edge.hodge.harmonic);
        if (absHarm > maxHarm) {
          maxHarm = absHarm;
          maxHarmEdge = edge;
        }
      }
    }

    if (maxHarmEdge) {
      const node = state.nodeById.get(maxHarmEdge.source);
      if (node) {
        state.hoveredNode = node;
        state.selectedCluster = node.cluster;
        els.edgeLimit.value = "800";
        state.edgeLimit = 800;
        updateDetails(node);
        updateMeters();
        draw();
        els.storyStepDetails.innerHTML = `
          <strong>🌍 Global Orbits (Harmonic Flow)</strong><br>
          These are large circular flows that route around the entire network boundaries. We selected <b>${node.city} (${node.code})</b>. Click the <span class="interactive-action-link" id="actionToggleInter">Inter-cluster toggle</span> to see how these routes orbit between clusters.
        `;
        const toggleBtn = document.getElementById("actionToggleInter");
        if (toggleBtn) {
          toggleBtn.addEventListener("click", () => {
            els.interClusterToggle.checked = !els.interClusterToggle.checked;
            state.showIntercluster = els.interClusterToggle.checked;
            draw();
          });
        }
      }
    } else {
      els.storyStepDetails.innerHTML = `No harmonic orbits found in the current selection.`;
    }
  });
}

if (els.storyStep4) {
  els.storyStep4.addEventListener("click", () => {
    setViewMode("corpus");
    clearActiveSteps();
    els.storyStep4.classList.add("active");

    const epsteinNode = state.corpus.nodes.find(n => n.label.includes("Epstein")) || state.corpus.nodes[0];
    if (epsteinNode) {
      state.corpus.selectedNode = epsteinNode.id;
      updateDetails(epsteinNode);
      updateMeters();
      draw();
      els.storyStepDetails.innerHTML = `
        <strong>🔍 DOJ Investigation Centrality</strong><br>
        This maps connections in Epstein DOJ disclosure documents. We selected <b>${epsteinNode.label}</b>, which sits at the bottom of the "blame waterfall" (gradient sink). Notice how terms cluster tightly around core targets.
      `;
    }
  });
}

if (els.storyStep5) {
  els.storyStep5.addEventListener("click", () => {
    setViewMode("benchmark");
    clearActiveSteps();
    els.storyStep5.classList.add("active");
    els.showPredLabelsButton.click();

    els.storyStepDetails.innerHTML = `
      <strong>🎮 The Cities & Tourists Game</strong><br>
      There are 4 cities and 60 tourists wandering the wilderness (noise). Try toggling <span class="interactive-action-link" id="actionShowTrue">True Labels</span>, <span class="interactive-action-link" id="actionShowHodge">Hodge</span>, or <span class="interactive-action-link" id="actionShowRbl">RBL</span> to watch the potential field sweep away the noise!
    `;

    const showTrue = document.getElementById("actionShowTrue");
    const showHodge = document.getElementById("actionShowHodge");
    const showRbl = document.getElementById("actionShowRbl");

    if (showTrue) showTrue.addEventListener("click", () => els.showTrueLabelsButton.click());
    if (showHodge) showHodge.addEventListener("click", () => els.showPredLabelsButton.click());
    if (showRbl) showRbl.addEventListener("click", () => els.showRblLabelsButton.click());
  });
}

function renderTradeSummary() {
  const subState = state.trade;
  const summary = subState.summary;
  if (!summary) return;
  els.datasetLabel.textContent = "WITS 2017 Global Supply Chain Network";
  els.metricOneLabel.textContent = "Countries";
  els.metricOneValue.textContent = fmt(summary.counts.countries);
  els.metricTwoLabel.textContent = "Net Flows";
  els.metricTwoValue.textContent = fmt(summary.counts.trade_flows);
  els.metricThreeLabel.textContent = "Triangles";
  els.metricThreeValue.textContent = fmt(summary.counts.triangles);
  els.metricFourLabel.textContent = "Sub-edges";
  els.metricFourValue.textContent = fmt(subState.edges.length);
  els.edgeLimitLabel.textContent = "Trade density";
  els.edgeLimit.min = "50";
  els.edgeLimit.step = "50";
  els.edgeLimit.max = String(Math.max(50, subState.edges.length));
  els.edgeLimit.value = String(Math.min(Math.max(state.edgeLimit, 50), subState.edges.length));
  state.edgeLimit = Number(els.edgeLimit.value);
  els.interClusterControl.hidden = true;
  els.sourceLine.textContent = "Source: World Integrated Trade Solution (WITS) 2017. All 166 countries shown.";
}

function updateTradeDetails(node) {
  els.detailTotalLabel.textContent = "Trade Volume";
  els.detailInboundLabel.textContent = "GDP";
  els.detailOutboundLabel.textContent = "Net Balance";
  els.detailPotentialLabel.textContent = "Hodge Rank";

  if (!node) {
    els.detailCode.textContent = "WITS";
    els.detailName.textContent = "Hover a country";
    els.detailLocation.textContent = "Global supply chain network of net trade flows.";
    els.detailTotal.textContent = "--";
    els.detailInbound.textContent = "--";
    els.detailOutbound.textContent = "--";
    els.detailPotential.textContent = "--";
    return;
  }

  els.detailCode.textContent = node.id;
  els.detailName.textContent = node.name || node.id;
  els.detailLocation.textContent = `${node.continent} | Population: ${fmt(node.population)}`;
  els.detailTotal.textContent = `$${fmt(node.tradeVolume * 1000)}`;
  els.detailInbound.textContent = `$${fmt(node.gdp)}`;
  els.detailOutbound.textContent = `$${fmt(node.netTradeBalance * 1000)}`;
  els.detailPotential.textContent = `${Math.round(node.potentialNorm * 100)}%`;
}

function renderTradeClusters() {
  els.clusterList.innerHTML = "";
  const subState = state.trade;
  const summary = subState.summary;
  if (!summary) return;

  const headerReg = document.createElement("div");
  headerReg.className = "legend-header";
  headerReg.style = "font-size:0.88rem; font-weight:700; margin:10px 0 6px 0; color:#58c6a4; letter-spacing:0.5px; text-transform:uppercase;";
  headerReg.textContent = "Top Exporters (Sources)";
  els.clusterList.appendChild(headerReg);

  summary.top_regulators.forEach((reg) => {
    const button = document.createElement("button");
    button.className = "cluster-button gene-button";
    button.type = "button";
    const active = subState.selectedNode === reg.iso3;
    if (active) button.classList.add("active");
    button.innerHTML = `
      <span class="cluster-swatch" style="background:#58c6a4"></span>
      <span class="cluster-copy">
        <strong>${reg.iso3}</strong>
        <p>Rank #${reg.rank} Exporter</p>
      </span>
      <span class="cluster-count">${Math.round(reg.potential * 100)}%</span>
    `;
    button.addEventListener("click", () => {
      const layout = getGraphLayout("trade");
      const node = layout.nodes.find(n => n.id === reg.iso3);
      if (node) {
        subState.selectedNode = subState.selectedNode === node.id ? null : node.id;
        document.querySelectorAll(".cluster-button").forEach((item) => item.classList.remove("active"));
        if (subState.selectedNode !== null) button.classList.add("active");
        updateDetails(subState.selectedNode ? node : null);
        draw();
      }
    });
    els.clusterList.appendChild(button);
  });

  const headerTgt = document.createElement("div");
  headerTgt.className = "legend-header";
  headerTgt.style = "font-size:0.88rem; font-weight:700; margin:18px 0 6px 0; color:#7aa6ff; letter-spacing:0.5px; text-transform:uppercase;";
  headerTgt.textContent = "Top Importers (Sinks)";
  els.clusterList.appendChild(headerTgt);

  summary.top_targets.forEach((tgt) => {
    const button = document.createElement("button");
    button.className = "cluster-button gene-button";
    button.type = "button";
    const active = subState.selectedNode === tgt.iso3;
    if (active) button.classList.add("active");
    button.innerHTML = `
      <span class="cluster-swatch" style="background:#7aa6ff"></span>
      <span class="cluster-copy">
        <strong>${tgt.iso3}</strong>
        <p>Rank #${tgt.rank} Importer</p>
      </span>
      <span class="cluster-count">${Math.round(tgt.potential * 100)}%</span>
    `;
    button.addEventListener("click", () => {
      const layout = getGraphLayout("trade");
      const node = layout.nodes.find(n => n.id === tgt.iso3);
      if (node) {
        subState.selectedNode = subState.selectedNode === node.id ? null : node.id;
        document.querySelectorAll(".cluster-button").forEach((item) => item.classList.remove("active"));
        if (subState.selectedNode !== null) button.classList.add("active");
        updateDetails(subState.selectedNode ? node : null);
        draw();
      }
    });
    els.clusterList.appendChild(button);
  });
}

function drawTradeGraph() {
  const layout = getGraphLayout("trade");
  const { box } = layout;
  const subState = state.trade;
  const selectedId = subState.selectedNode;
  const hoveredId = subState.hoveredNode ? subState.hoveredNode.id : null;

  ctx.save();
  ctx.beginPath();
  ctx.rect(box.x, box.y, box.width, box.height);
  ctx.clip();

  // Background
  const networkGradient = ctx.createLinearGradient(box.x, box.y, box.x + box.width, box.y + box.height);
  networkGradient.addColorStop(0, "rgba(10, 22, 28, 0.52)");
  networkGradient.addColorStop(0.55, "rgba(8, 14, 18, 0.32)");
  networkGradient.addColorStop(1, "rgba(22, 10, 28, 0.44)");
  ctx.fillStyle = networkGradient;
  ctx.fillRect(box.x, box.y, box.width, box.height);

  // Draw meridians
  const meridians = [
    { deg: -120, label: "120°W" },
    { deg: -60, label: "60°W" },
    { deg: 0, label: "0° (GMT)" },
    { deg: 60, label: "60°E" },
    { deg: 120, label: "120°E" }
  ];
  ctx.strokeStyle = "rgba(243, 239, 226, 0.04)";
  ctx.lineWidth = 0.8;
  ctx.fillStyle = "rgba(243, 239, 226, 0.25)";
  ctx.font = "9px Inter, ui-sans-serif, system-ui, sans-serif";
  ctx.textAlign = "center";
  for (const m of meridians) {
    const x = box.x + 45 + ((m.deg - (-180)) / 360) * (box.width - 90);
    ctx.beginPath();
    ctx.moveTo(x, box.y);
    ctx.lineTo(x, box.y + box.height - 20);
    ctx.stroke();
    ctx.fillText(m.label, x, box.y + box.height - 8);
  }

  // Draw economic potential levels
  const levels = [
    { val: 0.1, label: "Upstream Exporters (Sources)" },
    { val: 0.5, label: "Mid-stream Trade Hubs" },
    { val: 0.9, label: "Downstream Importers (Sinks)" }
  ];
  ctx.strokeStyle = "rgba(231, 198, 107, 0.05)";
  ctx.setLineDash([4, 4]);
  ctx.textAlign = "left";
  for (const l of levels) {
    const y = box.y + 45 + l.val * (box.height - 90);
    ctx.beginPath();
    ctx.moveTo(box.x, y);
    ctx.lineTo(box.x + box.width, y);
    ctx.stroke();
    ctx.fillText(l.label, box.x + 8, y - 4);
  }
  ctx.setLineDash([]); // Reset dash

  // Filter edges
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
    const bend = Math.min(25, Math.max(5, distance * 0.05));

    ctx.quadraticCurveTo(midX - (dy / distance) * bend, midY + (dx / distance) * bend, target.x, target.y);
    ctx.strokeStyle = active ? "rgba(243, 239, 226, 0.75)" : "rgba(243, 239, 226, 0.08)";
    ctx.globalAlpha = active ? 1.0 : 0.35;
    ctx.lineWidth = active ? 1.8 : 0.8;
    ctx.stroke();

    if (active && distance > 30) {
      const t = 0.5;
      const ax = (1-t)*(1-t)*source.x + 2*(1-t)*t*(midX - (dy / distance) * bend) + t*t*target.x;
      const ay = (1-t)*(1-t)*source.y + 2*(1-t)*t*(midY + (dx / distance) * bend) + t*t*target.y;
      const tx = 2*(1-t)*((midX - (dy / distance) * bend) - source.x) + 2*t*(target.x - (midX - (dy / distance) * bend));
      const ty = 2*(1-t)*((midY + (dx / distance) * bend) - source.y) + 2*t*(target.y - (midY + (dx / distance) * bend));
      const angle = Math.atan2(ty, tx);

      ctx.save();
      ctx.translate(ax, ay);
      ctx.rotate(angle);
      ctx.beginPath();
      ctx.moveTo(-5, -3);
      ctx.lineTo(2, 0);
      ctx.lineTo(-5, 3);
      ctx.closePath();
      ctx.fillStyle = "#f3efe2";
      ctx.fill();
      ctx.restore();
    }
  }
  ctx.globalAlpha = 1.0;

  // Draw nodes
  const sortedNodes = [...layout.nodes].sort((a, b) => a.gdp - b.gdp);
  for (const node of sortedNodes) {
    const isHovered = hoveredId === node.id;
    const isSelected = selectedId === node.id;
    const active = !selectedId || isSelected;

    ctx.beginPath();
    ctx.arc(node.x, node.y, node.radius + (isHovered ? 2 : 0), 0, Math.PI * 2);

    let fill = "#8a867d";
    if (node.continent === "Asia") fill = "#7aa6ff";
    else if (node.continent === "Europe") fill = "#df7d58";
    else if (node.continent === "Africa") fill = "#e7c66b";
    else if (node.continent === "America") fill = "#d77adf";
    else if (node.continent === "Pacific") fill = "#8fd36a";

    ctx.fillStyle = fill;
    ctx.globalAlpha = active ? 1.0 : 0.22;
    ctx.fill();

    ctx.strokeStyle = isSelected ? "#f3efe2" : "rgba(255, 255, 255, 0.12)";
    ctx.lineWidth = isSelected ? 2.0 : 1.0;
    ctx.stroke();

    if (isHovered || isSelected || node.gdp > 5e11) {
      ctx.fillStyle = "#f3efe2";
      ctx.font = isHovered ? "bold 10px Inter, ui-sans-serif, system-ui, sans-serif" : "9px Inter, ui-sans-serif, system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(node.label, node.x, node.y - node.radius - 4);
    }
  }

  ctx.restore();
}

// =========================================================================
window.addEventListener("resize", resizeCanvas);

loadData().catch((error) => {
  console.error(error);
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="load-error">Failed to load generated atlas artifacts: ${error.message}</div>`,
  );
});
