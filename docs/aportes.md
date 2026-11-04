# Participación y aportes de los integrantes

El proyecto se desarrolló de forma **colaborativa, en sesiones de trabajo conjuntas** en las que participaron todos los integrantes. Para organizar el trabajo y la sustentación, cada integrante fue **responsable** de un área: la lideró, revisó sus resultados y responde por ella.

## Resumen

| Integrante | Rol | Responsable de |
|---|---|---|
| Sebastián Rodríguez López | **Líder**: coordinación y documentación | Repositorio, README, arquitectura y diagramas, declaración de aportes y de uso de IA |
| Santiago Alzate Serna | Firmware del ESP32-C6 | ADC con DMA, presets, ventanas, SPI esclavo y autoprueba |
| Mateo Duque Gaviria | Protocolo y comunicación SPI | Protocolo v1.1, driver SPI maestro, sincronización con READY y velocidad máxima del SPI |
| Mateo Palacios López | Software de la Raspberry Pi | Backend, API HTTP, nginx, servicio de arranque e instalación |
| William Camilo Obando | Dashboard e integración | Dashboard web, integración de las dos placas y video |
| Jhojan Andrey Buritica | Verificación y pruebas | Matriz de verificación, experimentos, simulador y pruebas automáticas |

**Participación:** todos los integrantes participaron en todas las sesiones de trabajo. Se considera una participación equitativa (≈ 16,7 % cada uno).

**Commits:** la mayoría de los commits se hicieron desde la cuenta de GitHub de Sebastián Rodríguez López (SebastianRodriguez05), porque las sesiones fueron conjuntas en un mismo computador.

## Detalle por área

### Sebastián Rodríguez López: líder, coordinación y documentación
- Organización del plan de trabajo y de las sesiones conjuntas.
- Configuración del repositorio y del entorno de desarrollo (ESP-IDF en WSL2, GitHub).
- Documentación: `README.md`, `docs/01-arquitectura.md` (diagramas de bloques, de flujo y de secuencia; requerimientos y restricciones), `docs/aportes.md` y `docs/uso-ia.md`.

### Santiago Alzate Serna: firmware del ESP32-C6
- ADC con calibración y en modo continuo con DMA; presets de 100, 1.000, 10.000 y 40.000 Sa/s (promedio de 10 muestras para 100 Sa/s).
- Captura de ventanas de 256 muestras por canal, asignación de pines (CS en GPIO18, READY en GPIO19), SPI esclavo y autoprueba de 24 verificaciones.
- Evidencia: `firmware/osciloscopio/`.

### Mateo Duque Gaviria: protocolo y comunicación SPI
- Diseño del protocolo SPI v1.0 y v1.1 (comandos, respuestas, marca, checksum y línea READY).
- Driver SPI maestro, con la corrección de las lecturas prematuras (pausa y reintento).
- Tasas SPI: teórica a partir de las hojas de datos (40 MHz) y experimental con `barrido_spi.py` (25 MHz sin errores).
- Evidencia: `docs/protocolo-spi.md`, `sbc/backend/spi_osciloscopio.py`, `sbc/backend/barrido_spi.py`.

### Mateo Palacios López: software de la Raspberry Pi
- Preparación de la Raspberry Pi (sistema, red, SPI0, consola serial).
- Backend Flask con hilo de adquisición y API HTTP; sitio de nginx; servicio de systemd para el arranque autónomo; script de instalación.
- Evidencia: `sbc/backend/app.py`, `docs/api-http.md`, `sbc/nginx/`, `sbc/systemd/`, `sbc/instalar.sh`.

### William Camilo Obando: dashboard e integración
- Dashboard web con la gráfica de los dos canales, el selector de preset y el refresco de 1 a 4 s.
- Cableado e integración de la Pi con el ESP32-C6, y primera comunicación de punta a punta.
- Video del funcionamiento.
- Evidencia: `sbc/web/index.html`, prueba de integración en `sbc/README.md`.

### Jhojan Andrey Buritica: verificación y pruebas
- Matriz de verificación con métodos, criterios y resultados.
- Experimentos: frecuencia de muestreo con señal externa (PWM de la Pi), periodo de refresco del dashboard, ruido del ADC por el tráfico SPI y recuperación ante fallos.
- Simulador del ESP32-C6 y 28 pruebas automáticas con pytest.
- Evidencia: `docs/matriz-verificacion.md`, `sbc/backend/verificar_fs.py`, `medir_refresco.py`, `ruido_spi.py`, `simulador_esp32.py`, `tests/sbc/`.
