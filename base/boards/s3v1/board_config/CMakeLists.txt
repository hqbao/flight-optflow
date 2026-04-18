idf_component_register(INCLUDE_DIRS ".")

# Allow build-time overrides via: idf.py -DENABLE_RANGE_FINDER=0 build
# These propagate to all components that depend on board_config.
foreach(_def ENABLE_RANGE_FINDER CAMERA_DIRECTION OPTFLOW_METHOD_CROP ENABLE_DEBUG_LOGGING ENABLE_FRAME_TRANSMISSION)
    if(DEFINED ${_def})
        target_compile_definitions(${COMPONENT_LIB} INTERFACE ${_def}=${${_def}})
    endif()
endforeach()
