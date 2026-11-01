#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_adc/adc_continuous.h"
#include "esp_timer.h"
#include "esp_attr.h"
#include "soc/soc_caps.h"
#include "driver/gpio.h"
#include "driver/spi_slave.h"

// Firmware del osciloscopio: SPI esclavo con el protocolo v1.0 (docs/protocolo-spi.md)
// y captura de ventanas de 256 muestras por canal con presets de frecuencia.

// ---------- Pines ----------
#define PIN_SCLK    GPIO_NUM_6
#define PIN_MOSI    GPIO_NUM_7
#define PIN_MISO    GPIO_NUM_2
#define PIN_CS      GPIO_NUM_18
#define PIN_READY   GPIO_NUM_19

// ---------- Protocolo v1.0 ----------
#define MARCA               0xA5
#define CMD_SET_PRESET      0x01
#define CMD_START_CAPTURE   0x02
#define CMD_STATUS          0x03
#define CMD_READ_WINDOW     0x04
#define TAM_CMD             4
#define TAM_STATUS          16
#define TAM_VENTANA         1036
#define ESTADO_ESPERA       0
#define ESTADO_CAPTURANDO   1
#define ESTADO_LISTA        2
#define ERR_OK              0
#define ERR_CMD             1
#define ERR_OCUPADO         2
#define ERR_ARG             3

// ---------- Muestreo ----------
#define N_VENTANA    256     // muestras por canal en cada ventana
#define TAM_LECTURA  256     // bytes que se recogen del DMA en cada lectura

typedef struct {
    uint32_t fs_canal;        // frecuencia de salida por canal (Sa/s)
    uint32_t frec_adc_total;  // frecuencia total pedida al ADC (Hz)
    uint32_t promedio;        // muestras crudas promediadas en una de salida
    uint32_t fs_real_mhz;     // frecuencia real por canal (mHz) que se informa a la Pi
} preset_t;

static const preset_t PRESETS[] = {
    {   100,  2000, 10,   100000 },   // 0: 1.000 Sa/s promediadas de a 10
    {  1000,  2000,  1,  1000000 },   // 1
    { 10000, 20000,  1, 10000000 },   // 2
    { 40000, 80000,  1, 40322580 },   // 3 (bonus, valor medido)
};
#define N_PRESETS       ((uint8_t)(sizeof(PRESETS) / sizeof(PRESETS[0])))
#define PRESET_INICIAL  2

// ---------- Estado compartido entre tareas ----------
static volatile uint8_t  estado = ESTADO_ESPERA;
static volatile uint8_t  preset_actual = PRESET_INICIAL;
static volatile uint8_t  ultimo_error = ERR_OK;
static volatile uint16_t n_ventana = 0;
static volatile bool     ventana_valida = false;
static TaskHandle_t      tarea_captura = NULL;

static adc_continuous_handle_t adc = NULL;
static int preset_configurado = -1;
static uint16_t ventana0[N_VENTANA];
static uint16_t ventana1[N_VENTANA];

// Buffers para el DMA del SPI (alineados a 4 bytes)
WORD_ALIGNED_ATTR static uint8_t buf_cmd[TAM_CMD];
WORD_ALIGNED_ATTR static uint8_t buf_ceros[TAM_CMD];
WORD_ALIGNED_ATTR static uint8_t buf_status[TAM_STATUS];
WORD_ALIGNED_ATTR static uint8_t paquete_ventana[TAM_VENTANA];
WORD_ALIGNED_ATTR static uint8_t paquete_vacio[TAM_VENTANA];

// ---------- Utilidades little-endian y checksum ----------
static void escribir_u16(uint8_t *p, uint16_t v) { p[0] = v & 0xFF; p[1] = v >> 8; }
static void escribir_u32(uint8_t *p, uint32_t v) {
    p[0] = v & 0xFF; p[1] = (v >> 8) & 0xFF; p[2] = (v >> 16) & 0xFF; p[3] = v >> 24;
}
static uint16_t leer_u16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t leer_u32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static uint32_t calcular_checksum(const uint8_t *p, size_t n) {
    uint32_t suma = 0;
    for (size_t i = 0; i < n; i++) suma += p[i];
    return suma;
}

