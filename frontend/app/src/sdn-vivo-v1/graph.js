// Configuración de red y cálculos locales. No son mediciones ni predicciones ML.
export const DEMO = {
  id: "demo", name: "Demostración", source: "Ejemplo original de seis nodos",
  configurationSource: "Capacidades ilustrativas de tu App.jsx original.",
  hostAttachmentSource: "Sin información de hosts en este ejemplo.",
  illustrative: true,
  nodes: ["S1", "S2", "S3", "S4", "S5", "S6"].map((id) => ({ id, label: id })),
  links: [
    ["S1", "S2", 1000], ["S1", "S3", 100], ["S2", "S3", 100],
    ["S2", "S4", 1000], ["S3", "S4", 1000], ["S4", "S5", 1000],
    ["S5", "S6", 1000],
  ].map(([source, target, capacity], i) => ({
    id: `demo-${i + 1}`, source, target, capacity, delay: null,
    portU: null, portV: null, queue: null,
  })),
};

export const POLICIES = {
  hops: { label: "Menor número de saltos", unit: "saltos", description: "Cada enlace tiene costo 1." },
  delay: { label: "Menor retardo configurado", unit: "ms", description: "Suma el retardo configurado de los enlaces; no mide latencia." },
  capacity: { label: "Inversa de capacidad nominal", unit: "Σ 1/Mbps", description: "Suma 1/capacidad por enlace; no mide throughput ni maximiza necesariamente el cuello de botella." },
};

const text = (value) => typeof value === "string" ? value.trim() : "";
const compareIds = (a, b) => a.localeCompare(b, "en", { numeric: true });

function number(value, name, { optional = false, positive = false, integer = false } = {}) {
  if (value == null || (typeof value === "string" && value.trim() === "")) {
    if (optional) return null;
    throw new Error(`Falta ${name}.`);
  }
  if (typeof value !== "number" && typeof value !== "string") throw new Error(`${name} no es numérico.`);
  const n = Number(value);
  if (!Number.isFinite(n) || (positive ? n <= 0 : n < 0) || (integer && !Number.isInteger(n))) {
    throw new Error(`Valor inválido en ${name}.`);
  }
  return n;
}

export function parseTopologyDocument(document) {
  if (!document || document.schema_version !== 1 || !document.topologies || Array.isArray(document.topologies)) {
    throw new Error("Usa topologias_desde_csv.json, con schema_version: 1 y topologies.");
  }
  const result = {};
  for (const id of ["nsfnet", "geant2"]) {
    const profile = document.topologies[id];
    if (!profile) continue;
    if (!Array.isArray(profile.nodes) || !profile.nodes.length || !Array.isArray(profile.links) || !profile.links.length) {
      throw new Error(`${id}: faltan nodos o enlaces.`);
    }
    if (profile.nodes.length > 300 || profile.links.length > 3000) throw new Error(`${id}: el mapa supera el tamaño admitido.`);
    const nodes = profile.nodes.map((n) => {
      const nodeId = text(n?.switch);
      if (!/^[a-zA-Z][a-zA-Z0-9_.:-]{0,63}$/.test(nodeId)) throw new Error(`${id}: identificador de nodo inválido.`);
      return { id: nodeId, label: nodeId.toUpperCase(), runtimeSwitch: text(n.runtime_switch), dpid: text(n.dpid), host: text(n.host), hostIp: text(n.host_ip),
        hostPort: number(n.host_port, "host_port", { optional: true, positive: true, integer: true }) };
    });
    const nodeIds = new Set(nodes.map((n) => n.id));
    if (nodeIds.size !== nodes.length) throw new Error(`${id}: hay nodos duplicados.`);
    const linkIds = new Set();
    const pairs = new Set();
    const usedPorts = new Set();
    const links = profile.links.map((e, i) => {
      const source = text(e?.switch_u), target = text(e?.switch_v);
      const linkId = text(e?.link_id) || `${id}-${i + 1}`;
      if (!nodeIds.has(source) || !nodeIds.has(target) || source === target) throw new Error(`${id}: extremos inválidos en ${linkId}.`);
      if (linkIds.has(linkId)) throw new Error(`${id}: identificador de enlace repetido.`);
      linkIds.add(linkId);
      const pair = JSON.stringify([source, target].sort(compareIds));
      if (pairs.has(pair)) throw new Error(`${id}: enlaces paralelos ambiguos; este panel admite un enlace físico por pareja.`);
      pairs.add(pair);
      const portU = number(e.port_u, "port_u", { optional: true, positive: true, integer: true });
      const portV = number(e.port_v, "port_v", { optional: true, positive: true, integer: true });
      for (const [node, port] of [[source, portU], [target, portV]]) {
        if (port === null) continue;
        const key = `${node}:${port}`;
        if (usedPorts.has(key)) throw new Error(`${id}: el puerto ${key} está repetido.`);
        usedPorts.add(key);
      }
      return { id: linkId, source, target, portU, portV,
        capacity: number(e.capacity_mbps, "capacity_mbps", { positive: true }),
        delay: number(e.configured_delay_ms, "configured_delay_ms", { optional: true }),
        queue: number(e.queue_limit_packets, "queue_limit_packets", { optional: true, integer: true }) };
    });
    for (const node of nodes) {
      if (node.hostPort !== null && usedPorts.has(`${node.id}:${node.hostPort}`)) throw new Error(`${id}: el puerto del host colisiona en ${node.id}.`);
    }
    result[id] = { id, name: id === "nsfnet" ? "NSFNET" : "GEANT2", illustrative: false,
      source: text(profile.source_topology_id) || "Mapa importado",
      runId: text(profile.source_run_id), configurationSource: text(profile.configuration_source),
      hostAttachmentSource: text(profile.host_attachment_source),
      createdUtc: text(document.created_utc),
      nodes: nodes.sort((a, b) => compareIds(a.id, b.id)), links };
  }
  if (!Object.keys(result).length) throw new Error("El archivo no contiene nsfnet ni geant2.");
  return result;
}

