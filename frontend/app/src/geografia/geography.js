import locations from './locations.json' with { type: 'json' };
import cartography from './regions.json' with { type: 'json' };

const pairKey = (a, b) => JSON.stringify([a, b].sort());

export function withPlaces(topology) {
  const definition = locations.topologies[topology.id];
  if (!definition || topology.nodes.length !== Object.keys(definition.nodes).length) return topology;
  const expected = new Set(definition.edges.map(([a, b]) => pairKey(a, b)));
  if (topology.links.length !== expected.size || topology.nodes.some(n => !definition.nodes[n.id])
      || topology.links.some(e => !expected.has(pairKey(e.source, e.target)))) return topology;
  return { ...topology,
    geography: { kind: locations.kind, note: locations.note, title: definition.title,
      region: definition.region, bounds: definition.bounds, sources: locations.sources },
    nodes: topology.nodes.map(node => ({ ...node, ...definition.nodes[node.id],
      label: `${definition.nodes[node.id].city} · ${node.id.toUpperCase()}` })),
  };
}

export function projection(geography) {
  const [west, south, east, north] = geography.bounds;
  const cosine = Math.cos((north + south) * Math.PI / 360);
  const scale = 1000 / ((east - west) * cosine);
  return {
    width: 1000, height: (north - south) * scale,
    point: (longitude, latitude) => ({ x: (longitude - west) * cosine * scale, y: (north - latitude) * scale }),
  };
}

export function geographicPaths(geography) {
  const project = projection(geography);
  return (cartography.regions[geography.region] || []).map(country => ({ name: country.name,
    path: country.rings.map(ring => ring.map(([lon, lat], index) => {
      const p = project.point(lon, lat);
      return `${index ? 'L' : 'M'}${p.x.toFixed(2)},${p.y.toFixed(2)}`;
    }).join(' ') + ' Z').join(' '),
  }));
}

export function fitGeography(cy, geography) {
  const p = projection(geography), padding = 48;
  const zoom = Math.max(0.08, Math.min((cy.width() - padding * 2) / p.width, (cy.height() - padding * 2) / p.height));
  cy.viewport({ zoom, pan: { x: (cy.width() - p.width * zoom) / 2, y: (cy.height() - p.height * zoom) / 2 } });
}
