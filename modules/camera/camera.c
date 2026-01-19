#include "camera.h"
#include <esp_camera.h>
#include <esp_log.h>
#include <esp_timer.h>
#include <platform.h>
#include <pubsub.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <image_util.h>

#define TAG "camera"

static uint8_t g_frame_buffer[CAM_WIDTH * CAM_HEIGHT];
static camera_frame_t g_camera_msg;
static TaskHandle_t g_camera_task_handle = NULL;

static void trigger_camera(uint8_t *data, size_t size) {
    if (g_camera_task_handle) {
        xTaskNotifyGive(g_camera_task_handle);
    }
}

#if OPTFLOW_METHOD_CROP
static void fast_center_crop(uint8_t *src, int src_w, int src_h, uint8_t *dst, int dst_w, int dst_h) {
    int start_x = (src_w - dst_w) / 2;
    int start_y = (src_h - dst_h) / 2;

    for (int i = 0; i < dst_h; i++) {
        const uint8_t *src_ptr = src + ((start_y + i) * src_w) + start_x;
        uint8_t *dst_ptr = dst + (i * dst_w);
        memcpy(dst_ptr, src_ptr, dst_w);
    }
}
#endif

static void camera_task(void *arg) {
    while (1) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            ESP_LOGE(TAG, "Capture failed");
            continue;
        }

        // OPTIMIZATION: Return buffer immediately to DMA engine to maximize frame rate.
        // Reading from the buffer after return is safe-ish here because processing (2ms) 
        // is much faster than the next DMA fill (>30ms) with multiple buffers.
        uint8_t *src_buf = fb->buf;
        size_t src_w = fb->width;
        size_t src_h = fb->height;
        
        esp_camera_fb_return(fb);

#if OPTFLOW_METHOD_CROP
        // Center Crop (Focus on center 64x64 for maximum detail/sharpness)
        // 5x Digital Zoom (320->64). High sensitivity for hover.
        fast_center_crop(src_buf, src_w, src_h, g_frame_buffer, CAM_WIDTH, CAM_HEIGHT);
#else
        // Resize (Downscale full FOV to 64x64)
        // Better for high speed, less sensitive to small drifts.
        int min_dim = (src_w < src_h) ? src_w : src_h; // Usually 240
        int off_x = (src_w - min_dim) / 2;
        int off_y = (src_h - min_dim) / 2;
        
        fast_crop_and_resize_bilinear(
            src_buf, src_w, src_h,
            g_frame_buffer, CAM_WIDTH, CAM_HEIGHT,
            off_x, off_y, min_dim, min_dim);
#endif
        
        // Populate message
        memcpy(g_camera_msg.data, g_frame_buffer, CAM_WIDTH * CAM_HEIGHT);
        g_camera_msg.timestamp = (uint32_t)esp_timer_get_time();

        publish(SENSOR_CAMERA_FRAME, (uint8_t*)&g_camera_msg, sizeof(camera_frame_t));
    }
}

void camera_setup(void) {
    camera_config_t config = {
        .pin_pwdn = PWDN_GPIO_NUM,
        .pin_reset = RESET_GPIO_NUM,
        .pin_xclk = XCLK_GPIO_NUM,
        .pin_sscb_sda = SIOD_GPIO_NUM,
        .pin_sscb_scl = SIOC_GPIO_NUM,
        .pin_d7 = Y9_GPIO_NUM,
        .pin_d6 = Y8_GPIO_NUM,
        .pin_d5 = Y7_GPIO_NUM,
        .pin_d4 = Y6_GPIO_NUM,
        .pin_d3 = Y5_GPIO_NUM,
        .pin_d2 = Y4_GPIO_NUM,
        .pin_d1 = Y3_GPIO_NUM,
        .pin_d0 = Y2_GPIO_NUM,
        .pin_vsync = VSYNC_GPIO_NUM,
        .pin_href = HREF_GPIO_NUM,
        .pin_pclk = PCLK_GPIO_NUM,
        .xclk_freq_hz = 20000000,
        .ledc_timer = LEDC_TIMER_0,
        .ledc_channel = LEDC_CHANNEL_0,
        .pixel_format = PIXFORMAT_GRAYSCALE,
        .frame_size = FRAMESIZE_QVGA,
        .jpeg_quality = 10,
        .fb_count = 3,
        .fb_location = CAMERA_FB_IN_PSRAM,
        .grab_mode = CAMERA_GRAB_LATEST,
    };

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed with error 0x%x", err);
        return;
    }

    subscribe(SCHEDULER_CORE0_HP_25HZ, trigger_camera);
    xTaskCreatePinnedToCore(camera_task, "camera_task", 4096, NULL, 20, &g_camera_task_handle, 0);
}
