import { useCallback, useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import {
  Activity,
  AlertCircle,
  ArrowDownUp,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  Database,
  Gauge,
  LayoutDashboard,
  Network,
  RefreshCw,
  Route,
  Server,
  ShieldCheck,
  SlidersHorizontal,
  Wifi,
  Zap
} from "lucide-react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

// Topologia ilustrativa. No representa aun la NSFNET real.
const demoTopology = {
  nodes: ["S1", "S2", "S3", "S4", "S5", "S6"],
  links: [
    { origen: "S1", destino: "S2", capacidad_mbps: 1000 },
    { origen: "S1", destino: "S3", capacidad_mbps: 100 },
    { origen: "S2", destino: "S3", capacidad_mbps: 100 },
    { origen: "S2", destino: "S4", capacidad_mbps: 1000 },
    { origen: "S3", destino: "S4", capacidad_mbps: 1000 },
    { origen: "S4", destino: "S5", capacidad_mbps: 1000 },
    { origen: "S5", destino: "S6", capacidad_mbps: 1000 }
  ]
};

const navigation = [
  { label: "Overview", icon: LayoutDashboard, target: "overview" },
  { label: "Topologia", icon: Network, target: "topology" },
  { label: "Enrutamiento", icon: Route, target: "routing" },
  { label: "Metricas", icon: Activity, target: "metrics" },
  { label: "Controlador", icon: Server, target: "controller" }
];

function App() {
  const topologyRef = useRef(null);
  const cyRef = useRef(null);

  const [backendStatus, setBackendStatus] = useState("checking");
  const [lastChecked, setLastChecked] = useState("--");
  const [activeSection, setActiveSection] = useState("Overview");

  const [origin, setOrigin] = useState("S1");
  const [destination, setDestination] = useState("S6");
  const [routeResult, setRouteResult] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState("");

  // Comprobar conexion real con FastAPI.
  const checkBackend = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/salud`);

      if (!response.ok) {
        throw new Error("Backend no disponible");
      }

      setBackendStatus("online");
    } catch {
      setBackendStatus("offline");
    } finally {
      setLastChecked(new Date().toLocaleTimeString());
    }
  }, []);

  useEffect(() => {
    checkBackend();

    const timer = setInterval(checkBackend, 20000);

    return () => clearInterval(timer);
  }, [checkBackend]);

  // Construir la topologia interactiva con Cytoscape.
  useEffect(() => {
    const elements = [
      ...demoTopology.nodes.map((node) => ({
        data: { id: node, label: node }
      })),
      ...demoTopology.links.map((link, index) => ({
        data: {
          id: `link-${index}`,
          source: link.origen,
          target: link.destino,
          label: `${link.capacidad_mbps} Mbps`
        }
      }))
    ];

    const cy = cytoscape({
      container: topologyRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#142d49",
            "border-color": "#38bdf8",
            "border-width": 2,
            label: "data(label)",
            color: "#e2eaf5",
            "font-size": 12,
            "font-weight": 700,
            "text-valign": "center",
            "text-halign": "center",
            width: 48,
            height: 48
          }
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#405a78",
            "curve-style": "bezier",
            label: "data(label)",
            color: "#9aacc3",
            "font-size": 9,
            "text-background-color": "#0b1626",
            "text-background-opacity": 1,
            "text-background-padding": 3
          }
        },
        {
          selector: "edge.route-edge",
          style: {
            "line-color": "#34d399",
            width: 5,
            "z-index": 999
          }
        },
        {
          selector: "node.route-node",
          style: {
            "background-color": "#14532d",
            "border-color": "#4ade80",
            "border-width": 4
          }
        }
      ],
      layout: {
        name: "cose",
        animate: false,
        padding: 35,
        nodeRepulsion: 450000,
        idealEdgeLength: 120
      },
      wheelSensitivity: 0.2
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  // Calcular una ruta usando el backend real.
  const calculateRoute = async () => {
    setRouteLoading(true);
    setRouteError("");
    setRouteResult(null);

    if (backendStatus !== "online") {
      setRouteError("El backend no esta disponible. Verifica FastAPI.");
      setRouteLoading(false);
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/rutas/dijkstra/convencional`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            nodos: demoTopology.nodes,
            enlaces: demoTopology.links,
            origen: origin,
            destino: destination,
            dirigido: false
          })
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "No fue posible calcular la ruta.");
      }

      setRouteResult(data);

      const cy = cyRef.current;

      if (cy) {
        cy.elements().removeClass("route-edge route-node");

        data.ruta.forEach((node) => {
          cy.getElementById(node).addClass("route-node");
        });

        for (let i = 0; i < data.ruta.length - 1; i++) {
          const from = data.ruta[i];
          const to = data.ruta[i + 1];

          cy.edges().filter((edge) => {
            const source = edge.data("source");
            const target = edge.data("target");

            return (
              (source === from && target === to) ||
              (source === to && target === from)
            );
          }).addClass("route-edge");
        }

        cy.fit(undefined, 35);
      }
    } catch (error) {
      setRouteError(error.message);
    } finally {
      setRouteLoading(false);
    }
  };

  const clearRoute = () => {
    setRouteResult(null);
    setRouteError("");

    if (cyRef.current) {
      cyRef.current.elements().removeClass("route-edge route-node");
    }
  };

  const navigateTo = (item) => {
    setActiveSection(item.label);

    document.getElementById(item.target)?.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Network size={25} />
          </div>
          <div>
            <h2>NSFNET</h2>
            <span>SERVICE PROVIDER</span>
          </div>
        </div>

        <div className="sidebar-label">WORKSPACE</div>

        <nav className="navigation">
          {navigation.map((item) => {
            const Icon = item.icon;

            return (
              <button
                key={item.label}
                className={`nav-item ${
                  activeSection === item.label ? "active" : ""
                }`}
                onClick={() => navigateTo(item)}
              >
                <Icon size={19} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-status-icon">
            <ShieldCheck size={20} />
          </div>
          <div>
            <strong>SDN Laboratory</strong>
            <span>Development environment</span>
          </div>
          <span className="online-dot" />
        </div>

        <div className="sidebar-version">NSFNET PROJECT · v0.3.0</div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            <span>NSFNET</span>
            <ArrowRight size={14} />
            <strong>{activeSection}</strong>
          </div>

          <div className="topbar-right">
            <span className="environment-label">
              <span className="environment-dot" />
              LAB ENVIRONMENT
            </span>

            <button
              className="icon-button"
              title="Actualizar estado del backend"
              onClick={checkBackend}
            >
              <RefreshCw size={17} />
            </button>
          </div>
        </header>

        <div className="page-container">
          <section className="page-heading" id="overview">
            <div>
              <div className="eyebrow">NETWORK OPERATIONS / SDN</div>
              <h1>Network overview</h1>
              <p>
                Panel de supervision y gestion del enrutamiento de red.
              </p>
            </div>

            <div className="demo-label">
              <span />
              TOPOLOGIA DE DEMOSTRACION
            </div>
          </section>

          <section className="stats-grid">
            <article className="stat-card">
              <div className="stat-top">
                <span>Nodos de red</span>
                <Network size={19} />
              </div>
              <div className="stat-value">06</div>
              <div className="stat-description">Switches de demostracion</div>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span>Enlaces</span>
                <GitBranchIcon />
              </div>
              <div className="stat-value">07</div>
              <div className="stat-description">Conexiones ilustrativas</div>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span>Backend API</span>
                <Server size={19} />
              </div>
              <div className={`stat-value status-value ${backendStatus}`}>
                {backendStatus === "online"
                  ? "ONLINE"
                  : backendStatus === "checking"
                    ? "..."
                    : "OFFLINE"}
              </div>
              <div className="stat-description">FastAPI · Puerto 8000</div>
            </article>

            <article className="stat-card">
              <div className="stat-top">
                <span>Machine Learning</span>
                <BrainCircuit size={19} />
              </div>
              <div className="stat-value pending-value">PENDING</div>
              <div className="stat-description">Esperando dataset y modelo</div>
            </article>
          </section>

          <section className="content-grid">
            <article className="panel topology-panel" id="topology">
              <div className="panel-header">
                <div>
                  <div className="panel-title">
                    <Network size={19} />
                    <h2>Network topology</h2>
                  </div>
                  <p>Visualizacion interactiva de nodos y enlaces</p>
                </div>

                <button
                  className="secondary-button"
                  onClick={() => cyRef.current?.fit(undefined, 35)}
                >
                  Ajustar vista
                </button>
              </div>

              <div className="topology-canvas" ref={topologyRef} />

              <div className="topology-footer">
                <div className="legend-item">
                  <span className="legend-node" />
                  Switch
                </div>
                <div className="legend-item">
                  <span className="legend-line" />
                  Enlace
                </div>
                <div className="legend-item">
                  <span className="legend-line selected" />
                  Ruta seleccionada
                </div>
                <span className="demo-caption">DATOS ILUSTRATIVOS</span>
              </div>
            </article>

            <article className="panel routing-panel" id="routing">
              <div className="panel-header">
                <div>
                  <div className="panel-title">
                    <Route size={19} />
                    <h2>Route calculation</h2>
                  </div>
                  <p>Calculo mediante Dijkstra convencional</p>
                </div>
                <span className="ready-tag">READY</span>
              </div>

              <div className="algorithm-box">
                <div className="algorithm-icon">
                  <Zap size={20} />
                </div>
                <div>
                  <strong>Dijkstra convencional</strong>
                  <span>Pesos basados en capacidad nominal</span>
                </div>
              </div>

              <label className="field-label" htmlFor="origin">
                NODO DE ORIGEN
              </label>
              <select
                id="origin"
                className="select-control"
                value={origin}
                onChange={(event) => {
                  setOrigin(event.target.value);
                  clearRoute();
                }}
              >
                {demoTopology.nodes.map((node) => (
                  <option key={node} value={node}>{node}</option>
                ))}
              </select>

              <div className="direction-icon">
                <ArrowDownUp size={17} />
              </div>

              <label className="field-label" htmlFor="destination">
                NODO DE DESTINO
              </label>
              <select
                id="destination"
                className="select-control"
                value={destination}
                onChange={(event) => {
                  setDestination(event.target.value);
                  clearRoute();
                }}
              >
                {demoTopology.nodes.map((node) => (
                  <option key={node} value={node}>{node}</option>
                ))}
              </select>

              <button
                className="primary-button"
                onClick={calculateRoute}
                disabled={routeLoading || origin === destination}
              >
                {routeLoading ? (
                  <RefreshCw size={17} className="spin-icon" />
                ) : (
                  <Route size={17} />
                )}
                {routeLoading ? "Calculando..." : "Calcular ruta"}
              </button>

              {routeError && (
                <div className="error-message">
                  <AlertCircle size={16} />
                  {routeError}
                </div>
              )}

              {routeResult && (
                <div className="route-result">
                  <div className="result-heading">
                    <CheckCircle2 size={17} />
                    Ruta calculada correctamente
                  </div>

                  <div className="route-nodes">
                    {routeResult.ruta.map((node, index) => (
                      <span className="route-node-item" key={`${node}-${index}`}>
                        {index > 0 && <ArrowRight size={13} />}
                        <strong>{node}</strong>
                      </span>
                    ))}
                  </div>

                  <div className="cost-row">
                    <span>Costo total</span>
                    <strong>{routeResult.costo_total.toFixed(4)}</strong>
                  </div>

                  <button className="clear-button" onClick={clearRoute}>
                    Limpiar resultado
                  </button>
                </div>
              )}

              {!routeResult && !routeError && (
                <div className="route-placeholder">
                  Selecciona origen y destino para calcular una ruta.
                </div>
              )}
            </article>
          </section>

          <section className="bottom-grid">
            <article className="panel metrics-panel" id="metrics">
              <div className="panel-header">
                <div>
                  <div className="panel-title">
                    <Gauge size={19} />
                    <h2>Quality of service</h2>
                  </div>
                  <p>Metricas por enlace</p>
                </div>
                <span className="pending-tag">AWAITING DATA</span>
              </div>

              <div className="metrics-grid">
                <div className="metric-item">
                  <Activity size={19} />
                  <span>Packet loss</span>
                  <strong>-- %</strong>
                </div>
                <div className="metric-item">
                  <Clock3 size={19} />
                  <span>Delay</span>
                  <strong>-- ms</strong>
                </div>
                <div className="metric-item">
                  <ArrowDownUp size={19} />
                  <span>Throughput</span>
                  <strong>-- Mbps</strong>
                </div>
                <div className="metric-item">
                  <BrainCircuit size={19} />
                  <span>QS_metrics</span>
                  <strong>--</strong>
                </div>
              </div>

              <div className="waiting-message">
                <Database size={16} />
                Las metricas se habilitaran al integrar el dataset.
              </div>
            </article>

            <article className="panel infrastructure-panel" id="controller">
              <div className="panel-header">
                <div>
                  <div className="panel-title">
                    <SlidersHorizontal size={19} />
                    <h2>Infrastructure status</h2>
                  </div>
                  <p>Estado de los componentes</p>
                </div>
              </div>

              <div className="integration-list">
                <div className="integration-row">
                  <div className="integration-icon backend-icon">
                    <Server size={17} />
                  </div>
                  <div className="integration-info">
                    <strong>FastAPI backend</strong>
                    <span>127.0.0.1:8000</span>
                  </div>
                  <span className={`status-pill ${backendStatus}`}>
                    {backendStatus === "online"
                      ? "Online"
                      : backendStatus === "checking"
                        ? "Checking"
                        : "Offline"}
                  </span>
                </div>

                <div className="integration-row">
                  <div className="integration-icon controller-icon">
                    <Wifi size={17} />
                  </div>
                  <div className="integration-info">
                    <strong>RYU controller</strong>
                    <span>REST API · Puerto 8080</span>
                  </div>
                  <span className="status-pill pending">Pendiente</span>
                </div>

                <div className="integration-row">
                  <div className="integration-icon data-icon">
                    <Database size={17} />
                  </div>
                  <div className="integration-info">
                    <strong>Dataset / ML</strong>
                    <span>Entrenamiento y prediccion</span>
                  </div>
                  <span className="status-pill pending">Pendiente</span>
                </div>
              </div>

              <div className="last-checked">
                <RefreshCw size={13} />
                Ultima comprobacion: {lastChecked}
              </div>
            </article>
          </section>

          <footer className="page-footer">
            <span>NSFNET SERVICE PROVIDER</span>
            <span>Desarrollo academico · Entorno de laboratorio</span>
          </footer>
        </div>
      </main>
    </div>
  );
}

function GitBranchIcon() {
  return <Network size={19} />;
}

export default App;
