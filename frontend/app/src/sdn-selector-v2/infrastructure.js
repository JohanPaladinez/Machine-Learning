import { nodeKey } from '../sdn-vivo-v1/graph.js';

export const infrastructureKey = (kind, id = '') => `infra:${kind}:${id}`;

export function infrastructureElements(topology, positions, controller, showHosts = true, showControl = true) {
  const result = [];
  const points = [...positions.values()];
  if (!points.length) return result;
  if (showHosts) for (const n of topology.nodes) {
    if (!n.host || !n.hostIp || n.hostPort == null) continue;
    const p = positions.get(n.id);
    result.push({ data: { id: infrastructureKey('host', n.id), kind: 'host', owner: n.id,
      label: n.host, name: n.host }, position: { x: p.x - 32, y: p.y + 45 } });
    result.push({ data: { id: infrastructureKey('access', n.id), kind: 'access', owner: n.id,
      source: nodeKey(n.id), target: infrastructureKey('host', n.id), label: '' } });
  }
  if (showControl && controller?.ip) {
    result.push({ data: { id: infrastructureKey('controller'), kind: 'controller', label: 'RYU\n' + controller.ip },
      position: { x: Math.min(...points.map(p => p.x)) + 20, y: Math.min(...points.map(p => p.y)) - 90 } });
    for (const n of topology.nodes) result.push({ data: { id: infrastructureKey('control', n.id),
      kind: 'control', owner: n.id, source: infrastructureKey('controller'), target: nodeKey(n.id), label: '' } });
  }
  return result;
}
