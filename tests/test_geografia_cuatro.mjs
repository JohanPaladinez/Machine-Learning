import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import { parseTopologyDocument, backendPayload } from '../frontend/app/src/sdn-vivo-v1/graph.js';
import { withPlaces, projection, geographicPaths } from '../frontend/app/src/geografia/geography.js';
import { ROUTES, withoutForecasts, edgeCriteria, routeGroups } from '../frontend/app/src/sdn-selector-v2/comparisonView.js';
const load = name => JSON.parse(fs.readFileSync(new URL(`../laboratorio/mininet/${name}/perfil.json`,import.meta.url),'utf8'));
for (const name of ['nsfnet','geant2']) test(`${name}: ciudades completas e IDs y enlaces originales conservados`,()=>{
  const p=load(name).topologies[name];const original=JSON.stringify(p);
  const out=parseTopologyDocument({schema_version:1,topologies:{[name]:p}})[name];
  assert.equal(out.nodes.length,p.nodes.length);assert.equal(out.links.length,p.links.length);
  assert.deepEqual(out.nodes.map(n=>n.id),p.nodes.map(n=>n.switch));
  assert.deepEqual(out.links.map(e=>[e.id,e.source,e.target,e.capacity,e.delay]),p.links.map(e=>[e.link_id,e.switch_u,e.switch_v,e.capacity_mbps,e.configured_delay_ms]));
  assert.equal(JSON.stringify(p),original);
  assert.ok(out.nodes.every(n=>n.city&&n.country&&Number.isFinite(n.latitude)&&Number.isFinite(n.longitude)&&n.label.includes(n.id.toUpperCase())));
  const req=backendPayload(out,'s1','s2');assert.equal(req.origen,'s1');assert.equal(req.destino,'s2');assert.ok(req.nodos.every(n=>/^s\d+$/.test(n)));
  const pr=projection(out.geography);assert.ok(out.nodes.every(n=>{const p=pr.point(n.longitude,n.latitude);return p.x>=0&&p.x<=pr.width&&p.y>=0&&p.y<=pr.height;}));
  const paths=geographicPaths(out.geography);assert.ok(paths.length>0&&paths.every(p=>!p.path.includes('NaN')));
});
test('perfil desconocido no recibe ubicaciones de otro grafo',()=>{
  const p=load('nsfnet').topologies.nsfnet;const out=parseTopologyDocument({schema_version:1,topologies:{nsfnet:p}}).nsfnet;
  const changed={...out,geography:undefined,links:out.links.slice(1)};
  assert.equal(withPlaces(changed),changed);
});
test('proyección conserva oeste/este y norte/sur',()=>{
  const out=parseTopologyDocument({schema_version:1,topologies:{nsfnet:load('nsfnet').topologies.nsfnet}}).nsfnet;
  const p=projection(out.geography);assert.ok(p.point(-120,40).x<p.point(-80,40).x);assert.ok(p.point(-100,45).y<p.point(-100,30).y);
});
test('caducidad retira todas las predicciones y conserva los tres caminos convencionales',()=>{
  const route={ruta:['s1','s2'],edge_ids:['s1-s2'],saltos:1,costo_qos:1,delay_previsto_ms:2,loss_previsto_ratio:0,predicciones_enlaces:[{}]};
  const original={rutas:Object.fromEntries(ROUTES.map(r=>[r.key,{...route}])),ml:{status:'available'},errores_criterios:{}};
  const expired=withoutForecasts(original);assert.equal(expired.rutas.ml,null);assert.equal(expired.inteligente,null);
  for(const key of ['hops','delay','capacity']) {assert.equal(expired.rutas[key].costo_qos,null);assert.deepEqual(expired.rutas[key].predicciones_enlaces,[]);assert.deepEqual(expired.rutas[key].ruta,route.ruta);}
  assert.equal(original.ml.status,'available');assert.equal(original.rutas.ml.costo_qos,1);
});
test('cuatro trazados compartidos y foco individual no inventan enlaces',()=>{
  const routes=Object.fromEntries(ROUTES.map(r=>[r.key,{ruta:['s1','s2'],edge_ids:['s1-s2']}]));
  const result={rutas:routes};const visible=Object.fromEntries(ROUTES.map(r=>[r.key,true]));
  assert.equal(edgeCriteria(result,visible,'s1-s2').length,4);assert.equal(edgeCriteria(result,{ml:true},'s1-s2')[0].key,'ml');
  assert.equal(edgeCriteria(result,visible,'otro-enlace').length,0);assert.equal(routeGroups(routes).length,1);
});
