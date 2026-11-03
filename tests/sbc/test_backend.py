"""Pruebas de la API HTTP (app.py) con el backend real corriendo contra el simulador."""
import os
import time

import pytest

os.environ["OSC_SIMULADOR"] = "1"
import app as backend  # noqa: E402
import simulador_esp32  # noqa: E402


def esperar(condicion, timeout=5.0):
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture(scope="module")
def cliente():
    return backend.app.test_client()


def test_window_503_antes_de_capturar(cliente):
    # Debe ejecutarse antes de arrancar el hilo de adquisicion
    assert cliente.get("/api/window").status_code == 503


@pytest.fixture(scope="module")
def adquisicion(cliente):
    simulador_esp32.usar(simulador_esp32.SimuladorESP32())
    backend.adq.start()
    assert esperar(lambda: backend.adq.n_ventanas > 0), "el backend no capturo ninguna ventana"
    yield backend.adq
    backend.adq.detener.set()
    backend.adq.join(timeout=5)


def test_status(cliente, adquisicion):
    r = cliente.get("/api/status")
    assert r.status_code == 200
    d = r.get_json()
    assert d["preset_actual"] == 2 and d["errores"] == 0 and d["ultimo_error"] is None
    assert d["presets_sa_s"] == {"0": 100, "1": 1000, "2": 10000, "3": 40000}


def test_window(cliente, adquisicion):
    d = cliente.get("/api/window").get_json()
    assert d["n_muestras"] == 256 and d["fs_real_hz"] == 10000.0
    assert len(d["ch0_v"]) == 256 and len(d["ch1_v"]) == 256
    assert all(0.0 <= v <= 4.1 for v in d["ch0_v"] + d["ch1_v"])
    assert max(d["ch0_v"]) > 3.0                     # la senal cuadrada llega a ~3,33 V


def test_cambio_de_preset(cliente, adquisicion):
    r = cliente.post("/api/preset", json={"preset": 1})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert esperar(lambda: adquisicion.ultima and adquisicion.ultima["preset"] == 1)
    assert cliente.get("/api/window").get_json()["fs_real_hz"] == 1000.0


@pytest.mark.parametrize("cuerpo", [{"preset": 7}, {"preset": "2"}, {}, None])
def test_preset_invalido(cliente, cuerpo):
    r = cliente.post("/api/preset", json=cuerpo) if cuerpo is not None else cliente.post("/api/preset")
    assert r.status_code == 400


def test_dashboard_se_sirve(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and b"Osciloscopio" in r.data
