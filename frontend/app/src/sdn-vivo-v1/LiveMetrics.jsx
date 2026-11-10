const value = (n, unit = '', multiplier = 1) => typeof n === 'number' && Number.isFinite(n) ? `${(n * multiplier).toLocaleString('es-CO', { maximumFractionDigits: 3 })} ${unit}`.trim() : '—';
const refusals = d => d.tx_refused_enobufs == null || d.tx_refused_busy == null ? null : d.tx_refused_enobufs + d.tx_refused_busy;
const lost = d => d.sent == null || d.received == null ? null : d.sent - d.received;

export function LiveMetrics({ live, linkId }) {
  const metrics = live.snapshot.metrics || {};
  const sample = metrics.links?.[linkId];
  if (!live.ready || !sample) return <div className="sdn-measurement-label">Esperando mediciones verificadas de este enlace. No se reemplazan por cero.</div>;
  const a = sample.directions?.u_to_v || {}, b = sample.directions?.v_to_u || {};
  const rows = [
    ['Throughput RX', d => value(d.throughput_mbps, 'Mbps')],
    ['Throughput TX del emisor', d => value(d.tx_mbps, 'Mbps')],
    ['Bits TX en la ventana', d => value(d.tx_bits_delta, 'bits')],
    ['Bits RX en la ventana', d => value(d.rx_bits_delta, 'bits')],
    ['Paquetes TX del puerto emisor', d => value(d.tx_packets_delta)],
    ['Paquetes RX del puerto receptor', d => value(d.rx_packets_delta)],
    ['Delay promedio de sondas', d => value(d.delay_ms, 'ms')],
    ['Delay mínimo de sondas', d => value(d.delay_min_ms, 'ms')],
    ['Delay máximo de sondas', d => value(d.delay_max_ms, 'ms')],
    ['Sondas ofrecidas', d => value(d.sent)],
    ['Sondas aceptadas para TX', d => value(d.accepted)],
    ['Sondas recibidas', d => value(d.received)],
    ['Sondas no recibidas (ofrecidas − recibidas)', d => value(lost(d))],
    ['Loss ofrecido', d => value(d.loss_ratio, '%', 100)],
    ['Rechazos TX locales', d => value(refusals(d))],
    ['Drops TX emisor / RX receptor', d => `${value(d.tx_dropped_delta)} / ${value(d.rx_dropped_delta)}`],
    ['Errores TX emisor / RX receptor', d => `${value(d.tx_errors_delta)} / ${value(d.rx_errors_delta)}`],
    ['Descartes de cola del emisor', d => value(d.qdisc_drops_delta)],
    ['Capacidad residual estimada del emisor', d => value(d.residual_capacity_estimate_mbps, 'Mbps')],
  ];
  return <div className="sdn-live-metrics"><h3 className="sdn-subheading">Última ventana medida</h3><span className={`status-pill ${metrics.status === 'fresh' ? 'online' : 'pending'}`}>{metrics.status === 'fresh' ? 'Medición reciente' : 'Medición antigua'}</span><div className="sdn-table-scroll"><table className="sdn-table"><thead><tr><th>Métrica</th><th>u → v</th><th>v → u</th></tr></thead><tbody>{rows.map(([name, render]) => <tr key={name}><td>{name}</td><td>{render(a)}</td><td>{render(b)}</td></tr>)}</tbody></table></div><p className="sdn-muted">Ventana: {metrics.window_start} → {metrics.window_end}<br />Antigüedad al consultar: {value(metrics.age_s, 's')}</p><p className="sdn-muted">u y v son los extremos del enlace. TX se toma del puerto emisor y RX del receptor; los intervalos de consulta OpenFlow por extremo pueden diferir ligeramente. Loss ofrecido cuenta sondas no recibidas e incluye rechazos locales: no equivale exclusivamente a pérdida en tránsito. Los drops de cola y de puerto se muestran por separado y no se suman.</p><p className="sdn-muted">La capacidad residual es máx(0, capacidad nominal − tasa TX); es una estimación, no una prueba de ancho de banda disponible. Los extremos de delay solo se publican si fueron medidos. Un guion indica un dato no publicado, nunca cero.</p><p className="sdn-muted">Método: {sample.method || 'sin especificar'}. No se generan sondas adicionales para consultar el panel. Estas medidas de enlace no son una prueba de rendimiento extremo a extremo de una ruta.</p></div>;
}