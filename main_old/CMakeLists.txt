set(SOURCES 
  main.c 
  image_util.c
)

set(OPTFLOW_DIR ../components/optflow)

idf_component_register(SRCS ${SOURCES} 
                       INCLUDE_DIRS . ${OPTFLOW_DIR}
                       REQUIRES esp_timer driver esp_common vl53l1x
)

add_library(optflow STATIC IMPORTED)
set_property(TARGET optflow PROPERTY IMPORTED_LOCATION "${CMAKE_CURRENT_LIST_DIR}/${OPTFLOW_DIR}/liboptflow-esp32s3.a")

target_link_libraries(${COMPONENT_LIB} PUBLIC optflow)