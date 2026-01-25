idf_component_register(SRCS "camera.c"
                       INCLUDE_DIRS "."
                       REQUIRES esp32-camera board_config foundation utils esp_timer)
