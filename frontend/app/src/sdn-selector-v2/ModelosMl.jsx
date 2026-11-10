import { useRef, useState } from 'react';
import { BrainCircuit, Upload, Trash2 } from 'lucide-react';
import ModeloComunV1 from './ModeloComunV1.jsx';
import { ML_MODELS, ML_TARGETS, REPORT_STORAGE, validateModelReport, readStoredReports } from './modelReports.js';
const fmt = n => n == null ? '—' : Number(n).toLocaleString('es-CO', { maximumSignificantDigits: 5 });
const names = Object.fromEntries(ML_MODELS.map(m => [m.key, m.name]));

export default function ModelosMl({ apiUrl, topologia }) {
  const [reports, setReports] = useState(() => readStoredReports(window.localStorage));
  const [tab, setTab] = useState('validation');
  const [targetKey, setTarget] = useState(ML_TARGETS[0].key);
  const [groupChoice, setGroup] = useState('actual');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const input = useRef(null);
  const loaded = reports[tab], target = ML_TARGETS.find(t => t.key === targetKey);
  const requestedGroup = groupChoice === 'actual' ? `topologia:${String(topologia || '').toUpperCase()}` : groupChoice;
  const group = loaded?.groups.includes(requestedGroup) ? requestedGroup : 'global';
  const best = field => loaded ? Math.min(...ML_MODELS.map(m => loaded.report.modelos[m.key].metricas[group][target.key][field])) : null;
  const isBest = (n, field) => Number.isFinite(n) && Math.abs(n - best(field)) <= Number.EPSILON * 16 * Math.max(1, Math.abs(n), Math.abs(best(field)));
  function persist(next) {
    setReports(next);
    try { window.localStorage.setItem(REPORT_STORAGE, JSON.stringify(next)); }
    catch { setMessage('Informe cargado para esta sesión. El navegador no permitió guardarlo para la próxima visita.'); }
  }
  async function importReport(event) {
    const file = event.target.files?.[0]; event.target.value = '';
    if (!file) return;
    setError(''); setMessage('');
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error('El informe supera 2 MB. Selecciona el JSON resumen, no las predicciones CSV.');
      const parsed = validateModelReport(JSON.parse((await file.text()).replace(/^\uFEFF/, '')));
      persist({ ...reports, [parsed.kind]: { ...parsed, filename: file.name, importedAt: new Date().toISOString() } });
      setTab(parsed.kind);
      setMessage('Informe cargado. Sus métricas no cambian el modelo conectado a las rutas.');
    } catch (caught) { setError(caught.message); }
  }
  return <section className="panel sdn-models-panel" id="models">
    <div className="panel-header"><div className="panel-title"><BrainCircuit size={19} /><h2>Comparación de modelos ML</h2></div><span className="ready-tag">4 REGRESORES</span></div>
    <p className="sdn-muted">Compara errores con las mismas muestras y unidades. Los cuatro criterios de ruta de Enrutamiento son una comparación diferente.</p>
    <div className="sdn-ml-actions"><button className="secondary-button" onClick={() => input.current?.click()}><Upload size={15} />Cargar informe de RYU</button>
      <input ref={input} type="file" accept=".json,application/json" className="sdn-file-input" aria-label="Informe de comparación de modelos" onChange={importReport} />
      {loaded && <button className="secondary-button" onClick={() => { const next = { ...reports }; delete next[tab]; persist(next); setMessage('Se retiró la copia del navegador; los archivos de RYU se conservan.'); }}><Trash2 size={15} />Retirar informe de esta vista</button>}</div>
    <div className="sdn-ml-tabs" role="group" aria-label="Partición de evaluación"><button aria-pressed={tab === 'validation'} onClick={() => setTab('validation')}>Validación {reports.validation ? '· cargada' : '· pendiente'}</button><button aria-pressed={tab === 'test'} onClick={() => setTab('test')}>Test descriptivo {reports.test ? '· cargado' : '· pendiente'}</button></div>
    {error && <p role="alert" className="error-message">{error}</p>}{message && <p role="status" className="sdn-muted">{message}</p>}
    {!loaded ? <div className="sdn-ml-empty"><BrainCircuit size={28} /><strong>Esperando el informe real de {tab === 'validation' ? 'validación' : 'test'}</strong><p>Al terminar RYU, copia a Windows y carga <code>{tab === 'validation' ? 'comparacion_validation.json' : 'comparacion_test.json'}</code>. Aquí aparecerán los cuatro modelos; los datos ausentes no se reemplazan por cero.</p></div> : <>
      <div className="sdn-ml-filters"><label>VARIABLE Y SENTIDO<select className="select-control" value={targetKey} onChange={e => setTarget(e.target.value)}>{ML_TARGETS.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}</select></label><label>TOPOLOGÍA / PROCEDENCIA<select className="select-control" value={groupChoice} onChange={e => setGroup(e.target.value)}><option value="actual">Red seleccionada en el mapa</option>{loaded.groups.map(g => <option key={g} value={g}>{g === 'global' ? 'Ambas topologías · global' : g.replace('topologia:', '').replace('measurement_method:', 'Método: ').replace('probe_loss_scope:', 'Pérdida: ')}</option>)}</select></label></div>
      <p className="sdn-muted">Mostrando {group} · {target.label}. Menor MSE, RMSE y MAE es mejor. R² puede ser negativo y no es un porcentaje de acierto. Predicciones sin recortar.</p>
      {tab === 'test' && <p className="sdn-coincidence">El test ya fue examinado anteriormente. La comparación es descriptiva y la selección se fijó previamente con validation.</p>}
      <div className="sdn-comparison-cards">{ML_MODELS.map(m => {
        const model = loaded.report.modelos[m.key], metrics = model.metricas[group][target.key];
        return <article key={m.key} style={{ '--route-color': m.color }}><div className="sdn-route-card-heading"><span className="sdn-route-dot" /><h4>{m.name}</h4></div><p className="sdn-muted">{m.role}</p>
          <dl className="sdn-card-common-metrics">{[['MSE','mse',`${target.unit}²`],['RMSE','rmse',target.unit],['MAE','mae',target.unit],['R²','r2','']].map(([label, field, unit]) => <div key={field} className={field !== 'r2' && isBest(metrics[field], field) ? 'is-best' : ''}><dt>{label}</dt><dd>{fmt(metrics[field])} {unit}</dd></div>)}<div><dt>Muestras</dt><dd>{fmt(metrics.n)}</dd></div><div><dt>Predicciones fuera de rango</dt><dd>{fmt(metrics.predicciones_fuera_rango)}</dd></div><div><dt>Tiempo de entrenamiento</dt><dd>{fmt(model.entrenamiento_s)} {model.entrenamiento_s == null ? '' : 's'}</dd></div><div><dt>Tiempo de predicción del conjunto</dt><dd>{fmt(model.prediccion_s)} s</dd></div></dl>
          {tab === 'validation' && <p className="sdn-muted">Score global normalizado de validation: <strong>{fmt(model.score_validation)}</strong></p>}{loaded.selected === m.key && <span className="sdn-ml-selected">Seleccionado por validation</span>}</article>;
      })}</div>
      <div className="sdn-table-scroll"><table className="sdn-table sdn-four-table"><caption>{target.label} · {group} · mismas muestras para los cuatro modelos</caption><thead><tr><th>Indicador</th>{ML_MODELS.map(m => <th key={m.key}>{m.name}</th>)}</tr></thead><tbody>{['mse','rmse','mae','r2'].map(field => <tr key={field}><th scope="row">{field === 'r2' ? 'R²' : field.toUpperCase()}</th>{ML_MODELS.map(m => { const n = loaded.report.modelos[m.key].metricas[group][target.key][field]; return <td className={field !== 'r2' && isBest(n, field) ? 'sdn-best-metric' : ''} key={m.key}>{fmt(n)} {field === 'r2' ? '' : target.unit + (field === 'mse' ? '²' : '')}</td>; })}</tr>)}</tbody></table></div>
      <p className="sdn-muted">Seleccionado con validation: <strong>{names[loaded.selected]}</strong>. La selección combina los errores normalizados de las seis salidas y ambas topologías; puede diferir del mejor modelo para una sola variable. La polinomial es baseline. Los empates se resaltan por igual.</p>
      <p className="sdn-muted">Archivo: {loaded.filename} · importado: {new Date(loaded.importedAt).toLocaleString('es-CO')}. Informe estático de este navegador. Cargar validation y test por separado no verifica que pertenezcan a la misma ejecución.</p>
    </>}
    <div className="sdn-ml-route-service"><h3>Servicio de predicción individual de enlaces</h3><ModeloComunV1 apiUrl={apiUrl} info /><p className="sdn-muted">El inspector conserva su servicio original. Las cinco rutas consultan otro servicio con los cuatro modelos entrenados. Cargar informes solo muestra su evaluación; no inicia servicios ni instala rutas.</p></div>
  </section>;
}
