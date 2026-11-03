#!/usr/bin/env python3
"""Simulador del ESP32-C6 con el protocolo SPI v1.1 (docs/protocolo-spi.md).

Responde byte a byte como el firmware: marca 0xA5, estados, codigos de error, fs real y checksum.
Genera senales de prueba: CH0 cuadrada (500 Hz, 0 a 3.352 cuentas) y CH1 senoidal (50 Hz).
La captura empieza despues de entregar la respuesta de START_CAPTURE, como en el firmware.

activar() reemplaza los modulos spidev y gpiod por versiones falsas conectadas al simulador,
asi el driver real (spi_osciloscopio.py) funciona sin hardware. Usos:
  - Pruebas automaticas: tests/sbc (pytest).
  - Backend sin hardware:  OSC_SIMULADOR=1 python3 sbc/backend/app.py  -> http://127.0.0.1:5000

Inyeccion de fallas (atributos del simulador):
  desconectado, lecturas_vacias, marca_invalida_proxima, corromper_proxima_ventana.
"""

import enum
import math
import random
import struct
import sys
import time
import types

MARCA = 0xA5
TAM_STATUS = 16
TAM_VENTANA = 1036
N_MUESTRAS = 256
FS_REAL_MHZ = {0: 100_000, 1: 1_000_000, 2: 10_000_000, 3: 40_322_580}
ESPERA, CAPTURANDO, LISTA = 0, 1, 2
ERR_OK, ERR_CMD, ERR_OCUPADO, ERR_ARG = 0, 1, 2, 3


class SimuladorESP32:
    def __init__(self, escala_tiempo=1.0, f_ch0=500.0, f_ch1=50.0, ruido=2):
        self.escala_tiempo = escala_tiempo      # < 1 acelera las capturas (pruebas)
        self.f_ch0, self.f_ch1, self.ruido = f_ch0, f_ch1, ruido
        self.preset, self.estado, self.error, self.n_ventana = 2, ESPERA, ERR_OK, 0
        self.ventana = None                     # ultimo paquete de ventana completo
        self.fase_respuesta = False             # False: espera comando; True: respuesta pendiente
        self.respuesta = b""
        self.captura_pendiente = False
        self.fin_captura = 0.0
        self.preset_captura = 2
        self.comandos = []                      # registro de (comando, argumento) recibidos
        # Inyeccion de fallas
        self.desconectado = False
        self.lecturas_vacias = 0
        self.marca_invalida_proxima = False
        self.corromper_proxima_ventana = False

    # ---------- Senales y paquetes ----------
    def _muestras(self, preset):
        fs = FS_REAL_MHZ[preset] / 1000
        t0 = time.monotonic()
        ch0, ch1 = [], []
        for i in range(N_MUESTRAS):
            t = t0 + i / fs
            c0 = 3352 if (t * self.f_ch0) % 1.0 < 0.5 else 0
            c1 = 1676 + 1500 * math.sin(2 * math.pi * self.f_ch1 * t)
            ch0.append(min(4095, max(0, int(c0 + random.randint(-self.ruido, self.ruido)))))
            ch1.append(min(4095, max(0, int(c1 + random.randint(-self.ruido, self.ruido)))))
        return ch0, ch1

    def _armar_ventana(self, preset, n):
        p = bytearray(TAM_VENTANA)
        p[0], p[1] = MARCA, preset
        struct.pack_into("<HI", p, 2, n, FS_REAL_MHZ[preset])
        if n:
            ch0, ch1 = self._muestras(preset)
            struct.pack_into(f"<{N_MUESTRAS}H", p, 8, *ch0)
            struct.pack_into(f"<{N_MUESTRAS}H", p, 520, *ch1)
        struct.pack_into("<I", p, 1032, sum(p[:1032]) & 0xFFFFFFFF)
        return bytes(p)

    def _actualizar(self):
        if self.estado == CAPTURANDO and not self.captura_pendiente and time.monotonic() >= self.fin_captura:
            self.ventana = self._armar_ventana(self.preset_captura, N_MUESTRAS)
            self.n_ventana = (self.n_ventana + 1) & 0xFFFF
            self.estado = LISTA

    def _status(self):
        r = bytearray(TAM_STATUS)
        r[0], r[1], r[2], r[3] = MARCA, self.estado, self.preset, self.error
        struct.pack_into("<IHH", r, 4, FS_REAL_MHZ[self.preset], N_MUESTRAS, self.n_ventana)
        return bytes(r)

    # ---------- Protocolo ----------
    def procesar(self, cmd, arg):
        self._actualizar()
        self.comandos.append((cmd, arg))
        if cmd == 0x01:                                         # SET_PRESET
            if self.estado == CAPTURANDO:
                self.error = ERR_OCUPADO
            elif arg not in FS_REAL_MHZ:
                self.error = ERR_ARG
            else:
                self.preset, self.error = arg, ERR_OK
        elif cmd == 0x02:                                       # START_CAPTURE
            if self.estado == CAPTURANDO:
                self.error = ERR_OCUPADO
            else:
                self.ventana, self.estado, self.error = None, CAPTURANDO, ERR_OK
                self.captura_pendiente = True
        elif cmd == 0x03:                                       # STATUS
            self.error = ERR_OK
        elif cmd == 0x04:                                       # READ_WINDOW
            self.error = ERR_OK
            v = self.ventana if self.ventana else self._armar_ventana(self.preset, 0)
            if self.corromper_proxima_ventana:
                v = bytearray(v)
                v[100] ^= 0xFF                                  # dato alterado; el checksum ya no coincide
                v = bytes(v)
                self.corromper_proxima_ventana = False
            return v
        else:
            self.error = ERR_CMD
        return self._status()

    def ready(self):
        return not self.desconectado

    def transaccion(self, mosi):
        """Una transaccion SPI completa: recibe los bytes de MOSI y devuelve los de MISO."""
        n = len(mosi)
        if not self.fase_respuesta:                             # fase 1: comando
            resp = self.procesar(mosi[0], mosi[1] if n > 1 else 0)
            if self.marca_invalida_proxima:
                resp = bytes([0x5A]) + resp[1:]
                self.marca_invalida_proxima = False
            self.respuesta, self.fase_respuesta = resp, True
            return [0] * n
        if self.lecturas_vacias > 0:                            # lectura prematura: no consume nada
            self.lecturas_vacias -= 1
            return [0] * n
        datos = list(self.respuesta[:n]) + [0] * max(0, n - len(self.respuesta))
        self.fase_respuesta = False                             # fase 2: respuesta entregada
        if self.captura_pendiente:                              # la captura empieza despues de responder
            self.captura_pendiente = False
            self.preset_captura = self.preset
            duracion = N_MUESTRAS / (FS_REAL_MHZ[self.preset] / 1000)
            self.fin_captura = time.monotonic() + duracion * self.escala_tiempo
        return datos


