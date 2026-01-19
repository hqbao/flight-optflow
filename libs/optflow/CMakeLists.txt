idf_component_register(INCLUDE_DIRS ".")
target_link_libraries(${COMPONENT_LIB} INTERFACE "${CMAKE_CURRENT_LIST_DIR}/liboptflow-esp32s3.a")
