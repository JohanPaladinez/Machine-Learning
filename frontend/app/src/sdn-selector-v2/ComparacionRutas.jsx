import { useEffect, useRef, useState } from 'react';
import AplicarRuta from './AplicarRuta.jsx';
import { ROUTES, routeGroups, routesOf, comparisonContractError, completeComparison, savePresentation, restorePresentation, COMPARISON_STORAGE } from './fiveModelView.js';

const defaults = { delay: 0.5, loss: 0.35, capacity: 0.15, load: 0 };
const names = { delay: 'Delay', loss: 'Loss', capacity: 'Capacidad', load: 'Carga RX (opcional)' };
const fmt = (n, digits = 4) => n == null ? '—' : Number(n).toLocaleString('es-CO', { maximumFractionDigits: digits });
const rows = [
  ['Saltos', 'saltos', '', 1, 'min'],
  ['Retardo configurado total', 'retardo_configurado_total_ms', ' ms', 1, 'min'],
  ['Costo de referencia: Σ 1/capacidad', 'costo_referencia', ' 1/Mbps', 1, 'min'],
  ['QoS observado: misma fórmula', 'measured_qos', '', 1, 'min'],
  ['Delay medido: suma de enlaces', 'measured_delay_ms', ' ms', 1, 'min'],
  ['Loss medido: compuesto de enlaces', 'measured_loss_ratio', ' %', 100, 'min'],
  ['Capacidad mínima nominal', 'capacidad_minima_mbps', ' Mbps', 1, 'max'],
];

