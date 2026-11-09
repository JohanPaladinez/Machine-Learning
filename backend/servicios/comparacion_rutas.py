"""Calculo puro: costos adimensionales, direcciones y resumen de caminos."""
import math
from backend.algoritmos.dijkstra import calcular_ruta
from backend.algoritmos.pesos import calcular_costo_capacidad
from backend.servicios.sdn_vivo_runtime_v1 import route_inputs

DEFAULT_WEIGHTS = {'delay': 0.5, 'loss': 0.35, 'capacity': 0.15, 'load': 0.0}
DEFAULT_SCALES = {'delay_ms': 50.0, 'loss_ratio': 0.01, 'capacity_mbps': 1.0}
TARGETS = {
    'u_to_v': ('target_throughput_u_to_v_mbps', 'target_u_to_v_delay_avg_ms', 'target_u_to_v_loss_ratio'),
    'v_to_u': ('target_throughput_v_to_u_mbps', 'target_v_to_u_delay_avg_ms', 'target_v_to_u_loss_ratio'),
}
CRITERIA = {
    'hops': ('Menos saltos', 'saltos'),
    'delay': ('Retardo configurado', 'ms'),
    'capacity': ('Inverso de capacidad', 'Σ 1/Mbps'),
    'ml': ('Predicción ML', 'QoS normalizado'),
}


