# Firmware del osciloscopio (ESP32-C6)

Firmware del microcontrolador del proyecto. El ESP32-C6 captura las dos señales analógicas con su ADC y, en versiones posteriores, enviará las ventanas de muestras a la Raspberry Pi Zero 2 W por SPI (la Pi es maestro y el ESP32-C6 es esclavo).

## Estado actual

| Versión | Qué hace | Estado |
|---|---|---|
| Contador | Imprime `Osciloscopio: latido N` por el puerto serie cada segundo | Verificado |
| Lectura del ADC | Lee GPIO0 y GPIO1 cada 500 ms y los imprime en cuentas y en mV | Verificado (2026-10-30) |
| ADC en modo continuo (DMA) | 2 canales a frecuencia fija; mide la tasa real cada segundo | Verificado a 1.000, 10.000 y 40.000 Sa/s (2026-10-30) |
| Captura de ventanas | 256 muestras por canal en arreglos, con arranque y parada del ADC | Verificado a 10.000 Sa/s (2026-10-30) |
| Presets de muestreo | 100 (promedio de 10), 1.000, 10.000 y 40.000 Sa/s | Verificado (2026-10-30) |
| Elegir el preset por SPI | Comando SET_PRESET | Verificado con la autoprueba (2026-10-31) |
| SPI esclavo | Protocolo v1.0 (docs/protocolo-spi.md) con autoprueba al arrancar | Lógica verificada (2026-10-31); falta la prueba física con la Pi |

## Hardware

- Placa de desarrollo ESP32-C6 (chip QFN40, revisión v0.2, RISC-V a 160 MHz, 3,3 V), con puente USB-serie CH343.
- La flash se detecta de 8 MB, pero el proyecto usa 2 MB. El aviso `Detected size(8192k) larger than the size in the binary image header(2048k)` es inofensivo.

### Pines usados hasta ahora

| Función | Pin del ESP32-C6 | Notas |
|---|---|---|
| Canal 1 del osciloscopio | GPIO0 (ADC1_CH0) | Entrada analógica, 0 a 3,3 V |
| Canal 2 del osciloscopio | GPIO1 (ADC1_CH1) | Entrada analógica, 0 a 3,3 V |
| SPI CLK | GPIO6 | Pin nativo (IO MUX) de SPI2; a la Pi, pin 23 (GPIO11) |
| SPI MOSI | GPIO7 | Pin nativo (IO MUX) de SPI2; a la Pi, pin 19 (GPIO10) |
| SPI MISO | GPIO2 | Pin nativo (IO MUX) de SPI2; a la Pi, pin 21 (GPIO9) |
| SPI CS | GPIO18 | Entrada; a la Pi, pin 24 (GPIO8, CE0) |
| READY | GPIO19 | Salida, avisa a la Pi que hay una ventana lista; a la Pi, pin 22 (GPIO25) |

**Advertencia:** las entradas analógicas solo admiten de 0 a 3,3 V. Nunca conectar 5 V.

## Requisitos

- ESP-IDF v5.5 instalado para el target `esp32c6` (`./install.sh esp32c6`).
- En Windows con WSL2: pasar el USB de la placa a Ubuntu con `usbipd-win` (`usbipd attach --wsl --busid <BUSID> --auto-attach` en PowerShell como administrador). En Ubuntu la placa aparece como `/dev/ttyACM0`, y el usuario debe estar en el grupo `dialout`.

## Compilar, grabar y ver la salida

```bash
get_idf                                   # activa el entorno de ESP-IDF (en cada terminal nueva)
cd firmware/osciloscopio
idf.py set-target esp32c6                 # solo la primera vez en cada computador
idf.py -p /dev/ttyACM0 flash monitor      # compila, graba y abre el monitor serie
```

Para salir del monitor: `Ctrl+]`.

El archivo `sdkconfig` se genera en cada computador y **no se sube al repositorio** (está en `.gitignore`).

## Lectura del ADC en modo oneshot (commit 72596a7)

El programa (`main/osciloscopio.c`) hace lo siguiente:

1. Inicializa el ADC1 en modo *oneshot*, es decir, una conversión cada vez que el programa la pide.
2. Configura los canales 0 y 1 con atenuación de 12 dB (rango efectivo de 0 a 3.300 mV) y 12 bits (0 a 4095 cuentas).
3. Crea una calibración *curve fitting* por canal, que usa los datos de fábrica grabados en el chip para convertir cuentas a milivoltios.
4. Cada 500 ms lee ambos canales e imprime una línea como esta:

