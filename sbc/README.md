# Software de la Raspberry Pi (SBC)

Software de la Raspberry Pi Zero 2 W: driver SPI maestro y, más adelante, el backend HTTP y el dashboard.

## Requisitos en la Pi

- Raspberry Pi OS (Debian 13) con SPI0 activado (`sudo raspi-config nonint do_spi 0`): deben existir `/dev/spidev0.0` y `/dev/spidev0.1`.
- Paquetes: `python3-spidev` y `python3-libgpiod` (versión 2 de la librería `gpiod`).
- Cableado y protocolo: ver `docs/protocolo-spi.md`.

## Driver SPI: `backend/spi_osciloscopio.py`

Implementa el protocolo v1.0 como maestro. La clase `Osciloscopio` tiene un método por comando (`status()`, `set_preset()`, `start_capture()`, `read_window()`) y `capturar()`, que hace la secuencia completa: START_CAPTURE, esperar la ventana y READ_WINDOW. Lee la línea READY (GPIO25) con `gpiod` y verifica la marca 0xA5 y el checksum de cada respuesta.

Programa de prueba (recorre los 4 presets):

```bash
python3 sbc/backend/spi_osciloscopio.py            # reloj de 1 MHz
python3 sbc/backend/spi_osciloscopio.py --hz 4000000
```

Antes de cada prueba conviene reiniciar el ESP32-C6, por si quedó con una respuesta pendiente de una ejecución anterior.

### Sincronización con READY

Cada comando usa dos transacciones: el comando (4 bytes) y la respuesta. Durante el desarrollo, la Pi a veces leía la respuesta **antes** de que el ESP32-C6 la preparara y recibía solo ceros. Ocurría porque, justo después del comando, READY todavía puede estar en 1 unos microsegundos. Se probó esperar un flanco de subida de READY, pero también fallaba, porque el kernel puede registrar tarde el flanco de la fase anterior. La solución adoptada:

1. Después de enviar el comando, la Pi hace una pausa de 0,2 ms para que READY alcance a bajar, y luego espera READY = 1.
2. Si aun así la respuesta llega toda en ceros (lectura prematura, que no consume nada en el ESP32-C6), la Pi espera 1 ms y vuelve a leer, hasta 20 veces. El driver cuenta estos reintentos.

## Prueba de integración (2026-10-31)

Montaje: la Pi y el ESP32-C6 conectados según `docs/protocolo-spi.md` (6 cables), reloj SPI de 1 MHz, GPIO0 del ESP32-C6 a 3V3 y GPIO1 a GND.

| Preset | fs_real | Ciclo completo | Transferencia de la ventana | CH0 (3V3): min / max / prom | CH1 (GND): min / max / prom |
|---|---|---|---|---|---|
| 0 (100 Sa/s) | 100,000 Hz | 2.580,7 ms | 8,55 ms (969 kbit/s) | 3.351 / 3.356 / 3.352,9 | 0 / 11 / 1,0 |
| 1 (1.000 Sa/s) | 1.000,000 Hz | 273,8 ms | 8,55 ms (969 kbit/s) | 3.348 / 3.357 / 3.352,7 | 0 / 4 / 0,9 |
| 2 (10.000 Sa/s) | 10.000,000 Hz | 40,6 ms | 8,55 ms (969 kbit/s) | 3.325 / 3.357 / 3.352,0 | 0 / 3 / 0,8 |
| 3 (40.000 Sa/s) | 40.322,580 Hz | 22,7 ms | 8,55 ms (970 kbit/s) | 3.346 / 3.357 / 3.350,7 | 0 / 7 / 0,4 |

**Resultado:** 0 fallas y 0 reintentos. Las 4 ventanas llegaron con checksum válido.

### Observaciones

- A 1 MHz, la transferencia de la ventana (1.036 bytes) alcanza 969 kbit/s, el 97 % del máximo teórico de 1.000 kbit/s.
- El ciclo completo es más largo que la captura por la transferencia y por el tiempo que el ESP32-C6 dedica a imprimir cada comando en el monitor serie.
- Aparecieron valores aislados fuera del ruido habitual (±4 cuentas sin la Pi): CH0 llegó a 3.325 en el preset 2 y CH1 a 11 en el preset 0. Es posible que la actividad del SPI durante la captura (consultas de STATUS cada 5 ms) induzca algo de ruido en el ADC. Queda pendiente investigarlo.
