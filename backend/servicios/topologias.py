import math


def validar_topologia(nodos, enlaces, dirigido=False):

    if not nodos:
        raise ValueError("La topologia debe tener nodos")

    if any(not isinstance(n, str) or not n.strip() for n in nodos):
        raise ValueError("Todos los nodos deben tener identificadores validos")

    if len(nodos) != len(set(nodos)):
        raise ValueError("La topologia contiene nodos duplicados")

    conjunto_nodos = set(nodos)
    enlaces_registrados = set()
    enlaces_con_capacidad = 0

    for enlace in enlaces:

        origen = enlace.get("origen")
        destino = enlace.get("destino")

        if origen not in conjunto_nodos or destino not in conjunto_nodos:
            raise ValueError(
                f"El enlace {origen}-{destino} contiene nodos inexistentes"
            )

        if origen == destino:
            raise ValueError("No se permiten enlaces de un nodo consigo mismo")

        clave = (
            (origen, destino)
            if dirigido
            else tuple(sorted((origen, destino)))
        )

        if clave in enlaces_registrados:
            raise ValueError(f"El enlace {origen}-{destino} esta duplicado")

        enlaces_registrados.add(clave)

        capacidad = enlace.get("capacidad_mbps")

        if capacidad is not None:

            capacidad = float(capacidad)

            if not math.isfinite(capacidad) or capacidad <= 0:
                raise ValueError("La capacidad debe ser positiva y finita")

            enlaces_con_capacidad += 1

    return {
        "cantidad_nodos": len(nodos),
        "cantidad_enlaces": len(enlaces),
        "dirigido": dirigido,
        "enlaces_con_capacidad": enlaces_con_capacidad,
        "enlaces_sin_capacidad": len(enlaces) - enlaces_con_capacidad
    }

