#ifndef PLATFORM_H
#define PLATFORM_H

#include <inttypes.h>
#include <esp_timer.h>

#define DEG2RAD 0.01745329251
#define RAD2DEG 57.2957795131

void delay(uint32_t ms);
void flash(uint8_t count);
int64_t get_time(void);
uint32_t millis(void);

#endif
