import ComparacionRutas from "./ComparacionRutas.jsx";
import PrediccionesEnlaceV1 from "./PrediccionesEnlaceV1.jsx";
import ModeloComunV1 from "./ModeloComunV1.jsx";
import ModelosMl from "./ModelosMl.jsx";
import GeographicBackdrop from "../geografia/GeographicBackdrop.jsx";
import { fitGeography, projection } from "../geografia/geography.js";
import { ROUTES, edgeCriteria, comparisonMatchesNetwork } from "./fiveModelView.js";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import {
  Activity, AlertCircle, ArrowDownUp, ArrowRight, BrainCircuit, CheckCircle2,
  Clock3, Database, Gauge, LayoutDashboard, Network, RefreshCw, Route, Server,
  ShieldCheck, SlidersHorizontal,
} from "lucide-react";
import { LiveMetrics } from "../sdn-vivo-v1/LiveMetrics.jsx";
import { infrastructureElements, infrastructureKey } from './infrastructure.js';
import { InfrastructureDetails, SwitchOperational, LinkOperational } from './OperationalDetails.jsx';
import { DEMO, POLICIES, backendPayload, dijkstra, edgeKey, nodeKey, parseTopologyDocument, validateBackendRoute } from "../sdn-vivo-v1/graph.js";

const navigation = [
  { label: "Resumen", icon: LayoutDashboard, target: "overview" },
  { label: "Topología", icon: Network, target: "topology" },
  { label: "Enrutamiento", icon: Route, target: "routing" },
  { label: "Enlaces", icon: Activity, target: "links" },
  { label: "Integración", icon: Server, target: "integration" },
];
const INITIAL_API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8001";
const format = (n, decimals = 3) => n == null ? "—" : Number(n).toLocaleString("es-CO", { maximumFractionDigits: decimals });
const apiLabel = { checking: "Comprobando", online: "Responde", offline: "Sin conexión" };
const ROUTE_POLICIES = {
  ...POLICIES,
  ml: { label: "ML · modelo actual del inspector", unit: "QoS normalizado", description: "Este cálculo individual conserva el servicio del inspector. Para usar Polinomial, Decision Tree, Random Forest y XGBoost, pulsa Comparar las 5 rutas. No instala reglas ni modifica el tráfico." },
};

function PanelHeading({ icon: Icon, title, caption, children }) {
  return <div className="panel-header"><div><div className="panel-title"><Icon size={19} /><h2>{title}</h2></div>{caption && <p>{caption}</p>}</div>{children}</div>;
}
function Detail({ label, children }) {
  return <div className="sdn-detail"><dt>{label}</dt><dd>{children || "—"}</dd></div>;
}
function LinkMetrics() {
  return <><div className="sdn-measurement-label">MEDICIONES DEL ENLACE</div><div className="metrics-grid">
    <div className="metric-item"><Activity size={17} /><span>Loss</span><strong>— %</strong></div>
    <div className="metric-item"><Clock3 size={17} /><span>Delay</span><strong>— ms</strong></div>
    <div className="metric-item"><ArrowDownUp size={17} /><span>Throughput</span><strong>— Mbps</strong></div>
    <div className="metric-item"><BrainCircuit size={17} /><span>Predicción ML</span><strong>Pendiente</strong></div>
  </div><p className="sdn-muted">Sin telemetría conectada. La capacidad y el retardo configurados no son mediciones.</p></>;
}

