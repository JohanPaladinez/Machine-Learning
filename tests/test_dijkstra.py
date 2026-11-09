import pytest

from backend.algoritmos.dijkstra import calcular_ruta


def test_ruta_minima():

    nodos = ["A", "B", "C", "D"]

    enlaces = [
        {"origen": "A", "destino": "B", "costo": 2},
        {"origen": "A", "destino": "C", "costo": 5},
        {"origen": "B", "destino": "C", "costo": 1},
        {"origen": "B", "destino": "D", "costo": 4},
        {"origen": "C", "destino": "D", "costo": 2}
    ]

    ruta, costo = calcular_ruta(
        nodos, enlaces, "A", "D"
    )

    assert ruta == ["A", "B", "C", "D"]
    assert costo == 5


def test_destino_sin_conexion():

    nodos = ["A", "B", "C"]

    enlaces = [
        {"origen": "A", "destino": "B", "costo": 2}
    ]

    with pytest.raises(ValueError):
        calcular_ruta(nodos, enlaces, "A", "C")


def test_costo_negativo():

    nodos = ["A", "B"]

    enlaces = [
        {"origen": "A", "destino": "B", "costo": -5}
    ]

    with pytest.raises(ValueError):
        calcular_ruta(nodos, enlaces, "A", "B")


def test_nodo_inexistente():

    nodos = ["A", "B"]

    with pytest.raises(ValueError):
        calcular_ruta(nodos, [], "A", "C")


def test_grafo_dirigido():

    nodos = ["A", "B"]

    enlaces = [
        {"origen": "A", "destino": "B", "costo": 3}
    ]

    with pytest.raises(ValueError):
        calcular_ruta(
            nodos, enlaces, "B", "A", dirigido=True
        )

