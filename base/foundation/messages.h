#ifndef MESSAGES_H
#define MESSAGES_H

#include <stdint.h>

// Optical Flow Result
typedef struct {
    float dx_mm;
    float dy_mm;
    float rotation;
    float clarity;
    uint8_t quality;
    uint32_t timestamp;
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
