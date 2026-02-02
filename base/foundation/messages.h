#ifndef MESSAGES_H
#define MESSAGES_H

#include <stdint.h>

// Optical Flow Result (angular displacement in radians/frame)
typedef struct {
    float dx_rad;       // X angular displacement (radians/frame)
    float dy_rad;       // Y angular displacement (radians/frame)
    float rotation;     // Rotation around optical axis (radians/frame)
    float clarity;      // Gradient strength (texture quality metric)
    uint8_t quality;    // Quality 0-255
    uint32_t timestamp;
    uint32_t dt;        // Time delta (microseconds)
} optical_flow_result_t;

// Range Finder Result
typedef struct {
    float distance_mm;
    uint8_t status;
    uint32_t timestamp;
} range_finder_t;

// Camera Frame
#define CAM_WIDTH 64
#define CAM_HEIGHT 64

typedef struct {
    uint8_t data[CAM_WIDTH * CAM_HEIGHT];
    uint32_t timestamp;
} camera_frame_t;

#endif