```
GPIO0=3351 (3333 mV)   GPIO1=1229 (1225 mV)
```

**Por qué hace falta la calibración:** con atenuación de 12 dB, 4095 cuentas no equivalen a 3,3 V, y la relación entre cuentas y voltaje no es del todo lineal. En esta placa, 3,33 V corresponden a unas 3.352 cuentas, no a ~4.095. Por eso los voltajes se calculan con la calibración y no con una regla de tres.

`main/CMakeLists.txt` declara `REQUIRES esp_adc`, el componente de ESP-IDF que contiene el ADC y la calibración.

## Prueba de verificación del ADC (2026-10-30)

**Objetivo:** comprobar que los dos canales leen correctamente, que no están cruzados y que la conversión a mV es coherente con el datasheet (error total de hasta ±40 mV).

**Procedimiento:** con el programa corriendo y el monitor abierto, se conectó cada entrada a tres condiciones usando un jumper. Solo se tocaba un canal a la vez, y el otro quedaba sin conectar.

1. Pin sin conectar (flotante).
2. Jumper del pin a GND.
3. Jumper del pin a 3V3 de la propia placa.

**Resultados:**

| Canal | Flotante | GND | 3V3 |
|---|---|---|---|
| GPIO0 (ADC1_CH0) | Variable, entre ~900 y ~2.700 cuentas | 0 a 3 cuentas | 3.332 a 3.336 mV |
| GPIO1 (ADC1_CH1) | Variable, entre ~900 y ~1.550 cuentas | 0 a 1 mV | 3.332 a 3.336 mV |

**Observaciones:**

- Un pin sin conectar no tiene un voltaje definido y capta ruido del entorno, sobre todo al acercar la mano o el jumper. Su lectura variable es normal.
- Al poner un canal en GND o en 3V3, el otro siguió flotando, lo que confirma que los canales son independientes.
- La lectura en 3V3 (≈3.333 mV, variación de ±2 mV) está dentro del error de ±40 mV del datasheet. Probablemente el regulador de la placa entrega unos 3,33 V; falta confirmarlo con un multímetro.

**Conclusión:** el ADC1 queda verificado en ambos canales.

## Pendientes

- Probar el SPI esclavo con la Pi como maestro y medir la velocidad máxima del reloj sin errores.





## Prueba del ADC en modo continuo (2026-10-30)

El programa actual de `main/osciloscopio.c` usa el ADC en **modo continuo**: el ADC convierte solo, a una frecuencia fija, alternando entre el canal 0 (GPIO0) y el canal 1 (GPIO1). El DMA deja los resultados en memoria sin intervención del procesador. Cada segundo, el programa cuenta cuántas muestras llegaron de cada canal (usando `esp_timer`) e imprime la tasa medida y el último valor crudo. La frecuencia **total** del ADC se fija con `FREC_TOTAL_HZ` (por defecto 20.000 Hz, es decir, 10.000 Sa/s por canal).

### Límites del modo continuo en el ESP32-C6

Los límites se tomaron de `components/soc/esp32c6/include/soc/soc_caps.h` de ESP-IDF v5.5:

| Constante | Valor | Significado |
|---|---|---|
| `SOC_ADC_SAMPLE_FREQ_THRES_LOW` | 611 Hz | Frecuencia total mínima |
| `SOC_ADC_SAMPLE_FREQ_THRES_HIGH` | 83.333 Hz | Frecuencia total máxima |
| `SOC_ADC_DIGI_RESULT_BYTES` | 4 | Bytes por muestra en el buffer del DMA |
| `SOC_ADC_DIGI_MAX_BITWIDTH` | 12 | Resolución en bits |

La frecuencia total se reparte entre los dos canales. Por eso el preset de **100 Sa/s por canal (200 Hz en total) no cabe** en el modo continuo y necesita otra estrategia (por ejemplo, muestrear más rápido y quedarse con una de cada N muestras, o usar un timer con lecturas oneshot).

### Resultados

Montaje: GPIO0 a 3V3 y GPIO1 a GND con jumpers.

| Por canal (pedido) | Total pedido | Medido por canal | CH0 (3V3) | CH1 (GND) |
|---|---|---|---|---|
| 1.000 Sa/s | 2.000 Hz | 1.000 Sa/s | ~3.352 cuentas | 0 a 3 cuentas |
| 10.000 Sa/s | 20.000 Hz | 10.000 Sa/s | ~3.352 cuentas | 0 a 2 cuentas |
| 40.000 Sa/s (bonus) | 80.000 Hz | **40.323 Sa/s** | ~3.351 cuentas | 0 a 3 cuentas |

