#include "telemetry.h"
#include <driver/uart.h>
#include <string.h>
#include <pubsub.h>
#include <platform.h>
#include <esp_log.h>
#include "messages.h"

#define TAG "telemetry"
#define UART_PORT UART_NUM_1
#define UART_BAUD_RATE 19200

static float g_latest_z_mm = 0;
#if ENABLE_DEBUG_LOGGING
static uint32_t g_last_timestamp = 0;
#endif

static void on_range_data(uint8_t *data, size_t size) {
    if (size != sizeof(range_finder_t)) return;
    range_finder_t *rf = (range_finder_t*)data;
    if (rf->status) {
        g_latest_z_mm = rf->distance_mm;
    } else {
        g_latest_z_mm = 0;
    }
}

static void on_optflow_data(uint8_t *data, size_t size) {
    if (size != sizeof(optical_flow_result_t)) return;
    optical_flow_result_t *of = (optical_flow_result_t*)data;

#if ENABLE_DEBUG_LOGGING
    float fps = 0;
    if (g_last_timestamp > 0) {
        uint32_t diff = of->timestamp - g_last_timestamp;
        if (diff > 0) {
            fps = 1000000.0f / (float)diff;
        }
    }
    g_last_timestamp = of->timestamp;

    ESP_LOGI(TAG, "OF: dx=%.2f \tdy=%.2f \tqual=%d \tRF: dist=%.1f \tFreq: %.1f Hz",
        -of->dx_mm, of->dy_mm, of->quality,
        g_latest_z_mm, fps);
#endif

    // Construct protocol message
    // [ 'd', 'b', 0x01, direction, len_low, len_high, dx(4), dy(4), z(4), quality(4), chk(2) ]
    // Replicating main.c structure:
    // g_db_msg[0-2] = 'd', 'b', 0x01
    // g_db_msg[3] = direction (0=down, 1=up)
    
    static uint8_t msg[256] = {'d', 'b', 0x01, CAMERA_DIRECTION}; 
    int idx = 6;

    int dx_int = (int)(-of->dx_mm * 1000); // Note: main.c negated dx
    int dy_int = (int)(of->dy_mm * 1000);
    int z_int = (int)g_latest_z_mm;
    int quality_int = (int)(of->clarity * 10);

    memcpy(&msg[idx], &dx_int, 4); idx += 4;
    memcpy(&msg[idx], &dy_int, 4); idx += 4;
    memcpy(&msg[idx], &z_int, 4); idx += 4;
    memcpy(&msg[idx], &quality_int, 4); idx += 4;

    uint16_t payload_size = idx - 6;
    memcpy(&msg[4], &payload_size, 2);
    
    // Checksum (unused in main.c logic but space reserved)
    msg[idx++] = 0;
    msg[idx++] = 0;

    uart_write_bytes(UART_PORT, (const char*)msg, idx);
}

void telemetry_setup(void) {
    const uart_config_t uart_config = {
        .baud_rate = UART_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_APB,
    };
    ESP_ERROR_CHECK(uart_param_config(UART_PORT, &uart_config));
    ESP_ERROR_CHECK(uart_driver_install(UART_PORT, 1024, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_set_pin(UART_PORT, UART_TX_PIN, UART_RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));

    subscribe(SENSOR_RANGE, on_range_data);
    subscribe(SENSOR_OPTFLOW, on_optflow_data);
}
