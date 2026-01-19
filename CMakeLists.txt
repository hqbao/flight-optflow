# The following lines of boilerplate have to be in your project's
# CMakeLists in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.16)

set(EXTRA_COMPONENT_DIRS 
    "libs/optflow"
    "libs/vl53l1x"
    "libs/utils"
    "base/foundation"
    "base/boards/s3v1"
    "modules/camera"
    "modules/optical_flow"
    "modules/range_finder"
    "modules/telemetry"
    "modules/scheduler"
    "base/boards/s3v1/main"
)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(flight-optflow)

set(CMAKE_CXX_STANDARD 17)