La primera línea de cada prueba sale un poco más alta (por ejemplo 10.049) porque incluye muestras que ya estaban en el buffer al arrancar. Desde la segunda línea la tasa es constante.

### Observaciones

- **No se pierden muestras:** la tasa medida nunca quedó por debajo de la pedida.
- **Por qué 40.323 y no 40.000 (hipótesis):** los tres resultados coinciden con un reloj del ADC de 5 MHz dividido por un número entero. 5 MHz / 2.500 = 2.000 Hz y 5 MHz / 250 = 20.000 Hz son exactos, pero 5 MHz / 62,5 no es entero, el divisor queda en 62 y da 80.645 Hz en total, es decir, 40.323 por canal. Falta confirmarlo en el código del driver de ESP-IDF o en el manual técnico del ESP32-C6. **Consecuencia para el diseño:** el ESP32-C6 debe informar a la Pi la frecuencia de muestreo **real** (por ejemplo en la respuesta a `STATUS`) para que el eje de tiempo del dashboard sea correcto.
- **Alcance de la medición:** la tasa se midió con el reloj interno del ESP32-C6, que sale del mismo cristal de 40 MHz que el ADC. Esto comprueba que el ADC entrega la cantidad de muestras pedida, pero no la exactitud absoluta de la frecuencia. Para eso falta medir una señal de frecuencia conocida generada desde fuera.
- **Contacto de los jumpers:** en una corrida, CH1 en GND leyó entre 46 y 89 cuentas. Al reacomodar el jumper volvió a 0 a 3, aunque CH0 seguía en 3,3 V, así que la causa era mal contacto y no arrastre entre canales. Para las mediciones finales conviene usar conexiones firmes.
- **Entradas flotantes:** en modo continuo, un pin sin conectar tiende hacia el voltaje del otro canal, porque el condensador interno del ADC se comparte. La lectura de una entrada sin conectar no tiene significado.

## Captura de ventanas de 256 muestras (2026-10-30)

El programa actual de `main/osciloscopio.c` captura **ventanas**: arranca el ADC en modo continuo, guarda 256 muestras de cada canal en los arreglos `ventana0` (GPIO0) y `ventana1` (GPIO1), detiene el ADC y vacía su buffer interno con `adc_continuous_flush_pool`, para que la siguiente ventana no arrastre muestras viejas. Cada 2 segundos imprime la duración de la captura y el mínimo, el máximo, el promedio y las primeras 8 muestras de cada canal. Esta es la base de lo que la Pi pedirá con `READ_WINDOW`.

### Resultados

Montaje: GPIO0 a 3V3 y GPIO1 a GND, a 10.000 Sa/s por canal.

| Dato | Resultado |
|---|---|
| Duración de una ventana | 25.669 µs (esperado 25.600 µs); la primera ventana tardó 25.821 µs |
| CH0 (3V3) | 3.348 a 3.356 cuentas, promedio 3.352 |
| CH1 (GND) | 0 a 3 cuentas, promedio 0 |

### Observaciones

- Los 69 µs de diferencia (0,3 %) corresponden al arranque del ADC antes de la primera muestra; dentro de la ventana las muestras van a frecuencia constante.
- Con la entrada fija, el ruido propio del ADC es de unas ±4 cuentas (≈ ±4 mV).
- Las ventanas consecutivas son coherentes entre sí, lo que confirma que el vaciado del buffer funciona.

## Presets de frecuencia de muestreo (2026-10-30)

El programa actual define los presets en la tabla `PRESETS` de `main/osciloscopio.c`. Como todavía no hay SPI, el programa de prueba los recorre en orden, una ventana por preset; más adelante el comando `SET_PRESET` elegirá cuál usar. Al cambiar de preset, el ADC se libera (`adc_continuous_deinit`) y se configura de nuevo.

| Preset | Por canal | ADC total | Promedio |
|---|---|---|---|
| 0 | 100 Sa/s | 2.000 Hz | de 10 muestras |
| 1 | 1.000 Sa/s | 2.000 Hz | sin promedio |
| 2 | 10.000 Sa/s | 20.000 Hz | sin promedio |
| 3 (bonus) | 40.000 Sa/s (40.323 reales) | 80.000 Hz | sin promedio |

**Cómo se logra 100 Sa/s:** el modo continuo no baja de 611 Hz en total, así que se muestrea a 1.000 Sa/s por canal y cada 10 muestras crudas se promedian en una. El resultado mantiene la frecuencia constante, reduce el ruido y funciona como un filtro anti-aliasing sencillo.

### Resultados