// ---------- ADC ----------
static void configurar_adc(uint32_t frec_total)
{
    if (adc != NULL) {
        ESP_ERROR_CHECK(adc_continuous_deinit(adc));
        adc = NULL;
    }
    adc_continuous_handle_cfg_t manejador_cfg = {
        .max_store_buf_size = 4096,
        .conv_frame_size = TAM_LECTURA,
    };
    ESP_ERROR_CHECK(adc_continuous_new_handle(&manejador_cfg, &adc));

    adc_digi_pattern_config_t patron[2] = {0};
    for (int i = 0; i < 2; i++) {
        patron[i].atten = ADC_ATTEN_DB_12;
        patron[i].channel = i;
        patron[i].unit = ADC_UNIT_1;
        patron[i].bit_width = SOC_ADC_DIGI_MAX_BITWIDTH;
    }
    adc_continuous_config_t cfg = {
        .pattern_num = 2,
        .adc_pattern = patron,
        .sample_freq_hz = frec_total,
        .conv_mode = ADC_CONV_SINGLE_UNIT_1,
        .format = ADC_DIGI_OUTPUT_FORMAT_TYPE2,
    };
    ESP_ERROR_CHECK(adc_continuous_config(adc, &cfg));
}

static void capturar_ventana(const preset_t *p)
{
    uint8_t buf[TAM_LECTURA];
    uint32_t recibidos = 0;
    int n0 = 0, n1 = 0;
    uint32_t acum0 = 0, acum1 = 0, k0 = 0, k1 = 0;

    ESP_ERROR_CHECK(adc_continuous_start(adc));
    while (n0 < N_VENTANA || n1 < N_VENTANA) {
        if (adc_continuous_read(adc, buf, TAM_LECTURA, &recibidos, 1000) != ESP_OK) {
            continue;
        }
        for (uint32_t i = 0; i < recibidos; i += SOC_ADC_DIGI_RESULT_BYTES) {
            adc_digi_output_data_t *d = (adc_digi_output_data_t *)&buf[i];
            uint32_t valor = d->type2.data;
            if (d->type2.channel == 0 && n0 < N_VENTANA) {
                acum0 += valor;
                if (++k0 == p->promedio) {
                    ventana0[n0++] = (uint16_t)((acum0 + p->promedio / 2) / p->promedio);
                    acum0 = 0; k0 = 0;
                }
            } else if (d->type2.channel == 1 && n1 < N_VENTANA) {
                acum1 += valor;
                if (++k1 == p->promedio) {
                    ventana1[n1++] = (uint16_t)((acum1 + p->promedio / 2) / p->promedio);
                    acum1 = 0; k1 = 0;
                }
            }
        }
    }
    ESP_ERROR_CHECK(adc_continuous_stop(adc));
    ESP_ERROR_CHECK(adc_continuous_flush_pool(adc));
}

// ---------- Armado de respuestas ----------
static void armar_status(void)
{
    memset(buf_status, 0, TAM_STATUS);
    buf_status[0] = MARCA;
    buf_status[1] = estado;
    buf_status[2] = preset_actual;
    buf_status[3] = ultimo_error;
    escribir_u32(&buf_status[4], PRESETS[preset_actual].fs_real_mhz);
    escribir_u16(&buf_status[8], N_VENTANA);
    escribir_u16(&buf_status[10], n_ventana);
}

static void armar_encabezado(uint8_t *paq, uint8_t preset, uint16_t n_muestras)
{
    paq[0] = MARCA;
    paq[1] = preset;
    escribir_u16(&paq[2], n_muestras);
    escribir_u32(&paq[4], PRESETS[preset].fs_real_mhz);
}

static void armar_paquete_ventana(uint8_t preset)
{
    armar_encabezado(paquete_ventana, preset, N_VENTANA);
    for (int i = 0; i < N_VENTANA; i++) {
        escribir_u16(&paquete_ventana[8 + 2 * i], ventana0[i]);
        escribir_u16(&paquete_ventana[520 + 2 * i], ventana1[i]);
    }
    escribir_u32(&paquete_ventana[1032], calcular_checksum(paquete_ventana, 1032));
}

static void armar_paquete_vacio(void)
{
    memset(paquete_vacio, 0, TAM_VENTANA);
    armar_encabezado(paquete_vacio, preset_actual, 0);
    escribir_u32(&paquete_vacio[1032], calcular_checksum(paquete_vacio, 1032));
}

