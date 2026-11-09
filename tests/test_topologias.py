import pytest

from backend.servicios.topologias import validar_topologia


def test_topologia_valida():

    resultado = validar_topologia(
        ["A", "B", "C"],
        [
            {"origen": "A", "destino": "B", "capacidad_mbps": 100},
            {"origen": "B", "destino": "C"}
        ]
    )

    assert resultado["cantidad_nodos"] == 3
    assert resultado["cantidad_enlaces"] == 2
    assert resultado["enlaces_con_capacidad"] == 1


def test_nodos_duplicados():

    with pytest.raises(ValueError):
        validar_topologia(["A", "A"], [])


def test_nodo_inexistente():

    with pytest.raises(ValueError):
        validar_topologia(
            ["A", "B"],
            [{"origen": "A", "destino": "C"}]
        )


def test_enlace_duplicado():

    with pytest.raises(ValueError):
        validar_topologia(
            ["A", "B"],
            [
                {"origen": "A", "destino": "B"},
                {"origen": "B", "destino": "A"}
            ]
        )


def test_capacidad_invalida():

    with pytest.raises(ValueError):
        validar_topologia(
            ["A", "B"],
            [{"origen": "A", "destino": "B", "capacidad_mbps": 0}]
        )

