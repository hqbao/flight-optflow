#include "scheduler.h"
#include <pubsub.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <driver/gptimer.h>
#include <esp_log.h>

#define TAG "scheduler"

static TaskHandle_t g_task_c0_high = NULL;
static TaskHandle_t g_task_c0_low = NULL;
static TaskHandle_t g_task_c1_high = NULL;
static TaskHandle_t g_task_c1_low = NULL;
static gptimer_handle_t g_gptimer = NULL;

typedef struct {
    int core_id;
    // High Priority Band (1ms tick)
    // Fast HP topics
    int t_1000hz; int t_500hz; int t_250hz; int t_100hz;
    // Slow HP topics (run on HP thread but less frequently)
    int t_hp_50hz; int t_hp_25hz; int t_hp_10hz; int t_hp_5hz; int t_hp_1hz;

    // Low Priority Band (20ms tick)
    int t_50hz; int t_25hz; int t_10hz; int t_5hz; int t_1hz;
    
    TaskHandle_t *low_task_handle; // Pointer to the low task handle to notify
} sched_map_t;

// Map frequencies to topics for Core 0
static sched_map_t MAP_C0 = { 
    0, 
    // HP Fast
    SCHEDULER_CORE0_HP_1000HZ, SCHEDULER_CORE0_HP_500HZ, SCHEDULER_CORE0_HP_250HZ, SCHEDULER_CORE0_HP_100HZ, 
    // HP Slow
    SCHEDULER_CORE0_HP_50HZ, SCHEDULER_CORE0_HP_25HZ, SCHEDULER_CORE0_HP_10HZ, SCHEDULER_CORE0_HP_5HZ, SCHEDULER_CORE0_HP_1HZ,

    // LP Band
    SCHEDULER_CORE0_LP_50HZ,   SCHEDULER_CORE0_LP_25HZ,  SCHEDULER_CORE0_LP_10HZ,  SCHEDULER_CORE0_LP_5HZ, SCHEDULER_CORE0_LP_1HZ,
    &g_task_c0_low
};

// Map frequencies to topics for Core 1
static sched_map_t MAP_C1 = { 
    1, 
    // HP Fast
    SCHEDULER_CORE1_HP_1000HZ, SCHEDULER_CORE1_HP_500HZ, SCHEDULER_CORE1_HP_250HZ, SCHEDULER_CORE1_HP_100HZ, 
    // HP Slow
    SCHEDULER_CORE1_HP_50HZ, SCHEDULER_CORE1_HP_25HZ, SCHEDULER_CORE1_HP_10HZ, SCHEDULER_CORE1_HP_5HZ, SCHEDULER_CORE1_HP_1HZ,

    // LP Band
    SCHEDULER_CORE1_LP_50HZ,   SCHEDULER_CORE1_LP_25HZ,  SCHEDULER_CORE1_LP_10HZ,  SCHEDULER_CORE1_LP_5HZ, SCHEDULER_CORE1_LP_1HZ,
    &g_task_c1_low
};

static bool IRAM_ATTR on_timer_alarm(gptimer_handle_t timer, const gptimer_alarm_event_data_t *edata, void *user_ctx) {
    BaseType_t high_task_awoken = pdFALSE;
    if (g_task_c0_high) vTaskNotifyGiveFromISR(g_task_c0_high, &high_task_awoken);
    if (g_task_c1_high) vTaskNotifyGiveFromISR(g_task_c1_high, &high_task_awoken);
    return high_task_awoken == pdTRUE;
}