# ---------- Modulos falsos de spidev y gpiod ----------
_sim = None


def usar(simulador):
    """Conecta los modulos falsos a este simulador."""
    global _sim
    _sim = simulador


def simulador_actual():
    global _sim
    if _sim is None:
        _sim = SimuladorESP32()
    return _sim


class _SpiDevFalso:
    def __init__(self):
        self.mode, self.bits_per_word, self.max_speed_hz = 0, 8, 500_000

    def open(self, bus, dispositivo):
        pass

    def close(self):
        pass

    def xfer2(self, datos):
        return simulador_actual().transaccion(list(datos))


class _Value(enum.Enum):
    INACTIVE = 0
    ACTIVE = 1


class _Direction(enum.Enum):
    INPUT = 0
    OUTPUT = 1


class _Bias(enum.Enum):
    DISABLED = 0
    PULL_UP = 1
    PULL_DOWN = 2


class _Edge(enum.Enum):
    NONE = 0
    RISING = 1


class _LineSettings:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _SolicitudFalsa:
    def get_value(self, pin):
        return _Value.ACTIVE if simulador_actual().ready() else _Value.INACTIVE

    def release(self):
        pass


def _request_lines(ruta, consumer=None, config=None):
    return _SolicitudFalsa()


def activar():
    """Instala spidev y gpiod falsos y conecta el driver al simulador (se puede llamar varias veces)."""
    if getattr(sys.modules.get("spidev"), "_simulado", False):
        return
    spidev = types.ModuleType("spidev")
    spidev.SpiDev, spidev._simulado = _SpiDevFalso, True
    linea = types.ModuleType("gpiod.line")
    linea.Value, linea.Direction, linea.Bias, linea.Edge = _Value, _Direction, _Bias, _Edge
    gpiod = types.ModuleType("gpiod")
    gpiod.request_lines, gpiod.LineSettings, gpiod.line = _request_lines, _LineSettings, linea
    sys.modules.update({"spidev": spidev, "gpiod": gpiod, "gpiod.line": linea})
    import spi_osciloscopio
    spi_osciloscopio.buscar_chip_gpio = lambda: "/dev/gpiochip-simulado"
