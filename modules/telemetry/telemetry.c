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
    if (of->dt > 0) {
        fps = 1000000.0f / (float)of->dt;
    }

    ESP_LOGI(TAG, "OF: dx=%.4f \tdy=%.4f rad \tqual=%d \tRF: dist=%.1f \tFreq: %.1f Hz \tdt: %lu",
        -of->dx_rad, of->dy_rad, of->quality,
        g_latest_z_mm, fps, of->dt);
#endif

    // Construct protocol message
    // [ 'd', 'b', 0x01, direction, len_low, len_high, dx(4), dy(4), z(4), quality(4), chk(2) ]
    // dx/dy are radians scaled by 100000 for int32 transmission
    
    static uint8_t msg[64]; // Use stack buffer
    msg[0] = 'd';
    msg[1] = 'b';
    msg[2] = 0x01;
    msg[3] = CAMERA_DIRECTION;

    int idx = 6;

    // Scale radians to int32: multiply by 100000 for ~0.00001 rad precision
    int dx_int = (int)(-of->dx_rad * 100000.0f); // Note: negated dx
    int dy_int = (int)(of->dy_rad * 100000.0f);
    int z_int = (int)g_latest_z_mm;
    int quality_int = (int)(of->clarity * 10);

    memcpy(&msg[idx], &dx_int, 4); idx += 4;
    memcpy(&msg[idx], &dy_int, 4); idx += 4;
    memcpy(&msg[idx], &z_int, 4); idx += 4;
    memcpy(&msg[idx], &quality_int, 4); idx += 4;

    uint16_t payload_size = idx - 6;
    memcpy(&msg[4], &payload_size, 2);
    
    // Checksum (UBX algorithm: Class + ID + Len + Payload)
    uint8_t ck_a = 0, ck_b = 0;
    for (int i = 2; i < idx; i++) {
        ck_a = ck_a + msg[i];
        ck_b = ck_b + ck_a;
    }
    
    msg[idx++] = ck_a;
    msg[idx++] = ck_b;

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
