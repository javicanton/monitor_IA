import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const STATUS_COLORS = {
  active: '#1976d2',
  error: '#d32f2f',
  disabled: '#757575',
  discovered: '#ed6c02',
};

export const LAYOUT_OPTIONS = [
  { value: 'force', label: 'Force (muelles)' },
  { value: 'forceAtlas2', label: 'ForceAtlas2' },
  { value: 'circular', label: 'Circular' },
];

function nodeColor(node) {
  if (node.discontinued || node.status === 'error') return STATUS_COLORS.error;
  if (!node.monitored) return STATUS_COLORS.discovered;
  return STATUS_COLORS[node.status] || STATUS_COLORS.active;
}

function nodeRadius(node) {
  const base = 7;
  const byDegree = Math.min(16, Math.sqrt(node.degree || 0) * 2.4);
  const byMsgs = Math.min(10, Math.sqrt(node.message_count || 0) / 7);
  return base + byDegree + byMsgs * 0.35;
}

function matchesQuery(node, q) {
  if (!q) return false;
  return (
    (node.username || '').toLowerCase().includes(q)
    || (node.title || '').toLowerCase().includes(q)
  );
}

/**
 * Grafo canvas con varios layouts.
 * Algoritmo por defecto: force-directed (repulsión + muelles), estilo Fruchterman–Reingold.
 * ForceAtlas2: aproximación (atracción ∝ distancia, repulsión por grado, gravedad).
 * Circular: anillo ordenado por grado.
 *
 * La simulación NO se reinicia al cambiar selectedId / highlight (solo redibuja).
 */
