#!/usr/bin/env python3
"""Barrido de velocidades del SPI: mide la tasa efectiva y los errores a cada frecuencia de reloj.

Para cada frecuencia captura N ventanas con el preset 2 y cuenta los errores por tipo.
Calcula la frecuencia real que genera la Pi: SCLK = core / CDIV, con CDIV par
(BCM2835 ARM Peripherals, registro CLK del SPI; mismo calculo que el driver spi-bcm2835 de Linux).

Uso: python3 barrido_spi.py [--ventanas 100]
"""

import argparse
import subprocess
import time

from spi_osciloscopio import ErrorOsciloscopio, Osciloscopio

FRECUENCIAS_MHZ = [1, 2, 4, 8, 10, 16, 20, 25, 32, 40]


def core_clock_hz():
    salida = subprocess.run(["vcgencmd", "measure_clock", "core"],
                            capture_output=True, text=True, check=True).stdout
    return int(salida.strip().split("=")[1])          # "frequency(1)=400000000"


def sclk_real(core_hz, pedido_hz):
    cdiv = -(-core_hz // pedido_hz)                     # division hacia arriba
    if cdiv % 2:
        cdiv += 1                                       # el divisor debe ser par
    return core_hz / cdiv, cdiv


def probar(hz, n_ventanas):
    r = {"ok": 0, "marca": 0, "checksum": 0, "timeout": 0, "otro": 0,
         "kbits": [], "reintentos": 0}
    with Osciloscopio(hz=hz) as osc:
        osc.set_preset(2)
        for _ in range(n_ventanas):
            try:
                v = osc.capturar()
                r["ok"] += 1
                r["kbits"].append(1036 * 8 / v["segundos_transferencia"] / 1000)
            except ErrorOsciloscopio as e:
                texto = str(e)
                if "Marca" in texto:
                    r["marca"] += 1
                elif "Checksum" in texto:
                    r["checksum"] += 1
                elif "READY" in texto or "a tiempo" in texto or "vacia" in texto:
                    r["timeout"] += 1
                    break                               # posible desincronizacion: no seguir a esta frecuencia
                else:
                    r["otro"] += 1
        r["reintentos"] = osc.reintentos
    return r


def main():
    parser = argparse.ArgumentParser(description="Barrido de velocidades del SPI")
    parser.add_argument("--ventanas", type=int, default=100)
    args = parser.parse_args()

    core = core_clock_hz()
    print(f"Core clock de la Pi: {core / 1e6:.1f} MHz -> SCLK maximo teorico (CDIV=2): {core / 2e6:.1f} MHz")
    print(f"{args.ventanas} ventanas por frecuencia (preset 2)\n")
    print(f"{'Pedido':>7} {'Real':>8} {'CDIV':>5} | {'OK':>4} {'Marca':>5} {'Chksum':>6} {'Timeout':>7} "
          f"{'Reint':>5} | {'kbit/s prom':>11} {'Eficiencia':>10}")
    for mhz in FRECUENCIAS_MHZ:
        pedido = mhz * 1_000_000
        real, cdiv = sclk_real(core, pedido)
        r = probar(pedido, args.ventanas)
        prom = sum(r["kbits"]) / len(r["kbits"]) if r["kbits"] else 0
        efic = prom / (real / 1000) * 100 if prom else 0
        print(f"{mhz:>5} M {real / 1e6:>6.2f} M {cdiv:>5} | {r['ok']:>4} {r['marca']:>5} {r['checksum']:>6} "
              f"{r['timeout']:>7} {r['reintentos']:>5} | {prom:>11.0f} {efic:>9.1f}%")
        if r["timeout"]:
            print("        (timeout: posible desincronizacion; reinicia el ESP32-C6 antes de seguir)")
            break


if __name__ == "__main__":
    main()
