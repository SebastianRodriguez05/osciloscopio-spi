# Matriz de verificación

Versión 1.0 (2026-11-02). Relaciona cada requerimiento con su método de verificación, el criterio de aceptación, el resultado obtenido y la evidencia en el repositorio.

**Estados:** ✅ cumple · ⚠️ cumple con observación · ⏳ pendiente

## 1. Requerimientos del enunciado

| ID | Requerimiento | Método de verificación | Criterio de aceptación | Resultado | Estado | Evidencia |
|---|---|---|---|---|---|---|
| R1 | La SBC sirve un dashboard web por la red con un servidor HTTP (apache o nginx) | Acceso desde el navegador de otro equipo a `http://osciloscopio.local`; reinicio de la Pi sin entrar por SSH | El dashboard carga desde otro equipo y vuelve a funcionar solo después de reiniciar | nginx sirve el dashboard y reenvía `/api/` al backend. Después de `sudo reboot`, funcionó sin intervención | ✅ | `sbc/README.md` |
| R2 | Comunicación SBC ↔ microcontrolador por SPI | `spi_osciloscopio.py`: comandos de los 4 presets, verificando la marca 0xA5 y el checksum de cada ventana | 0 errores y checksums válidos | A 1 MHz: 4 de 4 ventanas sin errores. En el barrido: 100 de 100 ventanas a cada frecuencia entre 1 y 25 MHz | ✅ | `sbc/README.md`, `docs/protocolo-spi.md` |
| R3a | Ventanas de al menos 64 muestras | Campo `n_muestras` de cada ventana recibida | ≥ 64 muestras por canal | 256 muestras por canal | ✅ | `docs/protocolo-spi.md` |
| R3b | Frecuencia de muestreo constante | (1) Conteo de muestras por segundo en el ESP32-C6. (2) Medición de una onda cuadrada generada por el PWM por hardware de la Pi, con un reloj independiente | Conteo estable segundo a segundo; error frente a la señal externa < 0,1 % | (1) 1.000, 10.000 y 40.323 Sa/s, estables. (2) Error de −0,003 % a −0,027 % en los 4 presets | ✅ | `firmware/osciloscopio/README.md`, `sbc/README.md` |
| R4 | Frecuencia de muestreo intercambiable por SPI entre al menos 3 presets: 100, 1.000 y 10.000 Sa/s | `SET_PRESET` en la autoprueba, en la integración y desde el dashboard; medición con señal externa en cada preset | Cada preset se acepta y su frecuencia medida es correcta (< 0,1 %) | 4 presets (incluido el bonus). Errores: −0,003 % (100), 0,000 % (1.000), 0,000 % (10.000) | ✅ | `sbc/README.md` |
| R5 | El dashboard se refresca entre 0,25 Hz (4 s) y 1 Hz | Registro de nginx con hora en milisegundos y `medir_refresco.py`, 30 s por cada valor del selector | Frecuencia de refresco entre 0,25 y 1 Hz, con ±1 % de tolerancia por la variación de los temporizadores del navegador | 1,000 / 0,500 / 0,336 / 0,249 Hz para 1 / 2 / 3 / 4 s (detalle en la sección 3) | ⚠️ | Este documento |
| R6 | Estimar con las hojas de datos las tasas máximas teóricas del SPI y verificarlas experimentalmente | Teoría: `SCLK = core / CDIV` en la Pi (core de 400 MHz medido) y 40 MHz como esclavo en el ESP32-C6. Experimento: `barrido_spi.py`, 100 ventanas por frecuencia, dos corridas | Límite teórico documentado; límite experimental determinado y repetible | Teórico: 40 MHz (limita el ESP32-C6). Experimental: 25 MHz sin errores; a 28,57 MHz falla. Las dos corridas coinciden | ✅ | `sbc/README.md` |
| R7 | Bonus: captura ≥ 40.000 Sa/s verificada experimentalmente | Preset 3 medido con una onda de 2.000 Hz del PWM de la Pi | fs ≥ 40.000 Sa/s y error de la frecuencia medida < 0,1 % | 40.322,58 Sa/s por canal, error −0,027 % (con la fs nominal habría sido −0,826 %) | ✅ | `sbc/README.md` |

## 2. Verificaciones adicionales (requisitos derivados y restricciones)

