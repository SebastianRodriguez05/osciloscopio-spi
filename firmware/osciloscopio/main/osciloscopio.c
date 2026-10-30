#include <stdio.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_adc/adc_continuous.h"
#include "esp_timer.h"
#include "soc/soc_caps.h"

// Captura de ventanas: 256 muestras por canal con el ADC en modo continuo (DMA).

#define FREC_TOTAL_HZ   20000   // total del ADC: 2 canales x 10.000 Sa/s
#define N_VENTANA       256     // muestras por canal en cada ventana
#define TAM_LECTURA     256     // bytes que se recogen en cada lectura

static adc_continuous_handle_t adc;
static uint16_t ventana0[N_VENTANA];   // canal 0 (GPIO0)
static uint16_t ventana1[N_VENTANA];   // canal 1 (GPIO1)

// Configura el ADC (sin arrancarlo)
static void iniciar_adc(void)
{
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
        .sample_freq_hz = FREC_TOTAL_HZ,
        .conv_mode = ADC_CONV_SINGLE_UNIT_1,
        .format = ADC_DIGI_OUTPUT_FORMAT_TYPE2,
    };
    ESP_ERROR_CHECK(adc_continuous_config(adc, &cfg));
}

// Arranca el ADC, llena ventana0 y ventana1, lo detiene. Devuelve la duracion en us.
static int64_t capturar_ventana(void)
{
    uint8_t buf[TAM_LECTURA];
    uint32_t recibidos = 0;
    int n0 = 0, n1 = 0;

    int64_t t0 = esp_timer_get_time();
    ESP_ERROR_CHECK(adc_continuous_start(adc));

    while (n0 < N_VENTANA || n1 < N_VENTANA) {
        if (adc_continuous_read(adc, buf, TAM_LECTURA, &recibidos, 1000) != ESP_OK) {
            continue;
        }
        for (uint32_t i = 0; i < recibidos; i += SOC_ADC_DIGI_RESULT_BYTES) {
            adc_digi_output_data_t *d = (adc_digi_output_data_t *)&buf[i];
            uint16_t valor = d->type2.data;
            if (d->type2.channel == 0 && n0 < N_VENTANA) {
                ventana0[n0++] = valor;
            } else if (d->type2.channel == 1 && n1 < N_VENTANA) {
                ventana1[n1++] = valor;
            }
        }
    }

    int64_t duracion = esp_timer_get_time() - t0;
    ESP_ERROR_CHECK(adc_continuous_stop(adc));
    ESP_ERROR_CHECK(adc_continuous_flush_pool(adc));   // descarta muestras sobrantes
    return duracion;
}

// Imprime minimo, maximo, promedio y las primeras 8 muestras de una ventana
static void resumir(const char *nombre, const uint16_t *v)
{
    uint32_t suma = 0;
    uint16_t minimo = 4095, maximo = 0;
    for (int i = 0; i < N_VENTANA; i++) {
        suma += v[i];
        if (v[i] < minimo) minimo = v[i];
        if (v[i] > maximo) maximo = v[i];
    }
    printf("  %s: min=%4u max=%4u prom=%4lu | primeras: ", nombre, minimo, maximo,
           (unsigned long)(suma / N_VENTANA));
    for (int i = 0; i < 8; i++) printf("%4u ", v[i]);
    printf("\n");
}

void app_main(void)
{
    iniciar_adc();
    printf("Captura de ventanas: %d muestras por canal a %d Sa/s por canal\n",
           N_VENTANA, FREC_TOTAL_HZ / 2);

    int numero = 0;
    while (1) {
        int64_t duracion = capturar_ventana();
        printf("Ventana %d: %lld us (esperado ~%d us)\n", numero++,
               (long long)duracion, (int)(1000000LL * N_VENTANA / (FREC_TOTAL_HZ / 2)));
        resumir("CH0", ventana0);
        resumir("CH1", ventana1);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}
