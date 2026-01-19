#include <stdio.h>
#include <string.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_camera.h>
#include <driver/uart.h>
#include <driver/i2c.h>
#include <esp_timer.h>
#include <esp_mac.h>
#include <esp_log.h>
#include <image_util.h>
#include <optflow.h>
#include <math.h>
#include "platform.h"

#define ALT_ENABLED 1
#define OUTPUT_UART 1
#define OUTPUT_DEBUG 0

#define TAG "main.c"

#if ALT_ENABLED == 1
#include <vl53l1_api.h>
#endif

#define delay(ms) (vTaskDelay(pdMS_TO_TICKS(ms)))
#define LIMIT(number, min, max) (number < min ? min : (number > max ? max : number))

#define VL53L1X_ADDRESS 0x29

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
#define VSYNC_GPIO_NUM    38 // 38 or 2
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

#define WIDTH 64
#define HEIGHT 64

#define FRAME_FREQ 25

typedef struct {
  uint8_t byte;
  uint8_t buffer[128];
  uint8_t header[2];
  char stage;
  uint16_t payload_size;
  int buffer_idx;
} uart_rx_t;

static TaskHandle_t task_handle_1 = NULL;
static TaskHandle_t task_handle_2 = NULL;

static volatile char g_frame_captured = 0;

static volatile double g_z_alt = 0;

static uint8_t g_frame[WIDTH*HEIGHT] = {0,};

static void init_cam(void) {
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
    .fb_count = 2,      
    .fb_location = CAMERA_FB_IN_PSRAM, 
    .grab_mode = CAMERA_GRAB_WHEN_EMPTY,
  };

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    ESP_LOGI(TAG, "Camera init failed with error 0x%x\n", err);
    return;
  }
}

static void frame_timer(void *param) {
  // Capture frame
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    ESP_LOGI(TAG, "Capture failed\n");
    return;
  }

  // ESP_LOGI(TAG, "%dx%d, %d, %d\n", fb->height, fb->width, fb->format, fb->len);
  esp_camera_fb_return(fb);

  fast_crop_and_resize_bilinear(
    fb->buf, fb->width, fb->height,
    g_frame, WIDTH, HEIGHT,
    (int)((fb->width - fb->height) * 0.5), 0, fb->height, fb->height);

  g_frame_captured = 1;
}

