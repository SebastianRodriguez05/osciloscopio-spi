# Osciloscopio SPI: Raspberry Pi Zero 2 W + ESP32-C6

Osciloscopio de dos canales formado por un microcontrolador **ESP32-C6**, que captura las señales con su ADC, y una **Raspberry Pi Zero 2 W**, que recibe las ventanas de muestras por **SPI** y las muestra en un **dashboard web** servido con **nginx**.

Segundo proyecto del curso, Ingeniería Electrónica, Universidad Nacional de Colombia.

```
Señales ──► ESP32-C6 (ADC + DMA) ──SPI──► Raspberry Pi (driver + backend + nginx) ──WiFi──► Navegador
```

**Video del funcionamiento:** https://drive.google.com/file/d/1IYMBOwsES4EGaz3gu5S0Xgh0v3_3cKHi/view?usp=sharing

## Resultados principales

| Característica | Resultado |
|---|---|
| Canales | 2 (GPIO0 y GPIO1 del ESP32-C6), de 0 a 3,3 V, 12 bits |
| Ventana | 256 muestras por canal |
| Presets de muestreo | 100, 1.000, 10.000 y **40.322,58 Sa/s** por canal (bonus), cambiables desde el dashboard |
| Exactitud de la frecuencia de muestreo | Error ≤ 0,03 %, medido con una señal externa independiente |
| SPI | Protocolo propio v1.1 con checksum; 10 MHz de trabajo; 25 MHz máximo sin errores |
| Dashboard | Refresco de 1 a 4 s (0,25 a 1 Hz), sin dependencias externas |
| Robustez | Arranque autónomo; detección de errores y recuperación automática |
| Pruebas | Autoprueba del firmware (24 verificaciones) y 28 pruebas automáticas del software de la Pi |

Todos los requerimientos del enunciado están verificados en la [matriz de verificación](docs/matriz-verificacion.md).

## Estructura del repositorio

```
firmware/osciloscopio/    Firmware del ESP32-C6 (ESP-IDF v5.5)
sbc/backend/              Driver SPI, backend Flask, simulador y herramientas de medición
sbc/web/                  Dashboard (HTML + JavaScript)
sbc/nginx/                Configuración del sitio de nginx
sbc/systemd/              Servicio del backend
sbc/instalar.sh           Instalación o actualización en la Pi
tests/sbc/                Pruebas automáticas (pytest)
docs/                     Arquitectura, protocolo, API, matriz de verificación, aportes y uso de IA
```

## Inicio rápido

### Conexión física
La tabla de conexiones entre las placas está en [docs/protocolo-spi.md](docs/protocolo-spi.md). Se cablea siempre con la Pi apagada.

### Firmware del ESP32-C6
Requiere ESP-IDF v5.5 para el target `esp32c6`.

```bash
cd firmware/osciloscopio
idf.py set-target esp32c6            # solo la primera vez
idf.py -p /dev/ttyACM0 flash monitor
```

Detalles en [firmware/osciloscopio/README.md](firmware/osciloscopio/README.md).

### Raspberry Pi
Requiere Raspberry Pi OS (Debian 13) con acceso a internet.

```bash
git clone https://github.com/SebastianRodriguez05/osciloscopio-spi.git ~/osciloscopio-spi
cd ~/osciloscopio-spi
bash sbc/instalar.sh
```

Luego, en un navegador de la misma red: `http://osciloscopio.local` (o la IP de la Pi). Detalles en [sbc/README.md](sbc/README.md).

### Sin hardware (simulador)

```bash
cd sbc/backend
OSC_SIMULADOR=1 OSC_HOST=0.0.0.0 python3 app.py     # dashboard en http://127.0.0.1:5000
```

### Pruebas automáticas

```bash
python3 -m pytest tests/sbc -v
```

## Documentación

| Documento | Contenido |
|---|---|
| [docs/01-arquitectura.md](docs/01-arquitectura.md) | Diagramas de bloques, de flujo y de secuencia; requerimientos y restricciones |
| [docs/protocolo-spi.md](docs/protocolo-spi.md) | Protocolo SPI v1.1 entre la Pi y el ESP32-C6, y la conexión física |
| [docs/api-http.md](docs/api-http.md) | API HTTP del backend |
| [docs/matriz-verificacion.md](docs/matriz-verificacion.md) | Matriz de verificación con métodos, criterios y resultados |
| [firmware/osciloscopio/README.md](firmware/osciloscopio/README.md) | Firmware: ADC, presets, ventanas, SPI esclavo y sus pruebas |
| [sbc/README.md](sbc/README.md) | Software de la Pi: driver, velocidad del SPI, backend, dashboard, simulador y pruebas |
| [docs/aportes.md](docs/aportes.md) | Participación y aportes de cada integrante |
| [docs/uso-ia.md](docs/uso-ia.md) | Declaración de uso de inteligencia artificial |
