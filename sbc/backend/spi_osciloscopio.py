#!/usr/bin/env python3
"""Driver SPI (maestro) para el osciloscopio con ESP32-C6.

Implementa el protocolo v1.0 descrito en docs/protocolo-spi.md:
- Cada comando son dos transacciones: el comando (4 bytes) y la respuesta.
- Antes de cada transaccion se espera que la linea READY (GPIO25) este en alto.
- Las respuestas se verifican con la marca 0xA5 y, en la ventana, con el checksum.

Uso como programa de prueba:
    python3 spi_osciloscopio.py            (reloj de 1 MHz)
    python3 spi_osciloscopio.py --hz 4000000
"""

import argparse
import glob
import struct
import time

import gpiod
import spidev
from gpiod.line import Bias, Direction, Value

# ---------- Protocolo v1.0 ----------
MARCA = 0xA5
CMD_SET_PRESET = 0x01
CMD_START_CAPTURE = 0x02
CMD_STATUS = 0x03
CMD_READ_WINDOW = 0x04
TAM_STATUS = 16
TAM_VENTANA = 1036

ESTADOS = {0: "en espera", 1: "capturando", 2: "ventana lista"}
ERRORES = {0: "sin error", 1: "comando desconocido", 2: "ocupado", 3: "argumento invalido"}
PRESETS_SA_S = {0: 100, 1: 1000, 2: 10000, 3: 40000}


class ErrorOsciloscopio(Exception):
    """Error de comunicacion o de protocolo con el ESP32-C6."""


def buscar_chip_gpio():
    """Devuelve la ruta del chip GPIO principal de la Pi (pinctrl-bcm2835 en la Zero 2 W)."""
    for ruta in sorted(glob.glob("/dev/gpiochip*")):
        with gpiod.Chip(ruta) as chip:
            if "bcm2835" in chip.get_info().label:
                return ruta
    raise ErrorOsciloscopio("No se encontro el chip GPIO pinctrl-bcm2835")


class Osciloscopio:
    def __init__(self, bus=0, dispositivo=0, hz=1_000_000, pin_ready=25, timeout_ready=5.0):
        self.pin_ready = pin_ready
        self.timeout_ready = timeout_ready
        self.reintentos = 0          # lecturas prematuras detectadas y repetidas

        self.spi = spidev.SpiDev()
        self.spi.open(bus, dispositivo)          # SPI0, CE0 (GPIO8)
        self.spi.mode = 0
        self.spi.bits_per_word = 8
        self.spi.max_speed_hz = hz

        # READY como entrada con pull-down: si el ESP32-C6 no esta conectado, se lee 0
        self.ready = gpiod.request_lines(
            buscar_chip_gpio(),
            consumer="osciloscopio",
            config={pin_ready: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_DOWN)},
        )

    def cerrar(self):
        self.spi.close()
        self.ready.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cerrar()

    # ---------- Bajo nivel ----------
    def _esperar_ready(self):
        limite = time.monotonic() + self.timeout_ready
        while self.ready.get_value(self.pin_ready) != Value.ACTIVE:
            if time.monotonic() > limite:
                raise ErrorOsciloscopio(
                    f"READY no subio en {self.timeout_ready} s (ESP32-C6 desconectado o sin responder)")
            time.sleep(0.0001)

    def _comando(self, codigo, argumento, tam_respuesta, max_reintentos=20):
        """Envia un comando de 4 bytes y lee la respuesta. Devuelve (bytes, segundos de la respuesta).

        Si la Pi lee antes de que el ESP32-C6 prepare la respuesta, recibe solo ceros. Esa lectura
        no consume nada en el ESP32-C6, asi que se espera un momento y se vuelve a leer.
        """
        self._esperar_ready()
        self.spi.xfer2([codigo, argumento, 0, 0])
        for intento in range(max_reintentos + 1):
            time.sleep(0.0002)                   # da tiempo a que READY baje tras el comando
            self._esperar_ready()
            t0 = time.perf_counter()
            respuesta = bytes(self.spi.xfer2([0] * tam_respuesta))   # xfer2 recibe una lista nueva
            duracion = time.perf_counter() - t0
            if respuesta[0] == MARCA:
                return respuesta, duracion
            if any(respuesta):
                raise ErrorOsciloscopio(
                    f"Marca invalida: 0x{respuesta[0]:02X} (se esperaba 0xA5); datos: {respuesta[:8].hex(' ')}")
            self.reintentos += 1                 # solo ceros: lectura prematura, se repite
            time.sleep(0.001)
        raise ErrorOsciloscopio(f"Respuesta vacia tras {max_reintentos} reintentos")

    # ---------- Comandos ----------
    @staticmethod
    def _decodificar_status(r):
        estado, preset, error = r[1], r[2], r[3]
        fs_mhz, n_muestras, n_ventana = struct.unpack_from("<IHH", r, 4)
        return {
            "estado": estado,
            "estado_texto": ESTADOS.get(estado, "?"),
            "preset": preset,
            "error": error,
            "error_texto": ERRORES.get(error, "?"),
            "fs_real_hz": fs_mhz / 1000.0,
            "n_muestras": n_muestras,
            "n_ventana": n_ventana,
        }

    def status(self):
        r, _ = self._comando(CMD_STATUS, 0, TAM_STATUS)
        return self._decodificar_status(r)

    def set_preset(self, preset):
        r, _ = self._comando(CMD_SET_PRESET, preset, TAM_STATUS)
        return self._decodificar_status(r)

    def start_capture(self):
        r, _ = self._comando(CMD_START_CAPTURE, 0, TAM_STATUS)
        return self._decodificar_status(r)

    def read_window(self):
        r, duracion = self._comando(CMD_READ_WINDOW, 0, TAM_VENTANA)
        checksum_recibido = struct.unpack_from("<I", r, 1032)[0]
        checksum_calculado = sum(r[:1032]) & 0xFFFFFFFF
        if checksum_recibido != checksum_calculado:
            raise ErrorOsciloscopio(
                f"Checksum invalido: recibido {checksum_recibido}, calculado {checksum_calculado}")
        preset, n_muestras, fs_mhz = r[1], *struct.unpack_from("<HI", r, 2)
        return {
            "preset": preset,
            "n_muestras": n_muestras,
            "fs_real_hz": fs_mhz / 1000.0,
            "ch0": list(struct.unpack_from(f"<{n_muestras}H", r, 8)),
            "ch1": list(struct.unpack_from(f"<{n_muestras}H", r, 520)),
            "segundos_transferencia": duracion,
        }

    def capturar(self, timeout=6.0, espera_inicial=0.0, intervalo=0.005):
        """Secuencia completa: START_CAPTURE, esperar ventana lista y READ_WINDOW.

        espera_inicial: segundos sin trafico SPI antes de empezar a consultar STATUS.
        intervalo: segundos entre consultas de STATUS.
        """
        st = self.start_capture()
        if st["error"] != 0:
            raise ErrorOsciloscopio(f"START_CAPTURE rechazado: {st['error_texto']}")
        time.sleep(espera_inicial)
        limite = time.monotonic() + timeout
        while self.status()["estado"] != 2:
            if time.monotonic() > limite:
                raise ErrorOsciloscopio("La ventana no quedo lista a tiempo")
            time.sleep(intervalo)
        return self.read_window()


