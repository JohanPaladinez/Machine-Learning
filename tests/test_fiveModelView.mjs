import test from 'node:test';
import assert from 'node:assert/strict';
import {ROUTES,comparisonContractError,routeGroups,edgeCriteria,withoutForecasts} from '../frontend/app/src/sdn-selector-v2/fiveModelView.js';
const fixture=()=>({comparacion_modelos_version:1,rutas:Object.fromEntries(ROUTES.map(r=>[r.key,{ruta:['s1','s2'],edge_ids:['s1-s2'],saltos:1,measured_delay_ms:2,measured_qos:.1,measured_loss_ratio:.01}])),ml:{status:'available'}});
test('cinco alternativas reales esperadas y contrato anterior rechazado',()=>{
  assert.equal(ROUTES.length,5);assert.equal(comparisonContractError(fixture()),'');
  assert.ok(comparisonContractError({rutas:{hops:{},delay:{},capacity:{},ml:{}}}));
});
test('los cinco caminos pueden coincidir sin inventar diferencias',()=>{
  const f=fixture();const groups=routeGroups(f.rutas);assert.equal(groups.length,1);assert.equal(groups[0].criterios.length,5);
  assert.equal(edgeCriteria(f,Object.fromEntries(ROUTES.map(r=>[r.key,true])),'s1-s2').length,5);
  assert.equal(edgeCriteria(f,{polinomial:true},'s1-s2')[0].key,'polinomial');
});
test('caducidad retira las cuatro previsiones y mediciones viejas; conserva configuracion convencional',()=>{
  const f=fixture(),expired=withoutForecasts(f);assert.equal(expired.rutas.conventional.saltos,1);
  assert.equal(expired.rutas.conventional.measured_delay_ms,null);
  for(const r of ROUTES.slice(1))assert.equal(expired.rutas[r.key],null);
  assert.equal(f.rutas.polinomial.saltos,1);
});
test('servicio no disponible admite convencional y cuatro causas de indisponibilidad',()=>{
  const f=fixture();for(const r of ROUTES.slice(1))f.rutas[r.key]=null;
  assert.equal(comparisonContractError(f),'');assert.equal(routeGroups(f.rutas).length,1);
});