export default function PanelSdn({ live }) {
  const topologyRef = useRef(null);
  const cyRef = useRef(null);
  const geoLayerRef = useRef(null);
  const fitMapRef = useRef(null);
  const fileRef = useRef(null);
  const routeAbortRef = useRef(null);
  const routeRevisionRef = useRef(0);
  const profileRevisionRef = useRef(0);
  const [profiles, setProfiles] = useState({});
  const [manualTopology, setTopology] = useState(DEMO);
  const topology = live ? live.topology : manualTopology;
  const [mapLayout, setMapLayout] = useState("geographic");
  const [showHosts, setShowHosts] = useState(true);
  const [showControl, setShowControl] = useState(true);
  const controllerIp = live?.snapshot.controller?.ip;
  const geographic = mapLayout === "geographic" && Boolean(topology.geography);
  const [mapMessage, setMapMessage] = useState("Cargando el mapa, si está disponible…");
  const [mapError, setMapError] = useState("");
  const [activeSection, setActiveSection] = useState("Resumen");
  const [selected, setSelected] = useState(null);
  const [origin, setOrigin] = useState(topology.nodes[0]?.id || "");
  const [destination, setDestination] = useState(topology.nodes.at(-1)?.id || "");
  const [policy, setPolicy] = useState("capacity");
  const [engine, setEngine] = useState("local");
  const [storedRouteResult, setRouteResult] = useState(null);
  const [comparisonStored, setComparison] = useState(null);
  const [visibility, setVisibility] = useState(Object.fromEntries(ROUTES.map(r => [r.key, true])));
  const routeResult = live && (!live.ready || storedRouteResult?.graphVersion !== live.graphVersion) ? null : storedRouteResult;
  const comparison = comparisonStored;
  const comparisonForMap = comparisonMatchesNetwork(comparisonStored, live) ? comparisonStored : null;
  const [routeError, setRouteError] = useState("");
  const [routeLoading, setRouteLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [apiUrl, setApiUrl] = useState(live?.apiUrl || INITIAL_API.replace(/\/+$/, ""));
  const [apiDraft, setApiDraft] = useState(live?.apiUrl || INITIAL_API);
  const [apiError, setApiError] = useState("");
  const [backendStatus, setBackendStatus] = useState("checking");
  const [lastChecked, setLastChecked] = useState("—");
  const [healthRevision, setHealthRevision] = useState(0);

  const clearIndividualRoute = useCallback(() => {
    routeRevisionRef.current += 1;
    routeAbortRef.current?.abort();
    routeAbortRef.current = null;
    setRouteResult(null);
    setRouteError("");
    setRouteLoading(false);
  }, []);
  const clearRoute = useCallback(() => {
    clearIndividualRoute();
    setComparison(null);
  }, [clearIndividualRoute]);

  const activateTopology = useCallback((profile) => {
    clearRoute();
    setTopology(profile);
    setOrigin(profile.nodes[0].id);
    setDestination(profile.nodes.at(-1).id);
    setPolicy("hops");
    setSelected(null);
    setSearch("");
  }, [clearRoute]);

  const acceptDocument = useCallback((document, filename) => {
    const maps = parseTopologyDocument(document);
    setProfiles(maps);
    activateTopology(maps.nsfnet || maps.geant2);
    setMapMessage(`${filename} · configuración importada; sin mediciones en vivo`);
    setMapError("");
  }, [activateTopology]);

  useEffect(() => {
    if (live) return undefined;
    const controller = new AbortController();
    let disposed = false;
    const version = profileRevisionRef.current;
    const timer = setTimeout(() => controller.abort(), 7000);
    async function loadMap() {
      try {
        const url = new URL("./sdn-panel-v1/topologias_desde_csv.json", window.location.href);
        const response = await fetch(url, { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error("Mapa todavía no disponible");
        const document = await response.json();
        if (!controller.signal.aborted && profileRevisionRef.current === version) acceptDocument(document, "topologias_desde_csv.json");
      } catch {
        if (profileRevisionRef.current === version && !disposed) setMapMessage("Ejemplo original. Importa topologias_desde_csv.json para ver NSFNET y GEANT2.");
      } finally {
        clearTimeout(timer);
      }
    }
    loadMap();
    return () => { disposed = true; clearTimeout(timer); controller.abort(); };
  }, [acceptDocument, live]);

  // La salud de FastAPI no demuestra conectividad con RYU ni avance de la captura.
  useEffect(() => {
    let disposed = false;
    let activeController = null;
    let timeout = null;
    let poll = null;
    async function check() {
      const controller = new AbortController();
      activeController = controller;
      timeout = setTimeout(() => controller.abort(), 5000);
      try {
        const response = await fetch(`${apiUrl}/api/salud`, { signal: controller.signal, cache: "no-store" });
        if (!disposed) setBackendStatus(response.ok ? "online" : "offline");
      } catch {
        if (!disposed) setBackendStatus("offline");
      } finally {
        clearTimeout(timeout);
        if (!disposed) { setLastChecked(new Date().toLocaleTimeString("es-CO")); poll = setTimeout(check, 20000); }
      }
    }
    check();
    return () => { disposed = true; activeController?.abort(); clearTimeout(timeout); clearTimeout(poll); };
  }, [apiUrl, healthRevision]);

  useEffect(() => () => { routeRevisionRef.current += 1; routeAbortRef.current?.abort(); }, []);

  useEffect(() => {
    const count = topology.nodes.length;
    const project = geographic ? projection(topology.geography) : null;
    const positions = new Map(topology.nodes.map((node, i) => [node.id, geographic ? project.point(node.longitude, node.latitude)
      : { x: 220 * Math.cos(i * Math.PI * 2 / count), y: 220 * Math.sin(i * Math.PI * 2 / count) }]));
    const cy = cytoscape({
      container: topologyRef.current,
      elements: [
        ...topology.nodes.map((node) => ({ data: { id: nodeKey(node.id), nodeId: node.id,
          label: node.city ? `${node.city}\n${node.id.toUpperCase()}` : node.label,
          labelAlign: node.labelAlign || "right", labelValign: node.labelValign || "bottom",
          labelMarginX: node.labelAlign === "left" ? -10 : 10,
          labelMarginY: node.labelValign === "top" ? -8 : node.labelValign === "bottom" ? 8 : 0 },
          position: positions.get(node.id) })),
        ...topology.links.map((e) => ({ data: { id: edgeKey(e.id), linkId: e.id, source: nodeKey(e.source), target: nodeKey(e.target), label: `${format(e.capacity, 1)} Mbps` } })),
        ...infrastructureElements(topology, positions, { ip: controllerIp }, showHosts, showControl),
      ],
      style: [
        { selector: "node", style: { "background-color": geographic ? "#163b52" : "#142d49", "border-color": "#38bdf8", "border-width": geographic ? 3 : 2,
          label: "data(label)", color: "#e2eaf5", "font-size": geographic ? 22 : 12, "font-weight": 700,
          "text-wrap": "wrap", "text-max-width": geographic ? 210 : 120,
          "text-background-color": "#0b1828", "text-background-opacity": 0.87, "text-background-padding": 3,
          "text-valign": geographic ? "data(labelValign)" : topology.geography ? "bottom" : "center",
          "text-halign": geographic ? "data(labelAlign)" : "center",
          "text-margin-x": geographic ? "data(labelMarginX)" : 0,
          "text-margin-y": geographic ? "data(labelMarginY)" : topology.geography ? 9 : 0,
          width: geographic ? 24 : topology.geography ? 32 : 44, height: geographic ? 24 : topology.geography ? 32 : 44 } },
        { selector: "edge", style: { width: geographic ? 3 : 2, "line-color": geographic ? "#7495ae" : "#405a78", "curve-style": "bezier", label: geographic ? "" : "data(label)", color: "#9aacc3", "font-size": 9, "text-background-color": "#0b1626", "text-background-opacity": 0.94, "text-background-padding": 3 } },
        { selector: "edge.sdn-edge-down", style: { "line-color": "#7e5665", "line-style": "dashed", opacity: 0.65 } },
        { selector: "edge.route-edge", style: { "line-color": "#34d399", width: 5, "z-index": 999 } },
        { selector: "edge.route-ml", style: { "line-color": "#c084fc", "line-style": "dashed" } },
        { selector: "node.route-node", style: { "background-color": "#14532d", "border-color": "#4ade80", "border-width": 4 } },
        { selector: "edge.comparison-conventional", style: { "line-color": "#94a3b8", width: 6, "z-index": 1000 } },
        { selector: "edge.comparison-polinomial", style: { "line-color": "#38bdf8", width: 6, "line-style": "solid", "z-index": 1000 } },
        { selector: "edge.comparison-decision-tree", style: { "line-color": "#fb923c", width: 6, "line-style": "dashed", "z-index": 1000 } },
        { selector: "edge.comparison-random-forest", style: { "line-color": "#34d399", width: 6, "line-style": "dotted", "z-index": 1000 } },
        { selector: "edge.comparison-xgboost", style: { "line-color": "#c084fc", width: 5, "line-style": "dashed", "z-index": 1001 } },
        { selector: "edge.comparison-shared", style: { "line-color": "#fbbf24", width: 7, "line-style": "solid", "z-index": 1002,
          label: "data(comparisonLabel)", "font-size": geographic ? 18 : 10 } },
        { selector: "node:selected", style: { "border-color": "#f6c777", "border-width": 5 } },
        { selector: "edge:selected", style: { "line-color": "#f6c777", width: 5 } },
        { selector: 'node[kind="host"]', style: { shape: 'rectangle', width: geographic ? 17 : 24, height: geographic ? 17 : 24,
          'background-color': '#12483c', 'border-color': '#34d399', 'font-size': geographic ? 15 : 10,
          'text-halign': 'center', 'text-valign': 'bottom', 'text-margin-x': 0, 'text-margin-y': 4 } },
        { selector: 'node[kind="controller"]', style: { shape: 'round-rectangle', width: geographic ? 66 : 75, height: geographic ? 34 : 36,
          'background-color': '#39264e', 'border-color': '#c084fc', 'font-size': geographic ? 16 : 11,
          'text-halign': 'center', 'text-valign': 'center', 'text-margin-x': 0, 'text-margin-y': 0 } },
        { selector: 'edge[kind="access"]', style: { 'line-color': '#34d399', width: 1.5, label: '' } },
        { selector: 'edge[kind="control"]', style: { 'line-color': '#c084fc', 'line-style': 'dashed', opacity: 0.35, width: 1, label: '', 'z-index': 0 } },
        { selector: '.infra-unverified', style: { opacity: 0.4 } },
      ],
      layout: geographic || !count ? { name: "preset", fit: false } : { name: "cose", animate: false, randomize: false, padding: 50, nodeRepulsion: 450000, idealEdgeLength: topology.geography ? 140 : 105, nodeDimensionsIncludeLabels: true },
      wheelSensitivity: 0.2,
    });
    cyRef.current = cy;
    const syncMap = () => geoLayerRef.current?.setAttribute("transform", `translate(${cy.pan().x},${cy.pan().y}) scale(${cy.zoom()})`);
    fitMapRef.current = () => { if (!cy.destroyed()) { if (geographic) { fitGeography(cy, topology.geography); if (showControl || showHosts) cy.fit(cy.elements(), 50); } else cy.fit(undefined, 50); syncMap(); } };
    cy.on("pan zoom", syncMap);
    if (geographic) { fitMapRef.current(); cy.nodes().lock(); }
    cy.on("tap", "node", (event) => setSelected({ type: event.target.data('kind') || 'node', id: event.target.data('owner') || event.target.data("nodeId") || '' }));
    cy.on("tap", "edge", (event) => setSelected({ type: event.target.data('kind') || 'link', id: event.target.data('owner') || event.target.data("linkId") }));
    cy.on("tap", (event) => { if (event.target === cy) setSelected(null); });
    const observer = new ResizeObserver(() => { if (!cy.destroyed()) { cy.resize(); if (geographic) fitMapRef.current?.(); } });
    observer.observe(topologyRef.current);
    return () => { observer.disconnect(); cy.destroy(); cyRef.current = null; };
  }, [topology, geographic, controllerIp, showHosts, showControl]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("route-node route-edge route-ml");
    if (routeResult) {
      routeResult.path.forEach((id) => cy.getElementById(nodeKey(id)).addClass("route-node"));
      routeResult.edgeIds.forEach((id) => cy.getElementById(edgeKey(id)).addClass(routeResult.policy === "ml" ? "route-edge route-ml" : "route-edge"));
    }
  }, [topology, geographic, routeResult, showHosts, showControl]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.edges().removeClass("comparison-conventional comparison-polinomial comparison-decision-tree comparison-random-forest comparison-xgboost comparison-shared");
    if (!comparisonForMap) return;
    cy.edges().forEach(edge => {
      const using = edgeCriteria(comparisonForMap, visibility, edge.data("linkId"));
      edge.data("comparisonLabel", using.length > 1 ? `${using.length} rutas` : "");
      if (using.length) edge.addClass(using.length > 1 ? "comparison-shared" : using[0].className);
    });
  }, [topology, geographic, comparisonForMap, visibility, showHosts, showControl]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().unselect();
    if (selected) cy.getElementById(selected.type === "node" ? nodeKey(selected.id) : selected.type === 'link' ? edgeKey(selected.id) : infrastructureKey(selected.type, selected.id)).select();
  }, [topology, geographic, selected, showHosts, showControl]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !live) return;
    cy.edges().forEach((edge) => {
      if (edge.data('kind')) return;
      const state = live.edgeStates.get(edge.data("linkId"));
      edge.toggleClass("sdn-edge-down", !live.ready || state?.state !== "up");
    });
    cy.elements('[kind="control"], [kind="controller"]').toggleClass('infra-unverified', !live.ready || !live.snapshot.ryu?.identity_verified);
    cy.elements('[kind="host"], [kind="access"]').forEach(element => {
      const host = live.snapshot.hosts_runtime?.find(h => h.switch === element.data('owner'));
      element.toggleClass('infra-unverified', !live.ready || host?.state !== 'up');
    });
  }, [live, topology, geographic, showHosts, showControl]);

  const node = selected?.type === "node" ? topology.nodes.find((n) => n.id === selected.id) : null;
  const link = selected?.type === "link" ? topology.links.find((e) => e.id === selected.id) : null;
  const neighbors = node ? topology.links.filter((e) => e.source === node.id || e.target === node.id) : [];
  const labels = useMemo(() => new Map(topology.nodes.map((n) => [n.id, n.label])), [topology]);
  const filteredLinks = useMemo(() => {
    const term = search.trim().toLowerCase();
    return topology.links.filter((e) => [e.id, e.source, e.target, labels.get(e.source), labels.get(e.target)].some((value) => value?.toLowerCase().includes(term)));
  }, [topology, search, labels]);
  const hasDelay = topology.links.every((e) => e.delay !== null);

  async function importMap(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const version = ++profileRevisionRef.current;
    try {
      if (file.size > 4 * 1024 * 1024) throw new Error("El mapa debe pesar menos de 4 MB. No selecciones el dataset CSV.");
      const document = JSON.parse(await file.text());
      if (profileRevisionRef.current === version) acceptDocument(document, file.name);
    } catch (error) {
      if (profileRevisionRef.current === version) setMapError(`No se cargó el archivo. ${error.message}`);
    }
  }

  async function calculateRoute(event) {
    event.preventDefault();
    clearRoute();
    const version = routeRevisionRef.current;
    if (!live && engine === "local") {
      try { setRouteResult(dijkstra(topology, origin, destination, policy)); }
      catch (error) { setRouteError(error.message); }
      return;
    }
    setRouteLoading(true);
    const controller = new AbortController();
    routeAbortRef.current = controller;
    const timer = setTimeout(() => controller.abort(), policy === "ml" ? 60000 : 10000);
    try {
      const smart = Boolean(live && policy === "ml");
      const livePayload = live ? { topology_instance_id: live.instanceId, graph_version: live.graphVersion, origen: origin, destino: destination } : null;
      const response = await fetch(`${apiUrl}${smart ? "/api/sdn/rutas/comparar" : live ? "/api/sdn/rutas" : "/api/rutas/dijkstra/convencional"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(smart ? { ...livePayload, selection_revision: live.snapshot.selection_revision } : live ? { ...livePayload, criterio: policy } : backendPayload(topology, origin, destination)), signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `La API respondió ${response.status}.`);
      if (live && (data.topology_instance_id !== live.instanceId || data.graph_version !== live.graphVersion)) throw new Error("Cambió la red durante el cálculo. Vuelve a intentarlo.");
      if (smart && (data.selection_revision !== live.snapshot.selection_revision || data.session_id !== live.snapshot.session_id)) throw new Error("Cambió la sesión seleccionada. Vuelve a calcular.");
      if (smart && (!data.inteligente || data.ml?.status !== "available")) throw new Error(`Ruta inteligente no disponible: faltan predicciones válidas y recientes. ${data.ml?.motivo || ""}`);
      const routeData = smart ? { ruta: data.inteligente.ruta, costo_total: data.inteligente.costo_qos } : data;
      const result = { ...validateBackendRoute(topology, routeData, origin, destination), policy, engine: live ? "live" : "backend", graphVersion: data.graph_version,
        ...(smart ? { ml: data.ml, metrics: data.inteligente, weights: data.pesos, scales: data.escalas, warnings: data.advertencias } : {}) };
      if (routeRevisionRef.current === version) setRouteResult(result);
    } catch (error) {
      if (routeRevisionRef.current === version) setRouteError(error.name === "AbortError" ? `La API no respondió dentro de ${policy === "ml" ? "60" : "10"} segundos.` : `No se obtuvo una ruta: ${error.message}`);
    } finally {
      clearTimeout(timer);
      if (routeRevisionRef.current === version) { setRouteLoading(false); routeAbortRef.current = null; }
    }
  }

  function applyApi(event) {
    event.preventDefault();
    try {
      const parsed = new URL(apiDraft.trim());
      if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash) throw new Error("URL inválida");
      clearRoute();
      setApiUrl(parsed.toString().replace(/\/+$/, ""));
      live?.setApiUrl(parsed.toString().replace(/\/+$/, ""));
      setBackendStatus("checking");
      setHealthRevision((v) => v + 1);
      setApiError("");
    } catch { setApiError("Escribe una dirección HTTP o HTTPS, sin credenciales ni parámetros."); }
  }

  return <div className={`app-shell sdn-panel-v1 ${live && !live.ready ? "sdn-net-unverified" : ""}`}>
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><Network size={25} /></div><div><h2>SDN / KDN</h2><span>SERVICE PROVIDER</span></div></div>
      <div className="sidebar-label">ESPACIO DE TRABAJO</div>
      <nav className="navigation" aria-label="Secciones del panel">{navigation.map((item) => <button key={item.target} title={item.label} className={`nav-item ${activeSection === item.label ? "active" : ""}`} onClick={() => { setActiveSection(item.label); document.getElementById(item.target)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}><item.icon size={19} /><span>{item.label}</span></button>)}</nav>
      {live?.topologyControl}
      <div className="sidebar-bottom"><div className="sidebar-status-icon"><ShieldCheck size={20} /></div><div><strong>Laboratorio SDN</strong><span>Mininet ↔ RYU ↔ interfaz</span></div></div>
      <div className="sidebar-version">NSFNET + GEANT2 · RED ACTIVA</div>
    </aside>
    <main className="main-content">
      <header className="topbar"><div className="breadcrumb"><span>SDN / KDN</span><ArrowRight size={14} /><strong>{activeSection}</strong></div><div className="topbar-right"><span className="environment-label">WINDOWS · RYU · MININET</span><button className="icon-button" title="Comprobar FastAPI" onClick={() => { setBackendStatus("checking"); setHealthRevision((v) => v + 1); }}><RefreshCw size={17} /></button></div></header>
      <div className="page-container">
        <section className="page-heading" id="overview"><div><div className="eyebrow">OPERACIONES DE RED / SDN</div><h1>Red activa del laboratorio</h1><p>La misma topología que ejecutas en Mininet, verificada con RYU.</p></div><span className={`demo-label ${topology.illustrative ? "" : "sdn-imported-label"}`}><span />{live ? (live.ready ? "RED ACTIVA VERIFICADA" : "ESPERANDO CONEXIÓN") : "CONFIGURACIÓN"}</span></section>

        {live ? live.controls : <section className="panel sdn-map-toolbar" aria-label="Elegir topología">
          <div className="sdn-topology-field"><label className="field-label" htmlFor="sdn-topology">TOPOLOGÍA</label><select id="sdn-topology" className="select-control" value={topology.id} onChange={(event) => activateTopology(event.target.value === "demo" ? DEMO : profiles[event.target.value])}><option value="demo">Demostración · 6 nodos</option><option value="nsfnet" disabled={!profiles.nsfnet}>NSFNET{profiles.nsfnet ? "" : " · importar mapa"}</option><option value="geant2" disabled={!profiles.geant2}>GEANT2{profiles.geant2 ? "" : " · importar mapa"}</option></select></div>
          <p className="sdn-source-note" role="status">{mapMessage}</p><input ref={fileRef} type="file" accept=".json,application/json" className="sdn-file-input" aria-label="Archivo de topologías" onChange={importMap} /><button className="secondary-button" onClick={() => fileRef.current?.click()}><Database size={15} /> Importar mapa JSON</button>
        </section>}
        {mapError && <div className="error-message sdn-banner" role="alert"><AlertCircle size={17} />{mapError}</div>}

        <section className="stats-grid" aria-label="Resumen de la topología">
          <article className="stat-card"><div className="stat-top"><span>Nodos de red</span><Network size={19} /></div><div className="stat-value">{topology.id === "none" ? "—" : format(topology.nodes.length, 0)}</div><div className="stat-description">Switches de {topology.name}</div></article>
          <article className="stat-card"><div className="stat-top"><span>Enlaces físicos</span><ArrowDownUp size={19} /></div><div className="stat-value">{topology.id === "none" ? "—" : format(topology.links.length, 0)}</div><div className="stat-description">Enlaces físicos observados</div></article>
          <article className="stat-card"><div className="stat-top"><span>FastAPI</span><Server size={19} /></div><div className={`stat-value status-value ${backendStatus}`}>{apiLabel[backendStatus]}</div><div className="stat-description">API del laboratorio SDN/KDN</div></article>
          <ModeloComunV1 apiUrl={apiUrl} />
        </section>

        <section className="content-grid sdn-explorer-grid">
          <article className="panel topology-panel" id="topology">
            <PanelHeading icon={Network} title={topology.name} caption={geographic ? `${topology.geography.title} · ciudades de referencia` : "Nodos y enlaces de la sesión activa"}>
              <button className="secondary-button" onClick={() => fitMapRef.current?.()}>Ajustar vista</button>
            </PanelHeading>
            <div className="sdn-map-layout" role="group" aria-label="Disposición del mapa">
              <button type="button" disabled={!topology.geography} aria-pressed={geographic} onClick={() => setMapLayout("geographic")}>Mapa geográfico</button>
              <button type="button" aria-pressed={!geographic} onClick={() => setMapLayout("logical")}>Esquema de red</button>
              {topology.geography && <span>{topology.geography.title} · {topology.nodes.length} ubicaciones</span>}
            </div>
            <div className="sdn-infrastructure-controls"><label><input type="checkbox" checked={showHosts} onChange={e => setShowHosts(e.target.checked)} />Hosts y acceso</label><label><input type="checkbox" checked={showControl} onChange={e => setShowControl(e.target.checked)} />Controlador y conexiones OpenFlow</label></div>
            <div className={`sdn-geography-stage ${geographic ? `is-geographic region-${topology.geography.region}` : ""}`}>
              {geographic && <GeographicBackdrop geography={topology.geography} layerRef={geoLayerRef} />}
              <div className="topology-canvas" ref={topologyRef} role="img" aria-label={`Mapa interactivo de ${topology.name}: ${topology.nodes.length} nodos y ${topology.links.length} enlaces. Las ciudades son referencias visuales del laboratorio; los identificadores de red se conservan.`} />
            </div>
            <div className="topology-footer"><div className="legend-item"><span className="legend-node" />Switch</div><div className="legend-item"><span className="legend-line" />Enlace de núcleo</div><div className="legend-item"><span className="sdn-legend-host" />Host</div><div className="legend-item"><span className="sdn-legend-control" />Control OpenFlow</div><div className="legend-item"><span className="sdn-legend-inspected" />Selección</div></div>
            {comparisonForMap && <div className="sdn-map-route-key">{ROUTES.map(r => <span key={r.key} style={{ color: r.color }}><i style={{ background: r.color }} />{r.short}</span>)}<span style={{ color: "#fbbf24" }}><i style={{ background: "#fbbf24" }} />Compartido</span></div>}
            <p className="sdn-muted">{geographic ? "Arrastra el mapa para desplazarlo y usa la rueda para acercar. Selecciona un enlace para consultar su capacidad y sus métricas." : "Las etiquetas de enlace muestran capacidad nominal. Arrastra los nodos para reorganizar el esquema."}</p>
            {topology.geography && <details className="sdn-geography-note"><summary>Sobre las ubicaciones</summary><p>{topology.geography.note}</p><p>Coordenadas aproximadas de las ciudades. La posición del mapa no determina el retardo ni la capacidad de los enlaces.</p><a href="https://www.naturalearthdata.com/about/terms-of-use/" target="_blank" rel="noreferrer">Cartografía: Natural Earth · dominio público</a></details>}
            <details className="sdn-node-list"><summary>Seleccionar nodo o ciudad mediante teclado</summary><div className="sdn-node-buttons">{topology.nodes.map(n => <button className="secondary-button" key={n.id} onClick={() => setSelected({ type: "node", id: n.id })}>{n.label}</button>)}</div></details>
            <details className="sdn-node-list"><summary>Seleccionar hosts o controlador mediante teclado</summary><div className="sdn-node-buttons">{topology.nodes.filter(n => n.host).map(n => <button className="secondary-button" key={n.id} onClick={() => setSelected({ type: 'host', id: n.id })}>{n.host}</button>)}{controllerIp && <button className="secondary-button" onClick={() => setSelected({ type: 'controller', id: '' })}>RYU · {controllerIp}</button>}</div></details>
          </article>

          <article className="panel sdn-inspector" id="details"><PanelHeading icon={SlidersHorizontal} title="Detalles del elemento" caption={node ? `Switch ${node.label}` : link ? `Enlace ${labels.get(link.source)} ↔ ${labels.get(link.target)}` : "Selecciona un elemento del mapa"} />
            {selected && !['node', 'link'].includes(selected.type) && <InfrastructureDetails selected={selected} topology={topology} snapshot={live?.snapshot} />}
            {node && live && <SwitchOperational key={`${live.instanceId}:${node.id}`} live={live} node={node} />}
            {link && live && <LinkOperational key={`${live.instanceId}:${link.id}`} live={live} link={link} />}
            {!selected && <div className="sdn-inspector-placeholder"><Network size={35} /><strong>Explora la red</strong><p>Haz clic en un switch o en una conexión para ver su configuración.</p><span>También puedes usar la tabla de enlaces.</span></div>}
            {node && <><dl className="sdn-details">{node.city && <><Detail label="Ubicación de referencia">{node.city}</Detail><Detail label="País">{node.country}</Detail>{node.state && <Detail label="Estado">{node.state}</Detail>}<Detail label="Latitud aproximada">{format(node.latitude, 3)}°</Detail><Detail label="Longitud aproximada">{format(node.longitude, 3)}°</Detail></>}<Detail label="Identificador">{node.id}</Detail><Detail label="Switch en Mininet">{node.runtimeSwitch}</Detail><Detail label="DPID">{node.dpid}</Detail><Detail label="Host asociado">{node.host}</Detail><Detail label="IP del host">{node.hostIp}</Detail><Detail label="Puerto al host">{format(node.hostPort, 0)}</Detail><Detail label="Enlaces vecinos">{format(neighbors.length, 0)}</Detail></dl>{!topology.illustrative && <p className="sdn-muted">{topology.hostAttachmentSource || "Consulta la procedencia del mapa antes de interpretar la asociación de hosts."}</p>}<div className="sdn-inline-actions"><button className="secondary-button" onClick={() => { clearRoute(); setOrigin(node.id); }}>Usar como origen</button><button className="secondary-button" onClick={() => { clearRoute(); setDestination(node.id); }}>Usar como destino</button></div><h3 className="sdn-subheading">Enlaces del nodo</h3><div className="sdn-neighbors">{neighbors.map((e) => <button key={e.id} onClick={() => setSelected({ type: "link", id: e.id })}><span>{labels.get(e.source)} ↔ {labels.get(e.target)}</span><span>{format(e.capacity)} Mbps <ArrowRight size={13} /></span></button>)}</div></>}
            {link && <><dl className="sdn-details"><Detail label="Estado del enlace">{live?.edgeStates.get(link.id)?.state === "up" && live.ready ? "Activo" : "No disponible / sin verificar"}</Detail><Detail label="Capacidad nominal">{format(link.capacity)} Mbps</Detail><Detail label="Retardo configurado">{link.delay === null ? "No disponible" : `${format(link.delay)} ms`}</Detail><Detail label={`Puerto en ${labels.get(link.source)}`}>{format(link.portU, 0)}</Detail><Detail label={`Puerto en ${labels.get(link.target)}`}>{format(link.portV, 0)}</Detail><Detail label="Límite de cola">{link.queue === null ? "No disponible" : `${format(link.queue, 0)} paquetes`}</Detail><Detail label="Identificador">{link.id}</Detail></dl>{live ? <><LiveMetrics live={live} linkId={link.id} /><PrediccionesEnlaceV1 live={live} linkId={link.id} apiUrl={apiUrl} /></> : <LinkMetrics />}</>}
          </article>
        </section>

        <section className="panel sdn-routing" id="routing"><PanelHeading icon={Route} title="Cálculo de rutas" caption="Calcula alternativas; la instalación del flujo ICMP se realiza desde Aplicar y demostrar la ruta"><span className="ready-tag">{policy === "ml" ? "DIJKSTRA + ML" : "DIJKSTRA"}</span></PanelHeading><div className="sdn-routing-grid"><form onSubmit={calculateRoute}>
          {!live && <><label className="field-label" htmlFor="sdn-engine">DÓNDE CALCULAR</label><select id="sdn-engine" className="select-control" value={engine} onChange={(event) => { clearRoute(); setEngine(event.target.value); }}><option value="local">En este panel</option><option value="backend">FastAPI existente</option></select></>}
          {live || engine === "local" ? <><label className="field-label sdn-spaced" htmlFor="sdn-policy">CRITERIO DE LA RUTA</label><select id="sdn-policy" className="select-control" value={policy} onChange={(event) => { clearRoute(); setPolicy(event.target.value); }}>{Object.entries(live ? ROUTE_POLICIES : POLICIES).map(([key, value]) => <option key={key} value={key} disabled={key === "delay" && !hasDelay}>{value.label}{key === "delay" && !hasDelay ? " · falta configuración" : ""}</option>)}</select><p className="sdn-muted">{ROUTE_POLICIES[policy].description}</p></> : <p className="sdn-muted">Usa el endpoint convencional de tu interfaz original. El criterio y el costo los determina el backend.</p>}
          <div className="sdn-endpoints"><div><label className="field-label" htmlFor="sdn-origin">ORIGEN</label><select id="sdn-origin" className="select-control" value={origin} onChange={(event) => { clearRoute(); setOrigin(event.target.value); }}>{topology.nodes.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}</select></div><ArrowRight size={18} /><div><label className="field-label" htmlFor="sdn-destination">DESTINO</label><select id="sdn-destination" className="select-control" value={destination} onChange={(event) => { clearRoute(); setDestination(event.target.value); }}>{topology.nodes.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}</select></div></div>
          <button className="primary-button" disabled={routeLoading || !origin || origin === destination || (live && !live.ready)}><Route size={17} />{routeLoading ? "Calculando…" : policy === "ml" ? "Calcular ruta inteligente" : "Calcular ruta"}</button>{origin === destination && <p className="sdn-muted">Elige origen y destino distintos.</p>}
        </form><div aria-live="polite">{routeError && <div className="error-message" role="alert"><AlertCircle size={17} />{routeError}</div>}{routeResult ? <div className="route-result"><div className="result-heading"><CheckCircle2 size={17} />{routeResult.policy === "ml" ? "Ruta inteligente calculada" : "Ruta calculada"} · {routeResult.engine === "live" ? "red activa en FastAPI" : "panel local"}</div><div className="route-nodes">{routeResult.path.map((id, i) => <span className="route-node-item" key={id}>{i > 0 && <ArrowRight size={13} />}<strong>{labels.get(id)}</strong></span>)}</div><div className="cost-row"><span>Costo {ROUTE_POLICIES[routeResult.policy] ? `(${ROUTE_POLICIES[routeResult.policy].unit})` : "informado por la API"}</span><strong>{format(routeResult.cost, 6)}</strong></div><dl className="sdn-details sdn-route-details"><Detail label="Saltos">{format(routeResult.hops, 0)}</Detail><Detail label="Capacidad mínima nominal">{format(routeResult.capacity)} Mbps</Detail><Detail label="Suma de retardos configurados">{routeResult.configuredDelay === null ? "No disponible" : `${format(routeResult.configuredDelay)} ms`}</Detail>{routeResult.policy === "ml" && <>
            <Detail label="Delay previsto acumulado">{format(routeResult.metrics.delay_previsto_ms)} ms</Detail>
            <Detail label="Loss previsto compuesto">{format(routeResult.metrics.loss_previsto_ratio * 100)} %</Detail>
            <Detail label="Costo de referencia (Σ 1/Mbps)">{format(routeResult.metrics.costo_referencia, 6)}</Detail>
          </>}
          </dl>{routeResult.policy === "ml" && <>
            <p className="sdn-muted">Modelo: {routeResult.ml.modelo_id}. Ventana usada: {new Date(routeResult.ml.feature_start_epoch_s * 1000).toLocaleTimeString("es-CO")} → {new Date(routeResult.ml.feature_end_epoch_s * 1000).toLocaleTimeString("es-CO")}. Resultado guardado de esa ventana; no se actualiza automáticamente.</p>
            <details><summary>Predicciones de los enlaces de esta ruta</summary><div className="sdn-table-scroll"><table className="sdn-table"><caption>Predicciones fijadas a la ventana usada para esta ruta</caption><thead><tr><th>Dirección</th><th>RX Mbps</th><th>Delay ms</th><th>Loss %</th></tr></thead><tbody>
              {routeResult.metrics.predicciones_enlaces.map(e => <tr key={e.link_id}><td><button type="button" className="sdn-table-link" onClick={() => { setSelected({ type: "link", id: e.link_id }); document.getElementById("details")?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>{labels.get(e.origen)} → {labels.get(e.destino)}</button></td><td>{format(e.throughput_rx_mbps)}</td><td>{format(e.delay_ms)}</td><td>{format(e.loss_ratio * 100)}</td></tr>)}
            </tbody></table></div></details>
            <details><summary>Método y pesos utilizados</summary><p className="sdn-muted">Delay {format(routeResult.weights.delay)} · Loss {format(routeResult.weights.loss)} · Capacidad {format(routeResult.weights.capacity)} · Carga RX {format(routeResult.weights.load)}. Escalas: {format(routeResult.scales.delay_ms)} ms, {format(routeResult.scales.loss_ratio * 100)} % y {format(routeResult.scales.capacity_mbps)} Mbps. Puedes configurar los pesos en Comparar rutas.</p>{routeResult.warnings.map(text => <p className="sdn-muted" key={text}>{text}</p>)}</details>
          </>}
          <p className="sdn-muted">Ruta calculada sobre los enlaces disponibles de la red verificada. Las cifras nominales de la ruta no sustituyen las mediciones extremo a extremo.</p><button className="clear-button" onClick={clearRoute}>Limpiar ruta</button></div> : !routeError && <div className="sdn-route-placeholder"><Route size={32} /><strong>Elige el trayecto que quieres explorar</strong><p>{policy === "ml" ? "La ruta inteligente aparecerá en violeta discontinuo en el mapa." : "La ruta aparecerá resaltada en verde en el mapa."}</p><span>La telemetría se muestra cuando hay una ventana reciente.</span></div>}</div></div>
          {live && <ComparacionRutas key={JSON.stringify([apiUrl, live.instanceId, live.graphVersion, live.snapshot.selection_revision, live.ready, origin, destination])} live={live} apiUrl={apiUrl} origin={origin} destination={destination} labels={labels}
            result={comparison} onResult={setComparison} visibility={visibility} onVisibility={setVisibility} onStart={clearIndividualRoute}
            onSelectLink={id => { setSelected({ type: "link", id }); document.getElementById("details")?.scrollIntoView({ behavior: "smooth", block: "start" }); }} />}
          <details className="sdn-evaluation-details"><summary>Evaluación de los cuatro modelos · MSE, RMSE y MAE</summary><ModelosMl apiUrl={apiUrl} topologia={topology.id} /></details>
        </section>

        <section className="panel sdn-links-panel" id="links"><PanelHeading icon={Gauge} title="Inventario de enlaces" caption={`${filteredLinks.length} de ${topology.links.length} enlaces · valores de configuración`} /><label className="field-label" htmlFor="sdn-search">BUSCAR POR NODO O ENLACE</label><input id="sdn-search" type="search" className="select-control sdn-search" placeholder="Buscar por nodo, enlace o ciudad" value={search} onChange={(event) => setSearch(event.target.value)} /><div className="sdn-table-scroll"><table className="sdn-table"><caption className="sdn-sr-only">Enlaces de {topology.name}. Selecciona un enlace para ver su configuración y el estado de sus mediciones.</caption><thead><tr><th scope="col">Enlace</th><th scope="col">Estado</th><th scope="col">Puertos</th><th scope="col">Capacidad nominal</th><th scope="col">Retardo configurado</th><th scope="col">Cola máxima</th></tr></thead><tbody>{filteredLinks.map((e) => <tr key={e.id} className={selected?.type === "link" && selected.id === e.id ? "sdn-selected-row" : ""}><td><button className="sdn-table-link" onClick={() => { setSelected({ type: "link", id: e.id }); document.getElementById("details")?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>{labels.get(e.source)} ↔ {labels.get(e.target)}</button></td><td>{live?.ready ? (live.edgeStates.get(e.id)?.state === "up" ? "Activo" : "No disponible") : "Sin verificar"}</td><td>{format(e.portU, 0)} / {format(e.portV, 0)}</td><td>{format(e.capacity)} Mbps</td><td>{e.delay === null ? "—" : `${format(e.delay)} ms`}</td><td>{e.queue === null ? "—" : `${format(e.queue, 0)} paquetes`}</td></tr>)}</tbody></table>{!filteredLinks.length && <p className="sdn-muted">No hay enlaces que coincidan con la búsqueda.</p>}</div><p className="sdn-muted">Fuente: {topology.source}. {topology.configurationSource}</p></section>

        <section className="panel sdn-integration" id="integration"><PanelHeading icon={Server} title="Integración del laboratorio" caption="Estado comprobado por este panel y conexiones pendientes" /><div className="sdn-vm-grid"><div><strong>VM Mininet</strong><span>Topologías y captura</span><small>{live?.snapshot.capture?.state || "Sin captura registrada"}</small></div><div><strong>VM RYU</strong><span>Controlador y pipeline ML</span><small>{live?.snapshot.ryu?.identity_verified && live.ready ? "Puertos OpenFlow verificados" : "Controlador sin verificar"}</small></div><div><strong>Aplicación Windows</strong><span>React · FastAPI · Cytoscape</span><small>Visualización y cálculo sobre la red activa</small></div></div><form className="sdn-api-form" onSubmit={applyApi}><div><label className="field-label" htmlFor="sdn-api">DIRECCIÓN DE FASTAPI</label><input id="sdn-api" className="select-control" type="url" value={apiDraft} onChange={(event) => setApiDraft(event.target.value)} required /></div><button className="secondary-button">Comprobar API</button><span className={`status-pill ${backendStatus}`}>{apiLabel[backendStatus]}</span></form>{apiError && <p className="error-message" role="alert">{apiError}</p>}<p className="sdn-muted">127.0.0.1 apunta al equipo donde abres el navegador. Si abres el panel desde otro equipo, usa aquí la dirección de la VM que ejecuta FastAPI.</p><div className="last-checked"><RefreshCw size={13} />Última comprobación: {lastChecked} · API consultada: {apiUrl}</div><ModeloComunV1 apiUrl={apiUrl} info /></section>
        <footer className="page-footer"><span>SDN / KDN · NSFNET + GEANT2</span><span>Desarrollo académico · Entorno de laboratorio</span></footer>
      </div>
    </main>
  </div>;
}