// ---------- Procesamiento de comandos (lo usan el SPI y la autoprueba) ----------
static void procesar_comando(uint8_t cmd, uint8_t arg, const uint8_t **resp, size_t *len)
{
    switch (cmd) {
    case CMD_SET_PRESET:
        if (estado == ESTADO_CAPTURANDO)  ultimo_error = ERR_OCUPADO;
        else if (arg >= N_PRESETS)        ultimo_error = ERR_ARG;
        else { preset_actual = arg;       ultimo_error = ERR_OK; }
        break;
    case CMD_START_CAPTURE:
        if (estado == ESTADO_CAPTURANDO) {
            ultimo_error = ERR_OCUPADO;
        } else {
            ventana_valida = false;
            estado = ESTADO_CAPTURANDO;
            ultimo_error = ERR_OK;
            xTaskNotifyGive(tarea_captura);
        }
        break;
    case CMD_STATUS:
        ultimo_error = ERR_OK;
        break;
    case CMD_READ_WINDOW:
        ultimo_error = ERR_OK;
        if (ventana_valida) {
            *resp = paquete_ventana;
        } else {
            armar_paquete_vacio();
            *resp = paquete_vacio;
        }
        *len = TAM_VENTANA;
        return;
    default:
        ultimo_error = ERR_CMD;
        break;
    }
    armar_status();
    *resp = buf_status;
    *len = TAM_STATUS;
}

// ---------- Tarea de captura ----------
static void tarea_captura_fn(void *arg)
{
    while (1) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);       // espera START_CAPTURE
        uint8_t preset = preset_actual;
        if (preset_configurado != preset) {
            configurar_adc(PRESETS[preset].frec_adc_total);
            preset_configurado = preset;
        }
        capturar_ventana(&PRESETS[preset]);
        armar_paquete_ventana(preset);
        n_ventana++;
        ventana_valida = true;
        estado = ESTADO_LISTA;
    }
}

// ---------- SPI esclavo ----------
// READY sube cuando una transaccion queda lista en el hardware y baja al terminar.
static void IRAM_ATTR cb_transaccion_lista(spi_slave_transaction_t *t) { gpio_set_level(PIN_READY, 1); }
static void IRAM_ATTR cb_transaccion_fin(spi_slave_transaction_t *t)   { gpio_set_level(PIN_READY, 0); }

static void iniciar_spi(void)
{
    gpio_config_t ready = {
        .pin_bit_mask = 1ULL << PIN_READY,
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&ready));
    gpio_set_level(PIN_READY, 0);

    // Pull-ups para que, sin la Pi conectada, no aparezcan transacciones falsas
    gpio_set_pull_mode(PIN_MOSI, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(PIN_SCLK, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(PIN_CS, GPIO_PULLUP_ONLY);

    spi_bus_config_t bus = {
        .mosi_io_num = PIN_MOSI,
        .miso_io_num = PIN_MISO,
        .sclk_io_num = PIN_SCLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = TAM_VENTANA,
    };
    spi_slave_interface_config_t esclavo = {
        .mode = 0,
        .spics_io_num = PIN_CS,
        .queue_size = 1,
        .flags = 0,
        .post_setup_cb = cb_transaccion_lista,
        .post_trans_cb = cb_transaccion_fin,
    };
    ESP_ERROR_CHECK(spi_slave_initialize(SPI2_HOST, &bus, &esclavo, SPI_DMA_CH_AUTO));
}

static void tarea_spi_fn(void *arg)
{
    spi_slave_transaction_t t;
    while (1) {
        // Fase 1: recibir el comando (4 bytes)
        memset(buf_cmd, 0, TAM_CMD);
        memset(&t, 0, sizeof(t));
        t.length = TAM_CMD * 8;
        t.tx_buffer = buf_ceros;
        t.rx_buffer = buf_cmd;
        ESP_ERROR_CHECK(spi_slave_transmit(SPI2_HOST, &t, portMAX_DELAY));
        if (t.trans_len < TAM_CMD * 8) {
            printf("SPI: comando incompleto (%u bits), se ignora\n", (unsigned)t.trans_len);
            continue;
        }

        const uint8_t *resp = NULL;
        size_t len = 0;
        procesar_comando(buf_cmd[0], buf_cmd[1], &resp, &len);
        printf("SPI: cmd=0x%02X arg=%u -> error=%u, respuesta de %u bytes\n",
               buf_cmd[0], buf_cmd[1], ultimo_error, (unsigned)len);

        // Fase 2: entregar la respuesta
        memset(&t, 0, sizeof(t));
        t.length = len * 8;
        t.tx_buffer = resp;
        t.rx_buffer = NULL;
        ESP_ERROR_CHECK(spi_slave_transmit(SPI2_HOST, &t, portMAX_DELAY));
    }
}

// ---------- Autoprueba del protocolo (sin la Pi) ----------
static int fallas = 0;
#define VERIFICAR(cond, desc) do { \
    if (cond) printf("  PASA:  %s\n", desc); \
    else { printf("  FALLA: %s\n", desc); fallas++; } } while (0)

