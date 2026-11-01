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

## Velocidad máxima del SPI (2026-10-31)

### Teórica

- **Pi (maestro):** `SCLK = core / CDIV`, con CDIV par (BCM2835 ARM Peripherals, registro CLK del SPI). Con el core clock medido de 400 MHz (`vcgencmd measure_clock core`), el máximo es 400 / 2 = **200 MHz**. Como CDIV debe ser par, la Pi genera la frecuencia disponible más cercana por debajo de la pedida (por ejemplo, 16 MHz pedidos dan 15,38 MHz reales).
- **ESP32-C6 (esclavo):** hasta **40 MHz** según su hoja de datos.
- **Sistema:** el límite teórico es el menor de los dos, **40 MHz**.

### Experimental

Programa: `sbc/backend/barrido_spi.py`. Para cada frecuencia captura 100 ventanas con el preset 2 y cuenta los errores. Cableado con jumpers según `docs/protocolo-spi.md`.

| Pedido | Real | CDIV | Ventanas OK | Errores | Velocidad efectiva | Eficiencia |
|---|---|---|---|---|---|---|
| 1 MHz | 1,00 MHz | 400 | 100 | 0 | 970 kbit/s | 97,0 % |
| 2 MHz | 2,00 MHz | 200 | 100 | 0 | 1.846 kbit/s | 92,3 % |
| 4 MHz | 4,00 MHz | 100 | 100 | 0 | 3.431 kbit/s | 85,8 % |
| 8 MHz | 8,00 MHz | 50 | 100 | 0 | 6.010 kbit/s | 75,1 % |
| 10 MHz | 10,00 MHz | 40 | 100 | 0 | 7.077 kbit/s | 70,8 % |
| 16 MHz | 15,38 MHz | 26 | 100 | 0 | 9.391 kbit/s | 61,0 % |
| 20 MHz | 20,00 MHz | 20 | 100 | 0 | 10.946 kbit/s | 54,7 % |
| 25 MHz | 25,00 MHz | 16 | 100 | 0 | 12.323 kbit/s | 49,3 % |
| 32 MHz | 28,57 MHz | 14 | 23 | 28 de marca, el resto en START_CAPTURE | 12.993 kbit/s (solo las buenas) | 45,5 % |
| 40 MHz | 40,00 MHz | 10 | 0 | Falla desde el primer comando | — | — |

### Conclusiones

- **Límite práctico: 25 MHz** sin errores. La siguiente frecuencia disponible (28,57 MHz, CDIV = 14) ya falla, así que el límite está entre esos dos valores.
- **Causa del fallo:** a 28,57 MHz la marca llega como `0xD2` en vez de `0xA5`, que son los mismos bits desplazados una posición. La Pi lee cada bit antes de que el ESP32-C6 lo termine de poner en MISO: con 35 ns por bit, el retardo de salida del esclavo más el de los cables ya no cabe. Es un límite de tiempos físicos, inferior al teórico de 40 MHz.
- **Eficiencia:** baja del 97 % a 1 MHz al 49 % a 25 MHz, porque cada transferencia tiene un tiempo fijo de preparación en Linux que pesa más cuanto más rápido viajan los datos.
- **Frecuencia de trabajo elegida: 10 MHz** (7 Mbit/s), con un margen amplio frente al límite y mucho más de lo que necesita el osciloscopio: una ventana se transfiere en menos de 1,5 ms.
- **Repetibilidad:** una segunda corrida completa dio los mismos resultados. De 1 a 25 MHz, 100 de 100 ventanas a todas las frecuencias, con velocidades efectivas que difieren menos del 0,5 %. A 28,57 MHz: 28 ventanas buenas, 28 errores de marca y 44 comandos rechazados (llegaron con los bits desplazados). A 40 MHz, el ESP32-C6 no acepta ningún comando.

## Backend, dashboard y servicio (2026-10-31)

| Componente | Archivo | Función |
|---|---|---|
| Backend | `backend/app.py` | Flask en `127.0.0.1:5000`. Un hilo de adquisición es el único que usa el SPI (10 MHz) y guarda la última ventana. API: ver `docs/api-http.md` |
| Dashboard | `web/index.html` | Página única, sin librerías externas. Dibuja los dos canales con `<canvas>` y tiene selector de preset, refresco de 1 a 4 s y pausa |
| nginx | `nginx/osciloscopio.conf` | Sirve el dashboard desde `/var/www/osciloscopio` y reenvía `/api/` al backend (proxy inverso) |
| Servicio | `systemd/osciloscopio-backend.service` | Arranca el backend al encender la Pi y lo reinicia si se cae |
| Instalación | `instalar.sh` | Instala o actualiza todo lo anterior |

