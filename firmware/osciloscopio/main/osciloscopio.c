#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void app_main(void)
{
    int n = 0;
    while (1) {
        printf("Osciloscopio: latido %d\n", n);
        n++;
        vTaskDelay(pdMS_TO_TICKS(1000));   // espera 1 segundo
    }
}