Montaje: GPIO0 a 3V3 y GPIO1 a GND.

| Preset | Duración de la ventana | CH0 (3V3) | CH1 (GND) |
|---|---|---|---|
| 0 (100 Sa/s) | 2.559.998 µs | 3.351 a 3.354 | 0 a 2 |
| 1 (1.000 Sa/s) | 255.864 µs | 3.349 a 3.355 | 0 a 3 |
| 2 (10.000 Sa/s) | 25.686 µs | 3.349 a 3.355 | 0 a 3 |
| 3 (40.000 Sa/s) | 6.453 µs | 3.346 a 3.354 | 0 a 2 |

### Observaciones

- El promedio reduce el ruido: en el preset 0, CH0 varía 3 cuentas, frente a 6 a 8 en los demás.
- La duración de la ventana no es una medición precisa de la frecuencia: 256 muestras abarcan 255 intervalos, y se suma un retardo fijo de arranque y entrega de unos 100 a 200 µs. La frecuencia real se midió por conteo en la prueba del modo continuo.

## Asignación de los pines CS y READY (2026-10-31)

El CS se había propuesto en GPIO16, pero GPIO16 y GPIO17 son el UART0, conectado al puente CH343 que se usa para programar la placa y ver el monitor serie. Se descartaron también GPIO0 y GPIO1 (ADC), GPIO2, GPIO6 y GPIO7 (SPI), GPIO4 y GPIO5 (JTAG y ADC), GPIO8, GPIO9 y GPIO15 (pines de arranque o *strapping*) y GPIO12 y GPIO13 (USB nativo). Se eligieron **GPIO18 para el CS** y **GPIO19 para READY**, que son de uso general y no participan en el arranque. Que el CS no use su pin nativo del SPI no afecta la velocidad, que depende del reloj (CLK en GPIO6).

**Prueba:** un programa temporal configuró GPIO19 como salida alternando entre 0 y 1 cada 500 ms, y GPIO18 como entrada con *pull-up* interno.

| Prueba | Conexión | Resultado |
|---|---|---|
| A | Nada conectado | GPIO18 = 1 siempre (pull-up) |
| B | GPIO18 a GND | GPIO18 = 0 siempre |
| C | GPIO19 a GPIO18 | GPIO18 sigue a GPIO19 en cada lectura |

**Conclusión:** ambos pines funcionan. El programa de prueba no se conservó en el repositorio.

## SPI esclavo y autoprueba del protocolo (2026-10-31)

El programa actual de `main/osciloscopio.c` es el firmware completo del ESP32-C6. Implementa el **protocolo SPI v1.0**, documentado en `docs/protocolo-spi.md`, con dos tareas de FreeRTOS:

| Tarea | Función |
|---|---|
| `spi` | Recibe cada comando de 4 bytes, lo procesa con `procesar_comando()` y entrega la respuesta (STATUS de 16 bytes o VENTANA de 1.036 bytes). La línea READY (GPIO19) sube cuando una transacción está lista en el hardware y baja al terminar, mediante los *callbacks* del driver. |
| `captura` | Espera `START_CAPTURE`, captura una ventana con el preset actual y arma el paquete con su checksum. |

Los pines MOSI, SCLK y CS tienen *pull-up* interno para que no aparezcan transacciones falsas cuando la Pi no está conectada.

### Autoprueba

Al arrancar, antes de habilitar el SPI, el firmware ejecuta los comandos del protocolo internamente, con la misma función `procesar_comando()` que usa el SPI, y verifica las respuestas. Funciona como prueba unitaria de la lógica del protocolo, sin necesitar la Pi.

**Resultado (GPIO0 a 3V3, GPIO1 a GND): 24 de 24 verificaciones superadas.**

| Verificación | Resultado |
|---|---|
| STATUS inicial (marca 0xA5, en espera, preset 2) | Pasa |
| Comando desconocido, error 1 | Pasa |
| SET_PRESET con argumento inválido, error 3 | Pasa |
| READ_WINDOW sin ventana: n_muestras 0 y checksum válido | Pasa |
| Para cada preset (0 a 3): SET_PRESET, START_CAPTURE, START_CAPTURE repetido (error 2), ventana lista en menos de 5 s, y VENTANA con marca, preset, 256 muestras, fs_real y checksum correctos | Pasa en los 4 presets |
| Promedios de la ventana | CH0 entre 3.349 y 3.353 cuentas; CH1 entre 0 y 1 |

Sin la Pi conectada, el monitor no muestra transacciones falsas. Falta la prueba física de la comunicación SPI con la Pi como maestro.
