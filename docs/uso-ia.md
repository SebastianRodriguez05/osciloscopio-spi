# Declaración de uso de inteligencia artificial

En este proyecto se usó IA como **asistente**: generó código, propuso pasos, comandos y diseños, y explicó conceptos y resultados. **El equipo verificó todo** lo que propuso: el código se compiló y se probó en el hardware real, los datos técnicos se contrastaron con las hojas de datos o con los archivos de ESP-IDF, y los resultados reportados son la salida real de las pruebas. Cuando algo no coincidía, se investigó y se corrigió (ver la sección de errores detectados).

**Forma de trabajo:** la IA propone un paso con comandos exactos y el resultado esperado; el equipo lo ejecuta y comparte la salida real; solo se avanza si el resultado coincide. Las decisiones de diseño (protocolo, pines, frecuencia de trabajo del SPI, alcance) las tomó el equipo.

## Herramientas usadas

| Quién | Modelo / herramienta | Uso |
|---|---|---|
| Todo el equipo, en sesiones conjuntas, desde la cuenta de claude.ai de Sebastián Rodríguez López | Claude Opus 5.5 (Anthropic), en claude.ai | Asistencia en todas las áreas descritas abajo |

Si algún integrante usó otra herramienta de IA por su cuenta, debe agregarla en esta tabla.

## Entorno y repositorio

| Tarea | Qué aportó la IA | Cómo se verificó |
|---|---|---|
| Plan del proyecto y roles | Propuesta del plan por pasos y de las áreas de trabajo | Revisado y ajustado por el equipo |
| Instalación de ESP-IDF en WSL2 y usbipd | Comandos de instalación y configuración | Compilación y grabación de programas en el ESP32-C6 |
| Repositorio | Estructura, `.gitignore` y flujo de commits | Publicado en GitHub; `git ls-files` confirma que `sdkconfig` no está incluido |
| Diagnóstico de Git | Detectó un programa sin guardar y un commit duplicado | `git status`, `git log --graph` y `git diff` |

## Raspberry Pi

| Tarea | Qué aportó la IA | Cómo se verificó |
|---|---|---|
| Sistema, SSH, nginx y SPI0 | Configuración y prueba de loopback del SPI | Loopback OK con jumper y FALLA sin él |
| WiFi con el punto de acceso del celular | Diagnóstico: el hotspot transmitía en 5 GHz y la Pi solo ve 2,4 GHz | `netsh wlan show interfaces` y `nmcli device wifi list`; la Pi se conectó al cambiar la banda |
| Consola serial con FTDI | Activación de `enable_uart=1`, cableado TX/RX cruzado y `plink` | Arranque de Linux visible e inicio de sesión por la consola serial |

## Firmware (ESP32-C6)

| Tarea | Qué aportó la IA | Cómo se verificó |
|---|---|---|
| ADC oneshot con calibración | Código en C | Cada canal a GND y a 3V3: 0 cuentas y 3.333 mV |
| ADC continuo con DMA | Código y límites del modo continuo | Tasas medidas por conteo; límites confirmados en `soc_caps.h` |
| Hipótesis de 40.322,58 Sa/s | Explicación por divisor entero del reloj del ADC | Confirmada con una señal externa (error −0,027 % frente a −0,826 % con la nominal) |
| Presets y ventanas | Código; estrategia de promedio para 100 Sa/s | Duraciones y ruido medidos en cada preset |
| Pines CS y READY | Análisis de los pines disponibles | Prueba física de los dos pines |
| SPI esclavo y protocolo v1.0/v1.1 | Propuesta del protocolo (aprobada por el equipo), código y autoprueba | Autoprueba 24/24; integración con la Pi |
| Captura sin tráfico SPI | Diagnóstico del ruido y corrección | `ruido_spi.py`: de 224 a 4–5 cuentas de pico |

## Software de la Raspberry Pi

| Tarea | Qué aportó la IA | Cómo se verificó |
|---|---|---|
| Driver SPI maestro | Código; diagnóstico de la lectura prematura y su corrección (pausa y reintento) | Integración: 0 errores; barrido de 1 a 25 MHz sin errores |
| Barrido de velocidades del SPI | Programa y cálculo de la frecuencia real (`core/CDIV`) | Dos corridas con los mismos resultados |
| Backend, API, dashboard, nginx, systemd e instalación | Código y configuración | `curl`, dashboard en el navegador, reinicio de la Pi sin SSH |
| Verificación con señal externa | Programa con el PWM por hardware de la Pi | Errores ≤ 0,03 % en los 4 presets |
| Medición del refresco | Registro de nginx con milisegundos y programa de medición | 1,000 / 2,001 / 2,978 / 4,010 s |
| Simulador y pruebas automáticas | Simulador del protocolo y 28 pruebas con pytest | 28/28 pruebas superadas |

## Documentación

| Tarea | Qué aportó la IA | Cómo se verificó |
|---|---|---|
| README, protocolo, API, arquitectura, matriz de verificación y aportes | Redacción y diagramas Mermaid | Revisados por el equipo; los resultados se copiaron de la salida real de las pruebas |

## Errores de la IA detectados y corregidos

- Anticipó que 3,3 V se leería cerca de 4.095 cuentas; en realidad son ~3.352 cuentas sin calibrar. Se agregó la calibración a mV.
- Un bloque de código Markdown anidado se rompió al copiarlo desde el chat. Se detectó con `grep` y `cat -A` y se corrigió con un script.
- Antes de revisar el `git diff`, propuso subir la versión local de un commit duplicado; la revisión mostró que la versión remota era la correcta.
- Su primera corrección de la lectura prematura en el SPI (esperar un flanco de READY con `gpiod`) no funcionó. El registro del ESP32-C6 mostró la causa real y se cambió por una pausa y un reintento.
- Propuso la opción `--accept-visibility-change-consequences` de GitHub CLI, que no existe en la versión instalada (2.46). Se usó la opción disponible.
- Durante la prueba de recuperación (V9), atribuyó la falla a un posible bloqueo del firmware; la causa era un cable de READY suelto, que encontró el equipo.
- Contó mal el número de casos de prueba esperados (26 en lugar de 28).

## Contenido de los chats

Los chats con la IA se encuentran en los siguientes enlaces:

- PEGA_AQUI_EL_ENLACE
