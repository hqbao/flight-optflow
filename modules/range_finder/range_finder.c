#include "range_finder.h"
#include <driver/i2c_master.h>
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
static i2c_master_bus_handle_t g_i2c_bus = NULL;
static i2c_master_dev_handle_t g_i2c_dev = NULL;

static void check_range_finder(uint8_t *data, size_t size) {
    uint8_t isReady = 0;
    VL53L1_GetMeasurementDataReady(&dev, &isReady);
    
    if (isReady) {
        VL53L1_RangingMeasurementData_t ranging_data;
        VL53L1_Error status = VL53L1_GetRangingMeasurementData(&dev, &ranging_data);
        
        if (status != VL53L1_RANGESTATUS_SIGNAL_FAIL) {
            g_range_msg.distance_mm = 1 + ranging_data.RangeMilliMeter;
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
    // I2C init (new master driver)
    i2c_master_bus_config_t bus_conf = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = I2C_SDA_PIN,
        .scl_io_num = I2C_SCL_PIN,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_conf, &g_i2c_bus));

    i2c_device_config_t dev_conf = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = VL53L1X_ADDRESS,
        .scl_speed_hz = 400000,
    };
    ESP_ERROR_CHECK(i2c_master_bus_add_device(g_i2c_bus, &dev_conf, &g_i2c_dev));

    dev.I2cHandle = g_i2c_dev;
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
