import { useEffect, useRef, useState } from 'react';
import { ROUTES, routeGroups, routesOf, comparisonContractError } from './comparisonView.js';

const defaults = { delay: 0.5, loss: 0.35, capacity: 0.15, load: 0 };
const names = { delay: 'Delay', loss: 'Loss', capacity: 'Capacidad', load: 'Carga RX (opcional)' };
const fmt = (n, digits = 4) => n == null ? '—' : Number(n).toLocaleString('es-CO', { maximumFractionDigits: digits });
const rows = [
  ['Saltos', 'saltos', '', 1, 'min'],
  ['Retardo configurado total', 'retardo_configurado_total_ms', ' ms', 1, 'min'],
  ['Costo de referencia: Σ 1/capacidad', 'costo_referencia', ' 1/Mbps', 1, 'min'],
  ['QoS previsto: misma fórmula', 'costo_qos', '', 1, 'min'],
  ['Delay previsto acumulado', 'delay_previsto_ms', ' ms', 1, 'min'],
  ['Loss previsto compuesto', 'loss_previsto_ratio', ' %', 100, 'min'],
  ['Capacidad mínima nominal', 'capacidad_minima_mbps', ' Mbps', 1, 'max'],
];

export default function ComparacionRutas({ live, apiUrl, origin, destination, result, onResult, visibility, onVisibility, onSelectLink, clock, onStart, labels }) {
  const [weights, setWeights] = useState(defaults);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(null), epoch = useRef(0);
  const context = JSON.stringify([apiUrl, live.instanceId, live.graphVersion, live.snapshot.selection_revision, origin, destination, live.ready]);
  useEffect(() => () => { epoch.current += 1; pending.current?.abort(); }, [context]);
  const nodeName = id => labels?.get(id) || id?.toUpperCase();
  const pathName = path => path.map(nodeName).join(' → ');

  async function calculate(event) {
    event.preventDefault();
    onStart();
    const generation = ++epoch.current;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    const timeout = setTimeout(() => controller.abort(), 60000);
    setLoading(true); setError(''); onResult(null);
    try {
      const response = await fetch(`${apiUrl}/api/sdn/rutas/comparar`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ topology_instance_id: live.instanceId, graph_version: live.graphVersion,
          selection_revision: live.snapshot.selection_revision, origen: origin, destino: destination, pesos: weights }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Revisa los parámetros de comparación.');
      const contractError = comparisonContractError(data);
      if (contractError) throw new Error(contractError);
      if (data.topology_instance_id !== live.instanceId || data.graph_version !== live.graphVersion ||
          data.selection_revision !== live.snapshot.selection_revision || data.session_id !== live.snapshot.session_id) {
        throw new Error('La respuesta pertenece a otra selección. Vuelve a comparar.');
      }
      if (epoch.current === generation) onResult(data);
    } catch (caught) {
      if (epoch.current === generation) setError(caught.name === 'AbortError' ? 'La comparación tardó demasiado. Reintenta con una ventana reciente.' : caught.message);
    } finally {
      clearTimeout(timeout);
      if (epoch.current === generation) setLoading(false);
    }
  }
  const validWeights = Object.values(weights).every(n => Number.isFinite(n) && n >= 0) && Object.values(weights).some(n => n > 0);
  const routes = routesOf(result), groups = routeGroups(routes);
  const available = ROUTES.filter(({ key }) => routes[key]);
  const best = (field, kind = 'min') => {
    const values = available.map(({ key }) => routes[key][field]).filter(Number.isFinite);
    return values.length ? Math[kind](...values) : null;
  };
  const isBest = (value, field, kind) => Number.isFinite(value) && Math.abs(value - best(field, kind)) < 1e-9;
  const reason = key => result?.errores_criterios?.[key] || (key === 'ml' ? result?.ml?.motivo : 'El servicio no devolvió el resultado de este criterio. Vuelve a comparar.');
  return <div className="sdn-comparison" aria-live="polite">
    <div className="sdn-comparison-heading"><div><div className="eyebrow">MISMA RED · CUATRO CRITERIOS</div><h3>Compara las cuatro rutas</h3></div><span className="sdn-four-count">4 alternativas</span></div>
    <p className="sdn-muted">{nodeName(origin)} → {nodeName(destination)}. Dijkstra calcula por saltos, retardo configurado, inverso de capacidad o métricas previstas por ML.</p>
    <form onSubmit={calculate}>
      <details><summary>Pesos de la ruta ML</summary><div className="sdn-qos-inputs">
        {Object.entries(names).map(([key, name]) => <label key={key}>{name}<input className="select-control" type="number" min="0" step="0.05" value={Number.isFinite(weights[key]) ? weights[key] : ''} onChange={e => {
          epoch.current += 1; pending.current?.abort(); setLoading(false); onResult(null);
          setWeights(previous => ({ ...previous, [key]: e.target.value === '' ? NaN : Number(e.target.value) }));
        }} /></label>)}
      </div><p className="sdn-muted">Se normalizan para sumar 1. Escalas: 50 ms, loss 1 % y capacidad 1 Mbps. Carga RX queda en 0 por defecto; al activarla representa tráfico cursado, no capacidad libre.</p></details>
      <button className="primary-button" disabled={loading || !live.ready || !origin || origin === destination || !validWeights}>{loading ? 'Calculando los cuatro criterios…' : 'Comparar las 4 rutas'}</button>
      {!validWeights && <p role="alert">Los pesos deben ser no negativos y sumar más de cero.</p>}
    </form>
    {error && <p className="error-message" role="alert">{error}</p>}
    {result && <>
      <div className="sdn-comparison-summary"><strong>{groups.length} {groups.length === 1 ? 'camino distinto' : 'caminos distintos'}</strong><span>entre {available.length} criterios disponibles</span></div>
      <div className="sdn-comparison-cards">{ROUTES.map(({ key, label, color }) => <article key={key} style={{ '--route-color': color }} className={!routes[key] ? 'is-unavailable' : ''}>
        <div className="sdn-route-card-heading"><span className="sdn-route-dot" /><h4>{label}</h4><label title={`Mostrar ${label} en el mapa`}><input type="checkbox" aria-label={`Mostrar ${label}`} checked={Boolean(visibility[key])} disabled={!routes[key]} onChange={e => onVisibility(v => ({ ...v, [key]: e.target.checked }))} /></label></div>
        {routes[key] ? <><p className="sdn-route-path">{pathName(routes[key].ruta)}</p>
          <dl className="sdn-card-common-metrics">{rows.map(([metric, field, unit, multiplier, direction]) => {
            const value = routes[key][field];
            return <div key={field} className={isBest(value, field, direction) ? 'is-best' : ''}><dt>{metric}</dt><dd>{fmt(value == null ? null : value * multiplier)}{value == null ? '' : unit}</dd></div>;
          })}</dl>
          <p className="sdn-muted">Costo del criterio de selección: {fmt(routes[key].costo_criterio ?? (key === 'ml' ? routes[key].costo_qos : routes[key].costo_referencia))} {routes[key].unidad_costo || (key === 'ml' ? 'QoS' : '1/Mbps')}. Su unidad depende del criterio.</p>
          <div className="sdn-route-badges">{isBest(routes[key].saltos, 'saltos', 'min') && <span>Menos saltos</span>}{isBest(routes[key].costo_qos, 'costo_qos', 'min') && <span>QoS previsto mínimo</span>}</div>
          <button className="sdn-table-link" type="button" onClick={() => onVisibility(Object.fromEntries(ROUTES.map(r => [r.key, r.key === key])))}>Ver solo este trazado</button>
        </> : <p className="sdn-muted">No disponible. {reason(key)}</p>}
      </article>)}</div>
      <div className="sdn-route-legend"><span className="sdn-shared-key">Dorado: enlace compartido por varios criterios visibles</span><button className="secondary-button" type="button" onClick={() => onVisibility(Object.fromEntries(ROUTES.map(r => [r.key, Boolean(routes[r.key])])))}>Mostrar todos</button></div>
      {groups.filter(g => g.criterios.length > 1).map(g => <p className="sdn-coincidence" key={g.criterios.join('-')}><strong>Coinciden:</strong> {g.criterios.map(k => ROUTES.find(r => r.key === k).short).join(' + ')}. Seleccionan el mismo camino.</p>)}
      <div className="sdn-table-scroll"><table className="sdn-table sdn-four-table"><caption>Los cuatro caminos se evalúan sobre la misma red. QoS, delay y loss previstos usan las mismas predicciones por enlace.</caption>
        <thead><tr><th>Indicador</th>{ROUTES.map(r => <th key={r.key}><span className="sdn-route-dot" style={{ background: r.color }} />{r.short}</th>)}</tr></thead><tbody>
          {rows.map(([label, field, unit, multiplier, direction]) => <tr key={field}><th scope="row">{label}</th>{ROUTES.map(({ key }) => {
            const value = routes[key]?.[field];
            return <td key={key} className={isBest(value, field, direction) ? 'sdn-best-metric' : ''}>{fmt(value == null ? null : value * multiplier)}{value == null ? '' : unit}</td>;
          })}</tr>)}
        </tbody></table></div>
      <p className="sdn-muted">Resaltado: menor valor de la fila; en capacidad nominal, mayor valor. Los costos propios de cada tarjeta tienen unidades distintas. Un valor QoS menor es una estimación bajo los pesos elegidos.</p>
      <p className="sdn-muted">Modelo: {result.ml.status === 'available' ? result.ml.modelo_id : 'sin predicciones utilizables'}. {result.ml.motivo}</p>
      {result.ml.feature_end_epoch_s && <p className="sdn-muted">Ventana de entrada: {new Date(result.ml.feature_start_epoch_s * 1000).toLocaleTimeString('es-CO')} → {new Date(result.ml.feature_end_epoch_s * 1000).toLocaleTimeString('es-CO')}. Antigüedad: {fmt(clock / 1000 - result.ml.feature_end_epoch_s, 0)} s / {result.ml.max_age_s} s. Predice la ventana siguiente.</p>}
      <details><summary>Método y alcance</summary><p className="sdn-muted">{result.formula}. Pesos: {Object.entries(result.pesos).map(([k,v]) => `${names[k]} ${fmt(v)}`).join(' · ')}.</p>
        {result.advertencias.map(text => <p className="sdn-muted" key={text}>{text}</p>)}
      </details>
      {ROUTES.map(({ key, label }) => routes[key]?.predicciones_enlaces.length > 0 && <details key={key}><summary>Predicciones por enlace · {label}</summary>
        <div className="sdn-table-scroll"><table className="sdn-table"><caption>Predicciones fijadas a la ventana de esta comparación</caption><thead><tr><th>Dirección</th><th>RX Mbps</th><th>Delay ms</th><th>Loss %</th></tr></thead><tbody>
          {routes[key].predicciones_enlaces.map(e => <tr key={e.link_id}><td><button type="button" className="sdn-table-link" onClick={() => onSelectLink(e.link_id)}>{nodeName(e.origen)} → {nodeName(e.destino)}</button></td><td>{fmt(e.throughput_rx_mbps)}</td><td>{fmt(e.delay_ms)}</td><td>{fmt(e.loss_ratio * 100)}</td></tr>)}
        </tbody></table></div>
      </details>)}
    </>}
  </div>;
}
