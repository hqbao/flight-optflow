idf_component_register(SRCS "camera.c"
                       INCLUDE_DIRS "."
                       REQUIRES esp32-camera s3v1 foundation utils esp_timer)
