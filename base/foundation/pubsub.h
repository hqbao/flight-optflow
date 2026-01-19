#ifndef PUBSUB_H
#define PUBSUB_H

#include <stddef.h>
#include <stdint.h>

typedef enum {
	// === Scheduler Core 0 High Priority (Protocol/Wifi/Sensors) ===
	SCHEDULER_CORE0_HP_1000HZ,
	SCHEDULER_CORE0_HP_500HZ,
	SCHEDULER_CORE0_HP_250HZ,
	SCHEDULER_CORE0_HP_100HZ,
	SCHEDULER_CORE0_HP_50HZ,
	SCHEDULER_CORE0_HP_25HZ,
	SCHEDULER_CORE0_HP_10HZ,
	SCHEDULER_CORE0_HP_5HZ,
	SCHEDULER_CORE0_HP_1HZ,
    
	// === Scheduler Core 0 Low Priority ===
	SCHEDULER_CORE0_LP_50HZ,
	SCHEDULER_CORE0_LP_25HZ,
	SCHEDULER_CORE0_LP_10HZ,
	SCHEDULER_CORE0_LP_5HZ,
	SCHEDULER_CORE0_LP_1HZ,

	// === Scheduler Core 1 High Priority (Optical Flow/Heavy Math) ===
	SCHEDULER_CORE1_HP_1000HZ,
	SCHEDULER_CORE1_HP_500HZ,
	SCHEDULER_CORE1_HP_250HZ,
	SCHEDULER_CORE1_HP_100HZ,
	SCHEDULER_CORE1_HP_50HZ,
	SCHEDULER_CORE1_HP_25HZ,
	SCHEDULER_CORE1_HP_10HZ,
	SCHEDULER_CORE1_HP_5HZ,
	SCHEDULER_CORE1_HP_1HZ,
    
	// === Scheduler Core 1 Low Priority ===
	SCHEDULER_CORE1_LP_50HZ,
	SCHEDULER_CORE1_LP_25HZ,
	SCHEDULER_CORE1_LP_10HZ,
	SCHEDULER_CORE1_LP_5HZ,
	SCHEDULER_CORE1_LP_1HZ,

	SENSOR_CAMERA_FRAME,
	SENSOR_RANGE,
	SENSOR_OPTFLOW,
	TOPIC_NULL
} topic_t;

typedef void (*subscriber_callback_t)(uint8_t *data, size_t size);

void publish(topic_t topic, uint8_t *data, size_t size);
void subscribe(topic_t topic, subscriber_callback_t callback);

#endif
