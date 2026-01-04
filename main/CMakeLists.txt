set(SOURCES 
  main.c 
  image_util.c
)

idf_component_register(SRCS ${SOURCES} 
                       INCLUDE_DIRS .
                       REQUIRES optflow esp_timer driver esp_common vl53l1x
)