function ChannelGraph({
  nodes = [],
  edges = [],
  selectedId = null,
  highlightQuery = '',
  layout = 'forceAtlas2',
  reheatToken = 0,
  onSelectNode,
  height = 640,
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const simRef = useRef({ nodes: [], edges: [], width: 600, height, layout });
  const dragRef = useRef(null);
  const hoverRef = useRef(null);
  const drawRef = useRef(() => {});
  const runningRef = useRef(false);
  const [tooltip, setTooltip] = useState(null);
  const [size, setSize] = useState({ width: 600, height });

  const graphKey = useMemo(
    () => `${nodes.length}|${edges.length}|${nodes.map((n) => n.id).join(',')}`,
    [nodes, edges]
  );

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;
    const update = () => {
      const rect = el.getBoundingClientRect();
      const w = Math.max(320, rect.width);
      // Preferir área cuadrada aprovechando el alto disponible
      const h = Math.max(height, Math.min(w, height));
      setSize({ width: w, height: h });
    };
    update();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(update) : null;
    if (ro) ro.observe(el);
    window.addEventListener('resize', update);
    return () => {
      if (ro) ro.disconnect();
      window.removeEventListener('resize', update);
    };
  }, [height]);

  const initPositions = useCallback((simNodes, width, h, layoutMode) => {
    const cx = width / 2;
    const cy = h / 2;
    const n = simNodes.length || 1;
    if (layoutMode === 'circular') {
      const ranked = [...simNodes].sort((a, b) => (b.degree || 0) - (a.degree || 0));
      const R = Math.min(width, h) * 0.38;
      ranked.forEach((node, i) => {
        const angle = (2 * Math.PI * i) / n - Math.PI / 2;
        node.x = cx + Math.cos(angle) * R;
        node.y = cy + Math.sin(angle) * R;
        node.vx = 0;
        node.vy = 0;
      });
      return;
    }
    // force / forceAtlas2: círculo inicial + jitter
    const R = Math.min(width, h) * 0.28;
    simNodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / n;
      node.x = cx + Math.cos(angle) * R + (Math.random() - 0.5) * 30;
      node.y = cy + Math.sin(angle) * R + (Math.random() - 0.5) * 30;
      node.vx = 0;
      node.vy = 0;
    });
  }, []);

  // Inicializa / reinicia solo cuando cambian nodos, tamaño, layout o reheatToken
  useEffect(() => {
    const width = size.width;
    const h = size.height;
    const prevById = Object.fromEntries(
      (simRef.current.nodes || []).map((n) => [n.id, n])
    );
    const canReuse = (
      reheatToken === 0
      && simRef.current.layout === layout
      && simRef.current.width === width
      && Math.abs(simRef.current.height - h) < 8
      && simRef.current.nodes?.length === nodes.length
    );

    const simNodes = nodes.map((n, i) => {
      const prev = prevById[n.id];
      if (canReuse && prev && Number.isFinite(prev.x)) {
        return {
          ...n,
          x: prev.x,
          y: prev.y,
          vx: 0,
          vy: 0,
          mass: 1 + Math.sqrt(n.degree || 0),
        };
      }
      return {
        ...n,
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        mass: 1 + Math.sqrt(n.degree || 0),
        _i: i,
      };
    });

    if (!(canReuse && simNodes.every((n) => n.x !== 0 || n.y !== 0))) {
      initPositions(simNodes, width, h, layout);
    }

    const byId = Object.fromEntries(simNodes.map((n) => [n.id, n]));
    const simEdges = edges
      .map((e) => ({
        ...e,
        source: byId[e.source],
        target: byId[e.target],
      }))
      .filter((e) => e.source && e.target);

    simRef.current = {
      nodes: simNodes,
      edges: simEdges,
      width,
      height: h,
      layout,
      ticks: 0,
    };
  }, [graphKey, size.width, size.height, layout, reheatToken, nodes, edges, initPositions]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const { nodes: simNodes, edges: simEdges, width, height: h } = simRef.current;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.clearRect(0, 0, width, h);
    ctx.fillStyle = '#f4f6fa';
    ctx.fillRect(0, 0, width, h);

    const q = (highlightQuery || '').trim().toLowerCase();
    const maxFwd = Math.max(1, ...simEdges.map((e) => e.forward_count || 1));

    for (const e of simEdges) {
      const w = 0.7 + (3.2 * (e.forward_count || 1)) / maxFwd;
      const connected =
        !selectedId || e.source.id === selectedId || e.target.id === selectedId;
      const edgeMatches = !q || matchesQuery(e.source, q) || matchesQuery(e.target, q);
      ctx.beginPath();
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.strokeStyle = connected && edgeMatches
        ? 'rgba(25, 118, 210, 0.5)'
        : 'rgba(0,0,0,0.05)';
      ctx.lineWidth = connected ? w : Math.max(0.4, w * 0.35);
      ctx.stroke();

      if (connected && edgeMatches) {
        const dx = e.target.x - e.source.x;
        const dy = e.target.y - e.source.y;
        const len = Math.hypot(dx, dy) || 1;
        const ux = dx / len;
        const uy = dy / len;
        const tr = nodeRadius(e.target);
        const ax = e.target.x - ux * (tr + 2);
        const ay = e.target.y - uy * (tr + 2);
        const ah = 5;
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(ax - ux * ah - uy * ah * 0.6, ay - uy * ah + ux * ah * 0.6);
        ctx.lineTo(ax - ux * ah + uy * ah * 0.6, ay - uy * ah - ux * ah * 0.6);
        ctx.closePath();
        ctx.fillStyle = 'rgba(25, 118, 210, 0.55)';
        ctx.fill();
      }
    }

    for (const n of simNodes) {
      const r = nodeRadius(n);
      const isSelected = selectedId === n.id;
      const isHover = hoverRef.current === n.id;
      const isMatch = matchesQuery(n, q);
      const dimmed = (selectedId && !isSelected && !simEdges.some(
        (e) => (e.source.id === selectedId || e.target.id === selectedId)
          && (e.source.id === n.id || e.target.id === n.id)
      )) || (q && !isMatch);

      ctx.beginPath();
      ctx.arc(n.x, n.y, r + (isSelected || isHover || isMatch ? 2.5 : 0), 0, Math.PI * 2);
      ctx.fillStyle = dimmed ? '#cfd8dc' : nodeColor(n);
      ctx.globalAlpha = dimmed ? 0.28 : 1;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.lineWidth = isSelected || isMatch ? 2.5 : 1;
      ctx.strokeStyle = isSelected || isMatch ? '#0d47a1' : '#ffffff';
      ctx.stroke();

      if (isSelected || isMatch || isHover || (!q && simNodes.length < 50)) {
        ctx.font = `${isMatch || isSelected ? 12 : 11}px system-ui, sans-serif`;
        ctx.fillStyle = isMatch ? '#0d47a1' : '#263238';
        ctx.textAlign = 'center';
        const label = n.title && n.title.toLowerCase() !== n.username
          ? n.title.slice(0, 22)
          : `@${n.username}`;
        ctx.fillText(label, n.x, n.y + r + 13);
      }
    }
  }, [highlightQuery, selectedId]);

  drawRef.current = draw;

  // Simulación: solo depende de graph/layout/size/reheat — NO de selectedId
  useEffect(() => {
    let raf = 0;
    let ticks = 0;
    const maxTicks = layout === 'circular' ? 1 : 320;
    runningRef.current = true;

    const collide = (simNodes) => {
      const m = simNodes.length;
      for (let i = 0; i < m; i += 1) {
        for (let j = i + 1; j < m; j += 1) {
          const a = simNodes[i];
          const b = simNodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          let dist = Math.hypot(dx, dy) || 0.01;
          const minDist = nodeRadius(a) + nodeRadius(b) + 6;
          if (dist < minDist) {
            const push = (minDist - dist) / 2;
            const ux = dx / dist;
            const uy = dy / dist;
            a.x -= ux * push;
            a.y -= uy * push;
            b.x += ux * push;
            b.y += uy * push;
          }
        }
      }
    };

    const stepForce = (simNodes, simEdges, width, h, alpha) => {
      const n = simNodes.length;
      const kRep = 2800;
      for (let i = 0; i < n; i += 1) {
        for (let j = i + 1; j < n; j += 1) {
          const a = simNodes[i];
          const b = simNodes[j];
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let dist2 = dx * dx + dy * dy || 0.01;
          const dist = Math.sqrt(dist2);
          const force = kRep / dist2;
          dx = (dx / dist) * force;
          dy = (dy / dist) * force;
          a.vx += dx;
          a.vy += dy;
          b.vx -= dx;
          b.vy -= dy;
        }
      }
      for (const e of simEdges) {
        const dx = e.target.x - e.source.x;
        const dy = e.target.y - e.source.y;
        const dist = Math.hypot(dx, dy) || 1;
        const ideal = 90 + Math.min(100, (e.forward_count || 1) * 2);
        const f = (dist - ideal) * 0.025;
        const fx = (dx / dist) * f;
        const fy = (dy / dist) * f;
        e.source.vx += fx;
        e.source.vy += fy;
        e.target.vx -= fx;
        e.target.vy -= fy;
      }
      const cx = width / 2;
      const cy = h / 2;
      for (const node of simNodes) {
        if (dragRef.current?.id === node.id) {
          node.vx = 0;
          node.vy = 0;
          continue;
        }
        node.vx += (cx - node.x) * 0.008;
        node.vy += (cy - node.y) * 0.008;
        node.vx *= 0.82;
        node.vy *= 0.82;
        node.x += node.vx * alpha * 9;
        node.y += node.vy * alpha * 9;
      }
    };

    const stepFA2 = (simNodes, simEdges, width, h, alpha) => {
      // Aproximación ForceAtlas2: repulsión ∝ (mass_i * mass_j)/d², atracción ∝ d
      const n = simNodes.length;
      const kRep = 800;
      for (let i = 0; i < n; i += 1) {
        for (let j = i + 1; j < n; j += 1) {
          const a = simNodes[i];
          const b = simNodes[j];
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          const dist2 = dx * dx + dy * dy || 0.01;
          const dist = Math.sqrt(dist2);
          const force = (kRep * (a.mass || 1) * (b.mass || 1)) / dist2;
          dx = (dx / dist) * force;
          dy = (dy / dist) * force;
          a.vx += dx;
          a.vy += dy;
          b.vx -= dx;
          b.vy -= dy;
        }
      }
      for (const e of simEdges) {
        const dx = e.target.x - e.source.x;
        const dy = e.target.y - e.source.y;
        const dist = Math.hypot(dx, dy) || 1;
        const weight = Math.log2(2 + (e.forward_count || 1));
        const f = dist * 0.012 * weight;
        const fx = (dx / dist) * f;
        const fy = (dy / dist) * f;
        e.source.vx += fx;
        e.source.vy += fy;
        e.target.vx -= fx;
        e.target.vy -= fy;
      }
      const cx = width / 2;
      const cy = h / 2;
      for (const node of simNodes) {
        if (dragRef.current?.id === node.id) {
          node.vx = 0;
          node.vy = 0;
          continue;
        }
        // gravedad central débil (FA2)
        node.vx += (cx - node.x) * 0.012 * (node.mass || 1);
        node.vy += (cy - node.y) * 0.012 * (node.mass || 1);
        node.vx *= 0.8;
        node.vy *= 0.8;
        node.x += node.vx * alpha * 7;
        node.y += node.vy * alpha * 7;
      }
    };

    const step = () => {
      const sim = simRef.current;
      const { nodes: simNodes, edges: simEdges, width, height: h } = sim;
      if (!simNodes.length) {
        drawRef.current();
        return;
      }

      if (layout !== 'circular') {
        const alpha = Math.max(0.015, 1 - ticks / maxTicks);
        if (layout === 'forceAtlas2') {
          stepFA2(simNodes, simEdges, width, h, alpha);
        } else {
          stepForce(simNodes, simEdges, width, h, alpha);
        }
        collide(simNodes);
        const pad = 28;
        for (const node of simNodes) {
          node.x = Math.min(width - pad, Math.max(pad, node.x));
          node.y = Math.min(h - pad, Math.max(pad, node.y));
        }
      }

      ticks += 1;
      drawRef.current();
      if (ticks < maxTicks || dragRef.current) {
        raf = requestAnimationFrame(step);
      } else {
        runningRef.current = false;
      }
    };

    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      runningRef.current = false;
    };
  }, [graphKey, size.width, size.height, layout, reheatToken]);

  // Solo redibujar al cambiar selección / búsqueda (sin reiniciar física)
  useEffect(() => {
    draw();
  }, [draw, selectedId, highlightQuery]);

  // Centrar/seleccionar primer match al buscar
  useEffect(() => {
    const q = (highlightQuery || '').trim().toLowerCase();
    if (!q) return;
    const simNodes = simRef.current.nodes || [];
    const match = simNodes.find((n) => matchesQuery(n, q));
    if (match) {
      draw();
    }
  }, [highlightQuery, draw]);

  const findNodeAt = (clientX, clientY) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    let found = null;
    let best = Infinity;
    for (const n of simRef.current.nodes) {
      const r = nodeRadius(n) + 4;
      const d2 = (n.x - x) ** 2 + (n.y - y) ** 2;
      if (d2 <= r * r && d2 < best) {
        best = d2;
        found = n;
      }
    }
    return found;
  };

  const handlePointerDown = (event) => {
    const node = findNodeAt(event.clientX, event.clientY);
    if (!node) {
      if (onSelectNode) onSelectNode(null);
      return;
    }
    dragRef.current = { id: node.id };
    if (onSelectNode) onSelectNode(node);
    // Si la simulación paró, redibuja al arrastrar
    if (!runningRef.current) {
      runningRef.current = true;
      // reheat ligero sin reset de posiciones: el effect de sim no se relanza;
      // arrastre manual basta.
    }
  };

  const handlePointerMove = (event) => {
    const node = findNodeAt(event.clientX, event.clientY);
    hoverRef.current = node?.id || null;
    if (node) {
      const canvas = canvasRef.current;
      const rect = canvas.getBoundingClientRect();
      setTooltip({
        x: event.clientX - rect.left + 12,
        y: event.clientY - rect.top + 12,
        node,
      });
      canvas.style.cursor = 'pointer';
    } else {
      setTooltip(null);
      if (canvasRef.current) canvasRef.current.style.cursor = 'default';
    }

    if (dragRef.current) {
      const canvas = canvasRef.current;
      const rect = canvas.getBoundingClientRect();
      const dragged = simRef.current.nodes.find((n) => n.id === dragRef.current.id);
      if (dragged) {
        dragged.x = event.clientX - rect.left;
        dragged.y = event.clientY - rect.top;
        drawRef.current();
      }
    } else if (hoverRef.current) {
      drawRef.current();
    }
  };

  const handlePointerUp = () => {
    dragRef.current = null;
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: size.height }}>
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={() => {
          hoverRef.current = null;
          setTooltip(null);
          dragRef.current = null;
          drawRef.current();
        }}
        style={{ width: '100%', height: size.height, display: 'block', borderRadius: 8 }}
      />
      {tooltip && (
        <div
          style={{
            position: 'absolute',
            left: tooltip.x,
            top: tooltip.y,
            background: 'rgba(33,33,33,0.92)',
            color: '#fff',
            padding: '6px 10px',
            borderRadius: 6,
            fontSize: 12,
            pointerEvents: 'none',
            maxWidth: 240,
            zIndex: 2,
          }}
        >
          <div style={{ fontWeight: 600 }}>{tooltip.node.title}</div>
          <div>@{tooltip.node.username}</div>
          <div>
            grado {tooltip.node.degree} · {tooltip.node.message_count} msgs
          </div>
        </div>
      )}
    </div>
  );
}

export default ChannelGraph;
