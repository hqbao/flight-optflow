#!/bin/bash
#
# Build script for flight-optflow (ESP32-S3)
#
# USAGE:
#   ./build.sh [options]
#
# OPTIONS:
#   --rangefinder 0|1    Enable/disable VL53L1X range finder (default: 1)
#   --camera-dir  0|1    Camera direction: 0=downward, 1=upward (default: 0)
#   --crop        0|1    Optical flow method: 0=resize (wide FOV), 1=center crop (5x zoom) (default: 0)
#   --debug-log   0|1    Enable debug logging via ESP_LOGI (default: 0)
#   --clean               Clean build directory before building
#
# EXAMPLES:
#   ./build.sh                              # Build with defaults (downward camera, rangefinder on)
#   ./build.sh --camera-dir 1               # Build for upward-facing camera
#   ./build.sh --rangefinder 0              # Build without range finder
#   ./build.sh --crop 1 --debug-log 1       # Center crop mode with debug output
#   ./build.sh --clean                      # Full clean rebuild
#
# NOTES:
#   - ESP-IDF must be sourced first: source ~/skydev-research/esp/esp-idf/export.sh
#   - Options override defaults in board_config/platform.h via CMake -D flags
#   - Only specified options are overridden; others keep platform.h defaults
#

set -e

# Defaults (empty = use platform.h value)
RANGE_FINDER=""
CAMERA_DIR=""
CROP=""
DEBUG_LOG=""
CLEAN=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rangefinder)
            RANGE_FINDER="$2"; shift 2 ;;
        --camera-dir)
            CAMERA_DIR="$2"; shift 2 ;;
        --crop)
            CROP="$2"; shift 2 ;;
        --debug-log)
            DEBUG_LOG="$2"; shift 2 ;;
        --clean)
            CLEAN=1; shift ;;
        -h|--help)
            sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *)
            echo "Unknown option: $1"
            echo "Run ./build.sh --help for usage"
            exit 1 ;;
    esac
done

# Verify ESP-IDF is sourced
if ! command -v idf.py &>/dev/null; then
    echo "========================================"
    echo " ERROR: ESP-IDF environment not found"
    echo "========================================"
    echo ""
    echo " idf.py is not available in your PATH."
    echo ""
    echo " If ESP-IDF is already installed, source it first:"
    echo "   source ~/skydev-research/esp/esp-idf/export.sh"
    echo ""
    echo " If ESP-IDF is not installed, follow the setup guide:"
    echo "   https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/get-started/"
    echo ""
    echo " Quick install (macOS):"
    echo "   mkdir -p ~/esp && cd ~/esp"
    echo "   git clone --recursive https://github.com/espressif/esp-idf.git"
    echo "   cd esp-idf && ./install.sh esp32s3"
    echo "   source export.sh"
    echo "========================================"
    exit 1
fi

# Build cmake define flags
CMAKE_DEFS=""
[[ -n "$RANGE_FINDER" ]] && CMAKE_DEFS="$CMAKE_DEFS -DENABLE_RANGE_FINDER=$RANGE_FINDER"
[[ -n "$CAMERA_DIR" ]]   && CMAKE_DEFS="$CMAKE_DEFS -DCAMERA_DIRECTION=$CAMERA_DIR"
[[ -n "$CROP" ]]         && CMAKE_DEFS="$CMAKE_DEFS -DOPTFLOW_METHOD_CROP=$CROP"
[[ -n "$DEBUG_LOG" ]]    && CMAKE_DEFS="$CMAKE_DEFS -DENABLE_DEBUG_LOGGING=$DEBUG_LOG"

# Print config
echo "========================================"
echo " flight-optflow build (ESP32-S3 / s3v1)"
echo "========================================"
if [[ -n "$CMAKE_DEFS" ]]; then
    echo " Overrides:$CMAKE_DEFS"
else
    echo " Using platform.h defaults"
fi
echo "========================================"

# Clean if requested
if [[ $CLEAN -eq 1 ]]; then
    echo "Cleaning build..."
    idf.py fullclean
fi

# Build
if [[ -n "$CMAKE_DEFS" ]]; then
    idf.py build -- $CMAKE_DEFS
else
    idf.py build
fi
