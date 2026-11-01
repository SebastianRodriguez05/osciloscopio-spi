# Protocolo SPI entre la Raspberry Pi y el ESP32-C6

Versión 1.0 (2026-10-31). Este documento es la referencia común para el firmware del ESP32-C6, el driver SPI de la Pi y el simulador en Python. Cualquier cambio al protocolo se hace primero aquí.

## Conexión física

| Señal | ESP32-C6 | Raspberry Pi (pin físico) | Dirección |
|---|---|---|---|
| SCLK | GPIO6 | 23 (GPIO11) | Pi → ESP32 |
| MOSI | GPIO7 | 19 (GPIO10) | Pi → ESP32 |
| MISO | GPIO2 | 21 (GPIO9) | ESP32 → Pi |
| CS | GPIO18 | 24 (GPIO8, CE0) | Pi → ESP32, activo en bajo |
| READY | GPIO19 | 22 (GPIO25) | ESP32 → Pi, activo en alto |
| GND | GND | 25 | Tierra común |

Ambas placas trabajan a 3,3 V. Se cablea siempre con la Pi apagada.

## Parámetros del bus

- La Pi es **maestro** y el ESP32-C6 es **esclavo** (SPI2).
- **Modo SPI 0** (CPOL = 0, CPHA = 0), bytes con el bit más significativo primero.
- Enteros de varios bytes en **little-endian** (el byte menos significativo primero).
- Reloj inicial para pruebas: **1 MHz**. El máximo se determina experimentalmente.
- Todas las transacciones tienen longitud **múltiplo de 4 bytes**, como exige el DMA del ESP32-C6.

## Secuencia de un comando

En SPI el esclavo transmite al mismo tiempo que recibe, así que no puede responder a un comando en la misma transacción. Cada comando usa **dos transacciones**, sincronizadas con la línea **READY**:

1. La Pi espera **READY = 1** (el ESP32-C6 está listo para recibir).
2. La Pi envía el **comando**: una transacción de **4 bytes**.
3. El ESP32-C6 baja READY, procesa el comando, prepara la respuesta y vuelve a subir **READY = 1**.
4. La Pi lee la **respuesta**: una transacción con la longitud que corresponde a ese comando. Durante esa transacción la Pi envía ceros.

La Pi **debe** esperar READY antes de cada transacción; si no lo hace, la transacción se pierde.

## Formato del comando (Pi → ESP32-C6): 4 bytes

| Byte | Contenido |
|---|---|
| 0 | Código del comando |
| 1 | Argumento (0 si el comando no lo usa) |
| 2–3 | 0x00 0x00 (reservados) |

## Comandos

| Comando | Código | Argumento | Respuesta | Longitud |
|---|---|---|---|---|
| SET_PRESET | 0x01 | Preset (0 a 3) | STATUS | 16 bytes |
| START_CAPTURE | 0x02 | — | STATUS | 16 bytes |
| STATUS | 0x03 | — | STATUS | 16 bytes |
| READ_WINDOW | 0x04 | — | VENTANA | 1.036 bytes |

### Presets

| Preset | Frecuencia por canal | Frecuencia real (fs_real) | Duración aproximada de una ventana |
|---|---|---|---|
| 0 | 100 Sa/s (1.000 Sa/s promediadas de a 10) | 100.000 mHz | 2,56 s |
| 1 | 1.000 Sa/s | 1.000.000 mHz | 256 ms |
| 2 | 10.000 Sa/s | 10.000.000 mHz | 25,6 ms |
| 3 | 40.000 Sa/s (bonus) | 40.322.580 mHz (medido) | 6,35 ms |

El preset por defecto al arrancar es el **2 (10.000 Sa/s)**.

### Comportamiento

- **SET_PRESET:** cambia el preset. Se rechaza con error 2 si hay una captura en curso, y con error 3 si el argumento no está entre 0 y 3.
- **START_CAPTURE:** inicia la captura de una ventana con el preset actual y responde de inmediato (estado 1). Si ya hay una captura en curso, responde con error 2.
- **STATUS:** solo informa el estado; no cambia nada.
- **READ_WINDOW:** entrega la última ventana completa. La ventana sigue disponible hasta el siguiente START_CAPTURE, así que se puede leer más de una vez. Si no hay ninguna ventana completa, responde con n_muestras = 0 y los datos en cero.

### Uso típico desde la Pi

1. SET_PRESET (solo si cambió el preset).
2. START_CAPTURE.
3. STATUS repetido hasta que estado = 2 (ventana lista).
4. READ_WINDOW.
5. Volver al punto 2 para la siguiente ventana.

Con el preset de 100 Sa/s, cada ventana tarda unos 2,56 s, compatible con el refresco del dashboard (entre 1 y 4 s).

## Respuesta STATUS: 16 bytes

| Bytes | Campo | Tipo | Descripción |
|---|---|---|---|
| 0 | marca | uint8 | Siempre 0xA5 |
| 1 | estado | uint8 | 0 = en espera, 1 = capturando, 2 = ventana lista |
| 2 | preset | uint8 | Preset actual (0 a 3) |
| 3 | error | uint8 | Resultado del último comando (ver códigos de error) |
| 4–7 | fs_real | uint32 | Frecuencia real por canal del preset actual, en milihertz |
| 8–9 | n_muestras | uint16 | Muestras por canal en cada ventana (256) |
| 10–11 | n_ventana | uint16 | Número de ventanas capturadas desde el arranque (da la vuelta en 65.535) |
| 12–15 | reservado | — | Ceros |

## Respuesta VENTANA: 1.036 bytes

| Bytes | Campo | Tipo | Descripción |
|---|---|---|---|
| 0 | marca | uint8 | Siempre 0xA5 |
| 1 | preset | uint8 | Preset con el que se capturó la ventana |
| 2–3 | n_muestras | uint16 | 256, o 0 si no hay ventana disponible |
| 4–7 | fs_real | uint32 | Frecuencia real por canal, en milihertz |
| 8–519 | canal 0 | 256 × uint16 | Muestras crudas de GPIO0 (0 a 4095) |
| 520–1031 | canal 1 | 256 × uint16 | Muestras crudas de GPIO1 (0 a 4095) |
| 1032–1035 | checksum | uint32 | Suma de los bytes 0 a 1031 como enteros sin signo, módulo 2^32 |

Las muestras se envían **crudas** (cuentas del ADC). La conversión a voltios se hace en la Pi; con atenuación de 12 dB, unas 3.352 cuentas corresponden a ~3,33 V. Una conversión exacta requiere la curva de calibración del chip; ver el README del firmware.

## Códigos de error

| Código | Significado |
|---|---|
| 0 | Sin error |
| 1 | Comando desconocido |
| 2 | Ocupado: hay una captura en curso |
| 3 | Argumento inválido |

## Verificación de integridad

La Pi debe comprobar en cada respuesta:

1. Que el byte 0 sea **0xA5**. Si no lo es, la respuesta llegó corrupta o desfasada.
2. En la VENTANA, que el **checksum** recibido coincida con la suma calculada sobre los bytes 0 a 1031.

Estas comprobaciones también sirven para medir la velocidad máxima del SPI sin errores.
