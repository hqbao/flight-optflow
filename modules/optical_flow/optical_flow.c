#include "optical_flow.h"
#include <platform.h>
#include <pubsub.h>
#include <optflow.h>
#include <esp_timer.h>
#include <string.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

static optical_flow_result_t g_optflow_msg;
static uint8_t g_frame_buffer[CAM_WIDTH * CAM_HEIGHT];
static TaskHandle_t g_optflow_task = NULL;
static volatile bool g_processing_busy = false;

static void optical_flow_task_runner(void *arg) {
    while (1) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

        float clarity = 0;
        float dx_mm = 0;
        float dy_mm = 0;
        float rotation = 0;
        int mode = 0;

        // Perform heavy calculation on Core 1
        optflow_calc(g_frame_buffer, &dy_mm, &dx_mm, &rotation, &clarity, &mode);

        g_optflow_msg.dx_mm = dx_mm;
        g_optflow_msg.dy_mm = dy_mm;
        g_optflow_msg.rotation = rotation;
        g_optflow_msg.clarity = clarity;
        g_optflow_msg.quality = (uint8_t)(clarity * 10);
        g_optflow_msg.timestamp = (uint32_t)esp_timer_get_time();

        publish(SENSOR_OPTFLOW, (uint8_t*)&g_optflow_msg, sizeof(optical_flow_result_t));
        
        // Mark buffer as free for next frame
        g_processing_busy = false;
    }
}

static void on_camera_frame(uint8_t *data, size_t size) {
    if (size != sizeof(camera_frame_t)) return;
    
    // Simple protection: Drop frame if previous one is still processing
    // This prevents tearing (overwriting g_frame_buffer while Core 1 is reading it)
    if (g_processing_busy) {
        return; 
    }
    
    // Lock buffer
    g_processing_busy = true;

    camera_frame_t *frame = (camera_frame_t*)data;

    // Copy frame data from Core 0 context to shared buffer
    memcpy(g_frame_buffer, frame->data, CAM_WIDTH * CAM_HEIGHT);
    
    // Notify Core 1 task to process
    if (g_optflow_task) {
        xTaskNotifyGive(g_optflow_task);
    }
}

void optical_flow_setup(void) {
#if OPTFLOW_METHOD_CROP
    // Correct FOV for Center Crop (64x64 cropped from 320x240)
    // Original FOV: 66 deg. Zoom Factor: 320/64 = 5.
    // New FOV: 66 / 5 = 13.2 deg.
    optflow_camera_fov_degrees = 13.2f;
#else
    // Resize Mode: Takes 240x240 center and downscales.
    // FOV is approx 75% of full horizontal FOV.
    optflow_camera_fov_degrees = 49.5f;
#endif

    optflow_init(CAM_WIDTH, CAM_HEIGHT, 0); // 0 = Dense Mode (Lucas-Kanade)
    
    // Create Optical Flow Task on Core 1 (Priority 20, same as Camera but less than High Band)
    xTaskCreatePinnedToCore(optical_flow_task_runner, "optflow_task", 4096, NULL, 20, &g_optflow_task, 1);
    
    subscribe(SENSOR_CAMERA_FRAME, on_camera_frame);
}
