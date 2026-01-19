#include "range_finder.h"
#include <driver/i2c.h>
#include <esp_log.h>
#include <vl53l1_api.h>
#include <platform.h>
#include <pubsub.h>
#include <esp_timer.h>

#if ENABLE_RANGE_FINDER

#define TAG "range_finder"
#define VL53L1X_ADDRESS 0x29

static range_finder_t g_range_msg;
static VL53L1_Dev_t dev;
static int g_i2c_port = I2C_NUM_0;

static void check_range_finder(uint8_t *data, size_t size) {
    uint8_t isReady = 0;
    VL53L1_GetMeasurementDataReady(&dev, &isReady);
    
    if (isReady) {
        VL53L1_RangingMeasurementData_t ranging_data;
        VL53L1_Error status = VL53L1_GetRangingMeasurementData(&dev, &ranging_data);
        
        if (status != VL53L1_RANGESTATUS_SIGNAL_FAIL) {
            g_range_msg.distance_mm = ranging_data.RangeMilliMeter;
            g_range_msg.status = 1; // Valid
        } else {
            g_range_msg.status = 0; // Fail
        }
        g_range_msg.timestamp = (uint32_t)esp_timer_get_time();

        publish(SENSOR_RANGE, (uint8_t*)&g_range_msg, sizeof(range_finder_t));
        
        VL53L1_ClearInterruptAndStartMeasurement(&dev);
    }
}

void range_finder_setup(void) {
    // I2C init
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = I2C_SDA_PIN,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_io_num = I2C_SCL_PIN,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = 400000,
    };
    i2c_param_config(g_i2c_port, &conf);
    i2c_driver_install(g_i2c_port, conf.mode, 0, 0, 0);

    dev.I2cHandle = &g_i2c_port;
    dev.I2cDevAddr = 0x52; 

    // VL53L1 init sequence
    VL53L1_UserRoi_t roi0;
    roi0.TopLeftX = 0;
    roi0.BotRightX = 15;
    roi0.BotRightY = 0;
    roi0.TopLeftY = 15;

    VL53L1_WaitDeviceBooted(&dev);
    VL53L1_DataInit(&dev);
    VL53L1_StaticInit(&dev);
    VL53L1_SetDistanceMode(&dev, VL53L1_DISTANCEMODE_LONG);
    VL53L1_SetMeasurementTimingBudgetMicroSeconds(&dev, 20000);
    VL53L1_SetInterMeasurementPeriodMilliSeconds(&dev, 25);
    VL53L1_SetUserROI(&dev, &roi0);
    VL53L1_StartMeasurement(&dev);

    subscribe(SCHEDULER_CORE1_LP_50HZ, check_range_finder);
}

#else

void range_finder_setup(void) {
    ESP_LOGW("range_finder", "Range finder disabled by ENABLE_RANGE_FINDER");
}

#endif