export function pathSummary(topology, path) {
  if (!Array.isArray(path) || path.length < 2 || new Set(path).size !== path.length) throw new Error("La ruta devuelta no es válida.");
  const nodes = new Set(topology.nodes.map((n) => n.id));
  if (path.some((id) => !nodes.has(id))) throw new Error("La ruta incluye nodos ajenos al mapa seleccionado.");
  const links = [];
  for (let i = 1; i < path.length; i++) {
    const matches = topology.links.filter((e) => (e.source === path[i - 1] && e.target === path[i]) || (e.target === path[i - 1] && e.source === path[i]));
    if (matches.length !== 1) throw new Error("La ruta no coincide con los enlaces del mapa seleccionado.");
    links.push(matches[0]);
  }
  return { path: [...path], edgeIds: links.map((e) => e.id), hops: links.length,
    capacity: Math.min(...links.map((e) => e.capacity)),
    configuredDelay: links.every((e) => e.delay !== null) ? links.reduce((s, e) => s + e.delay, 0) : null };
}

export function dijkstra(topology, origin, destination, policy = "hops") {
  if (!POLICIES[policy]) throw new Error("Política de cálculo desconocida.");
  const adjacency = new Map(topology.nodes.map((n) => [n.id, []]));
  if (!adjacency.has(origin) || !adjacency.has(destination) || origin === destination) throw new Error("Selecciona dos nodos distintos del mapa.");
  // Se exige retardo conocido para todo el mapa: no se omiten enlaces sin avisar.
  if (policy === "delay" && topology.links.some((e) => e.delay === null)) throw new Error("Falta retardo configurado en algún enlace. Elige saltos o capacidad.");
  for (const e of topology.links) {
    const weight = policy === "hops" ? 1 : policy === "delay" ? e.delay : 1 / e.capacity;
    if (!Number.isFinite(weight) || weight < 0) throw new Error("El mapa contiene un costo inválido.");
    adjacency.get(e.source).push({ node: e.target, weight });
    adjacency.get(e.target).push({ node: e.source, weight });
  }
  for (const neighbors of adjacency.values()) neighbors.sort((a, b) => compareIds(a.node, b.node));
  const remaining = new Set([...adjacency.keys()].sort(compareIds));
  const distance = new Map([...remaining].map((id) => [id, Infinity]));
  const previous = new Map();
  distance.set(origin, 0);
  while (remaining.size) {
    let current = null;
    for (const id of remaining) if (current === null || distance.get(id) < distance.get(current)) current = id;
    if (current === null || distance.get(current) === Infinity) break;
    remaining.delete(current);
    if (current === destination) break;
    for (const neighbor of adjacency.get(current)) {
      if (!remaining.has(neighbor.node)) continue;
      const next = distance.get(current) + neighbor.weight;
      if (next < distance.get(neighbor.node)) { distance.set(neighbor.node, next); previous.set(neighbor.node, current); }
    }
  }
  if (!Number.isFinite(distance.get(destination))) throw new Error("No existe una ruta entre estos nodos.");
  const path = [destination];
  while (path[0] !== origin) {
    const parent = previous.get(path[0]);
    if (parent === undefined || path.length > topology.nodes.length) throw new Error("No se pudo reconstruir la ruta.");
    path.unshift(parent);
  }
  return { ...pathSummary(topology, path), cost: distance.get(destination), policy, engine: "local" };
}

export function backendPayload(topology, origin, destination) {
  return { nodos: topology.nodes.map((n) => n.id),
    enlaces: topology.links.map((e) => ({ origen: e.source, destino: e.target, capacidad_mbps: e.capacity })),
    origen: origin, destino: destination, dirigido: false };
}

export function validateBackendRoute(topology, response, origin, destination) {
  const summary = pathSummary(topology, response?.ruta);
  if (summary.path[0] !== origin || summary.path.at(-1) !== destination) throw new Error("La API devolvió una ruta con otros extremos.");
  if (typeof response.costo_total !== "number" || !Number.isFinite(response.costo_total) || response.costo_total < 0) throw new Error("La API devolvió un costo inválido.");
  return { ...summary, cost: response.costo_total, policy: "backend", engine: "backend" };
}

export const nodeKey = (id) => `node:${id}`;
export const edgeKey = (id) => `edge:${id}`;