### Instalación o actualización en la Pi

```bash
git clone https://github.com/SebastianRodriguez05/osciloscopio-spi.git ~/osciloscopio-spi   # solo la primera vez
cd ~/osciloscopio-spi
git pull
bash sbc/instalar.sh
```

Luego, en un navegador de la misma red: `http://osciloscopio.local` (o la IP de la Pi).

Comandos útiles:

```bash
systemctl status osciloscopio-backend --no-pager     # estado del backend
journalctl -u osciloscopio-backend -f               # mensajes del backend en vivo (Ctrl+C para salir)
sudo systemctl restart osciloscopio-backend          # reiniciar el backend
```

No se debe ejecutar `python3 app.py` a mano mientras el servicio está activo: el puerto 5000 y la línea GPIO25 solo pueden ser usados por un proceso a la vez.

### Pruebas

- La API probada con `curl`: estado, ventana y cambio de preset, sin errores (ver `docs/api-http.md`).
- Dashboard: con GPIO0 a 3V3 y GPIO1 a GND, a 100 Sa/s, el canal 1 mostró min 3,331 / max 3,336 / prom 3,333 V (Vpp 0,005 V) y el canal 2, min 0,000 / max 0,011 / prom 0,001 V, con 529 ventanas y 0 errores.
- Arranque autónomo: después de `sudo reboot`, el dashboard volvió a funcionar sin entrar por SSH.

## Verificación de la frecuencia de muestreo con una señal externa (2026-10-31)

Hasta este punto, la frecuencia de muestreo solo se había medido con el reloj del propio ESP32-C6. Para verificarla con una referencia **independiente**, la Pi genera una onda cuadrada con su **PWM por hardware**, cuyo reloj sale del cristal de la Pi, y el osciloscopio la mide.

**Montaje:** pin 12 de la Pi (GPIO18, PWM0) al GPIO0 del ESP32-C6 (canal 1), con tierra común por el cable GND del SPI. Se quita el jumper GPIO0 → 3V3 (si se dejara, habría un cortocircuito cuando el PWM baja a 0 V). GPIO1 sigue en GND.

**Configuración de la Pi:** agregar `dtoverlay=pwm,pin=18,func=2` al final de `/boot/firmware/config.txt` y reiniciar. `pinctrl get 18` debe mostrar `GPIO18 = PWM0`. Esto solo se necesita para esta prueba.

**Programa:** `backend/verificar_fs.py` (con `sudo`, porque escribe en `/sys/class/pwm`). Para cada preset programa una frecuencia de prueba que deja unos 12,8 periodos por ventana, toma 20 ventanas, calcula la frecuencia de la onda a partir de los flancos de subida usando la `fs_real` informada por el ESP32-C6, y la compara con la frecuencia del PWM. Al terminar deja el PWM en 500 Hz y el preset 2.

### Resultados

| Preset | fs_real | Frecuencia del PWM | Frecuencia medida (promedio de 20) | Desviación | Error | Error si se usara la fs nominal |
|---|---|---|---|---|---|---|
| 0 | 100,00 Sa/s | 5 Hz | 5,000 Hz | 0,001 Hz | −0,003 % | −0,003 % |
| 1 | 1.000,00 Sa/s | 50 Hz | 50,000 Hz | 0,000 Hz | 0,000 % | 0,000 % |
| 2 | 10.000,00 Sa/s | 500 Hz | 499,999 Hz | 0,004 Hz | 0,000 % | 0,000 % |
| 3 | 40.322,58 Sa/s | 2.000 Hz | 1.999,466 Hz | 1,885 Hz | −0,027 % | −0,826 % |

### Conclusiones

- Las cuatro frecuencias de muestreo son correctas frente a una referencia independiente, con errores de 0,03 % o menos.
- **Se confirma que el preset 3 muestrea a 40.322,58 Sa/s**, no a 40.000: con la frecuencia real el error es −0,027 %, y con la nominal sería −0,826 %, como predice la hipótesis del reloj del ADC (5 MHz con divisor entero 62). Por eso el protocolo informa la frecuencia real.
- **Bonus verificado:** la captura de 2 canales a ≥ 40.000 Sa/s funciona de punta a punta (ADC, SPI, backend y dashboard), con la frecuencia comprobada experimentalmente.
- La desviación es casi nula en los presets 0 a 2 porque las frecuencias de prueba caben un número entero de muestras por periodo, así que todas las ventanas dan el mismo resultado. En el preset 3 caben 20,16 muestras por periodo, y por eso varía entre ventanas; el promedio de 20 ventanas queda dentro del 0,03 %.
