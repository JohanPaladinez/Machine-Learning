export const ML_MODELS = [
  { key: 'polinomial', name: 'Regresión polinomial', color: '#38bdf8', role: 'Baseline · grado 2 con Ridge' },
  { key: 'decision_tree', name: 'Decision Tree', color: '#fb923c', role: 'Modelo candidato' },
  { key: 'random_forest', name: 'Random Forest', color: '#34d399', role: 'Modelo candidato' },
  { key: 'xgboost', name: 'XGBoost', color: '#c084fc', role: 'Modelo candidato' },
];
export const ML_TARGETS = [
  { key: 'target_throughput_u_to_v_mbps', label: 'Throughput RX · u → v', unit: 'Mbps' },
  { key: 'target_throughput_v_to_u_mbps', label: 'Throughput RX · v → u', unit: 'Mbps' },
  { key: 'target_u_to_v_delay_avg_ms', label: 'Delay medio · u → v', unit: 'ms' },
  { key: 'target_v_to_u_delay_avg_ms', label: 'Delay medio · v → u', unit: 'ms' },
  { key: 'target_u_to_v_loss_ratio', label: 'Pérdida ofrecida · u → v', unit: 'ratio 0–1' },
  { key: 'target_v_to_u_loss_ratio', label: 'Pérdida ofrecida · v → u', unit: 'ratio 0–1' },
];
export const REPORT_STORAGE = 'sdn-comparacion-modelos-v1';
const nonnegative = v => typeof v === 'number' && Number.isFinite(v) && v >= 0;
export function validateModelReport(value) {
  const invalid = reason => { throw new Error(`Informe de modelos inválido: ${reason}`); };
  if (!value || typeof value !== 'object' || !value.modelos) invalid('falta la comparación.');
  const kind = Object.hasOwn(value, 'seleccion_validation') ? 'validation' : Object.hasOwn(value, 'seleccion_previa_validation') ? 'test' : null;
  if (!kind) invalid('usa comparacion_validation.json o comparacion_test.json.');
  const selected = kind === 'validation' ? value.seleccion_validation : value.seleccion_previa_validation;
  if (!ML_MODELS.slice(1).some(m => m.key === selected)) invalid('selección de validation no reconocida.');
  if (Object.keys(value.modelos).sort().join(',') !== ML_MODELS.map(m => m.key).sort().join(',')) invalid('se requieren los cuatro modelos.');
  let groups;
  for (const { key } of ML_MODELS) {
    const model = value.modelos[key];
    if (!model?.metricas || typeof model.metricas !== 'object') invalid(`faltan métricas de ${key}.`);
    const keys = Object.keys(model.metricas).sort();
    if (keys.length > 200 || !['global', 'topologia:NSFNET', 'topologia:GEANT2'].every(g => keys.includes(g))) invalid('faltan grupos o hay demasiados.');
    if (groups && JSON.stringify(groups) !== JSON.stringify(keys)) invalid('los modelos no comparten los mismos grupos.');
    groups = keys;
    if (kind === 'validation' && (!nonnegative(model.score_validation) || !nonnegative(model.entrenamiento_s))) invalid(`score o tiempo inválido de ${key}.`);
    if (!nonnegative(model.prediccion_s)) invalid(`tiempo de predicción inválido de ${key}.`);
    for (const group of keys) for (const target of ML_TARGETS) {
      const m = model.metricas[group]?.[target.key];
      if (!m || !Number.isSafeInteger(m.n) || m.n <= 0 || !['mse','rmse','mae'].every(k => nonnegative(m[k])) ||
        !(m.r2 === null || (Number.isFinite(m.r2) && m.r2 <= 1)) ||
        !Number.isSafeInteger(m.predicciones_fuera_rango) || m.predicciones_fuera_rango < 0 || m.predicciones_fuera_rango > m.n) invalid(`valores de ${key}/${group}/${target.key}.`);
      const first = value.modelos.polinomial.metricas?.[group]?.[target.key];
      if (first && m.n !== first.n) invalid('diferente número de muestras entre modelos.');
      if (Math.abs(m.rmse ** 2 - m.mse) > 1e-7 * Math.max(1e-12, m.mse)) invalid('MSE y RMSE no corresponden.');
    }
  }
  if (kind === 'validation') {
    const lowest = Math.min(...ML_MODELS.slice(1).map(m => value.modelos[m.key].score_validation));
    if (value.modelos[selected].score_validation > lowest + 1e-12) invalid('la selección no corresponde al menor score de validation entre candidatos.');
  }
  return { kind, selected, groups, report: value };
}
export function readStoredReports(storage) {
  try {
    const text = storage.getItem(REPORT_STORAGE);
    if (!text || text.length > 4 * 1024 * 1024) return {};
    const stored = JSON.parse(text), result = {};
    for (const kind of ['validation', 'test']) {
      if (!stored[kind]) continue;
      const parsed = validateModelReport(stored[kind].report);
      if (parsed.kind === kind) result[kind] = { ...parsed, filename: String(stored[kind].filename), importedAt: String(stored[kind].importedAt) };
    }
    return result;
  } catch { return {}; }
}
