idf_component_register(SRCS "main.c"
                       INCLUDE_DIRS "."
                       REQUIRES camera optical_flow range_finder telemetry foundation board_config esp_timer nvs_flash scheduler)
