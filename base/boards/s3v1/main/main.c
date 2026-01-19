#include <stdio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <nvs_flash.h>
#include <esp_log.h>
#include <esp_timer.h>

#include "platform.h"
#include "camera.h"
#include "optical_flow.h"
#include "range_finder.h"
#include "telemetry.h"
#include "pubsub.h"
#include "scheduler.h"

#define TAG "main"

void app_main(void) {
    ESP_LOGI(TAG, "Starting Flight Optflow...");

    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
      ESP_ERROR_CHECK(nvs_flash_erase());
      ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize Modules
    ESP_LOGI(TAG, "Initializing Telemetry...");
    telemetry_setup();

    ESP_LOGI(TAG, "Initializing Camera...");
    camera_setup();

    ESP_LOGI(TAG, "Initializing Optical Flow...");
    optical_flow_setup();

#if ENABLE_RANGE_FINDER
    ESP_LOGI(TAG, "Initializing Range Finder...");
    range_finder_setup();
#endif

    ESP_LOGI(TAG, "Initializing Scheduler...");
    scheduler_init(); 

    ESP_LOGI(TAG, "System Started");
}