static bool esperar_lista(int timeout_ms)
{
    for (int t = 0; t < timeout_ms; t += 10) {
        if (estado == ESTADO_LISTA) return true;
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    return false;
}

static void autoprueba(void)
{
    const uint8_t *r = NULL;
    size_t n = 0;
    char desc[96];

    printf("=== Autoprueba del protocolo ===\n");
    procesar_comando(CMD_STATUS, 0, &r, &n);
    VERIFICAR(n == TAM_STATUS && r[0] == MARCA && r[1] == ESTADO_ESPERA && r[2] == PRESET_INICIAL,
              "STATUS inicial: marca, en espera, preset 2");
    procesar_comando(0x7F, 0, &r, &n);
    VERIFICAR(r[3] == ERR_CMD, "Comando desconocido -> error 1");
    procesar_comando(CMD_SET_PRESET, 9, &r, &n);
    VERIFICAR(r[3] == ERR_ARG, "SET_PRESET 9 -> error 3");
    procesar_comando(CMD_READ_WINDOW, 0, &r, &n);
    VERIFICAR(n == TAM_VENTANA && r[0] == MARCA && leer_u16(&r[2]) == 0 &&
              leer_u32(&r[1032]) == calcular_checksum(r, 1032),
              "READ_WINDOW sin ventana -> n_muestras 0 y checksum valido");

    for (uint8_t p = 0; p < N_PRESETS; p++) {
        printf("-- Preset %u (%lu Sa/s) --\n", p, (unsigned long)PRESETS[p].fs_canal);
        procesar_comando(CMD_SET_PRESET, p, &r, &n);
        VERIFICAR(r[3] == ERR_OK && r[2] == p, "SET_PRESET aceptado");
        procesar_comando(CMD_START_CAPTURE, 0, &r, &n);
        VERIFICAR(r[3] == ERR_OK && r[1] == ESTADO_CAPTURANDO, "START_CAPTURE -> capturando");
        procesar_comando(CMD_START_CAPTURE, 0, &r, &n);
        bool ocupado_ok = (r[3] == ERR_OCUPADO) || (estado == ESTADO_LISTA);  // el preset 3 puede terminar muy rapido
        VERIFICAR(ocupado_ok, "START_CAPTURE repetido -> error 2 (o ya termino)");
        VERIFICAR(esperar_lista(5000), "La ventana queda lista en menos de 5 s");

        procesar_comando(CMD_READ_WINDOW, 0, &r, &n);
        uint32_t suma0 = 0, suma1 = 0;
        for (int i = 0; i < N_VENTANA; i++) {
            suma0 += leer_u16(&r[8 + 2 * i]);
            suma1 += leer_u16(&r[520 + 2 * i]);
        }
        snprintf(desc, sizeof(desc), "VENTANA: marca, preset, 256 muestras, fs=%lu mHz, checksum",
                 (unsigned long)leer_u32(&r[4]));
        VERIFICAR(n == TAM_VENTANA && r[0] == MARCA && r[1] == p && leer_u16(&r[2]) == N_VENTANA &&
                  leer_u32(&r[4]) == PRESETS[p].fs_real_mhz &&
                  leer_u32(&r[1032]) == calcular_checksum(r, 1032), desc);
        printf("        promedio CH0 = %lu, CH1 = %lu (cuentas)\n",
               (unsigned long)(suma0 / N_VENTANA), (unsigned long)(suma1 / N_VENTANA));
    }

    printf("=== Autoprueba terminada: %d falla(s) ===\n", fallas);

    // Volver al estado inicial antes de atender a la Pi
    estado = ESTADO_ESPERA;
    preset_actual = PRESET_INICIAL;
    ultimo_error = ERR_OK;
    n_ventana = 0;
    ventana_valida = false;
}

void app_main(void)
{
    xTaskCreate(tarea_captura_fn, "captura", 4096, NULL, 5, &tarea_captura);
    autoprueba();
    iniciar_spi();
    xTaskCreate(tarea_spi_fn, "spi", 4096, NULL, 6, NULL);
    printf("SPI esclavo listo (CLK=GPIO6, MOSI=GPIO7, MISO=GPIO2, CS=GPIO18, READY=GPIO19)\n");
    printf("Esperando comandos de la Pi...\n");
}
