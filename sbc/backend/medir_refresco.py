#!/usr/bin/env python3
"""Medicion del periodo de refresco del dashboard (requerimiento: entre 0,25 y 1 Hz).

nginx registra cada peticion a /api/ con la hora en milisegundos en
/var/log/nginx/osciloscopio-api.log. Para cada valor del selector de refresco (1, 2, 3 y 4 s)
el programa mide durante DURACION segundos y calcula los intervalos entre peticiones
consecutivas a /api/window del navegador que mas peticiones hizo.

Uso: sudo python3 medir_refresco.py      (sudo: leer el registro de nginx)
Durante la prueba debe haber UNA sola pestana del dashboard abierta y visible
(los navegadores frenan los temporizadores de las pestanas en segundo plano).
"""

import collections
import statistics
import time

LOG = "/var/log/nginx/osciloscopio-api.log"
DURACION = 30          # segundos de medicion por cada valor de refresco
ESTABILIZACION = 3     # segundos que se ignoran al inicio de cada medicion


def peticiones_window(t_ini, t_fin):
    """Devuelve {ip: [tiempos]} de las peticiones GET /api/window entre t_ini y t_fin."""
    por_ip = collections.defaultdict(list)
    with open(LOG) as f:
        for linea in f:
            partes = linea.split()
            if len(partes) < 4 or "/api/window" not in linea:
                continue
            t = float(partes[0])
            if t_ini <= t <= t_fin:
                por_ip[partes[1]].append(t)
    return por_ip


def main():
    filas = []
    print(f"Medicion del refresco: {DURACION} s por cada valor. Deja UNA pestana del dashboard visible.\n")
    for periodo in (1, 2, 3, 4):
        input(f"Selecciona 'Refresco = {periodo} s' en el dashboard y presiona Enter aqui... ")
        t_ini = time.time() + ESTABILIZACION
        time.sleep(ESTABILIZACION + DURACION)
        por_ip = peticiones_window(t_ini, time.time())
        if not por_ip:
            print("  No se registraron peticiones: el dashboard esta abierto y sin pausa?\n")
            filas.append((periodo, None))
            continue
        ip, tiempos = max(por_ip.items(), key=lambda kv: len(kv[1]))
        intervalos = [b - a for a, b in zip(tiempos, tiempos[1:])]
        if len(intervalos) < 2:
            print("  Muy pocas peticiones para calcular intervalos.\n")
            filas.append((periodo, None))
            continue
        prom = statistics.mean(intervalos)
        r = (len(intervalos), prom, min(intervalos), max(intervalos), statistics.stdev(intervalos), 1 / prom, ip)
        filas.append((periodo, r))
        print(f"  {len(intervalos)} intervalos desde {ip}: promedio {prom:.3f} s\n")

    print(f"{'Refresco':>8} | {'N':>3} {'Prom (s)':>9} {'Min (s)':>8} {'Max (s)':>8} {'Desv (s)':>9} | "
          f"{'Frecuencia':>10} {'Cumple 0,25-1 Hz':>17}")
    for periodo, r in filas:
        if r is None:
            print(f"{periodo:>6} s | sin datos")
            continue
        n, prom, mn, mx, desv, frec, _ = r
        cumple = "SI" if 0.25 * 0.99 <= frec <= 1.0 * 1.01 else "NO"
        print(f"{periodo:>6} s | {n:>3} {prom:>9.3f} {mn:>8.3f} {mx:>8.3f} {desv:>9.3f} | "
              f"{frec:>7.3f} Hz {cumple:>17}")


if __name__ == "__main__":
    main()
