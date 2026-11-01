#!/usr/bin/env python3
"""Backend HTTP del osciloscopio (Flask).

Un hilo de adquisicion es el unico que usa el SPI: captura ventanas continuamente con el
preset pedido (como maximo 4 por segundo) y guarda la ultima en memoria. Los endpoints
solo leen esa ventana o piden un cambio de preset.

API:
    GET  /api/status   -> estado del backend y de la adquisicion
    GET  /api/window   -> ultima ventana (cuentas y voltios)
    POST /api/preset   -> {"preset": 0..3}

Uso: python3 app.py   (escucha en 127.0.0.1:5000; nginx lo publica en /api/)
"""

import logging
import threading
import time

from flask import Flask, jsonify, request

from spi_osciloscopio import PRESETS_SA_S, ErrorOsciloscopio, Osciloscopio

SPI_HZ = 10_000_000              # reloj de trabajo (limite medido sin errores: 25 MHz)
PERIODO_MIN_S = 0.25             # como maximo 4 ventanas por segundo
MV_POR_CUENTA = 3333 / 3352      # aproximacion lineal medida: 3.352 cuentas ~ 3.333 mV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("osciloscopio")


class Adquisicion(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.lock = threading.Lock()
        self.preset_pedido = 2
        self.preset_actual = None
        self.ultima = None
        self.n_ventanas = 0
        self.errores = 0
        self.ultimo_error = None

    def run(self):
        while True:
            try:
                with Osciloscopio(hz=SPI_HZ) as osc:
                    log.info("SPI abierto a %.1f MHz", SPI_HZ / 1e6)
                    self.preset_actual = None
                    while True:
                        t0 = time.monotonic()
                        pedido = self.preset_pedido
                        if pedido != self.preset_actual:
                            st = osc.set_preset(pedido)
                            if st["error"] != 0:
                                raise ErrorOsciloscopio(f"SET_PRESET {pedido} rechazado: {st['error_texto']}")
                            self.preset_actual = pedido
                            log.info("Preset %d (%d Sa/s)", pedido, PRESETS_SA_S[pedido])
                        v = osc.capturar()
                        ventana = {
                            "numero": self.n_ventanas + 1,
                            "timestamp": time.time(),
                            "preset": v["preset"],
                            "fs_real_hz": v["fs_real_hz"],
                            "n_muestras": v["n_muestras"],
                            "ch0": v["ch0"],
                            "ch1": v["ch1"],
                            "ch0_v": [round(c * MV_POR_CUENTA / 1000, 4) for c in v["ch0"]],
                            "ch1_v": [round(c * MV_POR_CUENTA / 1000, 4) for c in v["ch1"]],
                        }
                        with self.lock:
                            self.ultima = ventana
                            self.n_ventanas += 1
                            self.ultimo_error = None
                        espera = PERIODO_MIN_S - (time.monotonic() - t0)
                        if espera > 0:
                            time.sleep(espera)
            except ErrorOsciloscopio as e:
                self.errores += 1
                self.ultimo_error = str(e)
                log.warning("Error de comunicacion: %s (se reintenta en 1 s)", e)
                time.sleep(1.0)


app = Flask(__name__)
adq = Adquisicion()


@app.get("/api/status")
def api_status():
    return jsonify({
        "preset_pedido": adq.preset_pedido,
        "preset_actual": adq.preset_actual,
        "presets_sa_s": PRESETS_SA_S,
        "n_ventanas": adq.n_ventanas,
        "errores": adq.errores,
        "ultimo_error": adq.ultimo_error,
        "spi_hz": SPI_HZ,
    })


@app.get("/api/window")
def api_window():
    with adq.lock:
        ventana = adq.ultima
    if ventana is None:
        return jsonify({"error": "todavia no hay ventanas"}), 503
    return jsonify(ventana)


@app.post("/api/preset")
def api_preset():
    datos = request.get_json(silent=True) or {}
    preset = datos.get("preset")
    if not isinstance(preset, int) or preset not in PRESETS_SA_S:
        return jsonify({"error": "preset debe ser un entero de 0 a 3"}), 400
    adq.preset_pedido = preset
    return jsonify({"ok": True, "preset_pedido": preset, "sa_s": PRESETS_SA_S[preset]})


if __name__ == "__main__":
    adq.start()
    app.run(host="127.0.0.1", port=5000, threaded=True)
