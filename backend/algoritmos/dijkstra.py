import math
import networkx as nx


def calcular_ruta(nodos, enlaces, origen, destino, dirigido=False):

    # Validar nodos
    if not nodos:
        raise ValueError("La topologia no contiene nodos")

    if len(set(nodos)) != len(nodos):
        raise ValueError("Existen nodos duplicados")

    if origen not in nodos:
        raise ValueError(f"El nodo origen {origen} no existe")

    if destino not in nodos:
        raise ValueError(f"El nodo destino {destino} no existe")

    # Crear grafo
    grafo = nx.DiGraph() if dirigido else nx.Graph()
    grafo.add_nodes_from(nodos)

    enlaces_registrados = set()

    # Incorporar enlaces y sus costos
    for enlace in enlaces:

        a = enlace["origen"]
        b = enlace["destino"]
        costo = float(enlace["costo"])

        if a not in nodos or b not in nodos:
            raise ValueError(
                f"El enlace {a}-{b} contiene nodos inexistentes"
            )

        if a == b:
            raise ValueError("No se permiten enlaces de un nodo consigo mismo")

        if not math.isfinite(costo) or costo < 0:
            raise ValueError("El costo debe ser finito y no negativo")

        clave = (a, b) if dirigido else tuple(sorted((a, b)))

        if clave in enlaces_registrados:
            raise ValueError(f"El enlace {a}-{b} esta duplicado")

        enlaces_registrados.add(clave)

        grafo.add_edge(a, b, weight=costo)

    # Calcular ruta minima
    try:
        ruta = nx.dijkstra_path(
            grafo,
            origen,
            destino,
            weight="weight"
        )

        costo_total = nx.dijkstra_path_length(
            grafo,
            origen,
            destino,
            weight="weight"
        )

    except nx.NetworkXNoPath:
        raise ValueError("No existe una ruta entre el origen y el destino")

    return ruta, costo_total

