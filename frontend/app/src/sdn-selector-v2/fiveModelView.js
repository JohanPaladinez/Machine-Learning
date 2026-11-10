export const ROUTES = [
  { key: 'conventional', label: 'Convencional · 1/capacidad', short: 'Convencional', color: '#94a3b8', className: 'comparison-conventional' },
  { key: 'polinomial', label: 'Dijkstra + Polinomial', short: 'Polinomial', color: '#38bdf8', className: 'comparison-polinomial' },
  { key: 'decision_tree', label: 'Dijkstra + Decision Tree', short: 'Decision Tree', color: '#fb923c', className: 'comparison-decision-tree' },
  { key: 'random_forest', label: 'Dijkstra + Random Forest', short: 'Random Forest', color: '#34d399', className: 'comparison-random-forest' },
  { key: 'xgboost', label: 'Dijkstra + XGBoost', short: 'XGBoost', color: '#c084fc', className: 'comparison-xgboost' },
];
export const COMPARISON_STORAGE = 'sdn-cinco-rutas-guardada-v1';
export function completeComparison(value) {
  return !comparisonContractError(value) && value.ml?.status === 'available'
    && ROUTES.every(r => Array.isArray(value.rutas[r.key]?.ruta) && value.rutas[r.key].ruta.length >= 2);
}
export function savePresentation(value, origin, destination, labels, storage) {
  if (!completeComparison(value)) return value;
  const saved = JSON.parse(JSON.stringify(value));
  saved.presentation_snapshot = { saved_at: new Date().toISOString(), origin, destination,
    node_labels: Object.fromEntries(labels || []) };
  try { storage.setItem(COMPARISON_STORAGE, JSON.stringify(saved)); }
  catch { saved.presentation_snapshot.persistence_warning = 'Guardada en esta visita; el navegador no permitió conservarla al recargar.'; }
  return saved;
}
export function restorePresentation(storage) {
  try {
    const text = storage.getItem(COMPARISON_STORAGE);
    if (!text || text.length > 3*1024*1024) return null;
    const value = JSON.parse(text);
    if (!completeComparison(value) || !Number.isFinite(Date.parse(value.presentation_snapshot?.saved_at))) return null;
    return value;
  } catch { return null; }
}
export function comparisonMatchesNetwork(result, live) {
  return Boolean(live?.ready && result?.topology_instance_id === live.instanceId
    && result?.graph_version === live.graphVersion && result?.selection_revision === live.snapshot.selection_revision);
}
export function comparisonContractError(result) {
  if (result?.comparacion_modelos_version !== 1 || !result.rutas || ROUTES.some(r => !Object.hasOwn(result.rutas,r.key))) {
    return 'El backend abierto no ofrece las cinco rutas por modelo. Reinicia solo la aplicación Windows con Detener_interfaz.cmd y Abrir_interfaz.cmd.';
  }
  return '';
}
export function routesOf(result) {
  return result?.rutas || Object.fromEntries(ROUTES.map(r => [r.key,null]));
}
export function routeGroups(routes) {
  const groups = new Map();
  for (const {key} of ROUTES) {
    if (!routes[key]) continue;
    const path=JSON.stringify(routes[key].ruta);
    if (!groups.has(path)) groups.set(path,{criterios:[],ruta:routes[key].ruta});
    groups.get(path).criterios.push(key);
  }
  return [...groups.values()];
}
export function withoutForecasts(result) {
  const old=result.rutas.conventional;
  const conventional=old ? {...old,measured_qos:null,measured_delay_ms:null,measured_loss_ratio:null} : null;
  const routes=Object.fromEntries(ROUTES.map(r=>[r.key,r.key==='conventional'?conventional:null]));
  return {...result,rutas:routes,ml:{status:'expired',motivo:'La ventana caducó. Vuelve a comparar las cinco rutas.'},
    errores_criterios:Object.fromEntries(ROUTES.slice(1).map(r=>[r.key,'Las predicciones caducaron.'])),coincidencias:routeGroups(routes)};
}
export function edgeCriteria(result,visibility,linkId) {
  const routes=routesOf(result);
  return ROUTES.filter(r=>visibility[r.key]&&routes[r.key]?.edge_ids.includes(linkId));
}
