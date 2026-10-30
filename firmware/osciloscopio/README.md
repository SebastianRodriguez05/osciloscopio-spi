# Firmware del osciloscopio (ESP32-C6)

Firmware del microcontrolador del proyecto. El ESP32-C6 captura las dos señales analógicas con su ADC y, en versiones posteriores, enviará las ventanas de muestras a la Raspberry Pi Zero 2 W por SPI (la Pi es maestro y el ESP32-C6 es esclavo).

## Estado actual

| Versión | Qué hace | Estado |
|---|---|---|
| Contador | Imprime `Osciloscopio: latido N` por el puerto serie cada segundo | Verificado |
| Lectura del ADC | Lee GPIO0 y GPIO1 cada 500 ms y los imprime en cuentas y en mV | Verificado (2026-10-30) |
| ADC en modo continuo (DMA) | 2 canales a frecuencia fija; mide la tasa real cada segundo | Verificado a 1.000, 10.000 y 40.000 Sa/s (2026-10-30) |
| Captura de ventanas | 256 muestras por canal en arreglos, con arranque y parada del ADC | Verificado a 10.000 Sa/s (2026-10-30) |
| Presets por comando | 100 / 1.000 / 10.000 Sa/s | Pendiente |
| SPI esclavo | Protocolo de comandos con la Pi | Pendiente |

## Hardware

- Placa de desarrollo ESP32-C6 (chip QFN40, revisión v0.2, RISC-V a 160 MHz, 3,3 V), con puente USB-serie CH343.
- La flash se detecta de 8 MB, pero el proyecto usa 2 MB. El aviso `Detected size(8192k) larger than the size in the binary image header(2048k)` es inofensivo.

### Pines usados hasta ahora

| Función | Pin del ESP32-C6 | Notas |
|---|---|---|
| Canal 1 del osciloscopio | GPIO0 (ADC1_CH0) | Entrada analógica, 0 a 3,3 V |
| Canal 2 del osciloscopio | GPIO1 (ADC1_CH1) | Entrada analógica, 0 a 3,3 V |

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

- Muestreo a frecuencia constante con timer o modo continuo (DMA), con presets de 100, 1.000 y 10.000 Sa/s y ventanas de 256 muestras por canal.
- SPI esclavo en SPI2 (CLK GPIO6, MOSI GPIO7, MISO GPIO2) con el protocolo de comandos `SET_PRESET` 0x01, `START_CAPTURE` 0x02, `STATUS` 0x03 y `READ_WINDOW` 0x04.
- Reasignar el pin CS: GPIO16 y GPIO17 son UART0 y están conectados al puente CH343 que se usa para programar la placa.

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
