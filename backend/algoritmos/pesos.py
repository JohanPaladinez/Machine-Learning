import math


def calcular_costo_capacidad(capacidad_mbps):

    capacidad = float(capacidad_mbps)

    if not math.isfinite(capacidad) or capacidad <= 0:
        raise ValueError(
            "La capacidad debe ser positiva y finita"
        )

    return 1.0 / capacidad

