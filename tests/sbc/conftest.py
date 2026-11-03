"""Configuracion comun de las pruebas de la SBC: usan el simulador del ESP32-C6, sin hardware."""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "sbc" / "backend"))

import simulador_esp32  # noqa: E402

simulador_esp32.activar()
import spi_osciloscopio  # noqa: E402


@pytest.fixture
def sim():
    """Un simulador nuevo por prueba, con las capturas aceleradas 20 veces."""
    s = simulador_esp32.SimuladorESP32(escala_tiempo=0.05)
    simulador_esp32.usar(s)
    return s


@pytest.fixture
def osc(sim):
    o = spi_osciloscopio.Osciloscopio(hz=10_000_000, timeout_ready=0.3)
    yield o
    o.cerrar()