# ---------- Programa de prueba ----------
def resumir(nombre, datos):
    prom = sum(datos) / len(datos) if datos else 0
    return f"{nombre}: min={min(datos):4d} max={max(datos):4d} prom={prom:7.1f}"


def main():
    parser = argparse.ArgumentParser(description="Prueba del driver SPI del osciloscopio")
    parser.add_argument("--hz", type=int, default=1_000_000, help="reloj SPI en Hz (por defecto 1 MHz)")
    args = parser.parse_args()

    fallas = 0
    with Osciloscopio(hz=args.hz) as osc:
        print(f"Reloj SPI: {args.hz / 1e6:.3f} MHz")
        st = osc.status()
        print(f"STATUS: {st['estado_texto']}, preset {st['preset']}, fs={st['fs_real_hz']:.3f} Hz, "
              f"ventanas={st['n_ventana']}")

        for preset in range(4):
            st = osc.set_preset(preset)
            if st["error"] != 0 or st["preset"] != preset:
                print(f"FALLA: SET_PRESET {preset} -> {st['error_texto']}")
                fallas += 1
                continue
            t0 = time.perf_counter()
            v = osc.capturar()
            total = time.perf_counter() - t0
            kbits = TAM_VENTANA * 8 / v["segundos_transferencia"] / 1000
            print(f"Preset {preset} ({PRESETS_SA_S[preset]} Sa/s): fs_real={v['fs_real_hz']:.3f} Hz, "
                  f"{v['n_muestras']} muestras, ciclo completo {total * 1000:.1f} ms, "
                  f"transferencia {v['segundos_transferencia'] * 1000:.2f} ms ({kbits:.0f} kbit/s)")
            print("   " + resumir("CH0", v["ch0"]) + " | " + resumir("CH1", v["ch1"]))

        reintentos = osc.reintentos
    print(f"Prueba terminada: {fallas} falla(s), {reintentos} reintento(s) por lectura prematura")


if __name__ == "__main__":
    main()
