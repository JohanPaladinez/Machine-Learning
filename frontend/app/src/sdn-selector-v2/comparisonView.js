export const ROUTES = [
  { key: 'hops', label: 'Menos saltos', short: 'Saltos', color: '#38bdf8', className: 'comparison-hops' },
  { key: 'delay', label: 'Retardo configurado', short: 'Retardo', color: '#fb923c', className: 'comparison-delay' },
  { key: 'capacity', label: 'Inverso de capacidad', short: 'Capacidad', color: '#34d399', className: 'comparison-capacity' },
  { key: 'ml', label: 'Predicción ML', short: 'ML', color: '#c084fc', className: 'comparison-ml' },
];

export function comparisonContractError(result) {
  if (!result?.rutas || ROUTES.some(({ key }) => !Object.hasOwn(result.rutas, key))) {
    return 'El servicio de Windows todavía no devuelve los cuatro criterios. Cierra la interfaz con Detener_interfaz.cmd y vuelve a iniciarla con Abrir_interfaz.cmd. Después pulsa Comparar las 4 rutas. Esto no indica que falten datos en la topología.';
  }
  return '';
}

export function routesOf(result) {
  return result?.rutas || { hops: null, delay: null, capacity: result?.convencional || null, ml: result?.inteligente || null };
}

export function routeGroups(routes) {
  const groups = new Map();
  for (const { key } of ROUTES) {
    if (!routes[key]) continue;
    const path = JSON.stringify(routes[key].ruta);
    if (!groups.has(path)) groups.set(path, { criterios: [], ruta: routes[key].ruta });
    groups.get(path).criterios.push(key);
  }
  return [...groups.values()];
}

export function withoutForecasts(result) {
  const routes = {};
  for (const { key } of ROUTES) {
    const old = routesOf(result)[key];
    routes[key] = key === 'ml' || !old ? null : { ...old,
      costo_qos: null, delay_previsto_ms: null, loss_previsto_ratio: null, predicciones_enlaces: [] };
  }
  return { ...result, rutas: routes, convencional: routes.capacity, inteligente: null,
    ml: { status: 'expired', motivo: 'La ventana ML caducó. Compara de nuevo para obtener predicciones recientes.' },
    errores_criterios: { ...result.errores_criterios, ml: 'La ventana ML caducó.' },
    coincidencias: routeGroups(routes), caminos_distintos: routeGroups(routes).length,
  };
}

export function edgeCriteria(result, visibility, linkId) {
  const routes = routesOf(result);
  return ROUTES.filter(({ key }) => visibility[key] && routes[key]?.edge_ids.includes(linkId));
}
