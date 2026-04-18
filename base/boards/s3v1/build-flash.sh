#!/bin/bash
#
# Build, flash and monitor flight-optflow (ESP32-S3)
#
# USAGE:
#   ./build-flash.sh [options] [--port /dev/cu.usbmodemXXXX]
#
# All options from build.sh are supported, plus:
#   --port PATH    Serial port for flashing (default: auto-detect)
#
# EXAMPLES:
#   ./build-flash.sh                                    # Build + flash + monitor
#   ./build-flash.sh --camera-dir 1                     # Upward camera, flash + monitor
#   ./build-flash.sh --port /dev/cu.usbmodem1101        # Specify serial port
#

set -e

PORT=""
BUILD_ARGS=()

# Separate --port from build args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)
            PORT="$2"; shift 2 ;;
        *)
            BUILD_ARGS+=("$1"); shift ;;
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

# Build first
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/build.sh" "${BUILD_ARGS[@]}"

# Flash and monitor
if [[ -n "$PORT" ]]; then
    idf.py -p "$PORT" flash monitor
else
    idf.py flash monitor
fi
