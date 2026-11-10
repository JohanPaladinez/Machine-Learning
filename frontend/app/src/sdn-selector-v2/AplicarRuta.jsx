import { useEffect, useRef, useState } from 'react';
import { ROUTES } from './fiveModelView.js';
import { appliedMatchesComparison, canPrepareForwarding, forwardingLabels, forwardingPayload } from './forwardingView.js';
import './forwarding.css';

export default function AplicarRuta({ comparison, live, apiUrl, origin, destination, onFocus }) {
  const [criterion, setCriterion] = useState('conventional');
  const [plan, setPlan] = useState(null);
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const operation = useRef(null), generation = useRef(0);
  const instance = live.instanceId, graph = live.graphVersion, selection = live.snapshot.selection_revision, ready = live.ready;
  const active = status?.active;
  const available = ROUTES.filter(r => comparison.rutas?.[r.key]);
  const context = { topology_instance_id: instance, graph_version: graph, selection_revision: selection };
  const contextId = JSON.stringify([apiUrl, instance, graph, selection]);
  const valid = canPrepareForwarding(comparison, live, origin, destination);

  useEffect(() => () => { generation.current += 1; operation.current?.abort(); }, [contextId]);
  useEffect(() => {
    if (!ready) return undefined;
    let disposed = false, timer, controller;
    async function poll() {
      const started = generation.current;
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 20000);
      try {
        const query = new URLSearchParams({ topology_instance_id: instance, graph_version: graph, selection_revision: selection });
        const response = await fetch(`${apiUrl}/api/sdn/enrutamiento/estado?${query}`, { signal: controller.signal, cache: 'no-store' });
        const data = await response.json();
        if (!response.ok) throw new Error(response.status === 404 ? 'Reinicia el servidor Windows para cargar Aplicar ruta.' : data.detail || 'No se pudo leer el estado de las reglas.');
        if (!disposed && started === generation.current) setStatus(data);
      } catch (e) {
        if (!disposed && started === generation.current) setStatus({ active: null, error: e.name === 'AbortError' ? 'Estado de reglas sin confirmar: la consulta tardó demasiado.' : e.message });
      } finally { clearTimeout(timeout); if (!disposed) timer = setTimeout(poll, 8000); }
    }
    poll();
    return () => { disposed = true; controller?.abort(); clearTimeout(timer); };
  }, [apiUrl, instance, graph, selection, ready, revision]);

  async function act(action) {
    const version = ++generation.current;
    const controller = new AbortController();
    operation.current = controller;
    const timeout = setTimeout(() => controller.abort(), 120000);
    setBusy(action); setError(''); setMessage('');
    try {
      const body = action === 'preparar' ? forwardingPayload(comparison, criterion, live, origin, destination)
        : action === 'aplicar' ? { ...context, plan_id: plan.plan_id } : context;
      const response = await fetch(`${apiUrl}/api/sdn/enrutamiento/${action}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'No se confirmó la operación.');
      if (generation.current !== version) return;
      if (data.plan) { setPlan(data.plan); setMessage('Plan preparado. Revisa los puertos y pulsa Aplicar ruta para instalarlo.'); }
      if (data.active) {
        setStatus(previous => ({ ...previous, error: null, active: data.active }));
        if (action === 'aplicar' && appliedMatchesComparison(data.active, comparison, live)) onFocus(data.active.criterio);
        setMessage(action === 'iniciar-evidencia' ? 'Base de contadores tomada. Ejecuta el ping indicado en Mininet y luego Verificar tráfico.' : action === 'aplicar' ? 'RYU confirmó las reglas del recorrido. Falta generar tráfico y verificar sus contadores.' : data.active.verification?.all_hops ? 'Todos los saltos de ida y regreso registraron tráfico ICMP desde la base.' : 'Las reglas están presentes; falta tráfico en uno o más saltos.');
      }
      if (action === 'retirar') { setStatus({ active: null }); setPlan(null); setMessage(data.message); }
      if (action === 'aplicar') setPlan(null);
    } catch (e) {
      if (generation.current === version) setError(e.name === 'AbortError' ? 'No se confirmó la respuesta. Consulta el estado antes de reintentar: la operación del servidor puede seguir en curso.' : e.message);
    } finally {
      clearTimeout(timeout);
      if (generation.current === version) { setBusy(''); setRevision(v => v + 1); }
    }
  }

  const blocked = Boolean(busy) || !ready;
  const shown = plan || active;
  const routeLabel = key => ROUTES.find(r => r.key === key)?.label || key;
  return <section className="sdn-apply-route" aria-label="Aplicar y demostrar enrutamiento ICMP real">
    <div className="eyebrow">CONTROL EXPLÍCITO DEL TRÁFICO</div><h3>Aplicar y demostrar la ruta</h3>
    <p className="sdn-muted">Esta acción instala reglas mediante RYU para el <strong>flujo ICMP (ping)</strong> entre los hosts asociados al origen y destino. El regreso usa el mismo recorrido invertido; no se presenta como una optimización ML independiente del regreso. UDP del recolector, ARP y sondas conservan sus reglas.</p>
    <label className="field-label" htmlFor="sdn-apply-model">ALTERNATIVA A APLICAR</label>
    <select className="select-control" id="sdn-apply-model" value={criterion} disabled={blocked} onChange={e => { setCriterion(e.target.value); setPlan(null); setError(''); }}>
      {available.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
    </select>
    <div className="sdn-apply-actions"><button className="secondary-button" type="button" disabled={blocked || !valid || Boolean(status?.error)} onClick={() => act('preparar')}>{busy === 'preparar' ? 'Revalidando el camino…' : 'Preparar ruta seleccionada'}</button>
      {plan && <button className="primary-button" type="button" disabled={blocked} onClick={() => act('aplicar')}>{busy === 'aplicar' ? 'Instalando y verificando…' : 'Aplicar ruta ICMP'}</button>}
    </div>
    {!valid && <p className="sdn-muted">Para aplicar, actualiza la comparación de la sesión y los extremos actuales. Los resultados guardados siguen disponibles para consulta.</p>}
    {status?.error && <p role="alert" className="error-message">{status.error}</p>}
    {error && <p role="alert" className="error-message">{error}</p>}{message && <p role="status" className="sdn-muted">{message}</p>}
    {shown && <><strong className="sdn-applied-status">{forwardingLabels[shown.status] || shown.status}</strong><p>{routeLabel(shown.criterio)} · {shown.route.join(' → ')}</p><p className="sdn-muted">{shown.flow.source_host} ({shown.flow.source_ip}) ↔ {shown.flow.destination_host} ({shown.flow.destination_ip})<br />RYU: {shown.rest_url} · cookie {shown.cookie_hex} · prioridad {shown.priority}</p>
      {plan && active && <p className="sdn-muted">Continúa aplicada la anterior: {routeLabel(active.criterio)} · {active.route.join(' → ')}. Preparar esta alternativa todavía no cambia ese tráfico.</p>}
      <div className="sdn-table-scroll"><table className="sdn-table"><thead><tr><th>Sentido</th><th>Switch</th><th>Puerto de salida</th><th>Interfaz</th></tr></thead><tbody>{shown.ports.map((p, i) => <tr key={i}><td>{p.direction}</td><td>{p.runtime_switch}</td><td>{p.output_port}</td><td>{p.expected_interface}</td></tr>)}</tbody></table></div>
      {plan && <p className="sdn-muted">El plan se puede aplicar durante 90 s. Una vez instaladas, las reglas no caducan por tiempo: se retiran explícitamente o al detener la red. Preparar recalcula y valida entradas actuales; si cambia el camino, pide actualizar la comparación.</p>}
    </>}
    {active && <><p className="sdn-muted">Aplicada: {active.aplicado_utc}. {active.rules_checked_utc && `Reglas consultadas: ${active.rules_checked_utc}.`} La base de evidencia es {active.baseline_utc}.</p>{active.warning && <p className="error-message">{active.warning}</p>}
      <button className="secondary-button" type="button" disabled={!appliedMatchesComparison(active, comparison, live)} onClick={() => onFocus(active.criterio)}>Ver solo el recorrido aplicado</button>
      {!appliedMatchesComparison(active, comparison, live) && <p className="sdn-muted">La comparación visible no coincide con el registro aplicado; no se dibuja otro recorrido como si fuera el instalado.</p>}
      <ol><li>Pulsa <strong>Iniciar evidencia</strong> para tomar la base de contadores.</li><li>En la consola de {active.topologia.toUpperCase()}, ejecuta:<pre><code>{active.ping_command}</code></pre></li><li>Cuando termine el ping, pulsa <strong>Verificar tráfico</strong>.</li></ol>
      <div className="sdn-apply-actions"><button className="secondary-button" type="button" disabled={blocked} onClick={() => act('iniciar-evidencia')}>Iniciar evidencia</button><button className="primary-button" type="button" disabled={blocked} onClick={() => act('verificar-trafico')}>Verificar tráfico</button><button className="secondary-button" type="button" disabled={blocked} onClick={() => act('retirar')}>Retirar reglas aplicadas</button></div>
      {active.verification && <><h4>{active.verification.all_hops ? 'Tráfico verificado en todos los saltos' : 'Comprobación parcial: faltan incrementos'}</h4><p className="sdn-muted">Comprobación: {active.verification.utc}. {active.verification.note}</p><div className="sdn-table-scroll"><table className="sdn-table"><thead><tr><th>Sentido</th><th>Switch → puerto</th><th>Paquetes antes</th><th>Después</th><th>Incremento</th></tr></thead><tbody>{active.verification.rows.map((r, i) => <tr key={i}><td>{r.direction}</td><td>{r.switch} → {r.output_port}</td><td>{r.packets_before}</td><td>{r.packets_after}</td><td>{r.packets_delta}</td></tr>)}</tbody></table></div><a className="secondary-button" download={`evidencia_ruta_${active.topologia}.json`} href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(active, null, 2))}`}>Descargar evidencia JSON</a></>}
    </>}
    {status?.status === 'limpieza_pendiente' && <div className="error-message"><p>Hay reglas propias pendientes de limpieza. La aplicación no sobrescribe ese estado.</p><button type="button" disabled={blocked} onClick={() => act('retirar')}>Retirar reglas pendientes</button></div>}
    {busy && <p role="status">Operación en curso: {busy}. Espera su confirmación antes de cerrar o cambiar de sesión.</p>}
  </section>;
}
