idf_component_register(SRCS "range_finder.c"
                       INCLUDE_DIRS "."
                       REQUIRES vl53l1x foundation s3v1 esp_timer driver)
