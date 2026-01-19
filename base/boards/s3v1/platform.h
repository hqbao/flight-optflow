#ifndef PLATFORM_H
#define PLATFORM_H

#include <stdio.h>

#define ENABLE_RANGE_FINDER 0
#define CAMERA_DIRECTION 2 // 1=downward, 2=upward

#define ENABLE_DEBUG_LOGGING 1

#define platform_console(fmt, ...) printf(fmt, ##__VA_ARGS__)

// Camera Pins
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39
#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

// I2C Pins
#define I2C_SDA_PIN       5
#define I2C_SCL_PIN       6

// UART Pins
#define UART_TX_PIN       43
#define UART_RX_PIN       44

#endif
