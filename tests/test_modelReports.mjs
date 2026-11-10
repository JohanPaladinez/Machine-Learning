import test from 'node:test';
import assert from 'node:assert/strict';
import { ML_MODELS, ML_TARGETS, validateModelReport, readStoredReports } from '../frontend/app/src/sdn-selector-v2/modelReports.js';
function fixture() {
  const modelos = {};
  for (const [i, model] of ML_MODELS.entries()) {
    const metricas = {};
    for (const group of ['global','topologia:NSFNET','topologia:GEANT2','measurement_method:synthetic']) {
      metricas[group] = Object.fromEntries(ML_TARGETS.map(t => [t.key,{n:20,mse:(i+1)**2,rmse:i+1,mae:(i+1)*.8,r2:.9-i*.1,predicciones_fuera_rango:i}]));
    }
    modelos[model.key] = {metricas,score_validation:[.2,.3,.1,.25][i],entrenamiento_s:10*(i+1),prediccion_s:.01*(i+1)};
  }
  return {modelos,seleccion_validation:'random_forest',nota_visual:'EXCLUSIVAMENTE DATOS SINTETICOS DE PRUEBA'};
}
test('informe con cuatro modelos y seis salidas aceptado sin mutacion',()=>{
  const r=fixture(),before=JSON.stringify(r),parsed=validateModelReport(r);
  assert.equal(parsed.kind,'validation');assert.equal(parsed.selected,'random_forest');assert.equal(JSON.stringify(r),before);
});
test('test descriptivo conserva seleccion previa y no necesita scores nuevos',()=>{
  const r=fixture();r.seleccion_previa_validation=r.seleccion_validation;delete r.seleccion_validation;
  for(const model of Object.values(r.modelos)){delete model.score_validation;delete model.entrenamiento_s;}
  assert.equal(validateModelReport(r).kind,'test');
});
test('no se aceptan resultados incompletos ni comparaciones con diferente n',()=>{
  const r=fixture();delete r.modelos.xgboost;assert.throws(()=>validateModelReport(r),/cuatro modelos/);
  const s=fixture();s.modelos.xgboost.metricas.global[ML_TARGETS[0].key].n=19;assert.throws(()=>validateModelReport(s),/muestras/);
});
test('MSE RMSE incoherentes y valores no finitos rechazados',()=>{
  const r=fixture();r.modelos.xgboost.metricas.global[ML_TARGETS[0].key].mse=1;assert.throws(()=>validateModelReport(r),/MSE/);
  const s=fixture();s.modelos.xgboost.metricas.global[ML_TARGETS[0].key].mae=Infinity;assert.throws(()=>validateModelReport(s),/valores/);
});
test('seleccion por test no sustituye la seleccion de validation',()=>{
  const r=fixture();r.seleccion_validation='xgboost';assert.throws(()=>validateModelReport(r),/menor score/);
});
test('persistencia rechaza datos corruptos sin afectar la interfaz',()=>{
  assert.deepEqual(readStoredReports({getItem:()=>'{bad'}),{});
  assert.deepEqual(readStoredReports({getItem:()=>{throw new Error('storage');}}),{});
  const record={report:fixture(),filename:'SINTETICO_PRUEBA.json',importedAt:new Date().toISOString()};
  assert.equal(readStoredReports({getItem:()=>JSON.stringify({validation:record})}).validation.selected,'random_forest');
});
