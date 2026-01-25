cmake_minimum_required(VERSION 3.16)

# Calculate relative path to project root (flight-optflow)
get_filename_component(PROJECT_PATH "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)

set(EXTRA_COMPONENT_DIRS 
    "${PROJECT_PATH}/libs/optflow"
    "${PROJECT_PATH}/libs/vl53l1x"
    "${PROJECT_PATH}/libs/utils"
    "${PROJECT_PATH}/base/foundation"
    "board_config"
    "${PROJECT_PATH}/modules/camera"
    "${PROJECT_PATH}/modules/optical_flow"
    "${PROJECT_PATH}/modules/range_finder"
    "${PROJECT_PATH}/modules/telemetry"
    "${PROJECT_PATH}/modules/scheduler"
    "main"
)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(flight-optflow)
