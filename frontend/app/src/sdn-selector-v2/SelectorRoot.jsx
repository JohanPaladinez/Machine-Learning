import { useEffect, useRef, useState } from "react";
import { AlertCircle, CheckCircle2, RefreshCw } from "lucide-react";
import PanelSdn from "./PanelSdn.jsx";
import { parseTopologyDocument } from "../sdn-vivo-v1/graph.js";

const EMPTY = { id: "none", name: "Sin red activa verificada", source: "Esperando al observador de Mininet",
  illustrative: false, nodes: [], links: [] };
const STATUS = { unconfigured: "Configura la conexión", active: "Red activa verificada", inactive: "Sin red activa registrada",
  unregistered: "Red sin registrar", ambiguous: "Varias redes activas", mininet_unreachable: "Mininet sin conexión",
  ryu_unconfigured: "Falta el REST de RYU", waiting_ryu: "Esperando a RYU", controller_mismatch: "El controlador no coincide",
  ryu_unreachable: "RYU sin conexión" };

async function jsonRequest(url, options = {}, signal) {
  const response = await fetch(url, { ...options, signal, cache: "no-store" });
  let data;
  try { data = await response.json(); } catch { throw new Error("La API no devolvió JSON. Revisa la dirección y el puerto 8001."); }
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `La API respondió ${response.status}.`);
  return data;
}

