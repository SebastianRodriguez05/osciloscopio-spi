#!/usr/bin/env python3
"""V3: compara el ruido del ADC con y sin trafico SPI durante la captura.

Modo "rapido": la Pi consulta STATUS cada 5 ms mientras el ESP32-C6 captura (como el backend).
Modo "silencio": la Pi espera 1,5 veces la duracion de la ventana antes de consultar,
asi que no hay trafico SPI durante la captura.
Se mide el ruido en CH1 (GPIO1 a GND con un jumper local del ESP32-C6).

Uso (el backend debe estar detenido, porque usa el SPI):
    sudo systemctl stop osciloscopio-backend
    python3 ruido_spi.py
    sudo systemctl start osciloscopio-backend
"""

import statistics

from spi_osciloscopio import Osciloscopio

N_VENTANAS = 50
DURACION_S = {2: 256 / 10000, 3: 256 / 40322.58}       # duracion de una ventana por preset
UMBRAL = 5                                              # cuentas consideradas "fuera de lo normal" en GND


def medir(osc, preset, espera_inicial):
    maximos, desviaciones, fuera, rango_ch0 = [], [], 0, [4095, 0]
    for _ in range(N_VENTANAS):
        v = osc.capturar(espera_inicial=espera_inicial)
        ch1, ch0 = v["ch1"], v["ch0"]
        maximos.append(max(ch1))
        desviaciones.append(statistics.pstdev(ch1))
        fuera += sum(1 for x in ch1 if x > UMBRAL)
        rango_ch0 = [min(rango_ch0[0], min(ch0)), max(rango_ch0[1], max(ch0))]
    return max(maximos), statistics.mean(desviaciones), fuera, rango_ch0


def main():
    print(f"{N_VENTANAS} ventanas por modo; ruido en CH1 (GND). Umbral: > {UMBRAL} cuentas\n")
    print(f"{'Preset':>6} {'Modo':>9} | {'CH1 max':>7} {'CH1 desv prom':>13} {'Muestras >5':>11} | {'CH0 min-max':>12}")
    with Osciloscopio(hz=10_000_000) as osc:
        for preset in (2, 3):
            osc.set_preset(preset)
            for modo, espera in (("rapido", 0.0), ("silencio", DURACION_S[preset] * 1.5)):
                mx, desv, fuera, r0 = medir(osc, preset, espera)
                print(f"{preset:>6} {modo:>9} | {mx:>7} {desv:>13.2f} {fuera:>11} | {r0[0]:>5}-{r0[1]:<5}")


if __name__ == "__main__":
    main()
