import { useEffect, useRef, useState } from 'react';

const defaults = { delay: 0.5, loss: 0.35, capacity: 0.15, load: 0 };
const names = { delay: 'Delay', loss: 'Loss', capacity: 'Capacidad', load: 'Carga RX (opcional)' };
const fmt = (n, digits = 4) => n == null ? '—' : Number(n).toLocaleString('es-CO', { maximumFractionDigits: digits });

export default function ComparacionRutas({ live, apiUrl, origin, destination, result, onResult, visibility, onVisibility, onSelectLink, clock, onStart }) {
  const [weights, setWeights] = useState(defaults);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(null);
  const epoch = useRef(0);
  const context = JSON.stringify([apiUrl, live.instanceId, live.graphVersion, live.snapshot.selection_revision, origin, destination, live.ready]);
  useEffect(() => () => { epoch.current += 1; pending.current?.abort(); }, [context]);

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
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Revisa los parametros de comparacion.');
      if (data.topology_instance_id !== live.instanceId || data.graph_version !== live.graphVersion ||
          data.selection_revision !== live.snapshot.selection_revision || data.session_id !== live.snapshot.session_id) {
        throw new Error('La respuesta pertenece a otra seleccion. Vuelve a comparar.');
      }
      if (epoch.current === generation) onResult(data);
    } catch (caught) {
      if (epoch.current === generation) setError(caught.name === 'AbortError' ? 'La comparacion tardo demasiado. Reintenta con una ventana reciente.' : caught.message);
    } finally {
      clearTimeout(timeout);
      if (epoch.current === generation) setLoading(false);
    }
  }
  const validWeights = Object.values(weights).every(n => Number.isFinite(n) && n >= 0) && Object.values(weights).some(n => n > 0);
  const routes = [['convencional', 'Convencional'], ['inteligente', 'Inteligente ML']];
  const rows = [
    ['Saltos', 'saltos', ''], ['Costo de referencia (Σ 1/Mbps)', 'costo_referencia', ''],
    ['Costo QoS (misma formula)', 'costo_qos', ''], ['Delay previsto acumulado', 'delay_previsto_ms', ' ms'],
    ['Loss previsto compuesto', 'loss_previsto_ratio', ' %', 100], ['Cuello de botella nominal', 'capacidad_minima_mbps', ' Mbps'],
  ];
  return <div className="sdn-comparison" aria-live="polite">
    <style>{`.sdn-comparison{margin-top:24px;border-top:1px solid #28445e;padding-top:20px}.sdn-comparison h3{margin:0 0 12px}.sdn-qos-inputs,.sdn-comparison-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.sdn-qos-inputs label{display:grid;gap:6px}.sdn-comparison-cards{margin-top:16px}.sdn-comparison-cards article{padding:16px;border:1px solid #345a7e;border-radius:10px}.sdn-route-legend{display:flex;gap:16px;flex-wrap:wrap;margin:14px 0}.sdn-route-legend label{display:flex;align-items:center;gap:6px}.sdn-comparison-cards p{overflow-wrap:anywhere}.sdn-comparison .primary-button{margin-top:14px}@media(max-width:760px){.sdn-comparison-cards{grid-template-columns:1fr}}`}</style>
    <h3>Comparacion de rutas: convencional vs. inteligente</h3>
    <p className="sdn-muted">Origen {origin?.toUpperCase()} → destino {destination?.toUpperCase()}. Usa los selectores de arriba. La referencia conserva el costo inverso de la capacidad; ML minimiza QoS direccional.</p>
    <form onSubmit={calculate}>
      <details><summary>Pesos QoS configurables</summary><div className="sdn-qos-inputs">
        {Object.entries(names).map(([key, name]) => <label key={key}>{name}<input className="select-control" type="number" min="0" step="0.05" value={Number.isFinite(weights[key]) ? weights[key] : ''} onChange={e => {
          epoch.current += 1; pending.current?.abort(); setLoading(false); onResult(null);
          setWeights(previous => ({ ...previous, [key]: e.target.value === '' ? NaN : Number(e.target.value) }));
        }} /></label>)}
      </div><p className="sdn-muted">Se normalizan para sumar 1. Escalas: 50 ms, loss 1 %, capacidad 1 Mbps. Carga RX queda en 0 por defecto: poco trafico no implica un enlace malo. Al activarla, solo penaliza trafico RX cursado como proxy; no estima capacidad libre.</p></details>
      <button className="primary-button" disabled={loading || !live.ready || !origin || origin === destination || !validWeights}>{loading ? 'Comparando con predicciones recientes…' : 'Comparar rutas'}</button>
      {!validWeights && <p role="alert">Los pesos deben ser no negativos y sumar mas de cero.</p>}
    </form>
    {error && <p className="error-message" role="alert">{error}</p>}
    {result && <>
      <div className="sdn-comparison-cards">{routes.map(([key, name]) => <article key={key}><h3>{name}</h3>
        {result[key] ? <><p>{result[key].ruta.map(n => n.toUpperCase()).join(' → ')}</p><p>{result[key].saltos} saltos</p></>
          : <p>Ruta inteligente no disponible: faltan predicciones validas y recientes.</p>}
      </article>)}</div>
      <p><strong>{result.recomendacion}</strong></p>
      <p className="sdn-muted">Modelo: {result.ml.status === 'available' ? result.ml.modelo_id : 'sin predicciones utilizables'}. {result.ml.motivo}</p>
      {result.ml.feature_end_epoch_s && <p className="sdn-muted">Ventana fijada: {new Date(result.ml.feature_start_epoch_s * 1000).toLocaleTimeString('es-CO')} → {new Date(result.ml.feature_end_epoch_s * 1000).toLocaleTimeString('es-CO')}. Antiguedad actual de entradas: {fmt(clock / 1000 - result.ml.feature_end_epoch_s, 0)} s / {result.ml.max_age_s} s. Predice la ventana siguiente; no son mediciones extremo a extremo.</p>}
      <div className="sdn-route-legend" aria-label="Rutas en el mapa">
        <label><input type="checkbox" checked={visibility.convencional} onChange={e => onVisibility(v => ({ ...v, convencional: e.target.checked }))} /> Azul continua: convencional</label>
        <label><input type="checkbox" checked={visibility.inteligente} onChange={e => onVisibility(v => ({ ...v, inteligente: e.target.checked }))} /> Violeta discontinua: ML</label>
        <span>Dorado punteado: tramos compartidos</span>
      </div>
      <div className="sdn-table-scroll"><table className="sdn-table"><caption>Valores derivados de la misma topologia y ventana; los dos costos tienen escalas distintas</caption>
        <thead><tr><th>Indicador</th><th>Convencional</th><th>Inteligente</th></tr></thead><tbody>
          {rows.map(([label, key, unit, multiplier = 1]) => <tr key={key}><th scope="row">{label}</th>{routes.map(([route]) => <td key={route}>{fmt(result[route]?.[key] == null ? null : result[route][key] * multiplier)}{result[route]?.[key] == null ? '' : unit}</td>)}</tr>)}
        </tbody></table></div>
      <details><summary>Metodo, pesos y limitaciones</summary><p className="sdn-muted">{result.formula}. Pesos usados: {Object.entries(result.pesos).map(([k,v]) => `${names[k]} ${fmt(v)}`).join(' · ')}.</p>
        {result.advertencias.map(text => <p className="sdn-muted" key={text}>{text}</p>)}
      </details>
      {routes.map(([key, name]) => result[key]?.predicciones_enlaces.length > 0 && <details key={key}><summary>Predicciones por enlace · {name}</summary>
        <div className="sdn-table-scroll"><table className="sdn-table"><caption>Predicciones fijadas a la ventana de esta comparacion</caption><thead><tr><th>Direccion</th><th>RX Mbps</th><th>Delay ms</th><th>Loss %</th></tr></thead><tbody>
          {result[key].predicciones_enlaces.map(e => <tr key={e.link_id}><td><button type="button" className="sdn-table-link" onClick={() => onSelectLink(e.link_id)}>{e.origen.toUpperCase()} → {e.destino.toUpperCase()}</button></td><td>{fmt(e.throughput_rx_mbps)}</td><td>{fmt(e.delay_ms)}</td><td>{fmt(e.loss_ratio * 100)}</td></tr>)}
        </tbody></table></div>
      </details>)}
    </>}
  </div>;
}
