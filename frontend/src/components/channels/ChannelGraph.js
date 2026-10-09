import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CLUSTER_COLORS,
  LAYOUT_OPTIONS,
  detectCommunities,
  nodeRadiusBase,
} from './graphLayout';

export { LAYOUT_OPTIONS };

const STATUS_COLORS = {
  active: '#1976d2',
  error: '#d32f2f',
  disabled: '#757575',
  discovered: '#ed6c02',
};

function statusColor(node) {
  if (node.discontinued || node.status === 'error') return STATUS_COLORS.error;
  if (!node.monitored) return STATUS_COLORS.discovered;
  return STATUS_COLORS[node.status] || STATUS_COLORS.active;
}

function matchesQuery(node, q) {
  if (!q) return false;
  return (
    (node.username || '').toLowerCase().includes(q)
    || (node.title || '').toLowerCase().includes(q)
  );
}

/**
 * Grafo canvas.
 * - Preserva posiciones al filtrar (solo elimina nodos; no reinicia layout).
 * - Soft-bound (sin pegar a esquinas).
 * - Clusters por modularidad (label propagation).
 */
function ChannelGraph({
  nodes = [],
  edges = [],
  selectedId = null,
  highlightQuery = '',
  layout = 'forceAtlas2',
  nodeSizeScale = 1,
  showClusters = false,
  onSelectNode,
  height = 640,
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const simRef = useRef({ nodes: [], edges: [], width: 600, height, layout });
  const posCacheRef = useRef(new Map()); // id → {x,y} persistente entre filtros
  const dragRef = useRef(null);
  const hoverRef = useRef(null);
  const drawRef = useRef(() => {});
  const layoutRef = useRef(layout);
  const [tooltip, setTooltip] = useState(null);
  const [size, setSize] = useState({ width: 600, height });
  const [communityVersion, setCommunityVersion] = useState(0);

  const communities = useMemo(() => {
    if (!showClusters) return new Map();
    return detectCommunities(nodes, edges);
    // communityVersion fuerza recálculo manual si se necesita
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, showClusters, communityVersion]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;
    const update = () => {
      const rect = el.getBoundingClientRect();
      // Usar todo el ancho del contenedor (sin forzar cuadrado → hueco blanco)
      const w = Math.max(320, Math.floor(rect.width));
      const h = Math.max(360, Math.floor(height || rect.height || 560));
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

  const placeNewNode = (node, width, h, layoutMode, index, total) => {
    const cx = width / 2;
    const cy = h / 2;
    if (layoutMode === 'circular') {
      const R = Math.min(width, h) * 0.36;
      const angle = (2 * Math.PI * index) / Math.max(total, 1) - Math.PI / 2;
      node.x = cx + Math.cos(angle) * R;
      node.y = cy + Math.sin(angle) * R;
    } else {
      const R = Math.min(width, h) * 0.22;
      const angle = (2 * Math.PI * index) / Math.max(total, 1);
      node.x = cx + Math.cos(angle) * R * (0.6 + Math.random() * 0.5);
      node.y = cy + Math.sin(angle) * R * (0.6 + Math.random() * 0.5);
    }
    node.vx = 0;
    node.vy = 0;
  };

  // Sync nodos/aristas: PRESERVAR posiciones; solo colocar nodos nuevos.
  // Reinicio completo solo si cambia el algoritmo de layout.
  useEffect(() => {
    const width = size.width;
    const h = size.height;
    const layoutChanged = layoutRef.current !== layout;
    layoutRef.current = layout;

    if (layoutChanged) {
      posCacheRef.current.clear();
    }

    const simNodes = nodes.map((n, i) => {
      const cached = posCacheRef.current.get(n.id);
      const node = {
        ...n,
        x: cached?.x,
        y: cached?.y,
        vx: 0,
        vy: 0,
        mass: 1 + Math.sqrt((n.degree || 0) + 1),
        community: communities.get(n.id) ?? -1,
      };
      if (!Number.isFinite(node.x) || !Number.isFinite(node.y) || layoutChanged) {
        placeNewNode(node, width, h, layout, i, nodes.length);
      }
      return node;
    });

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
      cool: layout === 'circular' ? 1 : 0,
    };

    // Guardar cache actualizado (solo ids visibles)
    const nextCache = new Map();
    simNodes.forEach((n) => nextCache.set(n.id, { x: n.x, y: n.y }));
    // Conservar también posiciones de nodos filtrados por si vuelven
    posCacheRef.current.forEach((pos, id) => {
      if (!nextCache.has(id)) nextCache.set(id, pos);
    });
    posCacheRef.current = nextCache;
  }, [nodes, edges, size.width, size.height, layout, communities]);

  const radiusOf = useCallback(
    (node) => nodeRadiusBase(node, nodeSizeScale),
    [nodeSizeScale]
  );

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
      const w = 0.4 + (2.2 * (e.forward_count || 1)) / maxFwd;
      const connected =
        !selectedId || e.source.id === selectedId || e.target.id === selectedId;
      const sameCluster = showClusters
        && e.source.community >= 0
        && e.source.community === e.target.community;
      const edgeMatches = !q || matchesQuery(e.source, q) || matchesQuery(e.target, q);
      ctx.beginPath();
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      if (connected && edgeMatches) {
        ctx.strokeStyle = sameCluster
          ? `${CLUSTER_COLORS[e.source.community % CLUSTER_COLORS.length]}99`
          : 'rgba(25, 118, 210, 0.35)';
        ctx.lineWidth = w;
      } else {
        ctx.strokeStyle = 'rgba(0,0,0,0.04)';
        ctx.lineWidth = Math.max(0.3, w * 0.3);
      }
      ctx.stroke();
    }

    for (const n of simNodes) {
      const r = radiusOf(n);
      const isSelected = selectedId === n.id;
      const isHover = hoverRef.current === n.id;
      const isMatch = matchesQuery(n, q);
      const dimmed = (selectedId && !isSelected && !simEdges.some(
        (e) => (e.source.id === selectedId || e.target.id === selectedId)
          && (e.source.id === n.id || e.target.id === n.id)
      )) || (q && !isMatch);

      let fill = statusColor(n);
      if (showClusters && n.community >= 0) {
        fill = CLUSTER_COLORS[n.community % CLUSTER_COLORS.length];
      }

      ctx.beginPath();
      ctx.arc(n.x, n.y, r + (isSelected || isHover || isMatch ? 1.5 : 0), 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.globalAlpha = dimmed ? 0.22 : 0.92;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.lineWidth = isSelected || isMatch ? 2 : 0.8;
      ctx.strokeStyle = isSelected || isMatch ? '#0d47a1' : '#ffffff';
      ctx.stroke();

      if (isSelected || isMatch || isHover || (!q && simNodes.length < 35 && r > 4)) {
        ctx.font = `${isMatch || isSelected ? 11 : 10}px system-ui, sans-serif`;
        ctx.fillStyle = isMatch ? '#0d47a1' : '#37474f';
        ctx.textAlign = 'center';
        const label = n.title && n.title.toLowerCase() !== n.username
          ? n.title.slice(0, 18)
          : `@${n.username}`;
        ctx.fillText(label, n.x, n.y + r + 11);
      }
    }

    // Persistir posiciones tras dibujar
    for (const n of simNodes) {
      posCacheRef.current.set(n.id, { x: n.x, y: n.y });
    }
  }, [highlightQuery, selectedId, showClusters, radiusOf]);

  drawRef.current = draw;

  // Simulación continua suave: se reactiva al cambiar nodos/edges/layout/tamaño
  useEffect(() => {
    let raf = 0;
    let ticks = 0;
    const maxTicks = layout === 'circular' ? 2 : 280;

    const softBound = (node, width, h, r) => {
      // Margen amplio + fuerza hacia el centro si se acerca al borde (evita esquinas)
      const margin = Math.max(48, r + 28);
      const strength = 0.14;
      const cx = width / 2;
      const cy = h / 2;
      if (node.x < margin) {
        node.vx += (margin - node.x) * strength + (cx - node.x) * 0.002;
      }
      if (node.x > width - margin) {
        node.vx -= (node.x - (width - margin)) * strength - (cx - node.x) * 0.002;
      }
      if (node.y < margin) {
        node.vy += (margin - node.y) * strength + (cy - node.y) * 0.002;
      }
      if (node.y > h - margin) {
        node.vy -= (node.y - (h - margin)) * strength - (cy - node.y) * 0.002;
      }
      // Si está en esquina, empujar fuerte al centro
      const nearL = node.x < margin * 1.2;
      const nearR = node.x > width - margin * 1.2;
      const nearT = node.y < margin * 1.2;
      const nearB = node.y > h - margin * 1.2;
      if ((nearL || nearR) && (nearT || nearB)) {
        node.vx += (cx - node.x) * 0.05;
        node.vy += (cy - node.y) * 0.05;
      }
      const hard = margin * 0.5;
      node.x = Math.min(width - hard, Math.max(hard, node.x));
      node.y = Math.min(h - hard, Math.max(hard, node.y));
    };

    const collide = (simNodes) => {
      const m = simNodes.length;
      // Muestreo si hay demasiados nodos (rendimiento)
      const step = m > 800 ? 2 : 1;
      for (let i = 0; i < m; i += step) {
        for (let j = i + step; j < m; j += step) {
          const a = simNodes[i];
          const b = simNodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          let dist = Math.hypot(dx, dy) || 0.01;
          const minDist = radiusOf(a) + radiusOf(b) + 3;
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
      const kRep = n > 600 ? 900 : 1800;
      const stride = n > 900 ? 3 : n > 500 ? 2 : 1;
      for (let i = 0; i < n; i += stride) {
        for (let j = i + stride; j < n; j += stride) {
          const a = simNodes[i];
          const b = simNodes[j];
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          const dist2 = dx * dx + dy * dy || 0.01;
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
        const ideal = 55 + Math.min(60, (e.forward_count || 1));
        const f = (dist - ideal) * 0.02;
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
        node.vx += (cx - node.x) * 0.01;
        node.vy += (cy - node.y) * 0.01;
        node.vx *= 0.84;
        node.vy *= 0.84;
        node.x += node.vx * alpha * 8;
        node.y += node.vy * alpha * 8;
        softBound(node, width, h, radiusOf(node));
      }
    };

    const stepFA2 = (simNodes, simEdges, width, h, alpha) => {
      const n = simNodes.length;
      const kRep = n > 600 ? 350 : 650;
      const stride = n > 900 ? 3 : n > 500 ? 2 : 1;
      for (let i = 0; i < n; i += stride) {
        for (let j = i + stride; j < n; j += stride) {
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
        const f = dist * 0.01 * weight;
        const fx = (dx / dist) * f;
        const fy = (dy / dist) * f;
        e.source.vx += fx;
        e.source.vy += fy;
        e.target.vx -= fx;
        e.target.vy -= fy;
      }
      // Atracción intra-cluster si hay comunidades
      if (showClusters) {
        for (const e of simEdges) {
          if (e.source.community >= 0 && e.source.community === e.target.community) {
            const dx = e.target.x - e.source.x;
            const dy = e.target.y - e.source.y;
            const dist = Math.hypot(dx, dy) || 1;
            const f = dist * 0.004;
            e.source.vx += (dx / dist) * f;
            e.source.vy += (dy / dist) * f;
            e.target.vx -= (dx / dist) * f;
            e.target.vy -= (dy / dist) * f;
          }
        }
      }
      const cx = width / 2;
      const cy = h / 2;
      for (const node of simNodes) {
        if (dragRef.current?.id === node.id) {
          node.vx = 0;
          node.vy = 0;
          continue;
        }
        node.vx += (cx - node.x) * 0.015 * (node.mass || 1);
        node.vy += (cy - node.y) * 0.015 * (node.mass || 1);
        node.vx *= 0.82;
        node.vy *= 0.82;
        node.x += node.vx * alpha * 6.5;
        node.y += node.vy * alpha * 6.5;
        softBound(node, width, h, radiusOf(node));
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
        const alpha = Math.max(0.02, 1 - ticks / maxTicks);
        if (layout === 'forceAtlas2') stepFA2(simNodes, simEdges, width, h, alpha);
        else stepForce(simNodes, simEdges, width, h, alpha);
        if (ticks % 2 === 0) collide(simNodes);
      }
      ticks += 1;
      drawRef.current();
      if (ticks < maxTicks || dragRef.current) {
        raf = requestAnimationFrame(step);
      }
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [nodes, edges, size.width, size.height, layout, showClusters, radiusOf]);

  useEffect(() => {
    // Actualizar community en nodos sim sin resetear posiciones
    const simNodes = simRef.current.nodes || [];
    for (const n of simNodes) {
      n.community = communities.get(n.id) ?? -1;
    }
    draw();
  }, [communities, draw]);

  useEffect(() => {
    draw();
  }, [draw, selectedId, highlightQuery, nodeSizeScale]);

  const findNodeAt = (clientX, clientY) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    let found = null;
    let best = Infinity;
    for (const n of simRef.current.nodes) {
      const r = radiusOf(n) + 4;
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
        posCacheRef.current.set(dragged.id, { x: dragged.x, y: dragged.y });
        drawRef.current();
      }
    } else if (hoverRef.current !== undefined) {
      drawRef.current();
    }
  };

  const handlePointerUp = () => {
    dragRef.current = null;
  };

  return (
    <div
      ref={containerRef}
      style={{ position: 'relative', width: '100%', height: '100%', minHeight: size.height }}
    >
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
            {showClusters && tooltip.node.community >= 0
              ? ` · cluster ${tooltip.node.community + 1}`
              : ''}
          </div>
        </div>
      )}
      {showClusters && communities.size > 0 && (
        <button
          type="button"
          onClick={() => setCommunityVersion((v) => v + 1)}
          style={{
            position: 'absolute',
            right: 8,
            bottom: 8,
            fontSize: 11,
            padding: '4px 8px',
            borderRadius: 6,
            border: '1px solid #cfd8dc',
            background: '#fff',
            cursor: 'pointer',
          }}
        >
          Rehacer clusters
        </button>
      )}
    </div>
  );
}

export default ChannelGraph;
