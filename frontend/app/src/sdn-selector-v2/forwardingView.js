import { ROUTES } from './fiveModelView.js';

export const forwardingLabels = {
  preparada: 'Ruta preparada · todavía no aplicada',
  aplicada: 'Ruta aplicada · reglas verificadas',
  trafico_verificado: 'Tráfico ICMP verificado en todos los saltos',
  grafo_cambiado: 'Cambió el grafo · aplicación sin revalidar',
  reglas_no_verificadas: 'No se confirman las reglas actuales',
  contadores_reiniciados: 'Contadores reiniciados · nueva evidencia necesaria',
  retiro_pendiente: 'Retiro incompleto · revisar antes de continuar',
  instalando: 'Instalación pendiente de comprobación',
};

export function canPrepareForwarding(comparison, live, origin, destination) {
  return Boolean(live?.ready && comparison?.topology_instance_id === live.instanceId &&
    comparison.graph_version === live.graphVersion && comparison.selection_revision === live.snapshot.selection_revision &&
    comparison.session_id === live.snapshot.session_id && origin && destination && origin !== destination);
}

export function appliedMatchesComparison(active, comparison, live) {
  return Boolean(live?.ready && active?.topology_instance_id === live.instanceId && active?.graph_version === live.graphVersion &&
    Array.isArray(active.route) && JSON.stringify(comparison?.rutas?.[active.criterio]?.ruta) === JSON.stringify(active.route));
}

export function forwardingPayload(comparison, criterion, live, origin, destination) {
  const route = comparison?.rutas?.[criterion];
  if (!ROUTES.some(r => r.key === criterion) || !canPrepareForwarding(comparison, live, origin, destination) ||
      !Array.isArray(route?.ruta) || route.ruta[0] !== origin || route.ruta.at(-1) !== destination) {
    throw new Error('Actualiza la comparación de esta sesión y elige una ruta disponible con los mismos extremos.');
  }
  return { topology_instance_id: live.instanceId, graph_version: live.graphVersion,
    selection_revision: live.snapshot.selection_revision, origen: origin, destino: destination,
    pesos: comparison.pesos, escalas: comparison.escalas, criterio: criterion,
    ruta_esperada: [...route.ruta], modelo_id_esperado: route.modelo_id || null };
}
