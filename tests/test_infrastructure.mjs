import assert from 'node:assert/strict';
import test from 'node:test';
import { infrastructureElements } from '../frontend/app/src/sdn-selector-v2/infrastructure.js';
import { dijkstra } from '../frontend/app/src/sdn-vivo-v1/graph.js';

test('hosts and control links remain separate from routed topology and preserve a route', () => {
  const topology = { nodes: [1, 2].map(i => ({ id: `s${i}`, host: `nsh${i}`, hostIp: `10.0.0.${i}`, hostPort: 2 })),
    links: [{ id: 'e1', source: 's1', target: 's2', capacity: 10, delay: 2 }] };
  const before = JSON.stringify(topology);
  const route = dijkstra(topology, 's1', 's2', 'capacity');
  const result = infrastructureElements(topology, new Map([['s1', { x: 0, y: 0 }], ['s2', { x: 100, y: 100 }]]), { ip: '192.168.56.108' });
  assert.equal(result.filter(x => x.data.kind === 'host').length, 2);
  assert.equal(result.filter(x => x.data.kind === 'controller').length, 1);
  assert.equal(result.filter(x => x.data.kind === 'access').length, 2);
  assert.equal(result.filter(x => x.data.kind === 'control').length, 2);
  assert.equal(new Set(result.map(x => x.data.id)).size, result.length);
  assert.equal(JSON.stringify(topology), before);
  assert.deepEqual(dijkstra(topology, 's1', 's2', 'capacity'), route);
});

test('no fictitious host or controller is added when evidence is absent', () => {
  const topology = { nodes: [{ id: 's1' }], links: [] };
  const positions = new Map([['s1', { x: 0, y: 0 }]]);
  assert.deepEqual(infrastructureElements(topology, positions, {}), []);
  topology.nodes[0] = { id: 's1', host: 'h1', hostIp: '10.0.0.1', hostPort: 1 };
  assert.deepEqual(infrastructureElements(topology, positions, { ip: '192.168.56.108' }, false, false), []);
});