| ID | Verificación | Método | Criterio | Resultado | Estado | Evidencia |
|---|---|---|---|---|---|---|
| V1 | El ADC lee los dos canales y son independientes | Cada canal flotante, a GND y a 3V3, con el otro sin conectar | GND ≈ 0; 3V3 ≈ 3,3 V; el otro canal no cambia | GND: 0 a 3 cuentas. 3V3: 3.333 mV. El otro canal siguió flotando | ✅ | `firmware/osciloscopio/README.md` |
| V2 | Exactitud del ADC con la calibración de fábrica | Lectura del pin 3V3 de la placa | Dentro de ±40 mV (hoja de datos) | 3.333 mV frente a 3,3 V nominales (+33 mV) | ⚠️ | `firmware/osciloscopio/README.md` |
| V3 | Ruido del ADC con la entrada fija | Mínimo y máximo de las ventanas | Documentar el valor | Sin la Pi: ±4 cuentas (≈ ±4 mV). En la integración aparecieron valores aislados de hasta 27 cuentas | ⚠️ | `firmware/osciloscopio/README.md`, `sbc/README.md` |
| V4 | Pines CS (GPIO18) y READY (GPIO19) | Programa temporal: salida en GPIO19 y entrada con pull-up en GPIO18, sin conexión, a GND y unidos entre sí | Lecturas según cada conexión | Las tres pruebas correctas | ✅ | `firmware/osciloscopio/README.md` |
| V5 | Lógica del protocolo en el firmware (prueba unitaria) | Autoprueba al arrancar: comandos internos con la misma función que usa el SPI | 24 de 24 verificaciones | 24 de 24 | ✅ | `firmware/osciloscopio/README.md` |
| V6 | Sincronización con la línea READY | Integración y barrido después de la corrección del driver (pausa de 0,2 ms y reintento) | Sin errores por lecturas prematuras | 0 errores y 0 reintentos a 1 MHz; 0 errores entre 1 y 25 MHz | ✅ | `sbc/README.md` |
| V7 | Arranque autónomo | `sudo reboot` y apertura del dashboard sin SSH | El sistema vuelve a funcionar sin intervención | Funcionó | ✅ | `sbc/README.md` |
| V8 | API HTTP | `curl` a `/api/status`, `/api/window` y `/api/preset` | Respuestas según el contrato; cambio de preset aplicado | Respuestas correctas; el preset cambió en menos de 4 s, sin errores | ✅ | `docs/api-http.md` |
| V9 | Recuperación del backend si el ESP32-C6 deja de responder | Mantener presionado el botón RST del ESP32-C6 durante 10 s con el backend corriendo, observando el registro del backend (`journalctl`), el monitor del ESP32-C6 y el dashboard | El backend informa el error, no se cae y se recupera solo | Mientras el ESP32-C6 estuvo en reinicio, el backend registró `READY no subio` y reintentó cada 6 s. Al arrancar el ESP32-C6, una transacción quedó desfasada (`comando desconocido`); el backend reabrió el SPI y se recuperó en ~1 s. Estado final: preset 2, sin error | ✅ | Este documento (sección 4) |

## 3. Detalle de R5: periodo de refresco del dashboard

nginx registra cada petición a `/api/` con la hora en milisegundos (`$msec`) en `/var/log/nginx/osciloscopio-api.log`. `sbc/backend/medir_refresco.py` mide, para cada valor del selector, los intervalos entre peticiones consecutivas a `/api/window` durante 30 s, ignorando los primeros 3 s. Se usó una sola pestaña del dashboard, visible.

| Refresco elegido | Intervalos | Promedio | Mínimo | Máximo | Desviación | Frecuencia |
|---|---|---|---|---|---|---|
| 1 s | 29 | 1,000 s | 0,948 s | 1,050 s | 0,020 s | 1,000 Hz |
| 2 s | 14 | 2,001 s | 1,987 s | 2,021 s | 0,010 s | 0,500 Hz |
| 3 s | 8 | 2,978 s | 2,762 s | 3,075 s | 0,141 s | 0,336 Hz |
| 4 s | 6 | 4,010 s | 3,911 s | 4,104 s | 0,084 s | 0,249 Hz |

**Observación:** con 4 s el promedio fue 4,010 s (0,249 Hz), un 0,25 % por debajo del límite de 0,25 Hz. El enunciado fija exactamente 4 s como límite, y los temporizadores del navegador varían decenas de milisegundos entre actualizaciones, así que el promedio puede quedar a uno u otro lado. Se considera que cumple dentro de la tolerancia del ±1 %.

## 4. Detalle de V9: recuperación ante fallos del ESP32-C6 (2026-11-02)

**Primera prueba (con un fallo de cableado).** Al presionar el botón RST se soltó sin querer el cable de READY (GPIO19 del ESP32-C6 al pin 22 de la Pi). El backend registró `READY no subio en 5.0 s (ESP32-C6 desconectado o sin responder)` cada 6 s, el dashboard mostró el error y el servidor siguió funcionando. Al abrir el monitor del ESP32-C6 se vio que el microcontrolador funcionaba normalmente; la causa era el cable. Al reconectarlo, el sistema se recuperó solo. Este fallo muestra que el sistema **informa con claridad** una conexión rota y **se recupera** al corregirla.

**Prueba repetida (cableado firme).** Registro del backend:

| Hora | Mensaje | Interpretación |
|---|---|---|
| 22:02:49 | `WARNING READY no subio en 5.0 s` | ESP32-C6 en reinicio (botón presionado) |
| 22:02:50 | `INFO SPI abierto a 10.0 MHz` | El backend reintenta |
| 22:02:55 | `WARNING SET_PRESET 2 rechazado: comando desconocido` | El ESP32-C6 ya arrancó; una transacción quedó desfasada porque el reinicio cortó un comando a la mitad |
| 22:02:56 | `INFO SPI abierto a 10.0 MHz` y `INFO Preset 2 (10000 Sa/s)` | Resincronizado y funcionando |

En el monitor del ESP32-C6 se vio el mismo desfase como `SPI: cmd=0x00 arg=0 -> error=1` justo después de la autoprueba, seguido de comandos normales. Estado final con `curl`: `preset_actual: 2`, `ultimo_error: null`.

**Recomendación para la presentación:** los cables jumper se sueltan con facilidad; conviene revisarlos antes de empezar y fijarlos con cinta.

## 5. Pendientes

- **V2:** medir el pin 3V3 con un multímetro, para saber si los +33 mV son error del ADC o el voltaje real de la placa.
- **V3:** investigar si la actividad del SPI durante la captura induce ruido en el ADC.
