import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, RefreshCw } from "lucide-react";
import PanelSdn from "./PanelSdn.jsx";
import { parseTopologyDocument } from "./graph.js";

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
  const [apiUrl, setApiUrl] = useState(import.meta.env.VITE_SDN_LIVE_API_URL || "http://127.0.0.1:8001");
  const [snapshot, setSnapshot] = useState({});
  const [connection, setConnection] = useState("checking");
  const [error, setError] = useState("");
  const [sourceDraft, setSourceDraft] = useState("");
  const [ryuDraft, setRyuDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
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
        if (!disposed) {
          setSnapshot((previous) => ({ ...data, topology_view: data.topology_instance_id && previous.topology_instance_id === data.topology_instance_id ? previous.topology_view : data.topology_view }));
          setSourceDraft((value) => value || data.source_url || "");
          setRyuDraft((value) => value || data.ryu_rest_override || "");
          setConnection("online");
          setError("");
        }
      } catch (caught) {
        if (!disposed) { setConnection("offline"); setError(caught.name === "AbortError" ? "La consulta no respondió dentro de 12 segundos." : caught.message); }
      } finally {
        clearTimeout(timeout);
        if (!disposed) poll = setTimeout(update, 5000);
      }
    }
    update();
    return () => { disposed = true; controller?.abort(); clearTimeout(timeout); clearTimeout(poll); };
  }, [apiUrl, revision]);

  async function configure(event) {
    event.preventDefault();
    setSaving(true);
    setConnection("checking");
    setError("");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      await jsonRequest(`${apiUrl}/api/sdn/fuente`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: sourceDraft.trim(), ryu_rest_url: ryuDraft.trim() }) }, controller.signal);
      setRevision((value) => value + 1);
    } catch (caught) { setError(caught.message); setConnection("offline"); }
    finally { clearTimeout(timer); setSaving(false); }
  }

  const ready = snapshot.ready === true && connection === "online" && !saving;
  const topology = snapshot.topology_view || EMPTY;
  const statusLabel = connection === "offline" ? "Estado sin actualizar" : STATUS[snapshot.status] || "Conectando con las VMs";
  const edgeStates = new Map((snapshot.links_runtime || []).map((edge) => [edge.id, edge]));
  const controls = <section className="panel sdn-live-setup" aria-label="Conexión con la red activa">
    <form onSubmit={configure} className="sdn-live-source-form"><div><label className="field-label" htmlFor="sdn-mininet-url">URL DEL OBSERVADOR DE MININET</label><input id="sdn-mininet-url" type="url" className="select-control" required value={sourceDraft} onChange={(event) => setSourceDraft(event.target.value)} placeholder="http://IP-de-Mininet:8766" /><p className="sdn-muted">Copia la URL que imprime el instalador en la VM Mininet. Se configura una vez por arranque del backend.</p></div><button className="secondary-button" disabled={saving}><RefreshCw size={15} />{saving ? "Conectando…" : "Conectar a Mininet"}</button></form>
    <details className="sdn-live-options"><summary>REST de RYU para sesiones manuales</summary><label className="field-label" htmlFor="sdn-ryu-url">OPCIONAL SI LA SESIÓN YA PUBLICA EL PUERTO</label><input id="sdn-ryu-url" className="select-control" value={ryuDraft} onChange={(event) => setRyuDraft(event.target.value)} placeholder="http://IP-de-RYU:puerto-REST" /><p className="sdn-muted">En la captura actual se utiliza su REST registrado automáticamente. Para una sesión manual, escribe su dirección real y vuelve a pulsar Conectar a Mininet.</p></details>
    <div className={`sdn-live-banner ${ready ? "sdn-live-ok" : "sdn-live-wait"}`} role="status">{ready ? <CheckCircle2 size={19} /> : <AlertCircle size={19} />}<div><strong>{statusLabel}</strong><p>{error || snapshot.message || "Esperando la conexión con FastAPI."}</p>{snapshot.observed_utc && <small>Observado en Mininet: {snapshot.observed_utc} · consulta del panel cada 5 s</small>}</div></div>
    {snapshot.status === "unregistered" && <p className="sdn-muted">El observador reconoce el lanzador topologia_dual_sdn.py y la captura actual. Una red iniciada con otro script necesita registrar su sesión; no se identifica solo por el número de switches.</p>}
  </section>;
  const live = { apiUrl, setApiUrl, snapshot, ready, topology, instanceId: snapshot.topology_instance_id,
    graphVersion: snapshot.graph_version, edgeStates, controls };
  return <PanelSdn key={snapshot.topology_instance_id || "waiting"} live={live} />;
}
