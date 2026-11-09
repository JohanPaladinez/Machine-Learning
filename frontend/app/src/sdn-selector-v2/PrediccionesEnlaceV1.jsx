import { useEffect, useState } from "react";

const OBJETIVOS = [
  ["Throughput RX", "target_throughput_u_to_v_mbps", "target_throughput_v_to_u_mbps", "Mbps", 1],
  ["Delay", "target_u_to_v_delay_avg_ms", "target_v_to_u_delay_avg_ms", "ms", 1],
  ["Loss ofrecido", "target_u_to_v_loss_ratio", "target_v_to_u_loss_ratio", "%", 100],
];
const numero = (n, unidad, factor) => `${(n * factor).toLocaleString("es-CO", { maximumFractionDigits: 4 })} ${unidad}`;

export default function PrediccionesEnlaceV1({ live, linkId, apiUrl }) {
  const snapshot = live?.snapshot || {};
  const metricas = snapshot.metrics || {};
  const entrada = metricas.links?.[linkId]?.ml;
  const base = String(apiUrl || "").trim().replace(/\/+$/, "");
  const edad = typeof entrada?.feature_end_epoch_s === "number" ? Date.now() / 1000 - entrada.feature_end_epoch_s : Infinity;
  const disponible = Boolean(live?.ready && live.edgeStates?.get(linkId)?.state === "up"
    && metricas.status === "fresh" && entrada?.status === "inputs_ready"
    && entrada.session_id === snapshot.session_id && entrada.topologia === snapshot.topologia
    && entrada.link_id === linkId && edad >= -5 && edad <= 120
    && entrada.features && Object.keys(entrada.features).length === 60);
  const clave = JSON.stringify([base, disponible, snapshot.topology_instance_id, snapshot.graph_version,
    snapshot.session_id, snapshot.topologia, linkId, entrada?.feature_start_epoch_s, entrada?.feature_end_epoch_s]);
  const [resultado, setResultado] = useState(null);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    if (!disponible) { setResultado(null); return; }
    let activo = true;
    const controlador = new AbortController();
    const limite = setTimeout(() => controlador.abort(), 15000);
    const solicitud = {
      topology_instance_id: snapshot.topology_instance_id,
      graph_version: snapshot.graph_version,
      link_id: linkId,
      feature_end_epoch_s: entrada.feature_end_epoch_s,
    };
    setResultado({ clave, pendiente: true });
    async function consultar() {
      try {
        const respuesta = await fetch(`${base}/api/sdn/ml/predecir`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(solicitud), signal: controlador.signal, cache: "no-store",
        });
        const datos = await respuesta.json();
        if (!respuesta.ok) throw new Error(typeof datos.detail === "string" ? datos.detail : "No se pudo calcular la predicción.");
        if (datos.topology_instance_id !== solicitud.topology_instance_id || datos.graph_version !== solicitud.graph_version
          || datos.link_id !== linkId || datos.session_id !== snapshot.session_id || datos.topologia !== snapshot.topologia
          || datos.feature_start_epoch_s !== entrada.feature_start_epoch_s
          || datos.feature_end_epoch_s !== entrada.feature_end_epoch_s) throw new Error("La predicción pertenece a otra ventana o sesión.");
        for (const [, u, v, , factor] of OBJETIVOS) {
          for (const campo of [u, v]) {
            const valor = datos.predicciones?.[campo];
            if (typeof valor !== "number" || !Number.isFinite(valor) || valor < 0 || (factor === 100 && valor > 1)) {
              throw new Error("La respuesta del modelo contiene valores inválidos.");
            }
          }
        }
        if (activo) setResultado({ clave, datos });
      } catch (error) {
        if (activo) setResultado({ clave, error: error.name === "AbortError" ? "La consulta al modelo tardó demasiado." : error.message });
      } finally { clearTimeout(limite); }
    }
    consultar();
    return () => { activo = false; clearTimeout(limite); controlador.abort(); };
    // La clave contiene la sesion, el enlace, la revision de red y las fechas de entrada.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, intento]);

  const actual = resultado?.clave === clave ? resultado : null;
  return <div className="sdn-live-metrics" aria-live="polite">
    <h3 className="sdn-subheading">Predicción de la próxima ventana</h3>
    {!disponible ? <p className="sdn-muted">Predicción no disponible: esta sesión no publica una ventana reciente y completa para este enlace.</p>
      : actual?.error ? <><p className="error-message" role="alert">{actual.error}</p><button type="button" className="secondary-button" onClick={() => setIntento(n => n + 1)}>Reintentar</button></>
      : !actual?.datos ? <p className="sdn-muted">Calculando con las mediciones recientes del enlace…</p>
      : <><span className="status-pill online">Estimación del modelo común</span>
        <div className="sdn-table-scroll"><table className="sdn-table">
          <caption className="sdn-sr-only">Estimaciones para la ventana posterior a la medición de entrada</caption>
          <thead><tr><th>Métrica estimada</th><th>u → v</th><th>v → u</th></tr></thead>
          <tbody>{OBJETIVOS.map(([nombre, u, v, unidad, factor]) => <tr key={u}><td>{nombre}</td>
            <td>{numero(actual.datos.predicciones[u], unidad, factor)}</td><td>{numero(actual.datos.predicciones[v], unidad, factor)}</td></tr>)}</tbody>
        </table></div>
        <p className="sdn-muted">Ventana usada: {new Date(actual.datos.feature_start_epoch_s * 1000).toLocaleTimeString("es-CO")} → {new Date(actual.datos.feature_end_epoch_s * 1000).toLocaleTimeString("es-CO")}. La tabla anterior muestra la medición; esta muestra la estimación de la ventana siguiente.</p>
        <p className="sdn-muted">La pérdida ofrecida de esta sesión incluye los rechazos locales al enviar sondas. La evaluación del modelo conserva los resultados separados por procedencia.</p>
      </>}
  </div>;
}
