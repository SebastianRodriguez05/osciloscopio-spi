#include <stdio.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_adc/adc_continuous.h"
#include "esp_timer.h"
#include "soc/soc_caps.h"

// Captura de ventanas de 256 muestras por canal con presets de frecuencia.
// El preset de 100 Sa/s se obtiene muestreando a 1.000 Sa/s y promediando cada 10 muestras,
// porque el modo continuo del ESP32-C6 no baja de 611 Hz en total.

#define N_VENTANA       256     // muestras por canal en cada ventana
#define TAM_LECTURA     256     // bytes que se recogen en cada lectura

typedef struct {
    uint32_t fs_canal;        // frecuencia de salida por canal (Sa/s)
    uint32_t frec_adc_total;  // frecuencia total pedida al ADC (Hz, ambos canales)
    uint32_t promedio;        // muestras crudas que se promedian en una de salida
} preset_t;

static const preset_t PRESETS[] = {
    {   100,  2000, 10 },   // preset 0: 1.000 Sa/s crudas, promedio de 10
    {  1000,  2000,  1 },   // preset 1
    { 10000, 20000,  1 },   // preset 2
    { 40000, 80000,  1 },   // preset 3 (bonus)
};
#define N_PRESETS (sizeof(PRESETS) / sizeof(PRESETS[0]))

static adc_continuous_handle_t adc = NULL;
static uint16_t ventana0[N_VENTANA];   // canal 0 (GPIO0)
static uint16_t ventana1[N_VENTANA];   // canal 1 (GPIO1)

// (Re)configura el ADC para una frecuencia total. Si ya existia, lo libera primero.
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

// Llena ventana0 y ventana1 segun el preset. Devuelve la duracion en us.
static int64_t capturar_ventana(const preset_t *p)
{
    uint8_t buf[TAM_LECTURA];
    uint32_t recibidos = 0;
    int n0 = 0, n1 = 0;                 // muestras de salida guardadas
    uint32_t acum0 = 0, acum1 = 0;      // acumuladores para el promedio
    uint32_t k0 = 0, k1 = 0;            // muestras crudas acumuladas

    int64_t t0 = esp_timer_get_time();
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

    int64_t duracion = esp_timer_get_time() - t0;
    ESP_ERROR_CHECK(adc_continuous_stop(adc));
    ESP_ERROR_CHECK(adc_continuous_flush_pool(adc));
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
    printf("Prueba de presets: %d muestras por canal por ventana\n", N_VENTANA);

    while (1) {
        for (int i = 0; i < (int)N_PRESETS; i++) {
            const preset_t *p = &PRESETS[i];
            configurar_adc(p->frec_adc_total);
            int64_t duracion = capturar_ventana(p);
            int64_t esperado = 1000000LL * N_VENTANA / p->fs_canal;
            printf("Preset %d (%5lu Sa/s, ADC %5lu Hz, promedio %lu): %lld us (esperado ~%lld us)\n",
                   i, (unsigned long)p->fs_canal, (unsigned long)p->frec_adc_total,
                   (unsigned long)p->promedio, (long long)duracion, (long long)esperado);
            resumir("CH0", ventana0);
            resumir("CH1", ventana1);
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
        printf("----\n");
    }
}
