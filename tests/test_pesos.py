import pytest

from backend.algoritmos.pesos import calcular_costo_capacidad


def test_capacidad_100_mbps():
    assert calcular_costo_capacidad(100) == pytest.approx(0.01)


def test_capacidad_1000_mbps():
    assert calcular_costo_capacidad(1000) == pytest.approx(0.001)


def test_capacidad_cero():
    with pytest.raises(ValueError):
        calcular_costo_capacidad(0)


def test_capacidad_negativa():
    with pytest.raises(ValueError):
        calcular_costo_capacidad(-100)


def test_capacidad_infinita():
    with pytest.raises(ValueError):
        calcular_costo_capacidad(float("inf"))