static void scheduler_runner_high(void *arg) {
    sched_map_t *map = (sched_map_t *)arg;
    uint32_t tick = 0;
    
    ESP_LOGI(TAG, "High-Band Scheduler started on Core %d", map->core_id);

    while (1) {
        // High priority waits for Timer ISR
        uint32_t count = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        
        for (uint32_t i = 0; i < count; i++) {
            tick++; // 1 tick = 1ms (1000Hz)
            
            // --- High Priority Band ---
            publish(map->t_1000hz, NULL, 0);                   // 1ms
            if (tick % 2 == 0) publish(map->t_500hz, NULL, 0); // 2ms
            if (tick % 4 == 0) publish(map->t_250hz, NULL, 0); // 4ms
            if (tick % 10 == 0) publish(map->t_100hz, NULL, 0); // 10ms
            
            // --- Slow High Priority Band (New) ---
            if (tick % 20 == 0) publish(map->t_hp_50hz, NULL, 0);   // 20ms
            if (tick % 40 == 0) publish(map->t_hp_25hz, NULL, 0);   // 40ms
            if (tick % 100 == 0) publish(map->t_hp_10hz, NULL, 0);  // 100ms
            if (tick % 200 == 0) publish(map->t_hp_5hz, NULL, 0);   // 200ms
            if (tick % 1000 == 0) publish(map->t_hp_1hz, NULL, 0);  // 1000ms

            // --- Trigger Low Priority Band ---
            // Notify every 20ms (50Hz)
            if (tick % 20 == 0) {
                 if (*(map->low_task_handle)) xTaskNotifyGive(*(map->low_task_handle));
            }
            
            // overflow protection (LCM of 4, 10, 20 is 20, so 1M is safe)
            if (tick >= 1000000) tick = 0;
        }
    }
}

static void scheduler_runner_low(void *arg) {
    sched_map_t *map = (sched_map_t *)arg;
    uint32_t low_tick = 0;

    ESP_LOGI(TAG, "Low-Band Scheduler started on Core %d", map->core_id);

    while (1) {
        // Low priority waits for notification from High Task
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        
        low_tick++; // 1 tick = 20ms (50Hz)

        // --- Low Priority Band ---
        publish(map->t_50hz, NULL, 0);                        // 20ms * 1  = 20ms
        if (low_tick % 2 == 0) publish(map->t_25hz, NULL, 0); // 20ms * 2  = 40ms
        if (low_tick % 5 == 0) publish(map->t_10hz, NULL, 0); // 20ms * 5  = 100ms
        if (low_tick % 10 == 0) publish(map->t_5hz, NULL, 0); // 20ms * 10 = 200ms

        if (low_tick % 50 == 0) {
            publish(map->t_1hz, NULL, 0); // 20ms * 50 = 1000ms
            low_tick = 0;
        }
    }
}

void scheduler_init(void) {
    ESP_LOGI(TAG, "Initializing Priority-Based Dual-Core Scheduler");

    // Create Low Priority Tasks First (Prio 10)
    xTaskCreatePinnedToCore(scheduler_runner_low, "sched_c0_l", 4096, (void*)&MAP_C0, 10, &g_task_c0_low, 0);
    xTaskCreatePinnedToCore(scheduler_runner_low, "sched_c1_l", 4096, (void*)&MAP_C1, 10, &g_task_c1_low, 1);

    // Create High Priority Tasks (Prio 22 - nearly max)
    // Detailed configMAX_PRIORITIES is usually 25 in ESP-IDF
    xTaskCreatePinnedToCore(scheduler_runner_high, "sched_c0_h", 4096, (void*)&MAP_C0, 22, &g_task_c0_high, 0);
    xTaskCreatePinnedToCore(scheduler_runner_high, "sched_c1_h", 4096, (void*)&MAP_C1, 22, &g_task_c1_high, 1);


    // Create Timer
    gptimer_config_t timer_config = {
        .clk_src = GPTIMER_CLK_SRC_DEFAULT,
        .direction = GPTIMER_COUNT_UP,
        .resolution_hz = 1000000, // 1MHz, 1us per tick
    };
    ESP_ERROR_CHECK(gptimer_new_timer(&timer_config, &g_gptimer));

    gptimer_event_callbacks_t cbs = {
        .on_alarm = on_timer_alarm,
    };
    ESP_ERROR_CHECK(gptimer_register_event_callbacks(g_gptimer, &cbs, NULL));

    gptimer_alarm_config_t alarm_config = {
        .alarm_count = 1000, // 1000us = 1ms = 1000Hz
        .reload_count = 0,
        .flags.auto_reload_on_alarm = true,
    };
    ESP_ERROR_CHECK(gptimer_set_alarm_action(g_gptimer, &alarm_config));

    ESP_ERROR_CHECK(gptimer_enable(g_gptimer));
    ESP_ERROR_CHECK(gptimer_start(g_gptimer));
}

