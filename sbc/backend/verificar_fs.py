#!/usr/bin/env python3
"""Verificacion de la frecuencia de muestreo con una senal externa (paso 32).

La Pi genera una onda cuadrada con su PWM por hardware (GPIO18, pin fisico 12), conectada al
GPIO0 (canal 1) del ESP32-C6. Para cada preset se mide la frecuencia de la onda a partir de las
muestras, usando la fs_real que informa el ESP32-C6, y se compara con la frecuencia del PWM.
El reloj del PWM sale del cristal de la Pi, independiente del ESP32-C6.

Requisitos: "dtoverlay=pwm,pin=18,func=2" en /boot/firmware/config.txt y el backend corriendo.
Uso: sudo python3 verificar_fs.py [--ventanas 20]   (sudo: escribir en /sys/class/pwm)
"""

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:5000/api"
PWM = "/sys/class/pwm/pwmchip0"
CANAL = f"{PWM}/pwm0"
# preset -> (fs nominal por canal, frecuencia de prueba): ~12,8 periodos por ventana de 256 muestras
PRUEBAS = {0: (100, 5), 1: (1000, 50), 2: (10000, 500), 3: (40000, 2000)}


def escribir(ruta, valor):
    with open(ruta, "w") as f:
        f.write(str(valor))


def leer(ruta):
    with open(ruta) as f:
        return f.read().strip()


def pwm_configurar(frec_hz):
    """Programa una onda cuadrada (50 %) y devuelve la frecuencia real segun el periodo aceptado."""
    if not os.path.isdir(CANAL):
        escribir(f"{PWM}/export", 0)
        for _ in range(50):
            if os.path.exists(f"{CANAL}/period"):
                break
            time.sleep(0.05)
    periodo = round(1e9 / frec_hz)
    escribir(f"{CANAL}/enable", 0)
    escribir(f"{CANAL}/duty_cycle", 0)
    escribir(f"{CANAL}/period", periodo)
    escribir(f"{CANAL}/duty_cycle", periodo // 2)
    escribir(f"{CANAL}/enable", 1)
    return 1e9 / int(leer(f"{CANAL}/period"))


def api_get(ruta):
    with urllib.request.urlopen(f"{API}/{ruta}", timeout=10) as r:
        return json.load(r)


def api_preset(preset):
    req = urllib.request.Request(f"{API}/preset", data=json.dumps({"preset": preset}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def frecuencia(muestras, fs):
    """Frecuencia de la onda a partir de los flancos de subida (interpolados) de una ventana."""
    if max(muestras) - min(muestras) < 1000:
        return None                                       # no hay una onda en la entrada
    umbral = (max(muestras) + min(muestras)) / 2
    cruces = []
    for i in range(1, len(muestras)):
        a, b = muestras[i - 1], muestras[i]
        if a < umbral <= b:
            cruces.append((i - 1 + (umbral - a) / (b - a)) / fs)
    if len(cruces) < 3:
        return None
    return (len(cruces) - 1) / (cruces[-1] - cruces[0])


def medir(preset, n_ventanas, timeout_s):
    api_preset(preset)
    medidas, ultimo, descartar, fs = [], None, 1, None
    limite = time.monotonic() + timeout_s
    while len(medidas) < n_ventanas:
        if time.monotonic() > limite:
            raise RuntimeError(f"Tiempo agotado esperando ventanas del preset {preset}")
        try:
            v = api_get("window")
        except urllib.error.HTTPError:
            time.sleep(0.2)
            continue
        if v["preset"] != preset or v["numero"] == ultimo:
            time.sleep(0.1)
            continue
        ultimo = v["numero"]
        if descartar:
            descartar -= 1
            continue
        f = frecuencia(v["ch0"], v["fs_real_hz"])
        if f is None:
            raise RuntimeError("No se detecta la onda en el canal 1: revisa el cable del pin 12 al GPIO0")
        medidas.append(f)
        fs = v["fs_real_hz"]
    return medidas, fs


def main():
    parser = argparse.ArgumentParser(description="Verificacion de la frecuencia de muestreo")
    parser.add_argument("--ventanas", type=int, default=20)
    args = parser.parse_args()

    print(f"{args.ventanas} ventanas por preset\n")
    print(f"{'Preset':>6} {'fs_real':>12} {'f PWM':>9} | {'f medida (prom)':>15} {'desv':>8} "
          f"{'error':>8} | {'error con fs nominal':>20}")
    for preset, (fs_nominal, f_prueba) in PRUEBAS.items():
        f_pwm = pwm_configurar(f_prueba)
        medidas, fs = medir(preset, args.ventanas, timeout_s=120)
        prom = statistics.mean(medidas)
        desv = statistics.stdev(medidas)
        error = (prom - f_pwm) / f_pwm * 100
        f_nominal = prom * fs_nominal / fs                # lo que se mediria suponiendo fs nominal
        error_nominal = (f_nominal - f_pwm) / f_pwm * 100
        print(f"{preset:>6} {fs:>9.2f} Hz {f_pwm:>6.0f} Hz | {prom:>12.3f} Hz {desv:>6.3f} "
              f"{error:>+7.3f}% | {error_nominal:>+19.3f}%")

    pwm_configurar(500)
    api_preset(2)
    print("\nPWM en 500 Hz y preset 2: puedes ver la onda en el dashboard.")


if __name__ == "__main__":
    main()