#if OUTPUT_UART > 0
static void setup_uart(void) {
  #define BAUD_RATE 19200
  const uart_config_t uart_config = {
    .baud_rate = BAUD_RATE,
    .data_bits = UART_DATA_8_BITS,
    .parity = UART_PARITY_DISABLE,
    .stop_bits = UART_STOP_BITS_1,
    .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
    .source_clk = UART_SCLK_APB,
  };
  ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &uart_config));
  ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, 1024, 0, 0, NULL, 0));
  ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &uart_config));
  ESP_ERROR_CHECK(uart_set_pin(UART_NUM_1, 43, 44, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
}
#endif

static void calc_optflow(void) {
  g_frame_captured = 0;

  float clearity = 0;
  float dx_mm = 0;
  float dy_mm = 0;
  float rotation = 0;
  int mode = 0;
  
  optflow_calc(g_frame, &dy_mm, &dx_mm, &rotation, &clearity, &mode);

  // Scale up to preserve precision when casting to int
  int dx_int = (int)(-dx_mm * 1000);
  int dy_int = (int)(dy_mm * 1000);
  int z_raw_int = g_z_alt;

#if OUTPUT_DEBUG == 1
  static int64_t t_prev = 0;
  int64_t t1 = esp_timer_get_time();
  int dt_actual = t1 - t_prev;
  t_prev = t1;
  int f_actual = 1000000/dt_actual;

  ESP_LOGI(TAG, "$%f\t%f\t%d\t%f\t%f\t%d\t%d", 
    -dx_mm, dy_mm, z_raw_int, 
    clearity, rotation, f_actual, mode);
#endif

  // Output data
#if OUTPUT_UART > 0
  static uint8_t g_db_msg[256] = {'d', 'b', 0x01};
  int buf_idx = 6;
#endif

#define OPTFLOW_DIRECTION_DOWNWARD 0x00
#define OPTFLOW_DIRECTION_UPWARD 0x01

#if OUTPUT_UART == 1
  g_db_msg[3] = OPTFLOW_DIRECTION_DOWNWARD; // Downward
#elif OUTPUT_UART == 2
  g_db_msg[3] = OPTFLOW_DIRECTION_UPWARD; // Upward
#endif

#if OUTPUT_UART > 0
  int clearity_int = (int)(clearity * 10);
  memcpy(&g_db_msg[buf_idx], (void*)&dx_int, 4); buf_idx += 4;
  memcpy(&g_db_msg[buf_idx], (void*)&dy_int, 4); buf_idx += 4;
  memcpy(&g_db_msg[buf_idx], (void*)&z_raw_int, 4); buf_idx += 4;
  memcpy(&g_db_msg[buf_idx], (void*)&clearity_int, 4); buf_idx += 4;

  uint16_t payload_size = buf_idx - 6;
  memcpy(&g_db_msg[4], (void*)&payload_size, 2); // 2-byte checksum
  memset(&g_db_msg[buf_idx], 0, 2); // 2-byte checksum, no use

  uart_write_bytes(UART_NUM_1, g_db_msg, buf_idx + 2);
#endif
}

#if ALT_ENABLED == 1
static void alt_loop(void) {
  // I2C init
  int i2c_master_port = I2C_NUM_0;
  i2c_config_t conf = {
    .mode = I2C_MODE_MASTER,
    .sda_io_num = 5,
    .sda_pullup_en = GPIO_PULLUP_ENABLE,
    .scl_io_num = 6,
    .scl_pullup_en = GPIO_PULLUP_ENABLE,
    .master.clk_speed = 400000,
  };
  i2c_param_config(i2c_master_port, &conf);
  i2c_driver_install(i2c_master_port, conf.mode, 0, 0, 0);

  // VL53L1 check
  VL53L1_Dev_t dev;
  dev.I2cHandle = &i2c_master_port;
  dev.I2cDevAddr = 0x52;
  uint8_t byteData;
  uint16_t wordData;
  VL53L1_RdByte(&dev, 0x010F, &byteData);
  ESP_LOGI(TAG, "VL53L1X Model_ID: %02X", byteData);
  VL53L1_RdByte(&dev, 0x0110, &byteData);
  ESP_LOGI(TAG, "VL53L1X Module_Type: %02X", byteData);
  VL53L1_RdWord(&dev, 0x010F, &wordData);
  ESP_LOGI(TAG, "VL53L1X: %02X", wordData);

  // VL53L1 init
  VL53L1_UserRoi_t roi0;
  roi0.TopLeftX = 0;
  roi0.BotRightX = 15;
  roi0.BotRightY = 0;
  roi0.TopLeftY = 15;
  int status = 0;
  status = VL53L1_WaitDeviceBooted(&dev);
  ESP_LOGI(TAG, "VL53L1_WaitDeviceBooted %d", status);
  status = VL53L1_DataInit(&dev);                                       // performs the device initialization
  ESP_LOGI(TAG, "VL53L1_DataInit %d", status);
  status = VL53L1_StaticInit(&dev);                                     // load device settings specific for a given use case.
  ESP_LOGI(TAG, "VL53L1_StaticInit %d", status);
  status = VL53L1_SetDistanceMode(&dev, VL53L1_DISTANCEMODE_LONG);      // Max distance in dark:Short:136cm Medium:290cm long:360cm
  ESP_LOGI(TAG, "VL53L1_SetDistanceMode %d", status);
  status = VL53L1_SetMeasurementTimingBudgetMicroSeconds(&dev, 20000);  // 20 ms is the timing budget which allows the maximum distance of 4 m (in the dark on a white chart)
  ESP_LOGI(TAG, "VL53L1_SetMeasurementTimingBudgetMicroSeconds %d", status);
  status = VL53L1_SetInterMeasurementPeriodMilliSeconds(&dev, 25);      // period of time between two consecutive measurements 100ms
  ESP_LOGI(TAG, "VL53L1_SetInterMeasurementPeriodMilliSeconds %d", status);
  status = VL53L1_SetUserROI(&dev, &roi0);                              // SET region of interest
  ESP_LOGI(TAG, "VL53L1_SetUserROI %d", status);
  status = VL53L1_StartMeasurement(&dev);
  ESP_LOGI(TAG, "VL53L1_StartMeasurement %d", status);

  // VL53L1 measure
  VL53L1_RangingMeasurementData_t ranging_data;
  while (1) {
    int status = VL53L1_WaitMeasurementDataReady(&dev);
    if (!status) {
      status = VL53L1_GetRangingMeasurementData(&dev, &ranging_data);
      // ESP_LOGI(TAG, "%d\n%d\n%.2f\n%.2f\n%d\n%d", 
      //   ranging_data.RangeStatus,
      //   ranging_data.RangeMilliMeter,
      //   ranging_data.SignalRateRtnMegaCps / 65536.0,
      //   ranging_data.AmbientRateRtnMegaCps / 65336.0,
      //   ranging_data.RangeQualityLevel,
      //   ranging_data.EffectiveSpadRtnCount);
      // for (int i = 0; i < ranging_data.RangeMilliMeter/10; i++) printf("-");
      // printf("\n");

      if (status != VL53L1_RANGESTATUS_SIGNAL_FAIL) g_z_alt = 1 + ranging_data.RangeMilliMeter;
      else g_z_alt = 0;
      status = VL53L1_ClearInterruptAndStartMeasurement(&dev); // clear Interrupt start next measurement
    }

    delay(30);
  }
}
#endif

static void core0() {  
  // Init camera
  init_cam();

  // Frame capture timer
  const esp_timer_create_args_t timer_args1 = {
    .callback = &frame_timer,
    .name = "Frame capturing timer"
  };
  esp_timer_handle_t timer_handler1;
  ESP_ERROR_CHECK(esp_timer_create(&timer_args1, &timer_handler1));
  ESP_ERROR_CHECK(esp_timer_start_periodic(timer_handler1, 1000000/FRAME_FREQ));

#if ALT_ENABLED > 0
  alt_loop();
#else
  while (1) {delay(1000);}
#endif
}

static void core1() {
#if OUTPUT_UART > 0
  setup_uart();
#endif

  // Init optical flow
  optflow_init(WIDTH, HEIGHT, 0);  // 1=hybrid mode, 0=dense only

  while (1) {
    if (g_frame_captured > 0) {
      calc_optflow();
    } else {
      delay(1);
    }
  }
}

void app_main(void) {
  ESP_LOGI(TAG, "Start program\n");

  xTaskCreatePinnedToCore(core0, "Core 0 loop", 4096, NULL, 10, &task_handle_1, 0);
  xTaskCreatePinnedToCore(core1, "Core 1 loop", 4096, NULL, 10, &task_handle_2, 1);
  
  while (1) {delay(1000);}
}
