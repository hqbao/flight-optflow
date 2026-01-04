idf_component_register(SRCS "" INCLUDE_DIRS ".")

if(CONFIG_IDF_TARGET_ESP32S3)
    target_link_libraries(${COMPONENT_LIB} INTERFACE "${CMAKE_CURRENT_LIST_DIR}/liboptflow-esp32s3.a")
elseif(CONFIG_IDF_TARGET_ESP32P4)
    target_link_libraries(${COMPONENT_LIB} INTERFACE "${CMAKE_CURRENT_LIST_DIR}/liboptflow-esp32p4.a")
endif()
