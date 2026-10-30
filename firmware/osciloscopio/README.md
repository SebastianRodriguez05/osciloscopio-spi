# Firmware del osciloscopio (ESP32-C6)

Firmware del microcontrolador del proyecto. El ESP32-C6 captura las dos señales analógicas con su ADC y, en versiones posteriores, enviará las ventanas de muestras a la Raspberry Pi Zero 2 W por SPI (la Pi es maestro y el ESP32-C6 es esclavo).

## Estado actual

| Versión | Qué hace | Estado |
|---|---|---|
| Contador | Imprime `Osciloscopio: latido N` por el puerto serie cada segundo | Verificado |
| Lectura del ADC | Lee GPIO0 y GPIO1 cada 500 ms y los imprime en cuentas y en mV | Verificado (2026-10-30) |
| Muestreo con timer y presets | 100 / 1.000 / 10.000 Sa/s, ventanas de 256 muestras | Pendiente |
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

## Lectura del ADC (versión actual)

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
