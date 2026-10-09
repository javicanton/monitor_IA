import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const STATUS_COLORS = {
  active: '#1976d2',
  error: '#d32f2f',
  disabled: '#757575',
  discovered: '#ed6c02',
};

function nodeColor(node) {
  if (node.discontinued || node.status === 'error') return STATUS_COLORS.error;
  if (!node.monitored) return STATUS_COLORS.discovered;
  return STATUS_COLORS[node.status] || STATUS_COLORS.active;
}

function nodeRadius(node) {
  const base = 6;
  const byDegree = Math.min(14, Math.sqrt(node.degree || 0) * 2.2);
  const byMsgs = Math.min(8, Math.sqrt(node.message_count || 0) / 8);
  return base + byDegree + byMsgs * 0.35;
}

/**
 * Grafo force-directed ligero (canvas), sin dependencias extra.
 */
function ChannelGraph({
  nodes = [],
  edges = [],
  selectedId = null,
  highlightQuery = '',
  onSelectNode,
  height = 520,
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const simRef = useRef({ nodes: [], edges: [], width: 600, height });
  const dragRef = useRef(null);
  const hoverRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const [size, setSize] = useState({ width: 600, height });

  const graphKey = useMemo(() => {
    return `${nodes.length}:${edges.length}:${nodes.map((n) => n.id).join(',')}`;
  }, [nodes, edges]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;
    const update = () => {
      const rect = el.getBoundingClientRect();
      setSize({ width: Math.max(320, rect.width), height });
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

  useEffect(() => {
    const width = size.width;
    const h = size.height;
    const cx = width / 2;
    const cy = h / 2;
    const simNodes = nodes.map((n, i) => {
      const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
      const r = 40 + Math.min(180, nodes.length * 2);
      return {
        ...n,
        x: cx + Math.cos(angle) * r + (Math.random() - 0.5) * 20,
        y: cy + Math.sin(angle) * r + (Math.random() - 0.5) * 20,
        vx: 0,
        vy: 0,
      };
    });
    const byId = Object.fromEntries(simNodes.map((n) => [n.id, n]));
    const simEdges = edges
      .map((e) => ({
        ...e,
        source: byId[e.source],
        target: byId[e.target],
      }))
      .filter((e) => e.source && e.target);
    simRef.current = { nodes: simNodes, edges: simEdges, width, height: h };
  }, [graphKey, size.width, size.height, nodes, edges]);

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
    ctx.fillStyle = '#f7f9fc';
    ctx.fillRect(0, 0, width, h);

    const q = (highlightQuery || '').trim().toLowerCase();
    const maxFwd = Math.max(1, ...simEdges.map((e) => e.forward_count || 1));

    // Edges
    for (const e of simEdges) {
      const w = 0.6 + (3.5 * (e.forward_count || 1)) / maxFwd;
      const connected =
        !selectedId || e.source.id === selectedId || e.target.id === selectedId;
      ctx.beginPath();
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.strokeStyle = connected ? 'rgba(25, 118, 210, 0.45)' : 'rgba(0,0,0,0.06)';
      ctx.lineWidth = connected ? w : Math.max(0.4, w * 0.4);
      ctx.stroke();

      // arrow head
      if (connected || !selectedId) {
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
        ctx.fillStyle = connected ? 'rgba(25, 118, 210, 0.55)' : 'rgba(0,0,0,0.08)';
        ctx.fill();
      }
    }

    // Nodes
    for (const n of simNodes) {
      const r = nodeRadius(n);
      const isSelected = selectedId === n.id;
      const isHover = hoverRef.current === n.id;
      const matches = q && (
        (n.username || '').toLowerCase().includes(q)
        || (n.title || '').toLowerCase().includes(q)
      );
      const dimmed = selectedId && !isSelected && !simEdges.some(
        (e) => (e.source.id === selectedId || e.target.id === selectedId)
          && (e.source.id === n.id || e.target.id === n.id)
      );

      ctx.beginPath();
      ctx.arc(n.x, n.y, r + (isSelected || isHover ? 2 : 0), 0, Math.PI * 2);
      ctx.fillStyle = dimmed ? '#cfd8dc' : nodeColor(n);
      ctx.globalAlpha = dimmed ? 0.35 : 1;
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.lineWidth = isSelected || matches ? 2.5 : 1;
      ctx.strokeStyle = isSelected || matches ? '#0d47a1' : '#ffffff';
      ctx.stroke();

      if (isSelected || matches || (!q && simNodes.length < 40) || isHover) {
        ctx.font = '11px system-ui, sans-serif';
        ctx.fillStyle = '#263238';
        ctx.textAlign = 'center';
        ctx.fillText(`@${n.username}`, n.x, n.y + r + 12);
      }
    }
  }, [highlightQuery, selectedId]);

  useEffect(() => {
    let raf = 0;
    let ticks = 0;
    const step = () => {
      const sim = simRef.current;
      const { nodes: simNodes, edges: simEdges, width, height: h } = sim;
      const n = simNodes.length;
      if (n === 0) {
        draw();
        return;
      }

      // repulsion
      for (let i = 0; i < n; i += 1) {
        for (let j = i + 1; j < n; j += 1) {
          const a = simNodes[i];
          const b = simNodes[j];
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let dist2 = dx * dx + dy * dy || 0.01;
          const dist = Math.sqrt(dist2);
          const force = 1200 / dist2;
          dx = (dx / dist) * force;
          dy = (dy / dist) * force;
          a.vx += dx;
          a.vy += dy;
          b.vx -= dx;
          b.vy -= dy;
        }
      }

      // springs
      for (const e of simEdges) {
        const dx = e.target.x - e.source.x;
        const dy = e.target.y - e.source.y;
        const dist = Math.hypot(dx, dy) || 1;
        const ideal = 70 + Math.min(80, (e.forward_count || 1) * 2);
        const f = (dist - ideal) * 0.02;
        const fx = (dx / dist) * f;
        const fy = (dy / dist) * f;
        e.source.vx += fx;
        e.source.vy += fy;
        e.target.vx -= fx;
        e.target.vy -= fy;
      }

      // center gravity + integrate
      const cx = width / 2;
      const cy = h / 2;
      const alpha = Math.max(0.02, 1 - ticks / 220);
      for (const node of simNodes) {
        if (dragRef.current?.id === node.id) {
          node.vx = 0;
          node.vy = 0;
          continue;
        }
        node.vx += (cx - node.x) * 0.005;
        node.vy += (cy - node.y) * 0.005;
        node.vx *= 0.85;
        node.vy *= 0.85;
        node.x += node.vx * alpha * 8;
        node.y += node.vy * alpha * 8;
        const pad = 24;
        node.x = Math.min(width - pad, Math.max(pad, node.x));
        node.y = Math.min(h - pad, Math.max(pad, node.y));
      }

      ticks += 1;
      draw();
      if (ticks < 240 || dragRef.current) {
        raf = requestAnimationFrame(step);
      }
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [graphKey, size.width, size.height, draw]);

  useEffect(() => {
    draw();
  }, [draw, selectedId, highlightQuery]);

  const findNodeAt = (clientX, clientY) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    let found = null;
    for (const n of simRef.current.nodes) {
      const r = nodeRadius(n) + 3;
      if ((n.x - x) ** 2 + (n.y - y) ** 2 <= r * r) {
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
        draw();
      }
    }
  };

  const handlePointerUp = () => {
    dragRef.current = null;
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height }}>
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={() => {
          hoverRef.current = null;
          setTooltip(null);
          dragRef.current = null;
        }}
        style={{ width: '100%', height, display: 'block', borderRadius: 8 }}
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
            maxWidth: 220,
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
