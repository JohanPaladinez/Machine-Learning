import { useEffect, useState } from 'react';
import './operation.css';

const integer = n => {
  if (n == null) return '—';
  try { return BigInt(n).toLocaleString('es-CO'); } catch { return '—'; }
};
const rate = n => typeof n === 'number' && Number.isFinite(n) ? `${n.toLocaleString('es-CO', { maximumFractionDigits: 4 })} Mbps` : '—';
const stateLabel = value => ({ up: 'Activo', down: 'Inactivo', unverified: 'Sin verificar' }[value] || 'No disponible');

function useOperational(live, switches) {
  const [state, setState] = useState({ data: {}, error: '', loading: true });
  const ids = JSON.stringify(switches), api = live?.apiUrl, instance = live?.instanceId, graph = live?.graphVersion, ready = live?.ready;
  useEffect(() => {
    let closed = false, timer, request;
    if (!ready) return undefined;
    async function update() {
      request = new AbortController();
      const timeout = setTimeout(() => request.abort(), 15000);
      try {
        const entries = await Promise.all(JSON.parse(ids).map(async id => {
          const query = new URLSearchParams({ topology_instance_id: instance, graph_version: graph });
          const response = await fetch(`${api}/api/sdn/operacion/switch/${encodeURIComponent(id)}?${query}`, { signal: request.signal, cache: 'no-store' });
          const value = await response.json();
          if (!response.ok) throw new Error(value.detail || 'No se pudo consultar RYU.');
          if (value.topology_instance_id !== instance || value.graph_version !== graph) throw new Error('Cambio de sesion durante la consulta.');
          return [id, value];
        }));
        if (!closed) setState({ data: Object.fromEntries(entries), error: '', loading: false });
      } catch (e) {
        if (!closed) setState({ data: {}, error: e.name === 'AbortError' ? 'La consulta de puertos no respondió.' : e.message, loading: false });
      } finally { clearTimeout(timeout); if (!closed) timer = setTimeout(update, 10000); }
    }
    update();
    return () => { closed = true; clearTimeout(timer); request?.abort(); };
  }, [ids, api, instance, graph, ready]);
  return ready ? state : { data: {}, error: 'Esperando una sesión de red verificada.', loading: false };
}

function CounterTable({ ports, compact = false }) {
  return <div className="sdn-table-scroll"><table className="sdn-table sdn-port-table"><thead><tr><th>Puerto / vecino</th><th>Estado</th><th>Bits TX</th><th>Bits RX</th><th>Paquetes TX / RX</th><th>Drops TX / RX</th><th>Errores TX / RX</th>{!compact && <><th>Tasa TX / RX</th><th>Intervalo</th></>}</tr></thead><tbody>{ports.map(p => <tr key={p.port_no}><td><strong>{p.port_no} · {p.name}</strong><br />{p.peer || 'Sin vecino identificado'}</td><td>{stateLabel(p.state)}{p.counter_reset && <small> · contador reiniciado</small>}</td><td>{integer(p.tx_bits)}</td><td>{integer(p.rx_bits)}</td><td>{integer(p.counters?.tx_packets)} / {integer(p.counters?.rx_packets)}</td><td>{integer(p.counters?.tx_dropped)} / {integer(p.counters?.rx_dropped)}</td><td>{integer(p.counters?.tx_errors)} / {integer(p.counters?.rx_errors)}</td>{!compact && <><td>{rate(p.rates?.tx_mbps)} / {rate(p.rates?.rx_mbps)}</td><td>{p.rate_interval_s == null ? 'Segunda consulta pendiente' : `${p.rate_interval_s.toFixed(2)} s`}</td></>}</tr>)}</tbody></table></div>;
}