export default function LiveRoot() {
  const [apiUrl, setApiUrl] = useState(import.meta.env.VITE_SDN_SELECTOR_API_URL || "http://127.0.0.1:8002");
  const [snapshot, setSnapshot] = useState({});
  const [connection, setConnection] = useState("checking");
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [selectionPending, setSelectionPending] = useState(false);

  const selectionGeneration = useRef(0);

  useEffect(() => {
    const generation = selectionGeneration.current;
    let disposed = false;
    let controller = null;
    let timeout = null;
    let poll = null;
    async function update() {
      controller = new AbortController();
      timeout = setTimeout(() => controller.abort(), 12000);
      try {
        const data = await jsonRequest(`${apiUrl}/api/sdn/estado`, {}, controller.signal);
        if (data.schema_version !== 1) throw new Error("La API no ofrece el contrato de red activa esperado.");
        if (data.topology_document) {
          const maps = parseTopologyDocument(data.topology_document);
          if (!maps[data.topologia] || !data.topology_instance_id) throw new Error("La topología activa está incompleta.");
          data.topology_view = maps[data.topologia];
        }
        if (data.ready && (!data.graph_version || !data.topology_view)) throw new Error("Falta identificar la versión de la red activa.");
        if (!disposed && generation === selectionGeneration.current) {
          setSnapshot((previous) => ({ ...data, topology_view: data.topology_instance_id && previous.topology_instance_id === data.topology_instance_id && previous.graph_version === data.graph_version && previous.topology_view ? previous.topology_view : data.topology_view }));
          setConnection("online");
          setError("");
        }
      } catch (caught) {
        if (!disposed && generation === selectionGeneration.current) { setConnection("offline"); setError(caught.name === "AbortError" ? "La consulta no respondió dentro de 12 segundos." : caught.message); }
      } finally {
        clearTimeout(timeout);
        if (!disposed && generation === selectionGeneration.current) poll = setTimeout(update, 5000);
      }
    }
    update();
    return () => { disposed = true; controller?.abort(); clearTimeout(timeout); clearTimeout(poll); };
  }, [apiUrl, revision]);

  async function selectNetwork(raw) {
    selectionGeneration.current += 1;
    setSnapshot(previous => ({ ...previous, ready: false }));
    setSelectionPending(true);
    setConnection("checking");
    setError("");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const pair = raw === "auto" ? ["auto", ""] : JSON.parse(raw);
      await jsonRequest(`${apiUrl}/api/sdn/seleccionar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topologia: pair[0], session_id: pair[1]
        })
      }, controller.signal);
      setConnection("checking");
      setRevision((value) => value + 1);
    } catch (caught) {
      setError(caught.message);
      setConnection("offline");
    } finally {
      clearTimeout(timer);
      setSelectionPending(false);
    }
  }

  const choices = Array.isArray(snapshot.network_choices)
    ? snapshot.network_choices : [];
  const selectedValue = snapshot.selected_topologia
    && snapshot.selected_topologia !== "auto"
    ? JSON.stringify([
        snapshot.selected_topologia,
        snapshot.selected_session_id || ""
      ])
    : "auto";

  const networkOptions = ["nsfnet", "geant2"].flatMap((name) => {
    const found = choices.filter((n) => n.topologia === name);
    if (found.length) {
      return found.map((n) => ({
        value: JSON.stringify([name, n.session_id]),
        label: `${name.toUpperCase()} - ${n.node_count} nodos / ${n.link_count} enlaces - OF ${n.of_port}`
      }));
    }
    return [{
      value: JSON.stringify([name, ""]),
      label: `${name.toUpperCase()} - ${
        Array.isArray(snapshot.network_choices)
          ? "sin sesion detectada" : "por comprobar"
      }`
    }];
  });

  if (selectedValue !== "auto"
      && !networkOptions.some((n) => n.value === selectedValue)) {
    networkOptions.push({
      value: selectedValue,
      label: `${snapshot.selected_topologia.toUpperCase()} - sesion seleccionada no activa`
    });
  }

  const ready = snapshot.ready === true && connection === "online" && !selectionPending;
  const topology = snapshot.topology_view || EMPTY;
  const statusLabel = connection === "offline" ? "Estado sin actualizar" : STATUS[snapshot.status] || "Conectando con las VMs";
  const edgeStates = new Map((snapshot.links_runtime || []).map((edge) => [edge.id, edge]));

  const topologyControl = (
    <>
      <style>{`
        .sdn-topology-navigation {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 4px;
          margin-top: 16px;
          border: 1px solid #28445e;
          border-radius: 11px;
          background: #0a1726;
        }
        .sdn-topology-navigation .topology-choice {
          flex: 1;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          padding: 8px 7px;
          border: 1px solid transparent;
          border-radius: 7px;
          background: transparent;
          color: #91abc4;
          font: inherit;
          font-size: 10px;
          font-weight: 700;
          white-space: nowrap;
          cursor: pointer;
          transition: background-color .15s, color .15s, border-color .15s;
        }
        .sdn-topology-navigation .topology-choice:hover:not(:disabled) {
          color: #d8f2ff;
          background: #18354c;
        }
        .sdn-topology-navigation .topology-choice.is-current {
          color: #78dcff;
          background: #153a54;
          border-color: #33799d;
        }
        .sdn-topology-navigation .topology-auto {
          flex: 0 0 auto;
        }
        .sdn-topology-navigation .topology-auto.is-current {
          color: #c0d5e9;
          background: #23354a;
          border-color: #435e79;
        }
        .sdn-topology-navigation .is-unavailable {
          opacity: .6;
        }
        .sdn-topology-navigation .topology-choice:disabled {
          opacity: .5;
          cursor: wait;
        }
        .sdn-topology-navigation .topology-choice:focus-visible {
          outline: 2px solid #67d5ff;
          outline-offset: 2px;
        }
        .sdn-topology-navigation select.topology-choice {
          max-width: 100px;
        }
        @media (max-width: 760px) {
          .sdn-panel-v1 .sidebar {
            position: sticky;
            top: 0;
            z-index: 40;
            flex-wrap: wrap;
            overflow: visible;
            column-gap: 12px;
            row-gap: 10px;
          }
          .sdn-topology-navigation {
            flex: 0 0 auto;
            margin-top: 0;
            margin-left: auto;
            align-self: center;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .sdn-topology-navigation .topology-choice {
            transition: none;
          }
        }
      `}</style>

      <div
        className="sdn-topology-navigation"
        role="group"
        aria-label="Topologia a visualizar"
        aria-busy={selectionPending}
      >
        {["nsfnet", "geant2"].map((name) => {
          const sessions = choices.filter((n) => n.topologia === name);
          const current =
            snapshot.selected_topologia === name ||
            (selectedValue === "auto" && topology.id === name);
          const className =
            "topology-choice" +
            (current ? " is-current" : "") +
            (!sessions.length ? " is-unavailable" : "");

          if (sessions.length > 1) {
            return (
              <select
                key={name}
                className={className}
                aria-label={`Sesion de ${name.toUpperCase()}`}
                value={
                  snapshot.selected_topologia === name
                    ? selectedValue : ""
                }
                disabled={selectionPending}
                onChange={(event) => selectNetwork(event.target.value)}
              >
                <option value="" disabled>{name.toUpperCase()}</option>
                {networkOptions
                  .filter((option) => JSON.parse(option.value)[0] === name)
                  .map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
              </select>
            );
          }

          const session = sessions[0];
          const value = JSON.stringify([
            name, session ? session.session_id : ""
          ]);
          return (
            <button
              key={name}
              type="button"
              className={className}
              aria-pressed={current}
              disabled={selectionPending}
              title={session
                ? `${name.toUpperCase()}: ${session.node_count} nodos, ${session.link_count} enlaces. OF ${session.of_port}`
                : `${name.toUpperCase()}: sin sesion detectada`}
              onClick={() => selectNetwork(value)}
            >
              {name.toUpperCase()}
            </button>
          );
        })}

        <button
          type="button"
          className={
            "topology-choice topology-auto" +
            (selectedValue === "auto" ? " is-current" : "")
          }
          aria-pressed={selectedValue === "auto"}
          disabled={selectionPending}
          title="Conservar la red actual; al perderla, priorizar NSFNET y luego GEANT2"
          onClick={() => selectNetwork("auto")}
        >
          <RefreshCw
            size={12}
            className={selectionPending ? "spin-icon" : ""}
          />
          Auto
        </button>
      </div>
    </>
  );

  const controls = <section className="panel sdn-live-setup" aria-label="Conexión con la red activa">
    
    <p className="sdn-muted">Selecciona NSFNET o GEANT2 en el menu. La conexion al observador y a RYU se resuelve automaticamente.</p>
    <p className="sdn-muted">Controlador: {snapshot.ryu?.identity_verified && ready ? "verificado" : "sin verificar"} · Telemetria: {snapshot.metrics?.status === "fresh" ? "reciente" : "no reciente"} · Antiguedad de la ventana: {snapshot.metrics?.age_s ?? "—"} s.</p>
    <details className="sdn-live-options"><summary>Estado de las fuentes</summary><p className="sdn-muted">{Object.entries(snapshot.source_status || {}).map(([name, status]) => `${name.toUpperCase()}: ${status}`).join(" · ")}</p><p className="sdn-muted">Auto conserva la red seleccionada. Si pierde la sesion, busca NSFNET y despues GEANT2. No inicia ni detiene redes.</p></details>
    <div className={`sdn-live-banner ${ready ? "sdn-live-ok" : "sdn-live-wait"}`} role="status">{ready ? <CheckCircle2 size={19} /> : <AlertCircle size={19} />}<div><strong>{statusLabel}</strong><p>{error || snapshot.message || "Esperando la conexión con FastAPI."}</p>{snapshot.observed_utc && <small>Observado en Mininet: {snapshot.observed_utc} · consulta del panel cada 5 s</small>}</div></div>
    {snapshot.status === "unregistered" && <p className="sdn-muted">El observador reconoce el lanzador topologia_dual_sdn.py y la captura actual. Una red iniciada con otro script necesita registrar su sesión; no se identifica solo por el número de switches.</p>}
  </section>;
  const live = { apiUrl, setApiUrl, snapshot, ready, topology, instanceId: snapshot.topology_instance_id,
    graphVersion: snapshot.graph_version, edgeStates, controls, topologyControl };
  return <PanelSdn key={JSON.stringify([snapshot.topology_instance_id || "waiting", snapshot.graph_version, snapshot.selection_revision])} live={live} />;
}
