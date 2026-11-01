idf_component_register(SRCS "osciloscopio.c"
                    INCLUDE_DIRS "."
                    REQUIRES esp_adc esp_timer esp_driver_gpio esp_driver_spi)
