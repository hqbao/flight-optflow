idf_component_register(SRCS "range_finder.c"
                       INCLUDE_DIRS "."
                       REQUIRES vl53l1x foundation board_config esp_timer driver)
