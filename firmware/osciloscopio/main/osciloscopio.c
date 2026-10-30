#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_adc/adc_continuous.h"
#include "esp_timer.h"
#include "soc/soc_caps.h"

// Prueba del ADC en modo continuo (DMA): 2 canales, frecuencia fija.
// Cuenta cuantas muestras llegan por segundo de cada canal para medir la tasa real.

#define FREC_TOTAL_HZ   20000  // total del ADC: 2 canales x 10.000 Sa/s
#define TAM_LECTURA     256     // bytes que se recogen en cada lectura

void app_main(void)
{
    // 1) Crear el manejador del modo continuo (buffer interno del DMA)
    adc_continuous_handle_t adc;
    adc_continuous_handle_cfg_t manejador_cfg = {
        .max_store_buf_size = 4096,
        .conv_frame_size = TAM_LECTURA,
    };
    ESP_ERROR_CHECK(adc_continuous_new_handle(&manejador_cfg, &adc));

    // 2) Patron de conversion: canal 0 (GPIO0), luego canal 1 (GPIO1), y se repite
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
    ESP_ERROR_CHECK(adc_continuous_start(adc));
    printf("ADC continuo iniciado: %d Hz en total (%d Sa/s por canal)\n",
           FREC_TOTAL_HZ, FREC_TOTAL_HZ / 2);

    // 3) Recoger muestras y contarlas por canal durante intervalos de 1 s
    uint8_t buf[TAM_LECTURA];
    uint32_t recibidos = 0;
    uint32_t cuenta0 = 0, cuenta1 = 0, ultimo0 = 0, ultimo1 = 0;
    int64_t t_inicio = esp_timer_get_time();   // microsegundos

    while (1) {
        esp_err_t ret = adc_continuous_read(adc, buf, TAM_LECTURA, &recibidos, 1000);
        if (ret == ESP_OK) {
            for (uint32_t i = 0; i < recibidos; i += SOC_ADC_DIGI_RESULT_BYTES) {
                adc_digi_output_data_t *d = (adc_digi_output_data_t *)&buf[i];
                if (d->type2.channel == 0) { cuenta0++; ultimo0 = d->type2.data; }
                else if (d->type2.channel == 1) { cuenta1++; ultimo1 = d->type2.data; }
            }
        }

        int64_t ahora = esp_timer_get_time();
        if (ahora - t_inicio >= 1000000) {
            float segundos = (ahora - t_inicio) / 1e6f;
            printf("CH0: %6.0f Sa/s (ultimo=%4lu)   CH1: %6.0f Sa/s (ultimo=%4lu)\n",
                   cuenta0 / segundos, (unsigned long)ultimo0,
                   cuenta1 / segundos, (unsigned long)ultimo1);
            cuenta0 = cuenta1 = 0;
            t_inicio = ahora;
        }
    }
}
