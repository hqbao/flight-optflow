idf_component_register(SRCS "main.c"
                       INCLUDE_DIRS "."
                       REQUIRES camera optical_flow range_finder telemetry foundation s3v1 esp_timer nvs_flash scheduler)
