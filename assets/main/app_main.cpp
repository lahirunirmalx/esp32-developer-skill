// Entry point for a production ESP-IDF + PlatformIO app.
//
// Responsibilities:
//   1. Bootstrap NVS (encrypted), event loop, network stack.
//   2. Spawn one supervisor per "core role":
//        - net_task on PRO_CPU (core 0) for WiFi/MQTT/OTA
//        - rt_task  on APP_CPU (core 1) for real-time control
//      On single-core variants both pin to core 0 — this is automatic via
//      the SOC_CPU_CORES_NUM compile-time check below.
//
// Application logic (sensors, actuators, business rules) lives in
// components/app_core_*. This file should not grow beyond the supervisor
// wiring shown here.

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "soc/soc_caps.h"

namespace {
constexpr char TAG[] = "app";

#if SOC_CPU_CORES_NUM >= 2
constexpr BaseType_t kCoreNet = 0;   // PRO_CPU
constexpr BaseType_t kCoreRt  = 1;   // APP_CPU
#else
constexpr BaseType_t kCoreNet = 0;
constexpr BaseType_t kCoreRt  = 0;   // single-core variant: pin to core 0
#endif

constexpr UBaseType_t kPrioNet = tskIDLE_PRIORITY + 3;
constexpr UBaseType_t kPrioRt  = tskIDLE_PRIORITY + 5;

constexpr uint32_t kStackNet = 8192;
constexpr uint32_t kStackRt  = 4096;
}  // namespace

extern "C" void net_task(void *arg);
extern "C" void rt_task(void *arg);

static void init_nvs_secure(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

extern "C" void app_main(void) {
    ESP_LOGI(TAG, "boot: chip cores=%d, idf=%s",
             SOC_CPU_CORES_NUM, esp_get_idf_version());

    init_nvs_secure();
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_netif_init());

    // Network / housekeeping pinned to PRO_CPU.
    BaseType_t r = xTaskCreatePinnedToCore(
        net_task, "net", kStackNet, nullptr, kPrioNet, nullptr, kCoreNet);
    ESP_ERROR_CHECK(r == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);

    // Real-time / latency-critical pinned to APP_CPU when available.
    r = xTaskCreatePinnedToCore(
        rt_task, "rt", kStackRt, nullptr, kPrioRt, nullptr, kCoreRt);
    ESP_ERROR_CHECK(r == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);

    ESP_LOGI(TAG, "supervisor up: net@core%d rt@core%d", kCoreNet, kCoreRt);
}