export function SwitchOperational({ live, node }) {
  const { data, error, loading } = useOperational(live, [node.id]);
  const record = data[node.id], desc = record?.description;
  return <section className="sdn-operational"><h3 className="sdn-subheading">Información operativa de RYU</h3>{loading && <p className="sdn-muted">Consultando descripción y puertos…</p>}{error && <p role="status" className="sdn-muted">{error}</p>}{record && <><dl className="sdn-details">{[['Fabricante reportado', desc?.mfr_desc], ['Hardware / plataforma', desc?.hw_desc], ['Software / versión', desc?.sw_desc], ['Número de serie', desc?.serial_num], ['Descripción del datapath', desc?.dp_desc], ['OpenFlow configurado', record.openflow_configured], ['OpenFlow negociado', record.openflow_negotiated || 'No expuesto por este servicio REST'], ['Puertos de datos reportados', record.port_count], ['Puerto LOCAL', record.local_port]].map(([label, v]) => <div className="sdn-detail" key={label}><dt>{label}</dt><dd>{v ?? 'No disponible'}</dd></div>)}</dl><CounterTable ports={record.ports} /><p className="sdn-muted">{record.note} Las cifras corresponden al switch virtual, no a un equipo físico histórico.</p>{Object.keys(record.errors).length > 0 && <p className="sdn-muted">Datos parciales: {Object.entries(record.errors).map(([k, v]) => `${k}: ${v}`).join(' · ')}</p>}</>}</section>;
}

export function LinkOperational({ live, link }) {
  const { data, error, loading } = useOperational(live, [link.source, link.target]);
  return <section className="sdn-operational"><h3 className="sdn-subheading">Contadores de los puertos del enlace</h3>{loading && <p className="sdn-muted">Consultando ambos extremos…</p>}{error && <p className="sdn-muted" role="status">{error}</p>}{[[link.source, link.portU, 'u'], [link.target, link.portV, 'v']].map(([id, port, side]) => {
    const p = data[id]?.ports.find(p => p.port_no === port);
    return <div key={id}><h4>{side} · {id.toUpperCase()} · puerto {port}</h4>{p ? <CounterTable ports={[p]} /> : <p className="sdn-muted">Puerto sin datos disponibles.</p>}</div>;
  })}<p className="sdn-muted">TX sale del switch hacia el enlace; RX entra al switch. Son acumulados del puerto desde su creación o reinicio. Las tasas se calculan entre consultas de RYU y no usan la ventana de sondas. Drops y errores no equivalen a paquetes perdidos de extremo a extremo.</p></section>;
}

export function InfrastructureDetails({ selected, topology, snapshot }) {
  const n = topology.nodes.find(n => n.id === selected.id), c = snapshot?.controller || {};
  const host = snapshot?.hosts_runtime?.find(h => h.switch === selected.id);
  const control = selected.type === 'controller' || selected.type === 'control';
  const rows = control ? [['Tipo', selected.type === 'control' ? 'Conexión de control OpenFlow' : 'Controlador RYU'], ['IP de RYU', c.ip], ['Puerto OpenFlow', c.of_port ?? c.port], ['API REST', c.rest_url], ['Estado', snapshot?.ryu?.identity_verified && snapshot?.ready ? 'Identidad y puertos verificados' : 'Sin verificar'], ['Protocolo configurado', snapshot?.protocol_configured || 'No publicado por el observador']] :
    [['Tipo', selected.type === 'access' ? 'Enlace de acceso host ↔ switch' : 'Host Mininet'], ['Host', n?.host], ['IP', host?.ip || n?.hostIp], ['MAC observada', host?.mac], ['Switch', n?.runtimeSwitch || n?.id], ['Puerto del switch', n?.hostPort], ['Interfaz del host', host?.interface], ['Estado observado', host ? stateLabel(host.state) : 'Sin telemetría de acceso']];
  return <><dl className="sdn-details">{rows.map(([label, v]) => <div className="sdn-detail" key={label}><dt>{label}</dt><dd>{v ?? 'No disponible'}</dd></div>)}</dl><p className="sdn-muted">{control ? 'La línea discontinua representa la conexión lógica de control TCP; no es un enlace de datos ni interviene en Dijkstra.' : 'La asociación procede del perfil usado para crear Mininet; el estado solo se confirma cuando el recolector publica la interfaz de acceso.'} Las posiciones del host y del controlador son esquemáticas.</p></>;
}
