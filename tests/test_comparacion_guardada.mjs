import test from 'node:test';
import assert from 'node:assert/strict';
import { ROUTES, COMPARISON_STORAGE, savePresentation, restorePresentation, completeComparison, comparisonMatchesNetwork } from '../frontend/app/src/sdn-selector-v2/fiveModelView.js';
const fixture = () => ({comparacion_modelos_version:1,topologia:'geant2',topology_instance_id:'session',graph_version:'v1',selection_revision:2,
  rutas:Object.fromEntries(ROUTES.map(r=>[r.key,{ruta:['s1','s2'],edge_ids:['s1-s2'],measured_delay_ms:8,delay_previsto_ms:9}])),
  ml:{status:'available',feature_start_epoch_s:100,feature_end_epoch_s:120,max_age_s:120}});
const storage = () => {const values=new Map();return {getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)};};
test('las cinco predicciones y mediciones se conservan aunque la ventana sea antigua',()=>{
  const s=storage(),original=fixture(),saved=savePresentation(original,'s1','s2',new Map([['s1','Dublín · S1']]),s);
  const read=restorePresentation(s);
  assert.ok(completeComparison(read));assert.equal(read.rutas.xgboost.delay_previsto_ms,9);
  assert.equal(read.rutas.conventional.measured_delay_ms,8);assert.equal(read.ml.feature_end_epoch_s,120);
  assert.equal(read.presentation_snapshot.node_labels.s1,'Dublín · S1');assert.ok(Date.parse(saved.presentation_snapshot.saved_at));
  assert.equal(original.presentation_snapshot,undefined);
});
test('una respuesta parcial no reemplaza la ultima comparacion completa guardada',()=>{
  const s=storage();savePresentation(fixture(),'s1','s2',null,s);
  const partial=fixture();partial.rutas.polinomial=null;partial.ml.status='unavailable';
  assert.equal(completeComparison(partial),false);savePresentation(partial,'s1','s2',null,s);
  assert.ok(completeComparison(restorePresentation(s)));
});
test('un resultado recuperado no dibuja caminos en una red distinta o desconectada',()=>{
  const r=fixture();const live={ready:true,instanceId:'session',graphVersion:'v1',snapshot:{selection_revision:2}};
  assert.equal(comparisonMatchesNetwork(r,live),true);
  assert.equal(comparisonMatchesNetwork(r,{...live,graphVersion:'v2'}),false);
  assert.equal(comparisonMatchesNetwork(r,{...live,ready:false}),false);
  assert.equal(comparisonMatchesNetwork(r,{...live,instanceId:'otra'}),false);
});
test('fallo de almacenamiento conserva el resultado de la visita y avisa; corrupcion se descarta',()=>{
  const r=savePresentation(fixture(),'s1','s2',null,{setItem:()=>{throw Error('quota');}});
  assert.ok(completeComparison(r));assert.match(r.presentation_snapshot.persistence_warning,/visita/);
  assert.equal(restorePresentation({getItem:()=>'{bad'}),null);
  assert.equal(restorePresentation({getItem:()=>JSON.stringify(fixture())}),null);
  const s=storage();assert.equal(s.getItem(COMPARISON_STORAGE),null);
});
