# API HTTP del osciloscopio

Versión 1.0 (2026-10-31). Contrato entre el backend de la Raspberry Pi (`sbc/backend/app.py`) y el dashboard web.

## Arquitectura

Un **hilo de adquisición** dentro del backend es el único que usa el SPI. Captura ventanas continuamente con el preset pedido, como máximo **4 por segundo** (una cada 0,25 s), y guarda la última en memoria. Los endpoints solo leen esa última ventana o piden un cambio de preset, que se aplica antes de la siguiente captura. Así, varios navegadores pueden consultar a la vez sin chocar en el bus SPI.

Si hay un error de comunicación, el hilo lo registra, espera 1 s y reabre el SPI; el servidor no se cae.

- El backend escucha en `127.0.0.1:5000`. Desde la red se accede a través de nginx, en la ruta `/api/`.
- Reloj SPI: 10 MHz.

## Endpoints

### `GET /api/status`

Estado del backend y de la adquisición.

```json
{
  "preset_pedido": 2,
  "preset_actual": 2,
  "presets_sa_s": {"0": 100, "1": 1000, "2": 10000, "3": 40000},
  "n_ventanas": 438,
  "errores": 0,
  "ultimo_error": null,
  "spi_hz": 10000000
}
```

| Campo | Descripción |
|---|---|
| `preset_pedido` | Último preset pedido con `POST /api/preset` |
| `preset_actual` | Preset configurado en el ESP32-C6 (`null` mientras se reconecta) |
| `presets_sa_s` | Frecuencia nominal por canal de cada preset |
| `n_ventanas` | Ventanas capturadas desde que arrancó el backend |
| `errores` | Errores de comunicación acumulados |
| `ultimo_error` | Texto del último error, o `null` si la última captura fue buena |
| `spi_hz` | Reloj SPI configurado |

### `GET /api/window`

Última ventana capturada. Responde **503** con `{"error": "todavia no hay ventanas"}` si aún no hay ninguna.

| Campo | Tipo | Descripción |
|---|---|---|
| `numero` | entero | Número de la ventana desde el arranque |
| `timestamp` | número | Momento de la captura (segundos Unix) |
| `preset` | entero | Preset con el que se capturó |
| `fs_real_hz` | número | Frecuencia **real** de muestreo por canal |
| `n_muestras` | entero | Muestras por canal (256) |
| `ch0`, `ch1` | listas de enteros | Muestras crudas (0 a 4095 cuentas) |
| `ch0_v`, `ch1_v` | listas de números | Muestras en voltios |

**Eje de tiempo:** la muestra `i` corresponde a `t = i / fs_real_hz` segundos desde el inicio de la ventana.

**Conversión a voltios:** por ahora es una aproximación lineal medida, `V = cuentas × 3,333 / 3.352` (≈ 0,994 mV por cuenta). Ver el README del firmware.

### `POST /api/preset`

Pide un cambio de preset.

- Cuerpo (JSON): `{"preset": 0}`, con un entero de 0 a 3.
- Respuesta correcta: `{"ok": true, "preset_pedido": 0, "sa_s": 100}`.
- Preset inválido: **400** con `{"error": "preset debe ser un entero de 0 a 3"}`.

El cambio se aplica antes de la siguiente captura. Con el preset 0, la primera ventana nueva tarda unos 2,6 s.

## Ejemplos con curl (desde la Pi)

```bash
curl -s localhost:5000/api/status
curl -s localhost:5000/api/window | head -c 300
curl -s -X POST -H "Content-Type: application/json" -d '{"preset": 0}' localhost:5000/api/preset
```

## Prueba (2026-10-31)

Con la Pi y el ESP32-C6 conectados (GPIO0 a 3V3, GPIO1 a GND): `status` mostró 438 ventanas en unos 2 minutos, sin errores. `window` devolvió CH0 ≈ 3.351 cuentas, y el cambio al preset 0 se reflejó en `preset_actual` en menos de 4 s, sin errores.
