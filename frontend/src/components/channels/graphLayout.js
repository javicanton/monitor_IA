/**
 * Utilidades de layout / comunidades para el grafo de canales.
 */

export const LAYOUT_OPTIONS = [
  { value: 'force', label: 'Force (muelles)' },
  { value: 'forceAtlas2', label: 'ForceAtlas2' },
  { value: 'circular', label: 'Circular' },
];

/** Paleta de clusters (modularidad). */
export const CLUSTER_COLORS = [
  '#1976d2', '#e65100', '#2e7d32', '#6a1b9a', '#00838f',
  '#c62828', '#f9a825', '#4527a0', '#00695c', '#ad1457',
  '#1565c0', '#ef6c00', '#558b2f', '#7b1fa2', '#0097a7',
];

/**
 * Detecta comunidades con label propagation (barato) + refinamiento greedy.
 * Devuelve Map id → communityIndex (0..k-1).
 */
export function detectCommunities(nodes, edges) {
  const ids = nodes.map((n) => n.id);
  if (!ids.length) return new Map();

  const neighbors = new Map(ids.map((id) => [id, new Map()]));
  for (const e of edges) {
    const w = Math.max(1, e.forward_count || 1);
    if (!neighbors.has(e.source) || !neighbors.has(e.target)) continue;
    const a = neighbors.get(e.source);
    const b = neighbors.get(e.target);
    a.set(e.target, (a.get(e.target) || 0) + w);
    b.set(e.source, (b.get(e.source) || 0) + w);
  }

  // Label propagation
  let labels = new Map(ids.map((id) => [id, id]));
  for (let iter = 0; iter < 12; iter += 1) {
    let changed = 0;
    const order = [...ids].sort(() => Math.random() - 0.5);
    for (const id of order) {
      const counts = new Map();
      const neigh = neighbors.get(id);
      for (const [nb, w] of neigh.entries()) {
        const lab = labels.get(nb);
        counts.set(lab, (counts.get(lab) || 0) + w);
      }
      if (!counts.size) continue;
      let best = labels.get(id);
      let bestW = -1;
      for (const [lab, w] of counts.entries()) {
        if (w > bestW) {
          bestW = w;
          best = lab;
        }
      }
      if (best !== labels.get(id)) {
        labels.set(id, best);
        changed += 1;
      }
    }
    if (!changed) break;
  }

  // Compactar a índices 0..k-1 ordenados por tamaño
  const groups = new Map();
  for (const id of ids) {
    const lab = labels.get(id);
    if (!groups.has(lab)) groups.set(lab, []);
    groups.get(lab).push(id);
  }
  const sorted = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
  const result = new Map();
  sorted.forEach(([, members], idx) => {
    members.forEach((id) => result.set(id, idx));
  });
  return result;
}

export function nodeRadiusBase(node, sizeScale = 1) {
  const scale = Math.max(0.25, Math.min(2.5, sizeScale));
  const base = 2.2 * scale;
  const byDegree = Math.min(7 * scale, Math.sqrt(node.degree || 0) * 0.9 * scale);
  const byMsgs = Math.min(4 * scale, Math.sqrt(node.message_count || 0) / 14 * scale);
  return Math.max(1.5, base + byDegree + byMsgs);
}
