#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"

// Lectura de prueba del ADC1: canal 0 (GPIO0) y canal 1 (GPIO1), en cuentas y en mV
void app_main(void)
{
    // 1) Crear la unidad ADC1 en modo "oneshot"
    adc_oneshot_unit_handle_t adc1;
    adc_oneshot_unit_init_cfg_t unidad_cfg = {
        .unit_id = ADC_UNIT_1,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&unidad_cfg, &adc1));

    // 2) Configurar los dos canales: atenuacion 12 dB, 12 bits
    adc_oneshot_chan_cfg_t canal_cfg = {
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc1, ADC_CHANNEL_0, &canal_cfg));
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc1, ADC_CHANNEL_1, &canal_cfg));

    // 3) Calibracion (curve fitting) con los datos de fabrica del chip, una por canal
    adc_cali_handle_t cali0, cali1;
    adc_cali_curve_fitting_config_t cali_cfg = {
        .unit_id = ADC_UNIT_1,
        .chan = ADC_CHANNEL_0,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    ESP_ERROR_CHECK(adc_cali_create_scheme_curve_fitting(&cali_cfg, &cali0));
    cali_cfg.chan = ADC_CHANNEL_1;
    ESP_ERROR_CHECK(adc_cali_create_scheme_curve_fitting(&cali_cfg, &cali1));

    // 4) Leer e imprimir cada 500 ms
    int crudo0 = 0, crudo1 = 0, mv0 = 0, mv1 = 0;
    while (1) {
        ESP_ERROR_CHECK(adc_oneshot_read(adc1, ADC_CHANNEL_0, &crudo0));
        ESP_ERROR_CHECK(adc_oneshot_read(adc1, ADC_CHANNEL_1, &crudo1));
        ESP_ERROR_CHECK(adc_cali_raw_to_voltage(cali0, crudo0, &mv0));
        ESP_ERROR_CHECK(adc_cali_raw_to_voltage(cali1, crudo1, &mv1));
        printf("GPIO0=%4d (%4d mV)   GPIO1=%4d (%4d mV)\n", crudo0, mv0, crudo1, mv1);
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
