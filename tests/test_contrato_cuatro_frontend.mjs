import test from 'node:test';
import assert from 'node:assert/strict';
import { comparisonContractError } from '../frontend/app/src/sdn-selector-v2/comparisonView.js';

test('backend anterior se identifica como incompatible, sin atribuirlo a falta de configuracion', () => {
  const error = comparisonContractError({convencional: {}, inteligente: {}});
  assert.match(error, /servicio de Windows/);
  assert.match(error, /Detener_interfaz.cmd/);
  assert.match(error, /no indica que falten datos/);
});

test('respuesta incompleta no se presenta como comparacion de cuatro resultados', () => {
  assert.ok(comparisonContractError({rutas: {capacity: {}, ml: {}}}));
});

test('criterios no disponibles de forma explicita son un contrato valido', () => {
  assert.equal(comparisonContractError({rutas: {hops: {}, delay: null, capacity: {}, ml: null}}), '');
});
