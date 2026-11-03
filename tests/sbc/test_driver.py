"""Pruebas unitarias del driver SPI (spi_osciloscopio.py) contra el simulador del ESP32-C6."""
import pytest

from spi_osciloscopio import ErrorOsciloscopio
from verificar_fs import frecuencia

FS_REAL = {0: 100.0, 1: 1000.0, 2: 10000.0, 3: 40322.58}


def test_status_inicial(osc):
    st = osc.status()
    assert (st["estado"], st["preset"], st["error"]) == (0, 2, 0)
    assert st["fs_real_hz"] == 10000.0 and st["n_muestras"] == 256


@pytest.mark.parametrize("preset", [0, 1, 2, 3])
def test_set_preset_valido(osc, preset):
    st = osc.set_preset(preset)
    assert st["error"] == 0 and st["preset"] == preset
    assert st["fs_real_hz"] == pytest.approx(FS_REAL[preset], abs=0.01)


def test_set_preset_invalido(osc):
    assert osc.set_preset(9)["error"] == 3


def test_comando_desconocido(osc):
    respuesta, _ = osc._comando(0x7F, 0, 16)
    assert respuesta[3] == 1


def test_read_window_sin_ventana(osc):
    v = osc.read_window()
    assert v["n_muestras"] == 0 and v["ch0"] == [] and v["ch1"] == []


@pytest.mark.parametrize("preset", [0, 1, 2, 3])
def test_capturar_cada_preset(osc, preset):
    osc.set_preset(preset)
    v = osc.capturar()
    assert v["preset"] == preset and v["n_muestras"] == 256
    assert len(v["ch0"]) == 256 and len(v["ch1"]) == 256
    assert all(0 <= x <= 4095 for x in v["ch0"] + v["ch1"])


def test_start_capture_repetido_da_ocupado(osc):
    osc.set_preset(0)                      # la captura mas larga
    assert osc.start_capture()["estado"] == 1
    assert osc.start_capture()["error"] == 2


def test_detecta_checksum_corrupto(osc, sim):
    sim.corromper_proxima_ventana = True
    with pytest.raises(ErrorOsciloscopio, match="Checksum"):
        osc.capturar()


def test_detecta_marca_invalida(osc, sim):
    sim.marca_invalida_proxima = True
    with pytest.raises(ErrorOsciloscopio, match="Marca invalida"):
        osc.status()


def test_reintenta_lecturas_prematuras(osc, sim):
    sim.lecturas_vacias = 3
    assert osc.status()["error"] == 0
    assert osc.reintentos == 3


def test_timeout_si_esp32_desconectado(osc, sim):
    sim.desconectado = True
    with pytest.raises(ErrorOsciloscopio, match="READY"):
        osc.status()


@pytest.mark.parametrize("preset,f_ch0", [(2, 500.0), (3, 2000.0)])
def test_frecuencia_de_la_senal(osc, sim, preset, f_ch0):
    sim.f_ch0 = f_ch0
    osc.set_preset(preset)
    v = osc.capturar()
    assert frecuencia(v["ch0"], v["fs_real_hz"]) == pytest.approx(f_ch0, rel=0.01)