def finite(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError('Valores numericos finitos y no negativos requeridos')
    return float(value)


def parameters(weights=None, scales=None):
    weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
    scales = dict(DEFAULT_SCALES if scales is None else scales)
    if set(weights) != set(DEFAULT_WEIGHTS) or set(scales) != set(DEFAULT_SCALES):
        raise ValueError('Parametros QoS incompletos')
    weights = {k: finite(v) for k,v in weights.items()}
    total = sum(weights.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError('La suma de pesos debe ser positiva y finita')
    return {k:v/total for k,v in weights.items()}, {k:finite(v, True) for k,v in scales.items()}


def directional_cost(capacity, throughput, delay, loss, weights, scales):
    c, t, d, l = finite(capacity, True), finite(throughput), finite(delay), finite(loss)
    if l > 1:
        raise ValueError('Loss fuera del intervalo [0,1]')
    # Formas estables de x/(x+escala), sin sumar valores grandes.
    components = {'delay': 1/(1+scales['delay_ms']/d) if d else 0.0,
                  'loss': 1/(1+scales['loss_ratio']/l) if l else 0.0,
                  'capacity': 1/(1+c/scales['capacity_mbps']),
                  'load': 1/(1+c/t) if t else 0.0}
    return sum(weights[k]*components[k] for k in weights), components


def conventional(snapshot, request):
    args = route_inputs(snapshot, request.topology_instance_id, request.graph_version,
                        request.origen, request.destino, 'capacity', calcular_costo_capacidad)
    path, _ = calcular_ruta(**args)
    return args, summarize(snapshot, path)


def summarize(snapshot, path, directed=None):
    profile = snapshot['topology_document']['topologies'][snapshot['topologia']]
    pairs = {}
    for e in profile['links']:
        pairs[(e['switch_u'],e['switch_v'])] = pairs[(e['switch_v'],e['switch_u'])] = e
    edges = [pairs[(a,b)] for a,b in zip(path,path[1:])]
    configured = [e.get('configured_delay_ms') for e in edges]
    configured_total = None
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0 for v in configured):
        configured_total = finite(sum(configured))
    result = {'ruta':path, 'saltos':len(edges), 'edge_ids':[e['link_id'] for e in edges],
              'costo_referencia':finite(sum(calcular_costo_capacidad(e['capacity_mbps']) for e in edges)),
              'capacidad_minima_mbps':min(e['capacity_mbps'] for e in edges),
              'retardo_configurado_total_ms':configured_total,
              'costo_qos':None, 'delay_previsto_ms':None, 'loss_previsto_ratio':None,
              'predicciones_enlaces':[]}
    if directed is not None:
        values = [directed[(a,b)] for a,b in zip(path,path[1:])]
        result.update(costo_qos=sum(v['costo_qos'] for v in values),
                      delay_previsto_ms=finite(sum(v['delay_ms'] for v in values)),
                      loss_previsto_ratio=1-math.prod(1-v['loss_ratio'] for v in values),
                      predicciones_enlaces=values)
    return result


def classical_routes(snapshot, request):
    # La referencia valida también la identidad, los extremos y las capacidades.
    conventional(snapshot, request)
    routes, errors = {}, {}
    for criterion in ('hops', 'delay', 'capacity'):
        try:
            if criterion == 'delay':
                active = {e['id'] for e in snapshot['links_runtime'] if e.get('state') == 'up'}
                profile = snapshot['topology_document']['topologies'][snapshot['topologia']]
                for edge in profile['links']:
                    if edge['link_id'] in active:
                        finite(edge.get('configured_delay_ms'))
            args = route_inputs(snapshot, request.topology_instance_id, request.graph_version,
                                request.origen, request.destino, criterion, calcular_costo_capacidad)
            path, cost = calcular_ruta(**args)
            item = summarize(snapshot, path)
            item.update(criterio=criterion, nombre=CRITERIA[criterion][0],
                        unidad_costo=CRITERIA[criterion][1], costo_criterio=finite(cost))
            routes[criterion] = item
        except (ValueError, KeyError, TypeError, OverflowError) as error:
            if criterion != 'delay':
                raise ValueError(str(error)) from error
            routes[criterion] = None
            errors[criterion] = 'No hay retardo configurado válido para calcular este criterio.'
    routes['ml'] = None
    return routes, errors


def route_groups(routes):
    groups = {}
    for key, route in routes.items():
        if route is not None:
            groups.setdefault(tuple(route['ruta']), []).append(key)
    return [{'criterios': keys, 'ruta': list(path)} for path, keys in groups.items()]


def compare_four(snapshot, request, predictions, weights, scales):
    routes, errors = classical_routes(snapshot, request)
    args = route_inputs(snapshot, request.topology_instance_id, request.graph_version,
                        request.origen, request.destino, 'capacity', calcular_costo_capacidad)
    active = {e['id'] for e in snapshot['links_runtime'] if e.get('state') == 'up'}
    profile = snapshot['topology_document']['topologies'][snapshot['topologia']]
    directed, weighted = {}, []
    for edge in profile['links']:
        if edge['link_id'] not in active:
            continue
        p = predictions[edge['link_id']]['predicciones']
        u,v = edge['switch_u'], edge['switch_v']
        for direction,a,b in [('u_to_v',u,v),('v_to_u',v,u)]:
            t,d,l = (p[k] for k in TARGETS[direction])
            cost, components = directional_cost(edge['capacity_mbps'],t,d,l,weights,scales)
            directed[(a,b)] = {'link_id':edge['link_id'], 'origen':a, 'destino':b,
                'direccion':direction, 'throughput_rx_mbps':t, 'delay_ms':d, 'loss_ratio':l,
                'costo_qos':cost, 'componentes':components}
            weighted.append({'origen':a,'destino':b,'costo':cost})
    intelligent_path, intelligent_cost = calcular_ruta(nodos=args['nodos'], enlaces=weighted,
        origen=request.origen,destino=request.destino,dirigido=True)
    for key, route in list(routes.items()):
        if route is not None:
            enriched = summarize(snapshot, route['ruta'], directed)
            enriched.update({k: route[k] for k in ('criterio', 'nombre', 'unidad_costo', 'costo_criterio')})
            routes[key] = enriched
    routes['ml'] = summarize(snapshot, intelligent_path, directed)
    routes['ml'].update(criterio='ml', nombre=CRITERIA['ml'][0],
                        unidad_costo=CRITERIA['ml'][1], costo_criterio=finite(intelligent_cost))
    return routes, errors


def compare(snapshot, request, predictions, weights, scales):
    # Mantiene el contrato anterior para los clientes de dos rutas.
    routes, _ = compare_four(snapshot, request, predictions, weights, scales)
    return routes['capacity'], routes['ml']