export default function ComparacionRutas({ live, apiUrl, origin, destination, result, onResult, visibility, onVisibility, onSelectLink, onStart, labels }) {
  const [weights, setWeights] = useState(defaults);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(null), epoch = useRef(0);
  const context = JSON.stringify([apiUrl, live.instanceId, live.graphVersion, live.snapshot.selection_revision, origin, destination, live.ready]);
  useEffect(() => () => { epoch.current += 1; pending.current?.abort(); }, [context]);
  const nodeName = id => result?.presentation_snapshot?.node_labels?.[id] || labels?.get(id) || id?.toUpperCase();
  const pathName = path => path.map(nodeName).join(' → ');

  async function calculate(event) {
    event.preventDefault();
    onStart();
    const generation = ++epoch.current;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    const timeout = setTimeout(() => controller.abort(), 60000);
    setLoading(true); setError('');
    try {
      const response = await fetch(`${apiUrl}/api/sdn/rutas/comparar-modelos`, {
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
      if (epoch.current === generation) {
        if (completeComparison(result) && !completeComparison(data)) {
          setError('La actualización no obtuvo los cuatro modelos. Se conserva la comparación guardada. '+(data.ml?.motivo || ''));
        } else {
          onResult(savePresentation(data, origin, destination, labels, window.localStorage));
        }
      }
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
    <div className="sdn-comparison-heading"><div><div className="eyebrow">MISMA RED · CUATRO MODELOS + CONVENCIONAL</div><h3>Compara las cinco rutas</h3></div><span className="sdn-four-count">5 alternativas</span></div>
    <p className="sdn-muted">{nodeName(result?.presentation_snapshot?.origin || origin)} → {nodeName(result?.presentation_snapshot?.destination || destination)}. Una ruta convencional por inverso de capacidad y una por las predicciones de cada modelo: Polinomial, Decision Tree, Random Forest y XGBoost.</p>
    <form onSubmit={calculate}>
      <details><summary>Pesos comunes para los cuatro modelos</summary><div className="sdn-qos-inputs">
        {Object.entries(names).map(([key, name]) => <label key={key}>{name}<input className="select-control" type="number" min="0" step="0.05" value={Number.isFinite(weights[key]) ? weights[key] : ''} onChange={e => {
          epoch.current += 1; pending.current?.abort(); setLoading(false);
          setWeights(previous => ({ ...previous, [key]: e.target.value === '' ? NaN : Number(e.target.value) }));
        }} /></label>)}
      </div><p className="sdn-muted">Se normalizan para sumar 1. Escalas: 50 ms, loss 1 % y capacidad 1 Mbps. Carga RX queda en 0 por defecto; al activarla representa tráfico cursado, no capacidad libre.</p></details>
      <button className="primary-button" disabled={loading || !live.ready || !origin || origin === destination || !validWeights}>{loading ? 'Calculando las cinco alternativas…' : result ? 'Actualizar comparación' : 'Comparar las 5 rutas'}</button>
      {!validWeights && <p role="alert">Los pesos deben ser no negativos y sumar más de cero.</p>}
    </form>
    <div className="sdn-ml-actions"><button className="secondary-button" type="button" disabled={loading} onClick={() => { const saved = restorePresentation(window.localStorage); if (saved) { onResult(saved); setError(''); } else setError('Todavía no hay una comparación completa guardada en este navegador. Calcula una vez con los cuatro modelos conectados.'); }}>Recuperar última comparación guardada</button>{result && <button className="secondary-button" type="button" disabled={loading} onClick={() => { try { window.localStorage.removeItem(COMPARISON_STORAGE); } catch { /* La vista también puede limpiarse sin almacenamiento. */ } onResult(null); setError(''); }}>Limpiar comparación</button>}</div>
    {result?.presentation_snapshot && <div className="sdn-saved-comparison" role="status"><strong>Comparación guardada para la sustentación</strong><p>{result.topologia?.toUpperCase()} · guardada: {new Date(result.presentation_snapshot.saved_at).toLocaleString('es-CO')}. Se conservan los valores de la ventana original; no representan una actualización en vivo. Pulsa Actualizar comparación para calcular con mediciones nuevas.</p>{result.presentation_snapshot.persistence_warning && <p>{result.presentation_snapshot.persistence_warning}</p>}</div>}
    {error && <p className="error-message" role="alert">{error}</p>}
    {result && <>
      <div className="sdn-comparison-summary"><strong>{groups.length} {groups.length === 1 ? 'camino distinto' : 'caminos distintos'}</strong><span>entre {available.length} alternativas disponibles</span></div>
      <AplicarRuta key={JSON.stringify([result.comparison_id, live.instanceId, live.graphVersion, origin, destination])} comparison={result} live={live} apiUrl={apiUrl} origin={origin} destination={destination} onFocus={key => onVisibility(Object.fromEntries(ROUTES.map(r => [r.key, r.key === key])))} />
      <div className="sdn-comparison-cards">{ROUTES.map(({ key, label, color }) => <article key={key} style={{ '--route-color': color }} className={!routes[key] ? 'is-unavailable' : ''}>
        <div className="sdn-route-card-heading"><span className="sdn-route-dot" /><h4>{label}</h4><label title={`Mostrar ${label} en el mapa`}><input type="checkbox" aria-label={`Mostrar ${label}`} checked={Boolean(visibility[key])} disabled={!routes[key]} onChange={e => onVisibility(v => ({ ...v, [key]: e.target.checked }))} /></label></div>
        {routes[key] ? <><p className="sdn-route-path">{pathName(routes[key].ruta)}</p>
          <dl className="sdn-card-common-metrics">{rows.map(([metric, field, unit, multiplier, direction]) => {
            const value = routes[key][field];
            return <div key={field} className={isBest(value, field, direction) ? 'is-best' : ''}><dt>{metric}</dt><dd>{fmt(value == null ? null : value * multiplier)}{value == null ? '' : unit}</dd></div>;
          })}</dl>
          <p className="sdn-muted">Costo del criterio de selección: {fmt(routes[key].costo_criterio ?? (key === 'ml' ? routes[key].costo_qos : routes[key].costo_referencia))} {routes[key].unidad_costo || (key === 'ml' ? 'QoS' : '1/Mbps')}. Su unidad depende del criterio.</p>
          {key !== 'conventional' && <><h5>Previsión del modelo para su camino</h5><dl className="sdn-card-common-metrics"><div><dt>Delay previsto · suma</dt><dd>{fmt(routes[key].delay_previsto_ms)} ms</dd></div><div><dt>Loss previsto · compuesto</dt><dd>{fmt(routes[key].loss_previsto_ratio * 100)} %</dd></div><div><dt>Ajustes físicos en esta ruta</dt><dd>{routes[key].ajustes_ruta?.length ?? 0}</dd></div></dl><p className="sdn-muted">Modelo: {routes[key].modelo_id}. Estas previsiones pertenecen a este modelo y no se usan para elegir un ganador entre modelos.</p></>}
          <div className="sdn-route-badges">{isBest(routes[key].saltos, 'saltos', 'min') && <span>Menos saltos</span>}{isBest(routes[key].measured_qos, 'measured_qos', 'min') && <span>Menor QoS observado</span>}</div>
          <button className="sdn-table-link" type="button" onClick={() => onVisibility(Object.fromEntries(ROUTES.map(r => [r.key, r.key === key])))}>Ver solo este trazado</button>
        </> : <p className="sdn-muted">No disponible. {reason(key)}</p>}
      </article>)}</div>
      <div className="sdn-route-legend"><span className="sdn-shared-key">Dorado: enlace compartido por varias rutas visibles</span><button className="secondary-button" type="button" onClick={() => onVisibility(Object.fromEntries(ROUTES.map(r => [r.key, Boolean(routes[r.key])])))}>Mostrar todos</button></div>
      {groups.filter(g => g.criterios.length > 1).map(g => <p className="sdn-coincidence" key={g.criterios.join('-')}><strong>Coinciden:</strong> {g.criterios.map(k => ROUTES.find(r => r.key === k).short).join(' + ')}. Seleccionan el mismo camino.</p>)}
      <div className="sdn-table-scroll"><table className="sdn-table sdn-four-table"><caption>Los cinco caminos se evalúan con las mismas mediciones de la ventana original por enlace. Las previsiones de cada modelo se muestran aparte.</caption>
        <thead><tr><th>Indicador</th>{ROUTES.map(r => <th key={r.key}><span className="sdn-route-dot" style={{ background: r.color }} />{r.short}</th>)}</tr></thead><tbody>
          {rows.map(([label, field, unit, multiplier, direction]) => <tr key={field}><th scope="row">{label}</th>{ROUTES.map(({ key }) => {
            const value = routes[key]?.[field];
            return <td key={key} className={isBest(value, field, direction) ? 'sdn-best-metric' : ''}>{fmt(value == null ? null : value * multiplier)}{value == null ? '' : unit}</td>;
          })}</tr>)}
        </tbody></table></div>
      <p className="sdn-muted">Resaltado: menor valor de la fila; en capacidad nominal, mayor valor. Los costos propios de cada tarjeta tienen unidades distintas. El QoS observado usa las mismas mediciones para todas las rutas. No equivale a una medición extremo a extremo ni demuestra el desempeño futuro.</p>
      <p className="sdn-muted">Disponibilidad de los cuatro modelos al calcular: {result.ml.status === 'available' ? 'disponible' : 'no disponible'}. {result.ml.motivo}</p>
      {result.ml.feature_end_epoch_s && <p className="sdn-muted">Ventana común de entrada: {new Date(result.ml.feature_start_epoch_s * 1000).toLocaleTimeString('es-CO')} → {new Date(result.ml.feature_end_epoch_s * 1000).toLocaleTimeString('es-CO')}. Previsiones para la ventana siguiente a esa medición; resultado conservado para consulta.</p>}
      <p className="sdn-muted">Polinomial incluida como alternativa experimental. Para los cuatro modelos se limita throughput/delay a valores no negativos y loss a [0,1]. Se conservan las predicciones crudas; los informes MSE/RMSE/MAE no se modifican.</p>
      {ROUTES.map(({ key, label }) => routes[key]?.ajustes_ruta?.length > 0 && <details key={'ajustes-'+key}><summary>Predicciones fuera de rango ajustadas · {label}</summary><ul>{routes[key].ajustes_ruta.map((a,i) => <li key={i}>{a.link_id} · {a.target}: {fmt(a.raw,8)} → {fmt(a.used,8)}</li>)}</ul></details>)}
      <details><summary>Método y alcance</summary><p className="sdn-muted">{result.formula}. Pesos: {Object.entries(result.pesos).map(([k,v]) => `${names[k]} ${fmt(v)}`).join(' · ')}.</p>
        {result.advertencias.map(text => <p className="sdn-muted" key={text}>{text}</p>)}
      </details>
      {ROUTES.map(({ key, label }) => routes[key]?.predicciones_enlaces?.length > 0 && <details key={key}><summary>Predicciones por enlace · {label}</summary>
        <div className="sdn-table-scroll"><table className="sdn-table"><caption>Predicciones fijadas a la ventana de esta comparación</caption><thead><tr><th>Dirección</th><th>RX Mbps</th><th>Delay ms</th><th>Loss %</th></tr></thead><tbody>
          {routes[key].predicciones_enlaces.map(e => <tr key={e.link_id}><td><button type="button" className="sdn-table-link" onClick={() => onSelectLink(e.link_id)}>{nodeName(e.origen)} → {nodeName(e.destino)}</button></td><td>{fmt(e.throughput_rx_mbps)}</td><td>{fmt(e.delay_ms)}</td><td>{fmt(e.loss_ratio * 100)}</td></tr>)}
        </tbody></table></div>
      </details>)}
    </>}
  </div>;
}
