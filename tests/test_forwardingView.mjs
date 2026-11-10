import test from 'node:test';
import assert from 'node:assert/strict';
import {appliedMatchesComparison, canPrepareForwarding, forwardingPayload} from '../frontend/app/src/sdn-selector-v2/forwardingView.js';

const live = {ready: true, instanceId: 'instance', graphVersion: 'graph', snapshot: {selection_revision: 2, session_id: 'session'}};
const comparison = {topology_instance_id: 'instance', graph_version: 'graph', selection_revision: 2, session_id: 'session',
  pesos: {delay: .5}, escalas: {delay_ms: 50}, rutas: {conventional: {ruta: ['s1', 's3', 's6', 's14']}, xgboost: {ruta: ['s1', 's3', 's6', 's14'], modelo_id: 'xgb-real'}}};
test('preparar envia identidad, modelo y camino esperado, nunca una URL de controlador', () => {
  const p = forwardingPayload(comparison, 'xgboost', live, 's1', 's14');
  assert.equal(p.modelo_id_esperado, 'xgb-real');
  assert.deepEqual(p.ruta_esperada, ['s1', 's3', 's6', 's14']);
  assert.equal(p.rest_url, undefined);
  assert.equal(p.plan_id, undefined);
});
test('una comparacion archivada de otra sesion se puede ver pero no preparar para aplicar', () => {
  assert.equal(canPrepareForwarding(comparison, {...live, instanceId: 'other'}, 's1', 's14'), false);
  assert.throws(() => forwardingPayload(comparison, 'conventional', {...live, ready: false}, 's1', 's14'));
});
test('cambiar los extremos o elegir un modelo sin camino no instala una ruta diferente en silencio', () => {
  assert.throws(() => forwardingPayload(comparison, 'random_forest', live, 's1', 's14'));
  assert.throws(() => forwardingPayload(comparison, 'conventional', live, 's3', 's14'));
});
test('el mapa nunca etiqueta un nuevo camino calculado como el recorrido viejo aplicado', () => {
  const active = {topology_instance_id: 'instance', graph_version: 'graph', criterio: 'conventional', route: ['s1', 's3', 's6', 's14']};
  assert.equal(appliedMatchesComparison(active, comparison, live), true);
  assert.equal(appliedMatchesComparison({...active, route: ['s1', 's14']}, comparison, live), false);
  assert.equal(appliedMatchesComparison({...active, topology_instance_id: 'other'}, comparison, live), false);
});
